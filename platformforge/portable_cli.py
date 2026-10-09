"""Thin CLI adapter for portable distribution and workspace."""
from __future__ import annotations


def register(sub, add_common, emit):
    def install(a):
        # forge/* contract surface: `install <op>` routes the shared
        # lifecycle verbs; `apply` (default) keeps the legacy flags too —
        # `--profile agentic` and `--host agents` pass straight through.
        from platformforge.install import service

        op = getattr(a, "op", "apply") or "apply"
        hosts = a.host or ["all"]
        try:
            if op != "apply":
                fn = {
                    "status": lambda: service.status(scope=a.scope, root=a.repo),
                    "doctor": lambda: service.doctor(scope=a.scope, root=a.repo),
                    "repair": lambda: service.repair(scope=a.scope, root=a.repo,
                                                   dry_run=a.dry_run),
                    "uninstall": lambda: service.uninstall(scope=a.scope,
                                                         root=a.repo,
                                                         purge=a.purge,
                                                         dry_run=a.dry_run),
                    "update": lambda: service.update(to=a.to, repo=None,
                                                   dry_run=a.dry_run),
                    "mcp-verify": service.mcp_verify,
                }[op]
                out = fn()
            else:
                out = service.install(
                    scope=a.scope, root=a.repo,
                    host="all" if hosts == ["all"] else hosts[0]
                    if len(hosts) == 1 else "all",
                    profile=a.profile if a.profile in service.PROFILES
                    else "recommended",
                    yes=a.yes, dry_run=a.dry_run)
        except service.InstallRefusal as exc:
            return emit({"status": "refused",
                         "error": {"kind": exc.kind, "detail": exc.detail}}, a, 2)
        rc = 0 if out.get("status") in (
            "ok", "completed", "planned", "healthy", "unverified") else 1
        return emit(out, a, rc)

    def uninstall(a):
        from platformforge.distribution import uninstall as fn

        return emit(fn(a.repo, a.purge), a)

    def upgrade(a):
        from platformforge.distribution import upgrade as fn

        return emit(fn(a.repo, a.profile or None, a.host or None, a.dry_run), a)

    def portable(a):
        from platformforge.distribution import build_bundle, doctor, install_bundle, verify_bundle

        if a.portable_cmd == "build":
            return emit(build_bundle(a.path, a.profile, a.host, a.offline_bundle), a)
        if a.portable_cmd == "verify":
            out = verify_bundle(a.path)
            return emit(out, a, 0 if out["valid"] else 2)
        if a.portable_cmd == "install":
            out = install_bundle(a.path, a.repo)
            return emit(out, a, 2 if out.get("refusal") else 0)
        if a.portable_cmd == "doctor":
            return emit(doctor(a.repo), a)
        return emit({"refusal": "PF-DIST-UNKNOWN-COMMAND"}, a, 2)

    def workspace(a):
        from platformforge.workspace import add_repo, doctor, ensure_workspace, load_workspace, remove_repo

        command = a.workspace_cmd
        if command == "init":
            return emit(ensure_workspace(a.repo, a.profile, a.host).to_dict(), a)
        if command == "add":
            return emit(add_repo(a.repo, a.path, a.name).to_dict(), a)
        if command == "remove":
            return emit(remove_repo(a.repo, a.name).to_dict(), a)
        if command == "doctor":
            return emit(doctor(a.repo), a)
        if command == "status":
            return emit(load_workspace(a.repo).to_dict(), a)
        if command == "list":
            return emit({"repos": load_workspace(a.repo).to_dict()["repos"]}, a)
        return emit({"refusal": "PF-WORKSPACE-UNKNOWN-COMMAND"}, a, 2)

    sp = sub.add_parser("install", help="install Platform Forge assets into a workspace")
    add_common(sp)
    sp.add_argument("op", nargs="?", default="apply",
                    choices=["apply", "status", "doctor", "repair",
                             "uninstall", "update", "mcp-verify"],
                    help="forge/* lifecycle verb (default: apply)")
    sp.add_argument("--profile", default="recommended",
                    help="minimal|recommended|full (contract) or native profile name")
    sp.add_argument("--host", action="append",
                    choices=["agents", "claude", "codex", "devin", "copilot", "all"])
    sp.add_argument("--scope", default="project",
                    choices=["project", "workspace", "user"])
    sp.add_argument("--yes", "-y", action="store_true",
                    help="explicit approval — required for writes")
    sp.add_argument("--purge", action="store_true",
                    help="uninstall: also remove .platformforge state")
    sp.add_argument("--to", default=None,
                    help="update: pinned version — never 'latest'")
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(func=install)

    sp = sub.add_parser("uninstall", help="remove owned Platform Forge assets safely")
    add_common(sp)
    sp.add_argument("--purge", action="store_true")
    sp.set_defaults(func=uninstall)

    sp = sub.add_parser("upgrade", help="upgrade managed portable assets")
    add_common(sp)
    sp.add_argument("--profile", default="")
    sp.add_argument("--host", action="append", choices=["agents", "claude", "codex", "devin"])
    sp.add_argument("--dry-run", action="store_true")
    sp.set_defaults(func=upgrade)

    sp = sub.add_parser("portable", help="build/verify/doctor portable distributions")
    add_common(sp)
    sp.add_argument("portable_cmd", choices=["build", "verify", "install", "doctor"])
    sp.add_argument("path", nargs="?", default="dist/platformforge-portable")
    sp.add_argument("--profile", default="agentic")
    sp.add_argument("--host", action="append", choices=["agents", "claude", "codex", "devin"])
    sp.add_argument("--offline-bundle", action="store_true", default=True)
    sp.set_defaults(func=portable)

    sp = sub.add_parser("workspace", help="workspace lifecycle and multi-repo manifest")
    add_common(sp)
    sp.add_argument("workspace_cmd", choices=["init", "add", "remove", "list", "doctor", "status"])
    sp.add_argument("path", nargs="?", default=".")
    sp.add_argument("--name", default="")
    sp.add_argument("--profile", default="agentic")
    sp.add_argument("--host", action="append", choices=["agents", "claude", "codex", "devin"])
    sp.set_defaults(func=workspace)
