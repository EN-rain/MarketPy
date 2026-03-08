"""Security monitoring: auth attempts, anomaly detection, and IP blocking."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class SecurityEvent:
    timestamp: datetime
    event_type: str
    ip: str
    user_id: str
    detail: str


class SecurityMonitor:
    def __init__(self, *, failed_auth_threshold: int, block_duration_seconds: int) -> None:
        self.failed_auth_threshold = failed_auth_threshold
        self.block_duration = timedelta(seconds=block_duration_seconds)
        self.events: deque[SecurityEvent] = deque(maxlen=2_000)
        self.failed_attempts_by_ip: dict[str, int] = defaultdict(int)
        self.blocked_ips: dict[str, datetime] = {}
        self.request_count_by_ip: dict[str, int] = defaultdict(int)

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def _cleanup_blocks(self) -> None:
        now = self._now()
        for ip, expires_at in list(self.blocked_ips.items()):
            if expires_at <= now:
                self.blocked_ips.pop(ip, None)
                self.failed_attempts_by_ip.pop(ip, None)

    def is_blocked(self, ip: str) -> bool:
        self._cleanup_blocks()
        expires_at = self.blocked_ips.get(ip)
        return bool(expires_at and expires_at > self._now())

    def record_auth_attempt(self, *, ip: str, user_id: str, success: bool) -> None:
        now = self._now()
        if success:
            self.failed_attempts_by_ip[ip] = 0
            self.events.append(SecurityEvent(now, "auth_success", ip, user_id, "Authentication successful"))
            return
        self.failed_attempts_by_ip[ip] += 1
        self.events.append(SecurityEvent(now, "auth_failure", ip, user_id, "Authentication failed"))
        if self.failed_attempts_by_ip[ip] >= self.failed_auth_threshold:
            self.blocked_ips[ip] = now + self.block_duration
            self.events.append(SecurityEvent(now, "ip_blocked", ip, user_id, "Blocked after repeated auth failures"))

    def record_request(self, *, ip: str, endpoint: str, user_id: str = "anonymous") -> None:
        self.request_count_by_ip[ip] += 1
        self.events.append(SecurityEvent(self._now(), "request", ip, user_id, endpoint))

    def suspicious_usage(self, ip: str, threshold_per_minute: int = 600) -> bool:
        return self.request_count_by_ip.get(ip, 0) > threshold_per_minute

    def summary(self) -> dict[str, object]:
        self._cleanup_blocks()
        return {
            "blocked_ips": sorted(self.blocked_ips.keys()),
            "failed_auth_ips": {ip: count for ip, count in self.failed_attempts_by_ip.items() if count > 0},
            "recent_events": [event.__dict__ for event in list(self.events)[-20:]],
        }
