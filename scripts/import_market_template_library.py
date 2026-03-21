from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("psycopg is required to import market template data.") from exc

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sentinel_alpha.config import get_settings  # noqa: E402

SEGMENT_RANGES = [
    ("open_drive", 0, 15),
    ("morning_follow", 16, 31),
    ("midday_balance", 32, 47),
    ("pm_break", 48, 63),
    ("close_battle", 64, 77),
]


@dataclass(slots=True)
class OhlcvRow:
    ts: datetime
    symbol: str
    timeframe: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def load_csv(path: Path, timeframe: str) -> list[OhlcvRow]:
    rows: list[OhlcvRow] = []
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            rows.append(
                OhlcvRow(
                    ts=parse_timestamp(raw["timestamp"]),
                    symbol=raw["symbol"].upper(),
                    timeframe=timeframe,
                    open_price=float(raw["open"]),
                    high_price=float(raw["high"]),
                    low_price=float(raw["low"]),
                    close_price=float(raw["close"]),
                    volume=float(raw.get("volume") or 0),
                )
            )
    return rows


def group_intraday_by_day(rows: list[OhlcvRow]) -> dict[tuple[str, str], list[OhlcvRow]]:
    grouped: dict[tuple[str, str], list[OhlcvRow]] = defaultdict(list)
    for row in rows:
        grouped[(row.symbol, row.ts.date().isoformat())].append(row)
    for key in grouped:
        grouped[key].sort(key=lambda item: item.ts)
    return grouped


def import_symbol(connection: psycopg.Connection, symbol_dir: Path) -> None:
    daily_path = symbol_dir / "daily.csv"
    intraday_path = symbol_dir / "5m.csv"
    metadata_path = symbol_dir / "meta.json"
    if not daily_path.exists() or not intraday_path.exists():
        raise FileNotFoundError(f"Expected daily.csv and 5m.csv under {symbol_dir}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    daily_rows = load_csv(daily_path, "1d")
    intraday_rows = load_csv(intraday_path, "5m")
    intraday_by_day = group_intraday_by_day(intraday_rows)

    with connection.cursor() as cursor:
        for row in daily_rows:
            session_id = str(uuid4())
            cursor.execute(
                """
                insert into market_data_ts (
                    session_id, ts, symbol, timeframe, open_price, high_price, low_price,
                    close_price, volume, source, regime_tag
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session_id,
                    row.ts,
                    row.symbol,
                    row.timeframe,
                    row.open_price,
                    row.high_price,
                    row.low_price,
                    row.close_price,
                    row.volume,
                    "template_library",
                    metadata.get("playbook"),
                ),
            )

            key = (row.symbol, row.ts.date().isoformat())
            bars = intraday_by_day.get(key, [])
            if len(bars) < 78:
                continue

            template_day_id = uuid4()
            cursor.execute(
                """
                    insert into market_template_days (
                    id, symbol, trading_day, source, playbook, market_regime, shape_family, pattern_label,
                    open_price, high_price, low_price, close_price, volume, metadata
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                on conflict (symbol, trading_day, source) do nothing
                """,
                (
                    template_day_id,
                    row.symbol,
                    row.ts.date(),
                    "csv_import",
                    metadata.get("playbook"),
                    metadata.get("market_regime"),
                    metadata.get("shape_family"),
                    metadata.get("pattern_label"),
                    row.open_price,
                    row.high_price,
                    row.low_price,
                    row.close_price,
                    row.volume,
                    json.dumps(metadata),
                ),
            )

            for bar in bars:
                cursor.execute(
                    """
                    insert into market_data_ts (
                        session_id, ts, symbol, timeframe, open_price, high_price, low_price,
                        close_price, volume, source, regime_tag
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        session_id,
                        bar.ts,
                        bar.symbol,
                        bar.timeframe,
                        bar.open_price,
                        bar.high_price,
                        bar.low_price,
                        bar.close_price,
                        bar.volume,
                        "template_library",
                        metadata.get("playbook"),
                    ),
                )

            for segment_index, (segment_label, start_idx, end_idx) in enumerate(SEGMENT_RANGES, start=1):
                start_ts = bars[start_idx].ts
                end_ts = bars[end_idx].ts
                cursor.execute(
                    """
                    insert into market_template_intraday_segments (
                        id, template_day_id, symbol, trading_day, segment_index,
                        start_ts, end_ts, shape_family, market_regime, pattern_label, metadata
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    on conflict (template_day_id, segment_index) do nothing
                    """,
                    (
                        uuid4(),
                        template_day_id,
                        row.symbol,
                        row.ts.date(),
                        segment_index,
                        start_ts,
                        end_ts,
                        metadata.get("shape_family"),
                        metadata.get("market_regime"),
                        segment_label,
                        json.dumps(metadata),
                    ),
                )


def main() -> int:
    settings = get_settings()
    base_dir = ROOT / "data" / "market_templates"
    if not base_dir.exists():
        print(f"Missing template directory: {base_dir}", file=sys.stderr)
        return 1

    with psycopg.connect(settings.timescale_dsn) as connection:
        for symbol_dir in sorted(path for path in base_dir.iterdir() if path.is_dir()):
            import_symbol(connection, symbol_dir)
        connection.commit()

    print(f"Imported market template library from {base_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
