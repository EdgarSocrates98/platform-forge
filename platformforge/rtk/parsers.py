"""RTK parsers — one function per command family + a structured fallback.

Each parser returns dict fragments merged into CompactResult. Contract:
never lose error codes, resource ids, file:line, exit status, security
warnings, failed assertions.
"""

from __future__ import annotations

import json
import re
from typing import Any

ERR_RE = re.compile(r"(?i)\b(error|fatal|panic|failed|FAIL(?:ED)?|denied|"
                    r"forbidden|unauthorized|timeout)\b")
WARN_RE = re.compile(r"(?i)\b(warn(?:ing)?|deprecated|caution)\b")
FILELINE_RE = re.compile(r"([\w./\-]+\.\w+):(\d+)(?::(\d+))?")
RESOURCE_RE = re.compile(r"\b((?:arn:aws:[\w\-]+:[\w\-]*:\d*:[\w/=+,.@-]+)|"
                         r"(?:[a-z0-9\-]+\.)?[a-z0-9\-]+\.[a-z0-9\-_]+)\b")


def _grep_lines(lines: list[str], rx: re.Pattern) -> list[str]:
    return [l for l in lines if rx.search(l)]


def _fileline(text: str) -> dict[str, Any] | None:
    m = FILELINE_RE.search(text)
    if not m:
        return None
    return {"file": m.group(1), "line": int(m.group(2)),
            "col": int(m.group(3)) if m.group(3) else None}


def fallback(lines: list[str], **_kw) -> dict[str, Any]:
    errors = _grep_lines(lines, ERR_RE)
    warnings = _grep_lines(lines, WARN_RE)
    errs = []
    for e in errors[:100]:
        entry: dict[str, Any] = {"line": e.strip()}
        if fl := _fileline(e):
            entry.update(fl)
        errs.append(entry)
    return {
        "summary": {"lines": len(lines)},
        "errors": errs,
        "warnings": [w.strip() for w in warnings[:50]],
    }


def git_status(lines: list[str], **_kw) -> dict[str, Any]:
    staged = [l[3:] for l in lines if l[:1] in "MADR" and l[1:2] == " "]
    unstaged = [l[3:] for l in lines if len(l) > 2 and l[1] in "MD"]
    untracked = [l[3:] for l in lines if l.startswith("??")]
    return {"summary": {"staged": len(staged), "unstaged": len(unstaged),
                        "untracked": len(untracked)},
            "changed": staged + unstaged + untracked}


def git_diff(lines: list[str], **_kw) -> dict[str, Any]:
    files = [l.split(" b/")[-1] for l in lines if l.startswith("diff --git")]
    adds = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
    dels = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
    return {"summary": {"files_changed": len(files), "added": adds,
                        "removed": dels}, "changed": files}


def git_log(lines: list[str], **_kw) -> dict[str, Any]:
    commits = [l.split()[1] for l in lines if l.startswith("commit ")]
    return {"summary": {"commits": len(commits)}, "interesting": commits[:20]}


_PYTEST_SUM = re.compile(r"=+\s*(.*?)\s*=+\s*$")
_PYTEST_FAIL = re.compile(r"^(FAILED|ERROR)\s+(\S+)(?:\s+-\s+(.*))?$")


def pytest(lines: list[str], **_kw) -> dict[str, Any]:
    summary_line = next((m.group(1) for l in reversed(lines)
                         if (m := _PYTEST_SUM.match(l.strip()))), "")
    failures = [{"test": m.group(2), "reason": m.group(3) or ""}
                for l in lines if (m := _PYTEST_FAIL.match(l.strip()))]
    return {"summary": {"result": summary_line},
            "errors": [f["test"] for f in failures],
            "interesting": failures}


_TF_PLAN = re.compile(r"Plan:\s*(\d+)\s*to add,\s*(\d+)\s*to change,\s*(\d+)\s*to destroy")
_TF_RES = re.compile(r"#\s+([\w.\[\]\"-]+)\s+(will be|must be|is)\s+([\w-]+)")


def terraform_plan(lines: list[str], **_kw) -> dict[str, Any]:
    m = next((x for l in reversed(lines) if (x := _TF_PLAN.search(l))), None)
    summary = ({"add": int(m.group(1)), "change": int(m.group(2)),
                "destroy": int(m.group(3))} if m else {})
    changed = [f"{m.group(1)} {m.group(3)}" for l in lines
               if (m := _TF_RES.search(l))]
    errors = _grep_lines(lines, ERR_RE)
    return {"summary": summary, "changed": changed[:200],
            "errors": [e.strip() for e in errors[:50]],
            "warnings": [w.strip() for w in _grep_lines(lines, WARN_RE)[:50]]}


def terraform_validate(lines: list[str], **_kw) -> dict[str, Any]:
    errors = [l.strip() for l in lines if "Error:" in l]
    return {"summary": {"valid": not errors},
            "errors": errors[:50]}


def kubectl_get(lines: list[str], **_kw) -> dict[str, Any]:
    header = lines[0] if lines else ""
    rows = [l.split() for l in lines[1:] if l.strip()]
    not_ready = [r[0] for r in rows if len(r) > 1 and
                 re.search(r"0/|CrashLoop|Error|Pending|ImagePull|Evicted", " ".join(r))]
    return {"summary": {"header": header.strip(), "objects": len(rows),
                        "not_ready": len(not_ready)},
            "interesting": not_ready[:100]}


def kubectl_describe(lines: list[str], **_kw) -> dict[str, Any]:
    warnings = [l.strip() for l in lines if re.search(r"(?i)\bWarning\b", l)]
    reasons = re.findall(r"Reason:\s*(\w+)", "\n".join(lines))
    return {"summary": {"reasons": sorted(set(reasons))},
            "warnings": warnings[:100],
            "errors": [e.strip() for e in _grep_lines(lines, ERR_RE)[:50]]}


def kubectl_logs(lines: list[str], **_kw) -> dict[str, Any]:
    errors = _grep_lines(lines, ERR_RE)
    exceptions = [l.strip() for l in lines
                  if re.search(r"(Traceback|Exception|panic:|FATAL)", l)]
    return {"summary": {"lines": len(lines)},
            "errors": [e.strip() for e in (exceptions + errors)[:100]]}


def trivy(lines: list[str], **_kw) -> dict[str, Any]:
    counts = dict(re.findall(r"(CRITICAL|HIGH|MEDIUM|LOW|UNKNOWN):\s*(\d+)",
                             "\n".join(lines)))
    cves = re.findall(r"\b(CVE-\d{4}-\d{4,7})\b", "\n".join(lines))
    return {"summary": {"severities": {k: int(v) for k, v in counts.items()},
                        "unique_cves": len(set(cves))},
            "interesting": sorted(set(cves))[:200]}


def checkov(lines: list[str], **_kw) -> dict[str, Any]:
    failed = [l.strip() for l in lines if "FAILED" in l]
    passed = sum(1 for l in lines if "PASSED" in l)
    return {"summary": {"passed": passed, "failed": len(failed)},
            "errors": failed[:200]}


def go_test(lines: list[str], **_kw) -> dict[str, Any]:
    fails = [l.strip() for l in lines if l.startswith(("FAIL", "--- FAIL"))]
    ok = sum(1 for l in lines if l.startswith("ok "))
    return {"summary": {"packages_ok": ok, "failed": len(fails)},
            "errors": fails[:100]}


def npm_out(lines: list[str], **_kw) -> dict[str, Any]:
    errs = _grep_lines(lines, re.compile(r"npm error|ERR!"))
    vulns = re.search(r"(\d+) vulnerabilities", "\n".join(lines))
    return {"summary": {"vulnerabilities": int(vulns.group(1)) if vulns else 0},
            "errors": [e.strip() for e in errs[:100]]}


def json_kv(lines: list[str], **_kw) -> dict[str, Any]:
    """Generic JSON output: summarize shape + errors keys."""
    try:
        doc = json.loads("\n".join(lines))
    except json.JSONDecodeError:
        return fallback(lines)
    summary = {"type": type(doc).__name__}
    if isinstance(doc, list):
        summary["items"] = len(doc)
    elif isinstance(doc, dict):
        summary["keys"] = list(doc)[:50]
        for k in ("error", "errors", "Error", "message"):
            if k in doc:
                summary.setdefault("error_keys", []).append(k)
    return {"summary": summary}


PARSERS = {
    "git status": git_status, "git diff": git_diff, "git log": git_log,
    "git show": git_diff,
    "pytest": pytest, "py.test": pytest, "python -m pytest": pytest,
    "go test": go_test,
    "terraform plan": terraform_plan, "tofu plan": terraform_plan,
    "terraform validate": terraform_validate, "tofu validate": terraform_validate,
    "terraform show": fallback, "tofu show": fallback,
    "kubectl get": kubectl_get, "kubectl describe": kubectl_describe,
    "kubectl logs": kubectl_logs, "kubectl events": kubectl_describe,
    "kubectl diff": git_diff,
    "helm template": fallback, "helm diff": git_diff,
    "kustomize build": fallback,
    "argocd app get": kubectl_describe, "argocd app diff": git_diff,
    "docker": fallback, "podman": fallback,
    "trivy": trivy, "checkov": checkov,
    "npm": npm_out, "pnpm": npm_out, "mvn": fallback, "gradle": fallback,
    "aws": json_kv, "az": json_kv, "gcloud": json_kv,
}
