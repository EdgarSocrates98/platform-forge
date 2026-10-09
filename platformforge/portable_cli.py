"""Thin CLI adapter for portable distribution and workspace."""
from __future__ import annotations
from pathlib import Path

def register(sub, add_common, emit):
    def install(a):
        from platformforge.distribution import apply_install
        return emit(apply_install(a.repo, a.profile, a.host, a.dry_run), a)
    def uninstall(a):
        from platformforge.distribution import uninstall as fn
        return emit(fn(a.repo, a.purge), a)
    def upgrade(a):
        from platformforge.distribution import upgrade as fn
        return emit(fn(a.repo, a.profile or None, a.host or None, a.dry_run), a)
    def portable(a):
        from platformforge.distribution import build_bundle, verify_bundle, install_bundle, doctor
        if a.portable_cmd == "build":
            return emit(build_bundle(a.path, a.profile, a.host, a.offline_bundle), a)
        if a.portable_cmd == "verify":
            out = verify_bundle(a.path); return emit(out, a, 0 if out["valid"] else 2)
        if a.portable_cmd == "install":
            out = install_bundle(a.path, a.repo)
            return emit(out, a, 2 if out.get("refusal") else 0)
        if a.portable_cmd == "doctor":
            return emit(doctor(a.repo), a)
        return emit({"refusal": "PF-DIST-UNKNOWN-COMMAND"}, a, 2)
    def workspace(a):
        from platformforge.workspace import ensure_workspace, load_workspace, add_repo, remove_repo, doctor
        c = a.workspace_cmd
        if c == "init": return emit(ensure_workspace(a.repo, a.profile, a.host).to_dict(), a)
        if c == "add": return emit(add_repo(a.repo, a.path, a.name).to_dict(), a)
        if c == "remove": return emit(remove_repo(a.repo, a.name).to_dict(), a)
        if c in ("doctor", "status"): return emit(doctor(a.repo) if c == "doctor" else load_workspace(a.repo).to_dict(), a)
        if c == "list": return emit({"repos": load_workspace(a.repo).to_dict()["repos"]}, a)
        return emit({"refusal": "PF-WORKSPACE-UNKNOWN-COMMAND"}, a, 2)

    sp = sub.add_parser("install", help="install Platform Forge assets into a workspace")
    add_common(sp); sp.add_argument("--profile", default="agentic")
    sp.add_argument("--host", action="append", choices=["agents","claude","codex","devin"])
    sp.add_argument("--dry-run", action="store_true"); sp.set_defaults(func=install)

    sp = sub.add_parser("uninstall", help="remove owned Platform Forge assets safely")
    add_common(sp); sp.add_argument("--purge", action="store_true"); sp.set_defaults(func=uninstall)

    sp = sub.add_parser("upgrade", help="upgrade managed portable assets")
    add_common(sp); sp.add_argument("--profile", default="")
    sp.add_argument("--host", action="append", choices=["agents","claude","codex","devin"])
    sp.add_argument("--dry-run", action="store_true"); sp.set_defaults(func=upgrade)

    sp = sub.add_parser("portable", help="build/verify/doctor portable distributions")
    add_common(sp); sp.add_argument("portable_cmd", choices=["build","verify","install","doctor"])
    sp.add_argument("path", nargs="?", default="dist/platformforge-portable")
    sp.add_argument("--profile", default="agentic")
    sp.add_argument("--host", action="append", choices=["agents","claude","codex","devin"])
    sp.add_argument("--offline-bundle", action="store_true", default=True)
    sp.set_defaults(func=portable)

    sp = sub.add_parser("workspace", help="workspace lifecycle and multi-repo manifest")
    add_common(sp); sp.add_argument("workspace_cmd", choices=["init","add","remove","list","doctor","status"])
    sp.add_argument("path", nargs="?", default=".")
    sp.add_argument("--name", default=""); sp.add_argument("--profile", default="agentic")
    sp.add_argument("--host", action="append", choices=["agents","claude","codex","devin"])
    sp.set_defaults(func=workspace)
