"""Validate coverage XML against roadmap thresholds."""

from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree


TARGETS = {
    "core": (("backend/app/", "backend/ml/", "backend/sim/"), 0.90),
    "risk_management": (("backend/risk/",), 0.95),
    "data_validation": (("backend/features/validator.py", "backend/app/security/input_validation.py"), 0.95),
    "exchange_adapters": (("backend/ingest/exchanges/",), 0.85),
}


def _load_classes(xml_path: Path) -> list[tuple[str, float]]:
    root = ElementTree.parse(xml_path).getroot()
    classes: list[tuple[str, float]] = []
    for class_node in root.findall(".//class"):
        filename = class_node.attrib.get("filename", "")
        line_rate = float(class_node.attrib.get("line-rate", "0"))
        classes.append((filename.replace("\\", "/"), line_rate))
    return classes


def _coverage_for_prefixes(classes: list[tuple[str, float]], prefixes: tuple[str, ...]) -> float:
    matched = [rate for filename, rate in classes if filename.startswith(prefixes)]
    if not matched:
        return 0.0
    return sum(matched) / len(matched)


def main() -> int:
    xml_path = Path("coverage.xml")
    if not xml_path.exists():
        print("coverage.xml not found. Run: pytest --cov=backend --cov-report=xml")
        return 2

    classes = _load_classes(xml_path)
    failures: list[str] = []
    for label, (prefixes, target) in TARGETS.items():
        actual = _coverage_for_prefixes(classes, prefixes)
        print(f"{label}: {actual:.2%} (target {target:.2%})")
        if actual < target:
            failures.append(f"{label} below target: {actual:.2%} < {target:.2%}")

    if failures:
        print("\nCoverage target failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
