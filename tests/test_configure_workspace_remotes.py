# Copyright © 2026 Mindclade, LLC. All Rights Reserved.
# Mindclade Proprietary and Confidential.
# SPDX-License-Identifier: LicenseRef-Mindclade-Proprietary

"""Black-box tests for the local workspace remote helper."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/configure-workspace-remotes.py"


class WorkspaceRemoteTest(unittest.TestCase):
    """Exercise drift handling in isolated temporary Git repositories."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary_directory.name)
        self.catalog = self.workspace / "repositories.yaml"
        self.catalog.write_text(
            "bootstrap:\n  default_branch: main\ngitops:\n  default_branch: main\n",
            encoding="utf-8",
        )
        self.repository = self.workspace / "bootstrap"
        subprocess.run(
            ["git", "init", "-q", "-b", "main", str(self.repository)],
            check=True,
        )
        self.git(
            "remote",
            "add",
            "origin",
            "https://github.com/legacy/bootstrap.git",
        )
        self.git(
            "remote",
            "set-url",
            "--push",
            "origin",
            "git@github.com:legacy/bootstrap.git",
        )
        self.git(
            "remote",
            "add",
            "upstream",
            "https://example.invalid/mindclade/bootstrap.git",
        )
        self.git("config", "branch.main.remote", "legacy")
        self.git("config", "branch.main.merge", "refs/heads/legacy")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def git(self, *arguments: str) -> str:
        """Run Git against the temporary bootstrap clone."""
        return subprocess.run(
            ["git", "-C", str(self.repository), *arguments],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def helper(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        """Run the helper against the temporary catalog and workspace."""
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--catalog",
                str(self.catalog),
                "--workspace",
                str(self.workspace),
                *arguments,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_detects_repairs_and_stably_rechecks_remote_drift(self) -> None:
        """The helper is read-only by default, convergent, and idempotent."""
        config_path = self.repository / ".git/config"
        original_configuration = config_path.read_bytes()

        check = self.helper()
        self.assertEqual(check.returncode, 1, check.stdout + check.stderr)
        self.assertIn("DRIFT bootstrap", check.stdout)
        self.assertIn("SKIP  gitops", check.stdout)
        self.assertEqual(config_path.read_bytes(), original_configuration)

        apply = self.helper("--apply")
        self.assertEqual(apply.returncode, 0, apply.stdout + apply.stderr)
        self.assertIn("FIXED bootstrap", apply.stdout)
        self.assertEqual(
            self.git("remote", "get-url", "origin"),
            "https://github.com/mindclade/bootstrap.git",
        )
        self.assertEqual(
            self.git("remote", "get-url", "--push", "origin"),
            "https://github.com/mindclade/bootstrap.git",
        )
        self.assertEqual(self.git("config", "branch.main.remote"), "origin")
        self.assertEqual(self.git("config", "branch.main.merge"), "refs/heads/main")
        self.assertEqual(
            self.git("remote", "get-url", "upstream"),
            "https://example.invalid/mindclade/bootstrap.git",
        )

        converged_configuration = config_path.read_bytes()
        second_apply = self.helper("--apply")
        self.assertEqual(
            second_apply.returncode, 0, second_apply.stdout + second_apply.stderr
        )
        self.assertIn("OK    bootstrap", second_apply.stdout)
        self.assertEqual(config_path.read_bytes(), converged_configuration)


if __name__ == "__main__":
    unittest.main()
