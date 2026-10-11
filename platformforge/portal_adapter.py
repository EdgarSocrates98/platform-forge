"""Portal adapter for Platform Forge — maps forge/PortalApi/1 operations
onto the real install/service, distribution.hostflow, agents roster,
graphview and docs services. Nothing here fabricates state: every field
comes from a real service call; unverifiable values stay `unverified`.
"""
from __future__ import annotations

import json
import sys
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

from platformforge import _forge_portal as fp
from platformforge.install import service

_PACKAGE_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _PACKAGE_ROOT.parent
# Clone layout: portal/assets na raiz. Wheel layout: force-include copia para
# platformforge/portal_assets/ (mesmo padrão do data bundle).
_ASSETS_CANDIDATES = (
    _PACKAGE_ROOT / "portal_assets",
    _REPO_ROOT / "portal" / "assets",
)
_ASSETS_DIR = next((d for d in _ASSETS_CANDIDATES if (d / "index.html").is_file()), None)
# Skills: wheel carrega platformforge/data/portable_skills; clone usa
# .devin/skills (canônico) — mesma SKILL.md em ambos.
_SKILLS_CANDIDATES = (
    _PACKAGE_ROOT / "data" / "portable_skills",
    _REPO_ROOT / ".devin" / "skills",
)
_DOCS_DIR = _REPO_ROOT / "docs"
_HOSTS: tuple[str, ...] = service.CONTRACT_HOSTS
_PROFILES = service.PROFILES
_SCOPES = service.SCOPES
_DOCS_LIMIT = 600


def _version() -> str:
    try:
        return importlib_metadata.version("platformforge")
    except importlib_metadata.PackageNotFoundError:
        return "0.0.0+local"


def _health_state(status: dict[str, Any], doctor: dict[str, Any] | None) -> str:
    """Map the real lifecycle vocabulary — healthy|degraded|unverified —
    onto the contract InstallState. `status` is the ledger truth: an
    unverified ledger means "never installed", even when `doctor` reports
    `degraded` (its checks fail on missing artifacts)."""
    ledger = str(status.get("status") or "unverified").lower()
    if ledger == "unverified" and not status.get("ledger_entries"):
        return "NOT_INSTALLED"
    st = str((doctor or status).get("status") or "unverified").lower()
    if st == "unverified":
        return "NOT_INSTALLED"
    if st in ("degraded", "broken"):
        return "DEGRADED"
    if st == "healthy":
        checks = {c.get("id"): c.get("status") for c in (doctor or {}).get("checks", [])}
        mcp = checks.get("mcp-handshake")
        if mcp == "PASS":
            return "VERIFIED"
        if mcp in ("UNVERIFIED", "NOT_APPLICABLE", "BLOCKED"):
            return "ACTIVE"
        return "INSTALLED"
    return "NOT_INSTALLED"


def _named_refusal(exc: Exception) -> fp.PortalError:
    """service.InstallRefusal → named portal refusal, preserving the kind."""
    kind = getattr(exc, "kind", None) or "PF-PORTAL-REFUSED"
    return fp.PortalError(
        str(kind), str(exc), details={"kind": kind},
    )


class PlatformForgePortal(fp.PortalAdapter):
    forge_id = "platform-forge"
    forge_name = "Platform Forge"
    forge_version = _version()
    cli = "platformforge"
    theme = "platform-forge"
    federated = False

    def __init__(self, workspace: Path | None = None) -> None:
        self.workspace = str((workspace or Path.cwd()).resolve())
        self._root = Path(self.workspace)
        self.assets_dir = _ASSETS_DIR
        self._tasks: list[dict[str, Any]] = []
        self._task_seq = 0
        self.ops = fp.default_operations(self) + [
            fp.Operation("GET", "/profiles", lambda ctx: self._profiles()),
            fp.Operation("GET", "/hosts", lambda ctx: self._hosts()),
            fp.Operation("GET", "/mcp/servers", lambda ctx: self._mcp_servers()),
            fp.Operation("GET", "/skills", lambda ctx: self._skills()),
            fp.Operation("GET", "/agents", lambda ctx: self._agents()),
            fp.Operation("GET", "/tasks", lambda ctx: list(self._tasks)),
            fp.Operation("GET", "/graphs", lambda ctx: self._graphs()),
            fp.Operation("GET", "/docs/search", lambda ctx: self._docs_search(ctx)),
            fp.Operation("POST", "/installation/plan", self._install_plan, mutating=True),
            fp.Operation(
                "POST", "/installation/apply", self._install_apply,
                mutating=True, confirm="apply", needs_plan_token=True,
            ),
            fp.Operation(
                "POST", "/installation/repair", self._install_repair,
                mutating=True, confirm="repair",
            ),
            fp.Operation(
                "POST", "/installation/uninstall", self._install_uninstall,
                mutating=True, confirm="uninstall",
            ),
            fp.Operation(
                "POST", "/profiles/apply", self._profiles_apply,
                mutating=True, confirm="apply",
            ),
            fp.Operation("POST", "/hosts/launch", self._hosts_launch, mutating=False),
            fp.Operation("POST", "/mcp/verify", self._mcp_verify, mutating=True, confirm="verify"),
            fp.Operation("POST", "/tasks/plan", self._tasks_plan, mutating=True),
            fp.Operation(
                "POST", "/tasks/execute", self._tasks_execute,
                mutating=True, confirm="execute", needs_plan_token=True, timeout=120,
            ),
        ]

    # ------------------------------------------------------------------
    # descriptor / health / capabilities
    # ------------------------------------------------------------------
    def capabilities(self) -> list[dict]:
        return [
            {"id": "install", "state": "supported"},
            {"id": "hosts", "state": "supported"},
            {"id": "mcp", "state": "supported"},
            {"id": "skills", "state": "supported" if self._skills_dir() else "unverified"},
            {"id": "agents", "state": "supported"},
            {"id": "tasks", "state": "supported"},
            {"id": "docs", "state": "supported" if _DOCS_DIR.is_dir() else "unverified"},
            {
                "id": "graph",
                "state": "supported" if self._graph_view() is not None else "unverified",
            },
        ]

    def nav(self) -> list[dict]:
        return [
            {
                "id": "tasks",
                "label_key": "nav.tasks",
                "route": "/tasks",
                "requires_capability": "tasks",
            },
            {
                "id": "graph",
                "label_key": "nav.graph",
                "route": "/graph",
                "requires_capability": "graph",
            },
        ]

    def health(self) -> dict:
        status = self._status_doc()
        doctor = None
        doctor_error: str | None = None
        try:
            doctor = service.doctor(scope="project", root=self._root)
        except Exception as e:  # noqa: BLE001 — doctor failure degrades, never crashes bootstrap
            doctor_error = f"{type(e).__name__}: {e}"
        checks = []
        for c in (doctor or {}).get("checks", []):
            checks.append({
                "id": c.get("id", "check"),
                "state": c.get("status", "UNVERIFIED"),
                "detail": c.get("detail"),
            })
        if doctor_error:
            checks.append({"id": "doctor", "state": "UNVERIFIED", "detail": doctor_error})
        return {
            "state": _health_state(status, doctor),
            "checks": checks,
            "workspace": self.workspace,
            "profile": status.get("profile") if status.get("profile") else None,
            "updated_at": status.get("checked_at"),
        }

    def installation_status(self, ctx: fp.RequestContext | None = None) -> dict:
        return self.health()

    def _status_doc(self) -> dict[str, Any]:
        try:
            return service.status(scope="project", root=self._root)
        except Exception:  # noqa: BLE001 — non-repo root reads as uninstalled
            return {"drift": {}, "status": "unverified"}

    # ------------------------------------------------------------------
    # installation lifecycle — plan → confirm → apply, real receipts
    # ------------------------------------------------------------------
    def _install_plan(self, ctx: fp.RequestContext) -> dict:
        scope = (ctx.body or {}).get("scope", "project")
        if scope not in _SCOPES:
            raise fp.PortalError(
                "PORTAL-BAD-FIELD", f"scope must be one of {_SCOPES}",
                details={"field": "scope", "got": scope},
            )
        host = (ctx.body or {}).get("host", "all")
        known = service.CONTRACT_HOSTS + ("all", "none")
        if host not in known and not all(
            h.strip() in service.CONTRACT_HOSTS for h in str(host).split(",")
        ):
            raise fp.PortalError(
                "PORTAL-BAD-FIELD", f"host must be one of {known}",
                details={"field": "host", "got": host},
            )
        profile = (ctx.body or {}).get("profile", "recommended")
        try:
            receipt = service.install(
                scope=scope, root=self._root, host=host, profile=profile, dry_run=True,
            )
        except service.InstallRefusal as exc:
            raise _named_refusal(exc) from exc
        plan_input = {"scope": scope, "profile": profile, "host": host}
        return {
            "status": receipt.get("status", "planned"),
            "plan": plan_input,
            "plan_token": ctx.handler.server.sign_plan(plan_input),
            "receipt": receipt,
            "actions": [
                {"kind": "file", "path": p, "status": "planned"}
                for p in receipt.get("planned_files", [])
            ],
        }

    def _install_apply(self, ctx: fp.RequestContext) -> dict:
        # The echoed plan is the source of truth — the token binds to it.
        plan = (ctx.body or {}).get("plan") or {}
        if not ctx.handler.server.check_plan(ctx.body["plan_token"], plan):
            raise fp.PortalError(
                "PORTAL-PLAN-STALE",
                "plan token does not match this plan or expired — regenerate the plan",
                http=409, retryable=True, action="regenerate_plan",
            )
        try:
            return service.install(
                scope=plan.get("scope", "project"), root=self._root,
                host=plan.get("host", "all"),
                profile=plan.get("profile", "recommended"),
                dry_run=False, yes=True,
            )
        except service.InstallRefusal as exc:
            raise _named_refusal(exc) from exc

    def _install_repair(self, ctx: fp.RequestContext) -> dict:
        try:
            return service.repair(scope="project", root=self._root)
        except service.InstallRefusal as exc:
            raise _named_refusal(exc) from exc

    def _install_uninstall(self, ctx: fp.RequestContext) -> dict:
        try:
            return service.uninstall(scope="project", root=self._root)
        except service.InstallRefusal as exc:
            raise _named_refusal(exc) from exc

    # ------------------------------------------------------------------
    # profiles
    # ------------------------------------------------------------------
    def _profiles(self) -> list[dict]:
        current = self._installed_profile()
        return [
            {
                "id": "economy",
                "label_key": "profiles.economy",
                "description_key": "profiles.economy.desc",
                "current": current == "economy",
                "components": {
                    "skills": False, "agents": False, "mcp": True,
                    "tui": False, "graph_studio": False,
                },
            },
            {
                "id": "balanced",
                "label_key": "profiles.balanced",
                "description_key": "profiles.balanced.desc",
                "current": current == "balanced",
                "components": {
                    "skills": True, "agents": True, "mcp": True,
                    "tui": True, "graph_studio": False,
                },
            },
            {
                "id": "full",
                "label_key": "profiles.full",
                "description_key": "profiles.full.desc",
                "current": current == "full",
                "components": {
                    "skills": True, "agents": True, "mcp": True,
                    "tui": True, "graph_studio": True,
                },
            },
        ]

    def _installed_profile(self) -> str:
        """Sinal honesto: components.json do estado (só escrito com
        componentes explícitos). Sem ele, profile fica vazio (unverified)."""
        comp = self._root / ".platformforge" / "components.json"
        if not comp.is_file():
            return ""
        try:
            doc = json.loads(comp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
        if not isinstance(doc, dict) or not doc:
            return ""
        selected = {k for k, v in doc.items() if v}
        if selected >= {"skills", "agents", "mcp", "tui", "graph_studio"}:
            return "full"
        return ""

    def _profiles_apply(self, ctx: fp.RequestContext) -> dict:
        profile = (ctx.body or {}).get("profile", "balanced")
        real = {"economy": "minimal", "balanced": "recommended", "full": "full"}.get(profile)
        if real is None:
            raise fp.PortalError(
                "PORTAL-BAD-FIELD", f"profile must be one of {_PROFILES + ('economy', 'balanced')}",
                details={"field": "profile", "got": profile},
            )
        try:
            return service.install(
                scope="project", root=self._root, host="all", profile=real,
                dry_run=False, yes=True,
            )
        except service.InstallRefusal as exc:
            raise _named_refusal(exc) from exc

    # ------------------------------------------------------------------
    # hosts — observe-only; launch returns the command to copy
    # ------------------------------------------------------------------
    def _host_states(self) -> list[dict[str, Any]]:
        from platformforge.distribution.hostflow import host_state

        return [host_state(h, repo=self._root) for h in _HOSTS]

    def _hosts(self) -> list[dict]:
        try:
            states = self._host_states()
        except Exception as e:  # noqa: BLE001 — host probe degrades honestly
            return [{
                "host": h, "detected": False, "version": None,
                "supported": False, "logged_in": None,
                "integration": "unverified", "launchable": False,
                "detail": f"probe failed: {type(e).__name__}",
            } for h in _HOSTS]
        out: list[dict] = []
        for h in states:
            integration = h.get("integration") or {}
            # state: NOT_DETECTED|DETECTED|SUPPORTED|READY|NEEDS_LOGIN|
            # INTEGRATION_* (distribution.hostflow.host_state)
            detected = h.get("binary_path") is not None
            out.append({
                "host": h.get("host", "?"),
                "detected": detected,
                "version": h.get("version"),
                "supported": h.get("state") in ("READY", "SUPPORTED"),
                "logged_in": h.get("logged_in"),
                "integration": integration.get("state", "unverified"),
                "launchable": detected,
                "command_hint": h.get("launch_command") if detected else None,
                "detail": h.get("detail") or h.get("login_hint"),
            })
        return out

    def _hosts_launch(self, ctx: fp.RequestContext) -> dict:
        host = (ctx.body or {}).get("host")
        if host not in _HOSTS:
            raise fp.PortalError(
                "PORTAL-BAD-FIELD", f"host must be one of {_HOSTS}",
                details={"field": "host", "got": host},
            )
        from platformforge.distribution.hostflow import host_state

        h = host_state(host, repo=self._root)
        # NOT_DETECTED hosts still carry a launch_command string — the
        # binary is the evidence, not the label.
        if h.get("binary_path") is None:
            return {
                "command": None,
                "refusal": "PORTAL-HOST-ABSENT",
                "detail": f"{host} not detected on this system",
            }
        # A portal has no real TTY — return the command to copy.
        return {
            "command": h.get("launch_command"),
            "detail": f"run `{h.get('launch_command')}` in your terminal to open {host}",
            "host": h.get("host"),
        }

    # ------------------------------------------------------------------
    # mcp
    # ------------------------------------------------------------------
    def _mcp_verify_doc(self) -> dict[str, Any]:
        try:
            return service.mcp_verify()
        except Exception as e:  # noqa: BLE001
            return {
                "status": "FAIL",
                "detail": f"mcp verify failed: {type(e).__name__}",
            }

    def _mcp_servers(self) -> list[dict]:
        doc = self._mcp_verify_doc()
        status = doc.get("status", "FAIL")
        # kit.mcp_verify devolve o check {id,status,detail}: PASS significa
        # handshake+tools/list reais; o doc não carrega a contagem de tools.
        state = {
            "PASS": "INVOCATION_VERIFIED",
            "HANDSHAKE": "HANDSHAKE_VERIFIED",
            "FAIL": "FAILED",
            "BLOCKED": "DEGRADED",
            "NOT_APPLICABLE": "DEGRADED",
        }.get(status, "DEGRADED")
        return [{
            "id": "platformforge",
            "state": state,
            "host": None,
            "tools_count": None,
            "last_verify": None,
            "detail": doc.get("detail"),
        }]

    def _mcp_verify(self, ctx: fp.RequestContext) -> dict:
        doc = self._mcp_verify_doc()
        return {
            "status": doc.get("status", "FAIL"),
            "detail": doc.get("detail"),
            "actions": [
                {
                    "kind": "handshake",
                    "path": "mcp://platformforge",
                    "status": doc.get("status", "FAIL"),
                }
            ],
        }

    # ------------------------------------------------------------------
    # skills / agents — packaged skills + canonical roster
    # ------------------------------------------------------------------
    def _skills_dir(self) -> Path | None:
        for cand in _SKILLS_CANDIDATES:
            if cand.is_dir() and any(cand.glob("*/SKILL.md")):
                return cand
        return None

    def _skills(self) -> list[dict]:
        root = self._skills_dir()
        if root is None:
            raise fp.PortalError(
                "PF-PORTAL-REGISTRY-UNAVAILABLE",
                "skill catalog not found in package or clone",
                http=503, retryable=True,
                details={"candidates": [str(c) for c in _SKILLS_CANDIDATES]},
            )
        out: list[dict] = []
        for skill_md in sorted(root.glob("*/SKILL.md")):
            sid = skill_md.parent.name
            desc = ""
            try:
                for line in skill_md.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("description:"):
                        desc = line.split(":", 1)[1].strip().strip('"')
                        break
            except OSError:
                continue
            out.append({
                "id": sid,
                "name": sid,
                "domain": sid.rsplit("-", 1)[-1] if "-" in sid else None,
                "description": desc,
                "state": "available",
                "hosts": [],
                "source": "portable_skills" if "data" in root.parts else "devin_skills",
            })
        return out

    def _agents(self) -> list[dict]:
        from platformforge.agents import roster

        out: list[dict] = []
        for aid, spec in sorted(roster.AGENTS.items()):
            doc = spec.to_dict() if hasattr(spec, "to_dict") else dict(spec)
            out.append({
                "id": aid,
                "name": doc.get("name", aid),
                "role": doc.get("role", "agent"),
                "description": doc.get("mission", "") or doc.get("description", ""),
                "authority": doc.get("access"),
                "domains": list(doc.get("domains") or []),
                "skills": list(doc.get("required_skills") or []),
                "hosts": [],
                "state": "available",
            })
        return out

    # ------------------------------------------------------------------
    # tasks — safe read-only diagnostics mapped from intent, real receipts
    # ------------------------------------------------------------------
    # Order matters — first needle hit wins. `mcp`/`handshake` precede the
    # generic `verif` needles so "verificar o handshake mcp" picks mcp_verify,
    # and `doctor` precedes `instala` so "doctor da instalação" is not status.
    _SAFE_TASKS: tuple[tuple[tuple[str, ...], str, str], ...] = (
        (("mcp", "handshake"), "mcp_verify", "MCP handshake verification"),
        (("doctor", "saúde", "saude", "verifica", "verif"), "doctor", "installation doctor"),
        (("status", "estado", "instala"), "status", "installation status"),
        (("grafo", "graph"), "graph", "graph summary"),
        (("skill",), "skills", "skill catalog summary"),
        (("agent",), "agents", "agent roster summary"),
    )

    def _intent_to_task(self, intent: str) -> tuple[str, str] | None:
        low = intent.lower()
        for needles, verb, label in self._SAFE_TASKS:
            if any(n in low for n in needles):
                return verb, label
        return None

    def _tasks_plan(self, ctx: fp.RequestContext) -> dict:
        intent = ((ctx.body or {}).get("intent") or "").strip()
        if not intent:
            raise fp.PortalError(
                "PORTAL-MISSING-FIELD", "field 'intent' is required",
                details={"field": "intent"},
            )
        mapped = self._intent_to_task(intent)
        if mapped is None:
            verbs = sorted({v for _n, v, _l in self._SAFE_TASKS})
            raise fp.PortalError(
                "PF-PORTAL-AMBIGUOUS",
                "intent does not map to a safe portal task",
                severity="warning",
                action="use one of the safe tasks",
                details={"safe_verbs": verbs, "intent": intent},
            )
        verb, label = mapped
        plan = {"verb": verb, "label": label, "intent": intent}
        return {
            "plan": plan,
            "plan_token": ctx.handler.server.sign_plan(plan),
            "status": "planned",
        }

    def _tasks_execute(self, ctx: fp.RequestContext) -> dict:
        plan = (ctx.body or {}).get("plan") or {}
        verb = plan.get("verb", "")
        if not ctx.handler.server.check_plan(ctx.body["plan_token"], plan):
            raise fp.PortalError(
                "PORTAL-PLAN-STALE",
                "plan token does not match — regenerate the plan",
                http=409, retryable=True, action="regenerate_plan",
            )
        self._task_seq += 1
        task_id = f"task-{self._task_seq}"
        record: dict[str, Any] = {
            "id": task_id, "verb": verb, "label": plan.get("label", verb),
            "stage": "running", "started_at": _now(), "finished_at": None,
            "exit_code": None,
        }
        try:
            result = self._run_safe_task(verb)
            record["stage"] = "completed"
            record["exit_code"] = 0
            record["receipt"] = result
        except fp.PortalError as e:
            record["stage"] = "refused"
            record["exit_code"] = 2
            record["refusal"] = e.code
            record["receipt"] = {"detail": str(e)}
        except Exception as e:  # noqa: BLE001 — task failure is data, not a crash
            record["stage"] = "failed"
            record["exit_code"] = 1
            record["receipt"] = {"error": f"{type(e).__name__}: {e}"}
        record["finished_at"] = _now()
        self._tasks.append(record)
        return {
            "status": record["stage"],
            "task": record,
            "actions": [{"kind": "task", "path": verb, "status": record["stage"]}],
        }

    def _run_safe_task(self, verb: str) -> dict[str, Any]:
        if verb == "status":
            return self._status_doc()
        if verb == "doctor":
            return service.doctor(scope="project", root=self._root)
        if verb == "mcp_verify":
            return self._mcp_verify_doc()
        if verb == "graph":
            view = self._graph_view()
            if view is None:
                raise fp.PortalError(
                    "PF-PORTAL-NO-GRAPH", "no graph built in this workspace",
                    action="build the graph first",
                )
            return view
        if verb == "skills":
            return {"skills": len(self._skills())}
        if verb == "agents":
            return {"agents": len(self._agents())}
        raise fp.PortalError("PORTAL-UNSAFE-TASK", f"task '{verb}' is not in the safe set")

    # ------------------------------------------------------------------
    # graph — persisted graph via graphview.build_view(root)
    # ------------------------------------------------------------------
    def _graph_view(self) -> dict[str, Any] | None:
        try:
            from platformforge import graphview
        except Exception:  # noqa: BLE001
            return None
        try:
            view = graphview.build_view(self._root)
        except Exception:  # noqa: BLE001 — absent/partial graph → unavailable
            return None
        if view is None:
            return None
        return view.to_dict() if hasattr(view, "to_dict") else json.loads(
            json.dumps(view, default=str))

    def _graphs(self) -> dict:
        view = self._graph_view()
        if view is None:
            return {
                "availability": {
                    "state": "no_graph",
                    "detail": "no graph built in this workspace",
                    "unlock": "platformforge graph build --repo .",
                },
                "views": [],
                "studio_url": None,
            }
        return {
            "availability": {"state": "available"},
            "views": [view],
            "studio_url": None,
        }

    # ------------------------------------------------------------------
    # docs search — bounded markdown scan, offline
    # ------------------------------------------------------------------
    def _docs_search(self, ctx: fp.RequestContext) -> list[dict]:
        query = (ctx.query.get("q") or [""])[0].strip().lower()
        limit = int((ctx.query.get("limit") or ["20"])[0])
        if not query or not _DOCS_DIR.is_dir():
            return []
        hits: list[dict] = []
        terms = query.split()
        for md in sorted(_DOCS_DIR.rglob("*.md"))[:_DOCS_LIMIT]:
            rel = md.relative_to(_REPO_ROOT).as_posix()
            try:
                head = md.read_text(encoding="utf-8")[:4000]
            except OSError:
                continue
            title = next(
                (ln[2:].strip() for ln in head.splitlines() if ln.startswith("# ")),
                md.stem,
            )
            hay = f"{title} {rel} {head[:1500]}".lower()
            if not all(t in hay for t in terms):
                continue
            hits.append({
                "path": rel,
                "title": title,
                "excerpt": "",
                "category": md.parent.name,
            })
            if len(hits) >= limit:
                break
        return hits


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_server(workspace: Path | None = None, *, quiet: bool = True) -> fp.PortalServer:
    return fp.PortalServer(PlatformForgePortal(workspace), quiet=quiet)


def _portal(args) -> dict[str, Any]:
    import webbrowser

    root = Path(getattr(args, "repo", None) or getattr(args, "root", None) or Path.cwd())
    adapter = PlatformForgePortal(root)
    if adapter.assets_dir is None:
        return {
            "refusal": "PF-PORTAL-NO-ASSETS",
            "status": "refused",
            "detail": (
                "portal assets not vendored — run `platformforge portal` "
                "after `python scripts/vendor.py` in forge-portal"
            ),
        }
    server = fp.PortalServer(adapter, port=args.port, quiet=True)
    url = server.url
    print(json.dumps({
        "url": url,
        "note": "portal is optional — CLI/MCP keep working without it",
    }))
    if not getattr(args, "no_browser", False):
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
    return {"status": "completed"}


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="platformforge portal",
        description="Serve the Platform Forge portal locally (127.0.0.1).",
    )
    ap.add_argument(
        "--no-browser", action="store_true",
        help="print the URL without opening the browser",
    )
    ap.add_argument("--port", type=int, default=0, help="port (0 = free port)")
    ap.add_argument("--root", default=None, help="workspace root (default: cwd)")
    args = ap.parse_args(argv)
    doc = _portal(args)
    return 0 if doc.get("status") == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
