#!/usr/bin/env python3
# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Safety tests for local GitHub configuration operators."""

from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CI = load("export_ci_variables", "scripts/export-ci-variables.py")
IDP = load("export_idp_groups", "scripts/export-idp-groups.py")


class ExportSafetyTest(unittest.TestCase):
    def test_ci_generation_failure_never_calls_gh(self) -> None:
        arguments = SimpleNamespace(
            bootstrap=ROOT, repo="mindclade/github-config", set=True, check=False
        )
        with (
            mock.patch.object(CI, "parse_args", return_value=arguments),
            mock.patch.object(
                CI, "compile_payload", side_effect=ValueError("invalid contract")
            ),
            mock.patch.object(CI.subprocess, "run") as run,
        ):
            self.assertEqual(CI.main(), 1)
        run.assert_not_called()

    def test_idp_api_failure_is_not_treated_as_an_unmapped_user(self) -> None:
        failure = subprocess.CalledProcessError(
            1, ["gcloud"], stderr="permission denied"
        )
        with mock.patch.object(IDP.subprocess, "run", side_effect=failure):
            with self.assertRaises(IDP.ExportError):
                IDP.github_login("person@example.com")

    def test_empty_team_regression_is_detected(self) -> None:
        current = {"team_members": {"security": [{"username": "alice"}]}}
        generated = {"team_members": {"security": []}}
        self.assertEqual(
            IDP.empty_team_regressions(current, generated), ["security (had 1)"]
        )

    def test_atomic_write_replaces_complete_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "team-members.json"
            target.write_text("old", encoding="utf-8")
            IDP.atomic_write(target, "new\n")
            self.assertEqual(target.read_text(encoding="utf-8"), "new\n")


if __name__ == "__main__":
    unittest.main()
