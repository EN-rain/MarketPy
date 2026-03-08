"""Dataset builder — converts raw JSONL events into canonical Parquet bars.

Resamples to configurable bar size (1m/5m), computes OHLC + bid/ask/mid/spread,
and stores as partitioned Parquet files.

Usage:
    python -m backend.dataset.builder
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from backend.app.models.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path(settings.data_dir) / "raw"
PARQUET_DIR = Path(settings.data_dir) / "parquet"

MIN_PRICE = 0.0


def parse_jsonl_file(filepath: Path) -> list[dict]:
    """Parse a JSONL file into a list of event dicts."""
    events = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return events


def events_to_dataframe(events: list[dict]) -> pl.DataFrame:
    """Convert raw WebSocket events into a flat DataFrame.

    Extracts price_change, last_trade_price, and best_bid_ask events
    into rows with: timestamp, token_id, event_type, price, size, side,
    best_bid, best_ask.
    """
    rows = []
    invalid_rows = 0
    missing_timestamp = 0
    for evt in events:
        event_type = evt.get("event_type", "")
        token_id = evt.get("asset_id", "")
        event_ts = _extract_event_timestamp(evt)
        if not event_ts:
            missing_timestamp += 1
            continue

        if event_type == "price_change":
            for change in evt.get("price_changes", []):
                price = float(change.get("price", 0))
                size = float(change.get("size", 0))
                row = {
                    "timestamp": event_ts,
                    "token_id": token_id,
                    "event_type": event_type,
                    "price": price,
                    "size": size,
                    "side": change.get("side", ""),
                    "best_bid": None,
                    "best_ask": None,
                }
                if _is_valid_row(row):
                    rows.append(row)
                else:
                    invalid_rows += 1

        elif event_type == "last_trade_price":
            row = {
                "timestamp": event_ts,
                "token_id": token_id,
                "event_type": event_type,
                "price": float(evt.get("price", 0)),
                "size": float(evt.get("size", 0)),
                "side": evt.get("side", ""),
                "best_bid": None,
                "best_ask": None,
            }
            if _is_valid_row(row):
                rows.append(row)
            else:
                invalid_rows += 1

        elif event_type == "best_bid_ask":
            row = {
                "timestamp": event_ts,
                "token_id": token_id,
                "event_type": event_type,
                "price": None,
                "size": None,
                "side": None,
                "best_bid": float(evt.get("best_bid", 0)) if evt.get("best_bid") else None,
                "best_ask": float(evt.get("best_ask", 0)) if evt.get("best_ask") else None,
            }
            if _is_valid_row(row):
                rows.append(row)
            else:
                invalid_rows += 1

    if not rows:
        if missing_timestamp > 0 or invalid_rows > 0:
            logger.warning(
                "Dropped events before dataframe creation: missing_timestamp=%s invalid_rows=%s",
                missing_timestamp,
                invalid_rows,
            )
        return pl.DataFrame()

    if missing_timestamp > 0 or invalid_rows > 0:
        logger.warning(
            "Dropped events before dataframe creation: missing_timestamp=%s invalid_rows=%s",
            missing_timestamp,
            invalid_rows,
        )

    return pl.DataFrame(rows).with_columns(
        pl.col("timestamp").str.to_datetime(time_zone="UTC").alias("timestamp")
    )


def _extract_event_timestamp(evt: dict) -> str:
    """Prefer exchange timestamp and fallback to recorder timestamp."""
    # Common exchange timestamp fields (ms epoch)
    for key in ("timestamp_ms", "ts", "event_ts", "E"):
        value = evt.get(key)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000, UTC).isoformat()
    # Common ISO fields
    for key in ("timestamp", "event_timestamp", "time"):
        value = evt.get(key)
        if isinstance(value, str) and value:
            return value
    return evt.get("_recorded_at", "")


def _is_valid_row(row: dict) -> bool:
    """Validate event row for crypto market assumptions."""
    price = row.get("price")
    size = row.get("size")
    best_bid = row.get("best_bid")
    best_ask = row.get("best_ask")

    if price is not None and price <= MIN_PRICE:
        return False
    if size is not None and size < 0:
        return False
    if best_bid is not None and best_bid <= MIN_PRICE:
        return False
    if best_ask is not None and best_ask <= MIN_PRICE:
        return False
    if best_bid is not None and best_ask is not None and best_bid > best_ask:
        return False
    return True


def resample_to_bars(df: pl.DataFrame, bar_size: str = "5m") -> pl.DataFrame:
    """Resample event data into OHLC bars with bid/ask/mid/spread.

    Args:
        df: DataFrame with columns: timestamp, token_id, price, best_bid, best_ask
        bar_size: Polars duration string (1m, 5m, etc.)

    Returns:
        DataFrame with bar columns.
    """
    if df.is_empty():
        return pl.DataFrame()

    # Filter to rows with price data for OHLC
    price_df = df.filter(pl.col("price").is_not_null())
    bba_df = df.filter(pl.col("best_bid").is_not_null())

    if price_df.is_empty():
        return pl.DataFrame()

    # OHLC bars from trade/price events
    bars = price_df.group_by_dynamic(
        "timestamp",
        every=bar_size,
        group_by="token_id",
    ).agg(
        [
            pl.col("price").first().alias("open"),
            pl.col("price").max().alias("high"),
            pl.col("price").min().alias("low"),
            pl.col("price").last().alias("close"),
            pl.col("size").sum().alias("volume"),
            pl.col("size").count().alias("trade_count"),
        ]
    )

    # Bid/ask from best_bid_ask events
    if not bba_df.is_empty():
        bba_bars = bba_df.group_by_dynamic(
            "timestamp",
            every=bar_size,
            group_by="token_id",
        ).agg(
            [
                pl.col("best_bid").last().alias("bid"),
                pl.col("best_ask").last().alias("ask"),
            ]
        )

        bars = bars.join(bba_bars, on=["timestamp", "token_id"], how="left")
    else:
        bars = bars.with_columns(
            [
                pl.lit(None).alias("bid"),
                pl.lit(None).alias("ask"),
            ]
        )

    # Compute mid and spread
    bars = bars.with_columns(
        [
            ((pl.col("bid") + pl.col("ask")) / 2).alias("mid"),
            (pl.col("ask") - pl.col("bid")).alias("spread"),
        ]
    ).sort("timestamp")

    return bars


def build_dataset(
    raw_dir: Path | None = None,
    output_dir: Path | None = None,
    bar_size: str | None = None,
) -> None:
    """Build the canonical Parquet dataset from raw JSONL files.

    Args:
        raw_dir: Directory containing JSONL files.
        output_dir: Directory for Parquet output.
        bar_size: Bar size string (e.g., "5m").
    """
    raw_dir = raw_dir or RAW_DIR
    output_dir = output_dir or PARQUET_DIR
    bar_size = bar_size or settings.bar_size

    if not raw_dir.exists():
        logger.warning(f"Raw data directory {raw_dir} does not exist")
        return

    jsonl_files = sorted(raw_dir.glob("*.jsonl"))
    if not jsonl_files:
        logger.warning(f"No JSONL files found in {raw_dir}")
        return

    logger.info(f"Processing {len(jsonl_files)} JSONL files → {bar_size} bars")

    all_events = []
    for filepath in jsonl_files:
        events = parse_jsonl_file(filepath)
        all_events.extend(events)
        logger.info(f"  {filepath.name}: {len(events)} events")

    df = events_to_dataframe(all_events)
    if df.is_empty():
        logger.warning("No usable events found")
        return

    # Integrity checks
    before = len(df)
    deduped = df.unique(subset=["timestamp", "token_id", "event_type"], keep="first")
    dropped_duplicates = before - len(deduped)
    if dropped_duplicates > 0:
        logger.warning("Dropped %s duplicate rows", dropped_duplicates)
    df = deduped.sort(["token_id", "timestamp"])
    _log_timestamp_monotonicity_violations(df)

    bars = resample_to_bars(df, bar_size=bar_size)
    if bars.is_empty():
        logger.warning("No bars generated")
        return

    # Write partitioned Parquet
    output_dir.mkdir(parents=True, exist_ok=True)

    for token_id in bars["token_id"].unique().to_list():
        token_bars = bars.filter(pl.col("token_id") == token_id)
        token_dir = output_dir / f"market_id={token_id}"
        token_dir.mkdir(parents=True, exist_ok=True)

        output_path = token_dir / "bars.parquet"
        token_bars.write_parquet(output_path)
        logger.info(f"  Wrote {len(token_bars)} bars for {token_id[:12]}... → {output_path}")

    logger.info(f"Dataset build complete: {len(bars)} total bars")


def _log_timestamp_monotonicity_violations(df: pl.DataFrame) -> None:
    """Log non-monotonic timestamp rows per token."""
    if df.is_empty():
        return
    token_ids = df["token_id"].drop_nulls().unique().to_list()
    total_violations = 0
    for token_id in token_ids:
        token_df = df.filter(pl.col("token_id") == token_id).sort("timestamp")
        if len(token_df) < 2:
            continue
        diffs = token_df["timestamp"].diff().drop_nulls()
        # Diff values are durations; negative duration => out-of-order source events.
        violations = sum(1 for d in diffs if d.total_seconds() < 0)
        if violations > 0:
            total_violations += violations
            logger.warning(
                "Token %s has %s non-monotonic timestamp transitions",
                token_id,
                violations,
            )
    if total_violations == 0:
        logger.info("Timestamp monotonicity check passed for all tokens")


def main():
    parser = argparse.ArgumentParser(description="Build Parquet dataset from raw JSONL")
    parser.add_argument("--raw-dir", type=str, default=None, help="Raw JSONL directory")
    parser.add_argument("--output-dir", type=str, default=None, help="Parquet output directory")
    parser.add_argument("--bar-size", type=str, default=None, help="Bar size (e.g., 1m, 5m)")
    args = parser.parse_args()

    build_dataset(
        raw_dir=Path(args.raw_dir) if args.raw_dir else None,
        output_dir=Path(args.output_dir) if args.output_dir else None,
        bar_size=args.bar_size,
    )


if __name__ == "__main__":
    main()
