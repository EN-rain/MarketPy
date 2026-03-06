"""Property tests for Strategy Lab composition backend."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.strategy_lab.composer import (
    BlockDefinition,
    ComposedStrategy,
    ConnectionDefinition,
)


def make_min_valid_strategy(strategy_id: str = "s1") -> ComposedStrategy:
    return ComposedStrategy(
        strategy_id=strategy_id,
        name="test",
        blocks=[
            BlockDefinition(id="price", type="signal.price", config={}),
            BlockDefinition(
                id="th",
                type="operator.threshold",
                config={"operator": ">", "value": 0.0},
            ),
            BlockDefinition(id="buy", type="action.buy", config={"size": 100}),
        ],
        connections=[
            ConnectionDefinition(
                from_block_id="price",
                from_port="out",
                to_block_id="th",
                to_port="in",
            ),
            ConnectionDefinition(
                from_block_id="th",
                from_port="out",
                to_block_id="buy",
                to_port="trigger",
            ),
        ],
    )


# Property 18: Strategy Validation Soundness
@given(
    duplicate_ids=st.booleans(),
    missing_action=st.booleans(),
    add_cycle=st.booleans(),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_strategy_validation_soundness(
    duplicate_ids: bool, missing_action: bool, add_cycle: bool
) -> None:
    strategy = make_min_valid_strategy("strategy")
    blocks = list(strategy.blocks)
    connections = list(strategy.connections)

    if duplicate_ids:
        blocks[1] = BlockDefinition(id=blocks[0].id, type=blocks[1].type, config=blocks[1].config)
    if missing_action:
        blocks = [block for block in blocks if not block.type.startswith("action.")]
        connections = [conn for conn in connections if conn.to_block_id != "buy"]
    if add_cycle:
        connections.append(
            ConnectionDefinition(
                from_block_id="buy" if not missing_action else "th",
                from_port="out",
                to_block_id="price",
                to_port="out",  # invalid on purpose, should fail validation
            )
        )

    mutated = ComposedStrategy(
        strategy_id="strategy",
        name="test",
        blocks=blocks,
        connections=connections,
    )
    result = mutated.validate()

    should_fail = duplicate_ids or missing_action or add_cycle
    assert result.ok is (not should_fail)


# Property 19: Strategy Serialization Round-Trip
@given(
    sid=st.text(min_size=1, max_size=20),
    threshold=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_strategy_serialization_round_trip(sid: str, threshold: float) -> None:
    strategy = ComposedStrategy(
        strategy_id=sid,
        name="roundtrip",
        blocks=[
            BlockDefinition(id="price", type="signal.price", config={}),
            BlockDefinition(
                id="th",
                type="operator.threshold",
                config={"operator": ">", "value": threshold},
            ),
            BlockDefinition(id="buy", type="action.buy", config={"size": 1}),
        ],
        connections=[
            ConnectionDefinition("price", "out", "th", "in"),
            ConnectionDefinition("th", "out", "buy", "trigger"),
        ],
    )
    payload = strategy.to_dict()
    reconstructed = ComposedStrategy.from_dict(payload)
    assert reconstructed.to_dict() == payload
    assert reconstructed.validate().ok is True
    executable = reconstructed.to_executable()
    assert executable["strategy_id"] == sid
