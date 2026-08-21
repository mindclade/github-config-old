#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Reject expired access exceptions and optionally signal approaching expiry."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
import sys
from typing import Any
from zoneinfo import ZoneInfo

import yaml


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog/access-exceptions.yaml"
GOVERNANCE_TIMEZONE = ZoneInfo("America/Detroit")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate access exception expiry and warn before renewal is due."
    )
    parser.add_argument(
        "--warn-days",
        type=int,
        default=0,
        help="exit 2 when an active exception expires within this many days",
    )
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        default=datetime.now(GOVERNANCE_TIMEZONE).date(),
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def evaluate(
    items: list[dict[str, Any]], today: date, warn_days: int
) -> tuple[list[str], list[str]]:
    expired: list[str] = []
    upcoming: list[str] = []
    warning_limit = today + timedelta(days=warn_days)
    for item in items:
        expiry = date.fromisoformat(str(item["expires_at"]))
        summary = f"{item['id']} ({item['principal']} on {item['repository']})"
        if expiry < today:
            expired.append(f"{summary} expired {expiry.isoformat()}")
        elif warn_days > 0 and expiry <= warning_limit:
            remaining = (expiry - today).days
            upcoming.append(
                f"{summary} expires {expiry.isoformat()} ({remaining} day(s) remaining)"
            )
    return expired, upcoming


def main() -> int:
    args = parse_args()
    if args.warn_days < 0:
        print("--warn-days must be zero or greater", file=sys.stderr)
        return 1
    if not CATALOG.exists():
        print("access expiry validation passed: no exceptions")
        return 0

    items = yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or []
    expired, upcoming = evaluate(items, args.today, args.warn_days)
    if expired:
        for message in expired:
            print(f"::error::{message}", file=sys.stderr)
        return 1
    if upcoming:
        for message in upcoming:
            print(f"::warning::{message}")
        return 2

    print(f"access expiry validation passed: {len(items)} active exception(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
