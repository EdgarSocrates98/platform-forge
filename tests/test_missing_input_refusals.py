"""Missing-input refusals — a file-reading verb called on a directory or a
missing path must return a named ``PF-*`` refusal with an unlock command,
never a filesystem traceback (the contract every refusal preserves)."""

from __future__ import annotations

import json

import pytest

from platformforge.cli.main import main


@pytest.mark.parametrize("verb,refusal", [
    (["policy", "check"], "PF-POLICY-NO-FACTS"),
    (["finops", "costs"], "PF-FINOPS-NO-INPUT"),
    (["finops", "allocate"], "PF-FINOPS-NO-INPUT"),
    (["finops", "report"], "PF-FINOPS-NO-INPUT"),
])
def test_missing_file_is_named_refusal(verb, refusal, capsys, tmp_path):
    missing = tmp_path / "nope.json"
    rc = main([*verb, str(missing), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert out["refusal"] == refusal
    assert out["unlock"].startswith("platformforge ")


def test_directory_path_is_named_refusal(capsys, tmp_path):
    """`policy check .` used to crash with PermissionError on the dir read."""
    rc = main(["policy", "check", str(tmp_path), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert out["refusal"] == "PF-POLICY-NO-FACTS"
