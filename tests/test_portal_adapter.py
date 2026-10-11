"""`platformforge portal` — adapter forge/PortalApi/1 over real services.

Each test lifts the portal server against a `tmp_path/project` with an
isolated HOME: nothing touches the real HOME or the checkout. The
skills/agents catalogs come from the package — they are what the
installed forge ships, independent of the workspace.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from platformforge import portal_adapter as pa
from platformforge.distribution import hostflow


@pytest.fixture(autouse=True)
def _home_isolated(tmp_path, monkeypatch):
    casa = tmp_path / "home_padrao"
    casa.mkdir()
    monkeypatch.setenv("HOME", str(casa))
    monkeypatch.setenv("USERPROFILE", str(casa))
    monkeypatch.setenv("APPDATA", str(casa / "AppData" / "Roaming"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    # sem binário de host: todo probe cai no ramo NOT_DETECTED
    monkeypatch.setattr(hostflow, "_default_which", lambda _nome: None)
    monkeypatch.setattr(hostflow, "_default_runner", lambda _a: (1, ""))


@pytest.fixture()
def projeto(tmp_path):
    p = tmp_path / "projeto"
    p.mkdir()
    (p / ".git").mkdir()
    return p


@pytest.fixture()
def server(projeto):
    srv = pa.build_server(projeto)
    srv.serve_in_thread()
    yield srv
    srv.shutdown()
    srv.server_close()


def _call(srv, method: str, path: str, body: dict | None = None,
          session: str | None = None):
    req = urllib.request.Request(
        f"http://127.0.0.1:{srv.port}/api/v1{path}",
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "Content-Type": "application/json",
            "X-Forge-Session": session or srv.session_token,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


# ---------------------------------------------------------------------------
# bootstrap / health / catálogos
# ---------------------------------------------------------------------------

def test_bootstrap_workspace_vazio(server):
    code, env = _call(server, "GET", "/bootstrap")
    assert code == 200
    d = env["data"]["descriptor"]
    assert d["forge_id"] == "platform-forge"
    assert env["schema"] == "forge/PortalApi/1"
    assert {c["id"] for c in d["capabilities"]} >= {
        "install", "hosts", "mcp", "skills", "agents", "tasks",
    }
    # ledger unverified: honesto NOT_INSTALLED
    assert env["data"]["health"]["state"] == "NOT_INSTALLED"


def test_bootstrap_exige_sessao(server):
    code, _env = _call(server, "GET", "/bootstrap", session="token-errado")
    assert code == 403


def test_catalogo_skills_e_agents_do_pacote(server):
    code, env = _call(server, "GET", "/skills")
    assert code == 200
    assert len(env["data"]) >= 10
    assert all(s["state"] == "available" for s in env["data"])
    code, env = _call(server, "GET", "/agents")
    assert code == 200
    assert len(env["data"]) >= 40  # roster canônico de 41 agents
    primeiro = env["data"][0]
    assert primeiro["id"] and primeiro["name"]


def test_hosts_observe_sem_binario(server):
    # _default_which stubbed → nenhum host detectado; unverified, nunca inventado
    code, env = _call(server, "GET", "/hosts")
    assert code == 200
    assert len(env["data"]) == 4
    assert all(h["detected"] is False for h in env["data"])


def test_hosts_launch_host_ausente_recusa_nomeada(server):
    code, env = _call(server, "POST", "/hosts/launch", {"host": "devin"})
    assert code == 200
    assert env["data"]["refusal"] == "PORTAL-HOST-ABSENT"
    code, env = _call(server, "POST", "/hosts/launch", {"host": "emacs"})
    assert code == 400
    assert env["error"]["code"] == "PORTAL-BAD-FIELD"


def test_graph_sem_indice_recusa_com_unlock(server):
    code, env = _call(server, "GET", "/graphs")
    assert code == 200
    avail = env["data"]["availability"]
    assert avail["state"] == "no_graph"
    assert avail["unlock"]


# ---------------------------------------------------------------------------
# install lifecycle — plan → confirm → apply → health
# ---------------------------------------------------------------------------

def test_install_plan_apply_verified(server, projeto):
    code, env = _call(server, "POST", "/installation/plan",
                      {"scope": "project", "host": "devin", "profile": "minimal"})
    assert code == 200
    plan = env["data"]["plan"]
    token = env["data"]["plan_token"]
    assert plan["host"] == "devin" and token

    # token errado → PORTAL-PLAN-STALE
    code, env = _call(server, "POST", "/installation/apply", {
        "scope": "project", "host": "devin", "profile": "minimal",
        "plan": plan, "plan_token": "forjado", "confirm": "apply"})
    assert code == 409
    assert env["error"]["code"] == "PORTAL-PLAN-STALE"

    # sem confirm → PORTAL-CONFIRM
    code, env = _call(server, "POST", "/installation/apply", {
        "scope": "project", "host": "devin", "profile": "minimal",
        "plan": plan, "plan_token": token})
    assert code == 400
    assert env["error"]["code"] == "PORTAL-CONFIRM"

    # fluxo correto
    code, env = _call(server, "POST", "/installation/apply", {
        "scope": "project", "host": "devin", "profile": "minimal",
        "plan": plan, "plan_token": token, "confirm": "apply"})
    assert code == 200
    assert env["data"]["status"] == "completed"

    # a instalação valeu: o estado deixa de ser NOT_INSTALLED (o doctor
    # pode reportar degraded com honestidade num ambiente sem binário).
    code, env = _call(server, "GET", "/bootstrap")
    assert env["data"]["health"]["state"] != "NOT_INSTALLED"


def test_install_plan_scope_invalido(server):
    code, env = _call(server, "POST", "/installation/plan", {"scope": "system"})
    assert code == 400
    assert env["error"]["code"] == "PORTAL-BAD-FIELD"


def test_install_plan_host_invalido(server):
    code, env = _call(server, "POST", "/installation/plan", {"host": "emacs"})
    assert code == 400
    assert env["error"]["code"] == "PORTAL-BAD-FIELD"


# ---------------------------------------------------------------------------
# tasks — intent → plan → execute, recusa nomeada para ambíguo
# ---------------------------------------------------------------------------

def test_task_doctor_roundtrip(server):
    code, env = _call(server, "POST", "/tasks/plan", {"intent": "doctor da instalação"})
    assert code == 200
    assert env["data"]["plan"]["verb"] == "doctor"
    code, env = _call(server, "POST", "/tasks/execute", {
        "plan": env["data"]["plan"], "plan_token": env["data"]["plan_token"],
        "confirm": "execute"})
    assert code == 200
    task = env["data"]["task"]
    assert task["stage"] == "completed"
    assert task["receipt"]["schema"].startswith("forge/")


def test_task_mcp_vem_antes_de_verificar(server):
    code, env = _call(server, "POST", "/tasks/plan",
                      {"intent": "verificar o handshake mcp"})
    assert code == 200
    assert env["data"]["plan"]["verb"] == "mcp_verify"


def test_task_intencao_ambigua_recusa_nomeada(server):
    code, env = _call(server, "POST", "/tasks/plan", {"intent": "apaga tudo"})
    assert code == 400
    err = env["error"]
    assert err["code"] == "PF-PORTAL-AMBIGUOUS"
    assert "safe_verbs" in (err.get("details") or {})


def test_task_execute_exige_confirm_e_token(server):
    code, env = _call(server, "POST", "/tasks/plan", {"intent": "status"})
    plan, token = env["data"]["plan"], env["data"]["plan_token"]
    code, env = _call(server, "POST", "/tasks/execute",
                      {"plan": plan, "plan_token": token})
    assert code == 400
    assert env["error"]["code"] == "PORTAL-CONFIRM"


def test_tasks_listadas_apos_execucao(server):
    _call(server, "POST", "/tasks/plan", {"intent": "status"})
    code, _env = _call(server, "GET", "/tasks")
    assert code == 200


def test_portal_verb_parseia():
    from platformforge.cli.main import build_parser

    args = build_parser().parse_args(["portal", "--no-browser", "--port", "0"])
    assert args.command == "portal"
    assert args.no_browser is True


def test_assets_index_resolvido():
    # clone ou wheel: um dos candidatos tem o index.html da SPA
    assert pa._ASSETS_DIR is not None
    assert (pa._ASSETS_DIR / "index.html").is_file()


# ---------------------------------------------------------------------------
# docs
# ---------------------------------------------------------------------------

def test_docs_search_inventory(server):
    code, env = _call(server, "GET", "/docs/search?q=install")
    assert code == 200
    assert len(env["data"]) > 0
    assert all("path" in h and "title" in h for h in env["data"])


def test_docs_search_vazio_sem_query(server):
    code, env = _call(server, "GET", "/docs/search")
    assert code == 200
    assert env["data"] == []
