from __future__ import annotations

from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent


# ---- config


def test_config_defaults(sdt: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("")
    cfg = sdt.load_config(path)
    assert cfg.default_branch == "main"
    assert cfg.backlog_dir == "docs/backlog"
    assert cfg.timeout_for("developer") == 3600
    assert cfg.engine_for("developer") == "claude"


def test_config_template_loads(sdt: ModuleType) -> None:
    cfg = sdt.load_config(ROOT / "docs" / "config.template.toml")
    assert cfg.max_parallel_developers == 2
    assert cfg.timeout_for("merge-clerk") == 900


def test_config_rejects_bad_tier(sdt: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[engine.tiers]\nhuge = "x"\n')
    with pytest.raises(sdt.SdtError):
        sdt.load_config(path)


def test_config_missing(sdt: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(sdt.SdtError):
        sdt.load_config(tmp_path / "missing.toml")


# ---- adapters


@pytest.mark.parametrize("name", sorted(p.stem for p in (ROOT / "adapters").glob("*.toml")))
def test_shipped_adapters_load(sdt: ModuleType, name: str, tmp_path: Path) -> None:
    adapter = sdt.load_adapter(name, [ROOT / "adapters"])
    assert adapter.name == name
    assert adapter.command
    assert adapter.tested == (name in {"claude", "agy"}), "only engines exercised for real are marked tested"
    prompt = tmp_path / "p"
    prompt.write_text("PROMPT")
    argv = adapter.render(model="m", cwd=tmp_path, add_dirs=[Path("/g")], out=tmp_path / "o", prompt_file=prompt)
    assert argv[0] == adapter.executable
    if adapter.prompt == "arg":
        assert argv[-1] == "PROMPT"
        assert argv[-2] in {*adapter.prompt_args, *adapter.command, "/g", "m"}, "the prompt is the last token"
        for flag in ("-p", "--print"):
            assert flag not in adapter.command, f"{flag} would swallow the next flag; put it in prompt_args"


def test_render_claude(sdt: ModuleType, tmp_path: Path) -> None:
    adapter = sdt.load_adapter("claude", [ROOT / "adapters"])
    argv = adapter.render(
        model="opus", cwd=tmp_path, add_dirs=[Path("/a"), Path("/b")], out=tmp_path / "o", prompt_file=tmp_path / "p"
    )
    assert argv[:2] == ["claude", "-p"]
    assert "--permission-mode" in argv and "bypassPermissions" in argv
    assert argv[argv.index("--model") + 1] == "opus"
    i = argv.index("--add-dir")
    assert argv[i + 1 : i + 3] == ["/a", "/b"]


def test_render_codex(sdt: ModuleType, tmp_path: Path) -> None:
    adapter = sdt.load_adapter("codex", [ROOT / "adapters"])
    argv = adapter.render(
        model="", cwd=tmp_path, add_dirs=[Path("/a"), Path("/b")], out=tmp_path / "o", prompt_file=tmp_path / "p"
    )
    assert argv[:2] == ["codex", "exec"]
    assert "-m" not in argv, "no model → no model flag"
    assert argv.count("--add-dir") == 2
    assert argv[-1] == "-"
    assert str(tmp_path / "o") in argv and str(tmp_path) in argv


def test_render_gemini(sdt: ModuleType, tmp_path: Path) -> None:
    adapter = sdt.load_adapter("gemini", [ROOT / "adapters"])
    argv = adapter.render(
        model="m", cwd=tmp_path, add_dirs=[Path("/a"), Path("/b")], out=tmp_path / "o", prompt_file=tmp_path / "p"
    )
    assert argv[argv.index("--include-directories") + 1] == "/a,/b"
    assert argv[argv.index("-m") + 1] == "m"
    assert 53 in adapter.timeout_exit_codes


def test_tier_override(sdt: ModuleType) -> None:
    adapter = sdt.load_adapter("claude", [ROOT / "adapters"])
    assert adapter.model_for("mid", {}) == "sonnet"
    assert adapter.model_for("mid", {"mid": "custom"}) == "custom"


# ---- results


def test_parse_result_last_block(sdt: ModuleType) -> None:
    text = (
        'ran\n```json\n{"message": "FIRST"}\n```\nthen\n```json\n{"message": "READY-FOR-REVIEW", "head": "abc"}\n```\n'
    )
    assert sdt.parse_result(text)["message"] == "READY-FOR-REVIEW"


@pytest.mark.parametrize(
    "text",
    ["no block at all", "```json\nnot json\n```", '```json\n{"no": "message"}\n```', "```json\n[1, 2]\n```"],
)
def test_parse_result_fails_closed(sdt: ModuleType, text: str) -> None:
    with pytest.raises(sdt.SdtError):
        sdt.parse_result(text)


def test_extract_json_result_checks_success(sdt: ModuleType, tmp_path: Path) -> None:
    adapter = sdt.load_adapter("claude", [ROOT / "adapters"])
    stream = '{"type":"assistant","message":{}}\n{"type":"result","subtype": "success", "result": "final"}\n'
    assert sdt.extract_final_text(adapter, stream, tmp_path / "none") == "final"
    with pytest.raises(sdt.SdtError):
        sdt.extract_final_text(adapter, '{"subtype": "error_max_turns", "result": "x"}', tmp_path / "none")
    assert adapter.streams, "a single-object JSON engine cannot be judged by log growth"


def test_extract_nested_result(sdt: ModuleType, tmp_path: Path) -> None:
    adapter = sdt.load_adapter("agy", [ROOT / "adapters"])
    stream = '{"event":"step_update"}\n{"event":"result","result":{"status":"SUCCESS","response":"done"}}\n'
    assert sdt.extract_final_text(adapter, stream, tmp_path / "none") == "done"
    with pytest.raises(sdt.SdtError):
        sdt.extract_final_text(
            adapter, '{"event":"result","result":{"status":"ERROR","response":"x"}}', tmp_path / "none"
        )


def test_extract_file_mode(sdt: ModuleType, tmp_path: Path) -> None:
    adapter = sdt.load_adapter("codex", [ROOT / "adapters"])
    out = tmp_path / "out"
    out.write_text("from file")
    assert sdt.extract_final_text(adapter, "jsonl noise", out) == "from file"
    with pytest.raises(sdt.SdtError):
        sdt.extract_final_text(adapter, "", tmp_path / "missing")


def test_last_json_object_from_jsonl(sdt: ModuleType) -> None:
    text = '{"type":"event"}\n{"type":"result","response":"hi"}\n'
    assert sdt._last_json_object(text)["response"] == "hi"


# ---- roles and prompts


def test_frontmatter(sdt: ModuleType) -> None:
    meta, body = sdt.parse_frontmatter("---\nname: x\ndescription: >\n  one\n  two\ntier: mid\n---\nBody\n")
    assert meta["name"] == "x"
    assert meta["description"] == "one two"
    assert meta["tier"] == "mid"
    assert body == "Body\n"


def test_every_role_loads(sdt: ModuleType) -> None:
    for path in (ROOT / "roles").glob("*.md"):
        role = sdt.load_role(path.stem)
        assert role.tier in sdt.TIERS
        assert role.body.strip()


def test_prompt_shape(sdt: ModuleType) -> None:
    role = sdt.Role(name="developer", tier="mid", access="write", vision=False, engines=[], body="BODY\n")
    prompt = sdt.build_prompt(role, {"role": "developer", "scoped gate": ["a", "b"]}, {"message": "IMPLEMENT"}, "note")
    assert prompt.startswith("BODY")
    assert "- role: developer" in prompt
    assert "- scoped gate: a, b" in prompt
    assert "## Dispatch" in prompt and '"message": "IMPLEMENT"' in prompt
    assert "## Result contract" in prompt


# ---- triage


def triage_orchestrator(
    sdt: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, slugs: list[str]
) -> tuple[Any, list[dict[str, Any]]]:
    """An orchestrator on a scratch repository whose role runs are recorded, never spawned."""
    repo = tmp_path / "repo"
    (repo / "docs" / "backlog").mkdir(parents=True)
    (repo / ".delivery-team").mkdir()
    (repo / ".delivery-team" / "config.toml").write_text('[engine]\ndefault = "fake"\n')
    for slug in slugs:
        (repo / "docs" / "backlog" / f"{slug}.md").write_text(f"# {slug}\n")
    sdt.git("init", "-q", "-b", "main", cwd=repo)
    for key, value in (("user.email", "t@example.com"), ("user.name", "Test"), ("commit.gpgsign", "false")):
        sdt.git("config", key, value, cwd=repo)
    commit_all(sdt, repo, "chore: seed")
    orch = sdt.Orchestrator(
        sdt.Project(repo, [ROOT / "tests" / "adapters"]), engine="fake", watch=False, label="t", args_text=""
    )
    requests: list[dict[str, Any]] = []

    def start_run(role_name: str, payload: dict[str, Any], **kw: Any) -> SimpleNamespace:
        requests.append(payload)
        return SimpleNamespace(role=SimpleNamespace(name=role_name), payload=payload, tag=kw.get("tag", ""))

    monkeypatch.setattr(orch.p, "start_run", start_run)
    monkeypatch.setattr(orch.p, "ensure_detached_worktree", lambda name: tmp_path)
    return orch, requests


def commit_all(sdt: ModuleType, repo: Path, message: str) -> None:
    sdt.git("add", "-A", cwd=repo)
    sdt.git("commit", "-q", "-m", message, cwd=repo)


def answer_triage(sdt: ModuleType, orch: Any, request: dict[str, Any], decisions: list[dict[str, Any]]) -> None:
    run = SimpleNamespace(role=SimpleNamespace(name="manager"), tag="triage", payload=request)
    orch.on_manager(run, sdt.RunResult(ok=True, payload={"message": "TRIAGE", "items": decisions}))


def triaged_slugs(request: dict[str, Any]) -> list[str]:
    assert request["message"] == "TRIAGE-REQUEST"
    return [i["slug"] for i in request["items"]]


def test_held_items_never_dispatch_and_are_asked_again(
    sdt: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    orch, requests = triage_orchestrator(sdt, tmp_path, monkeypatch, ["P1-a", "P2-b"])
    orch.intake()
    hold = {"action": "hold", "reason": "waits on in-flight work"}
    answer_triage(sdt, orch, requests[-1], [{"slug": "P1-a", **hold}, {"slug": "P2-b", **hold}])
    assert orch.items["P1-a"].held and orch.items["P2-b"].held
    orch.dispatch_ready()
    assert len(requests) == 1, "a held item is never dispatched"

    (orch.p.backlog / "P3-c.md").write_text("# P3-c\n")
    commit_all(sdt, orch.p.root, "chore(backlog): file P3-c")
    orch.intake()
    assert len(requests) == 2 and triaged_slugs(requests[-1]) == ["P1-a", "P2-b", "P3-c"]
    assert requests[-1]["in_flight"] == [], "an item sent for triage is not also in flight"
    answer_triage(sdt, orch, requests[-1], [{"slug": "P1-a", "action": "dispatch"}, {"slug": "P2-b", **hold}])
    assert not orch.items["P1-a"].held and orch.items["P1-a"].stage == "queued"
    assert orch.items["P2-b"].held
    assert sorted(orch.items) == ["P1-a", "P2-b", "P3-c"]


def test_item_moved_back_out_of_blocked_is_triaged_again(
    sdt: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    orch, requests = triage_orchestrator(sdt, tmp_path, monkeypatch, ["P1-a"])
    backlog = orch.p.backlog
    monkeypatch.setattr(orch, "landing_in_flight", lambda: True)
    orch.intake()
    answer_triage(sdt, orch, requests[-1], [{"slug": "P1-a", "action": "block", "reason": "owner call"}])
    assert orch.items["P1-a"].stage == "blocked" and (backlog / "P1-a.md").is_file()
    orch.intake()
    assert len(requests) == 1, "a block still waiting on a landing is not mistaken for an owner's unblock"

    monkeypatch.setattr(orch, "landing_in_flight", lambda: False)
    orch.flush_housekeeping()
    assert (backlog / "blocked" / "P1-a.md").is_file() and not (backlog / "P1-a.md").exists()
    orch.intake()
    assert len(requests) == 1

    sdt.git("mv", str(backlog / "blocked" / "P1-a.md"), str(backlog / "P1-a.md"), cwd=orch.p.root)
    commit_all(sdt, orch.p.root, "chore(backlog): unblock P1-a")
    orch.intake()
    assert len(requests) == 2 and triaged_slugs(requests[-1]) == ["P1-a"]
    answer_triage(sdt, orch, requests[-1], [{"slug": "P1-a", "action": "dispatch"}])
    assert orch.items["P1-a"].stage == "queued" and not orch.items["P1-a"].parked


# ---- invariants


def test_sdt_never_pushes() -> None:
    """The orchestrator lands and files; pushing stays the root instance's alone."""
    source = (ROOT / "bin" / "sdt").read_text()
    assert '"push"' not in source
    assert "git push" not in source


def test_no_bypass_flags() -> None:
    source = (ROOT / "bin" / "sdt").read_text()
    assert "--no-verify" not in source
