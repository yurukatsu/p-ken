"""Command-line helpers shared by scripts/: period options read from config/report.toml."""

import argparse
from pathlib import Path

from p_ken import config


def parser(description: str) -> argparse.ArgumentParser:
    """Parser with --ytd-start / --start / --end (defaults: config/report.toml) and --out-dir."""
    period = config.load_period()
    p = argparse.ArgumentParser(description=description)
    g = p.add_argument_group("period (defaults from config/report.toml)")
    g.add_argument("--ytd-start", default=period.ytd_start, help="YTD charts start (YYYY-MM-DD)")
    g.add_argument("--start", default=period.start, help="highlighted period start")
    g.add_argument("--end", default=period.end, help="highlighted period end (report date)")
    p.add_argument("--out-dir", type=Path, default=None, help="default: output/figures")
    return p


def period(args: argparse.Namespace) -> config.Period:
    return config.Period(ytd_start=args.ytd_start, start=args.start, end=args.end)


def size(values) -> tuple[float, float] | None:
    return tuple(values) if values else None


def report(paths: list[Path]) -> None:
    for p in paths:
        print(f"Saved: {p.relative_to(config.ROOT) if p.is_absolute() else p}")
