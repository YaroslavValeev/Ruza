from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "server" / "restore-proof.sh"
pytestmark = pytest.mark.skipif(os.name == "nt", reason="Bash entrypoint tested on Linux; Git Bash syntax checked separately")


@pytest.mark.parametrize("args,expected", [(["--help"], 0), ([], 2), (["--unknown"], 2)])
def test_restore_proof_arguments_do_not_touch_runtime(tmp_path, args, expected):
    evidence = tmp_path / "must-not-be-created"
    env = dict(os.environ, RUZA_PROJECT_DIR=str(evidence), RUZA_EVIDENCE_ROOT=str(evidence))
    result = subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=10)
    assert result.returncode == expected
    assert "Usage:" in result.stdout + result.stderr
    assert not evidence.exists()


def test_unpinned_restore_proof_is_refused_before_runtime(tmp_path):
    evidence = tmp_path / "must-not-be-created"
    env = dict(os.environ, RUZA_PROJECT_DIR=str(evidence), RUZA_EVIDENCE_ROOT=str(evidence))
    result = subprocess.run([
        "bash", str(SCRIPT), "--source-backup-dir", str(tmp_path),
        "--target-spreadsheet-id", "synthetic-test-target", "--expected-target-title", "synthetic test",
        "--tools-sha", "main", "--restore-sha256", "not-a-hash", "--driver-sha256", "not-a-hash",
    ], capture_output=True, text=True, env=env, timeout=10)
    assert result.returncode == 2
    assert "Usage:" in result.stdout + result.stderr
    assert not evidence.exists()
