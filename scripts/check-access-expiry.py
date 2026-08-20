#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Reject stale time-bounded access exceptions if catalog/access-exceptions.yaml exists."""

from datetime import date
from pathlib import Path
import sys

import yaml

p = Path(__file__).resolve().parents[1] / "catalog/access-exceptions.yaml"
if not p.exists():
    print("access expiry validation passed: no exceptions")
    raise SystemExit
items = yaml.safe_load(p.read_text()) or []
errors = []
for item in items:
    expiry = date.fromisoformat(str(item["expires_at"]))
    if expiry < date.today():
        errors.append(f"{item['id']} expired {expiry}")
if errors:
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)
print(f"access expiry validation passed: {len(items)} active exception(s)")
