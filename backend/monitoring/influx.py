"""InfluxDB-oriented metric batching primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol


class InfluxWriteClient(Protocol):
    def write(self, bucket: str, org: str, record: list[dict[str, Any]]) -> Any: ...


@dataclass(slots=True)
class InfluxConfig:
    url: str = "http://localhost:8086"
    token: str = ""
    org: str = "marketpy"
    bucket: str = "marketpy_metrics"
    batch_size: int = 100
    high_resolution_retention_days: int = 30
    downsampled_retention_days: int = 365
    measurements: tuple[str, ...] = (
        "model_performance",
        "execution_quality",
        "portfolio_risk",
        "data_quality",
    )


@dataclass(slots=True)
class InfluxMetricWriter:
    client: InfluxWriteClient
    config: InfluxConfig = field(default_factory=InfluxConfig)
    _buffer: list[dict[str, Any]] = field(default_factory=list)

    def retention_policies(self) -> dict[str, str]:
        return {
            "high_resolution": f"{self.config.high_resolution_retention_days}d",
            "downsampled": f"{self.config.downsampled_retention_days}d",
        }

    def append(
        self,
        measurement: str,
        *,
        fields: dict[str, float | int],
        tags: dict[str, str] | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        if measurement not in self.config.measurements:
            raise ValueError(f"Unsupported measurement: {measurement}")
        self._buffer.append(
            {
                "measurement": measurement,
                "tags": tags or {},
                "fields": fields,
                "time": (timestamp or datetime.now(UTC)).isoformat(),
            }
        )

    @property
    def buffered_points(self) -> int:
        return len(self._buffer)

    def flush(self) -> int:
        if not self._buffer:
            return 0
        payload = list(self._buffer)
        self.client.write(self.config.bucket, self.config.org, payload)
        self._buffer.clear()
        return len(payload)
