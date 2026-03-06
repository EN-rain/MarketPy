"""Strategy Lab composition, validation, and serialization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

BLOCK_PORTS: dict[str, dict[str, dict[str, str]]] = {
    "signal.price": {"inputs": {}, "outputs": {"out": "number"}},
    "signal.volume": {"inputs": {}, "outputs": {"out": "number"}},
    "indicator.momentum": {"inputs": {"in": "number"}, "outputs": {"out": "number"}},
    "indicator.custom": {"inputs": {"in": "number"}, "outputs": {"out": "number"}},
    "operator.and": {
        "inputs": {"left": "boolean", "right": "boolean"},
        "outputs": {"out": "boolean"},
    },
    "operator.or": {
        "inputs": {"left": "boolean", "right": "boolean"},
        "outputs": {"out": "boolean"},
    },
    "operator.not": {"inputs": {"in": "boolean"}, "outputs": {"out": "boolean"}},
    "operator.threshold": {"inputs": {"in": "number"}, "outputs": {"out": "boolean"}},
    "action.buy": {"inputs": {"trigger": "boolean"}, "outputs": {"out": "action"}},
    "action.sell": {"inputs": {"trigger": "boolean"}, "outputs": {"out": "action"}},
}


@dataclass(frozen=True)
class BlockDefinition:
    id: str
    type: str
    config: Mapping[str, Any]


@dataclass(frozen=True)
class ConnectionDefinition:
    from_block_id: str
    from_port: str
    to_block_id: str
    to_port: str


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str]


@dataclass
class ComposedStrategy:
    strategy_id: str
    name: str
    blocks: list[BlockDefinition]
    connections: list[ConnectionDefinition]

    def validate(self) -> ValidationResult:
        errors: list[str] = []
        if not self.blocks:
            errors.append("Strategy must contain at least one block")
            return ValidationResult(ok=False, errors=errors)

        ids = [block.id for block in self.blocks]
        if len(ids) != len(set(ids)):
            errors.append("Block IDs must be unique")

        by_id = {block.id: block for block in self.blocks}
        if not any(block.type.startswith("action.") for block in self.blocks):
            errors.append("Strategy must contain at least one action block")

        incoming: dict[str, int] = {block.id: 0 for block in self.blocks}
        graph: dict[str, set[str]] = {block.id: set() for block in self.blocks}
        for conn in self.connections:
            if conn.from_block_id not in by_id:
                errors.append(f"Unknown source block: {conn.from_block_id}")
                continue
            if conn.to_block_id not in by_id:
                errors.append(f"Unknown destination block: {conn.to_block_id}")
                continue

            from_type = by_id[conn.from_block_id].type
            to_type = by_id[conn.to_block_id].type
            from_ports = BLOCK_PORTS.get(from_type, {}).get("outputs", {})
            to_ports = BLOCK_PORTS.get(to_type, {}).get("inputs", {})

            if conn.from_port not in from_ports:
                errors.append(f"Invalid output port '{conn.from_port}' on {conn.from_block_id}")
                continue
            if conn.to_port not in to_ports:
                errors.append(f"Invalid input port '{conn.to_port}' on {conn.to_block_id}")
                continue

            if from_ports[conn.from_port] != to_ports[conn.to_port]:
                errors.append(
                    f"Type mismatch {conn.from_block_id}.{conn.from_port}"
                    f" -> {conn.to_block_id}.{conn.to_port}"
                )
                continue

            graph[conn.from_block_id].add(conn.to_block_id)
            incoming[conn.to_block_id] += 1

        for block in self.blocks:
            required_inputs = set(BLOCK_PORTS.get(block.type, {}).get("inputs", {}).keys())
            if required_inputs:
                connected_inputs = {
                    conn.to_port for conn in self.connections if conn.to_block_id == block.id
                }
                missing = required_inputs - connected_inputs
                if missing:
                    errors.append(f"Block {block.id} missing required inputs: {sorted(missing)}")

        if self._has_cycle(graph):
            errors.append("Circular dependency detected")

        return ValidationResult(ok=len(errors) == 0, errors=errors)

    @staticmethod
    def _has_cycle(graph: dict[str, set[str]]) -> bool:
        state: dict[str, int] = {node: 0 for node in graph}

        def visit(node: str) -> bool:
            if state[node] == 1:
                return True
            if state[node] == 2:
                return False
            state[node] = 1
            for nxt in graph[node]:
                if visit(nxt):
                    return True
            state[node] = 2
            return False

        return any(visit(node) for node in graph)

    def to_executable(self) -> dict[str, Any]:
        validation = self.validate()
        if not validation.ok:
            raise ValueError(f"Strategy validation failed: {validation.errors}")

        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "blocks": [asdict(block) for block in self.blocks],
            "connections": [asdict(conn) for conn in self.connections],
            "engine_plan": {
                "kind": "graph",
                "version": 1,
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "blocks": [asdict(block) for block in self.blocks],
            "connections": [asdict(conn) for conn in self.connections],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ComposedStrategy:
        return cls(
            strategy_id=str(payload["strategy_id"]),
            name=str(payload["name"]),
            blocks=[
                BlockDefinition(
                    id=str(item["id"]),
                    type=str(item["type"]),
                    config=item.get("config", {}),
                )
                for item in payload.get("blocks", [])
            ],
            connections=[
                ConnectionDefinition(
                    from_block_id=str(item["from_block_id"]),
                    from_port=str(item["from_port"]),
                    to_block_id=str(item["to_block_id"]),
                    to_port=str(item["to_port"]),
                )
                for item in payload.get("connections", [])
            ],
        )
