"""Cycle 2.1 §86–91 — redaction coverage, false positives, receipt
purity, caveman pipeline, offline enforcement."""

import json
import re

import pytest

from platformforge.core.redaction import (
    redact_text,
    redact_text_report,
    redaction_receipt,
)

SECRETS = {
    "aws_access_key": "AKIAIOSFODNN7EXAMPLE",
    "github_token": "ghp_" + "a" * 36,
    "gitlab_token": "glpat-" + "b" * 20,
    "slack_token": "xoxb-" + "1" * 12 + "-" + "2" * 12,
    "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIBOg==\n-----END RSA PRIVATE KEY-----",
    "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0." + "c" * 20,
    "password_kv": 'password: "Sup3rSecretValue"',
    "conn_string": "postgres://u:p@db.internal:5432/app",
    "conn_string_redis": "redis://default:s3cret@cache:6379",
    "generic_secret_kv": 'api_key = "k9X2mQ7vB4nL8wPz3jH5f"',
}


@pytest.mark.parametrize("name", sorted(SECRETS))
def test_pattern_detects(name):
    out, counts = redact_text_report(f"config = {SECRETS[name]}")
    label = name.split("_redis")[0]
    assert counts.get(label, 0) >= 1, (label, counts, out)
    assert SECRETS[name] not in out


def test_marker_is_stable_and_valueless():
    out1 = redact_text("token: " + SECRETS["github_token"])
    out2 = redact_text("elsewhere " + SECRETS["github_token"])
    m = re.search(r"\[REDACTED:github_token:[0-9a-f]{8}\]", out1)
    assert m and m.group(0) in out2  # same secret → same marker


def test_receipt_never_carries_values():
    blob = " ".join(SECRETS.values())
    _text, counts = redact_text_report(blob)
    receipt = redaction_receipt("test", counts)
    payload = json.dumps(receipt)
    for v in SECRETS.values():
        assert v not in payload
    assert receipt["total"] == sum(counts.values())
    assert receipt["kind"] == "pf-redaction-receipt/1"


def test_index_redacts_before_fts(tmp_path):
    """§87 — a secret in an indexed file is never searchable raw."""
    from platformforge.tokensave.index import SearchIndex
    (tmp_path / "cfg.py").write_text(
        f'TOKEN = "{SECRETS["github_token"]}"\n')
    idx = SearchIndex(tmp_path / "i.db")
    idx.index_workspace(tmp_path)
    hits = idx.search(SECRETS["github_token"][:20])
    assert not hits  # raw value never entered the index
    hits = idx.search("REDACTED")
    assert hits  # marker is searchable


def test_caveman_redacts_even_off():
    """§86 — redact → compress ordering holds for mode='off' too."""
    from platformforge.caveman.compress import compress
    for mode in ("off", "lite", "full"):
        out, _receipt = compress(f"key={SECRETS['aws_access_key']}",
                                 mode=mode)
        assert SECRETS["aws_access_key"] not in out
        assert "REDACTED" in out


FALSE_POSITIVE_GUARDS = [
    "the password policy requires 16 chars",   # talks about passwords
    "token bucket algorithm",                   # the word token
    "redis",                                    # bare scheme name
    "AKIAIOSFODNN7EXAMPL",                      # AKIA + 15 chars (too short)
    "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----",
]


@pytest.mark.parametrize("text", FALSE_POSITIVE_GUARDS)
def test_false_positives_not_redacted(text):
    out, counts = redact_text_report(text)
    assert out == text and not counts
