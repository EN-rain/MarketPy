"""Staging smoke checks for core backend endpoints."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx


@dataclass(frozen=True)
class SmokeCheck:
    method: str
    path: str
    expected_status: int
    requires_auth: bool = False


@dataclass(frozen=True)
class SmokeResult:
    check: SmokeCheck
    status_code: int
    ok: bool
    duration_ms: float
    detail: str


DEFAULT_CHECKS = [
    SmokeCheck("GET", "/api/status", 200),
    SmokeCheck("GET", "/api/portfolio", 200),
    SmokeCheck("GET", "/api/health/connections", 200),
    SmokeCheck("GET", "/api/health/processing", 200),
    SmokeCheck("GET", "/api/health/memory", 200),
    SmokeCheck("GET", "/api/health/rate-limits", 200),
    SmokeCheck("GET", "/api/health/config", 200),
    SmokeCheck("GET", "/api/metrics/tasks", 200),
]


def _is_local_url(url: str) -> bool:
    lowered = url.lower()
    return (
        "localhost" in lowered
        or "127.0.0.1" in lowered
        or "0.0.0.0" in lowered
        or lowered.startswith("http://backend:")
    )


def _render_report(
    *,
    base_url: str,
    build_sha: str,
    env_name: str,
    started_at: datetime,
    results: list[SmokeResult],
) -> str:
    passed = sum(1 for result in results if result.ok)
    failed = len(results) - passed
    overall = "PASS" if failed == 0 else "FAIL"

    lines = [
        "# Staging Smoke Report",
        "",
        f"- environment: {env_name}",
        f"- base_url: {base_url}",
        f"- build_sha: {build_sha}",
        f"- started_at_utc: {started_at.isoformat()}",
        f"- total_checks: {len(results)}",
        f"- passed: {passed}",
        f"- failed: {failed}",
        f"- overall: {overall}",
        "",
        "## Endpoint Matrix",
        "",
        "| Method | Endpoint | Expected | Actual | Duration(ms) | Result | Detail |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.check.method} | {result.check.path} | {result.check.expected_status} | "
            f"{result.status_code} | {result.duration_ms:.2f} | "
            f"{'OK' if result.ok else 'FAIL'} | {result.detail} |"
        )
    lines.append("")
    return "\n".join(lines)


async def main() -> int:
    base_url = os.getenv("STAGING_API_URL", "http://localhost:8000")
    require_remote = os.getenv("SMOKE_REQUIRE_REMOTE", "false").lower() in {"1", "true", "yes"}
    env_name = os.getenv("APP_ENV", "staging")
    build_sha = os.getenv("GITHUB_SHA") or os.getenv("BUILD_SHA") or "unknown"
    report_path = os.getenv(
        "SMOKE_REPORT_PATH", str(Path("deploy") / "staging-smoke-report.md")
    )
    started_at = datetime.now(UTC)

    checks = list(DEFAULT_CHECKS)
    auth_endpoint = os.getenv("SMOKE_AUTH_ENDPOINT", "").strip()
    auth_expected = int(os.getenv("SMOKE_AUTH_EXPECTED_STATUS", "200"))
    if auth_endpoint:
        checks.append(
            SmokeCheck(
                method="GET",
                path=auth_endpoint,
                expected_status=auth_expected,
                requires_auth=True,
            )
        )

    if require_remote and _is_local_url(base_url):
        print("FAIL staging smoke requires non-local STAGING_API_URL")
        return 1

    auth_token = os.getenv("AUTH_BEARER_TOKEN", "").strip()
    results: list[SmokeResult] = []
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        for check in checks:
            headers: dict[str, str] = {}
            if check.requires_auth:
                if not auth_token:
                    results.append(
                        SmokeResult(
                            check=check,
                            status_code=0,
                            ok=False,
                            duration_ms=0.0,
                            detail="missing AUTH_BEARER_TOKEN",
                        )
                    )
                    continue
                headers["Authorization"] = f"Bearer {auth_token}"

            start = time.perf_counter()
            response = await client.request(check.method, check.path, headers=headers)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            ok = response.status_code == check.expected_status
            detail = "status_match" if ok else f"unexpected_status:{response.status_code}"
            results.append(
                SmokeResult(
                    check=check,
                    status_code=response.status_code,
                    ok=ok,
                    duration_ms=elapsed_ms,
                    detail=detail,
                )
            )
            prefix = "OK" if ok else "FAIL"
            print(
                f"{prefix} {check.method} {check.path}: "
                f"expected={check.expected_status} actual={response.status_code}"
            )

    report = _render_report(
        base_url=base_url,
        build_sha=build_sha,
        env_name=env_name,
        started_at=started_at,
        results=results,
    )
    report_file = Path(report_path)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(report + "\n", encoding="utf-8")
    print(f"Smoke report written to {report_file}")

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
