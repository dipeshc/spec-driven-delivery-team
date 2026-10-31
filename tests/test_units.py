from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from functools import partial
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
    assert cfg.known_failures == ".delivery-team/known-failures.txt"


def test_config_empty_known_failures_means_the_default(sdt: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[qa]\nknown_failures = ""\n')
    assert sdt.load_config(path).known_failures == ".delivery-team/known-failures.txt"


def test_config_engines_cover_per_role_routes(sdt: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[engine]\ndefault = "a"\n[engine.roles]\ndeveloper = "b"\nreviewer = "a"\nqa = "b"\n')
    assert sdt.load_config(path).engines() == ["a", "b"]


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
    assert "--dangerously-bypass-approvals-and-sandbox" in argv, "confinement is the orchestrator's"
    assert "--sandbox" not in argv
    assert adapter.network
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


def test_shipped_preconditions_are_adapter_fields(sdt: ModuleType) -> None:
    assert sdt.load_adapter("claude", [ROOT / "adapters"]).project_hooks_file == ".claude/settings.json"
    assert sdt.load_adapter("codex", [ROOT / "adapters"]).requires_git_repo
    assert not sdt.load_adapter("gemini", [ROOT / "adapters"]).requires_git_repo
    assert sdt.load_adapter("gemini", [ROOT / "adapters"]).project_hooks_file == ".gemini/settings.json"


def test_tier_override(sdt: ModuleType) -> None:
    adapter = sdt.load_adapter("claude", [ROOT / "adapters"])
    assert adapter.model_for("mid", {}) == "sonnet"
    assert adapter.model_for("mid", {"mid": "custom"}) == "custom"


# ---- doctor


def test_doctor_hooks_file_from_adapter(sdt: ModuleType, tmp_path: Path) -> None:
    project = make_project(
        sdt,
        tmp_path,
        '[engine]\ndefault = "stub"\n[engine.roles]\nreviewer = "plain"\n',
        {"stub": {"extra": 'project_hooks_file = ".stub/settings.json"'}, "plain": {}},
    )
    hooks = project.root / ".stub" / "settings.json"
    hooks.parent.mkdir()
    hooks.write_text('{"permissions": {}}')
    assert not [m for _, m in sdt.doctor_checks(project) if "hooks" in m]
    hooks.write_text('{"hooks": {"PreToolUse": []}}')
    findings = [(lvl, m) for lvl, m in sdt.doctor_checks(project) if "hooks" in m]
    assert findings == [
        ("warn", "engine stub: project .stub/settings.json declares hooks; they run inside every headless role run")
    ], "only the adapter that declares the file reports it"


def test_doctor_git_repo_from_adapter(sdt: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = make_project(
        sdt,
        tmp_path,
        '[engine]\ndefault = "stub"\n[engine.roles]\nreviewer = "plain"\n',
        {"stub": {"extra": "requires_git_repo = true"}, "plain": {}},
    )
    assert not [m for lvl, m in sdt.doctor_checks(project) if lvl == "error"]
    monkeypatch.setattr(sdt, "git_ok", lambda *args, **kwargs: False)
    errors = [m for lvl, m in sdt.doctor_checks(project) if lvl == "error"]
    assert errors == ["engine stub: needs a git repository"]


def test_doctor_checks_every_configured_engine(sdt: ModuleType, tmp_path: Path) -> None:
    project = make_project(
        sdt,
        tmp_path,
        '[engine]\ndefault = "stub"\n[engine.roles]\ndeveloper = "ghost"\nreviewer = "nope"\n',
        {"stub": {}, "ghost": {"command": "ghost-cli-not-on-path"}},
    )
    errors = [m for lvl, m in sdt.doctor_checks(project) if lvl == "error"]
    assert "engine ghost: 'ghost-cli-not-on-path' is not on PATH" in errors
    assert any("no adapter named 'nope'" in m for m in errors), errors
    project.cfg.engine_default = "ghost"
    assert project.cfg.engines() == ["ghost", "nope"], "an --engine override replaces the default"


def test_doctor_checks_role_vision_against_its_engine(sdt: ModuleType, tmp_path: Path) -> None:
    project = make_project(sdt, tmp_path, '[engine]\ndefault = "stub"\n', {"stub": {}, "seer": {"vision": "true"}})
    findings = [(lvl, m) for lvl, m in sdt.doctor_checks(project) if "vision" in m]
    assert findings == [("warn", "role ui-inspector needs a vision-capable engine; stub is not")], (
        "an owner-run role never blocks a pipeline run"
    )
    project.cfg.engine_roles["ui-inspector"] = "seer"
    assert not [m for _, m in sdt.doctor_checks(project) if "vision" in m]


# ---- role runs


def test_unstartable_engine_is_a_failed_run(sdt: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "ghost.toml").write_text('command = ["ghost-cli-not-on-path"]\n')
    adapter = sdt.load_adapter("ghost", [tmp_path])
    role = sdt.Role(name="developer", tier="mid", vision=False, engines=[], body="BODY\n")
    run = sdt.RoleRun(
        run_id="r1",
        role=role,
        adapter=adapter,
        model="",
        cwd=tmp_path,
        add_dirs=[],
        prompt="PROMPT",
        runs_dir=tmp_path,
        timeout=60,
        stall=60,
        payload={},
    )
    assert run.poll()
    run.kill("interrupted")
    res = run.result()
    assert not res.ok and not res.timed_out
    assert "engine ghost did not start" in res.error and "ghost-cli-not-on-path" in res.error


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


def test_failure_reason_quotes_engine_error_line(sdt: ModuleType) -> None:
    log = "starting up\nError: authentication failed, run `login`\nexiting\n"
    error = sdt.describe_failure(sdt.SdtError("engine stdout holds no JSON object"), 1, log)
    assert error.startswith("engine stdout holds no JSON object; exit code 1")
    assert "Error: authentication failed, run `login`" in error


def test_failure_reason_falls_back_to_last_line(sdt: ModuleType) -> None:
    log = "starting up\n\nshutting down quietly\n\n"
    error = sdt.describe_failure(sdt.SdtError("engine wrote no output file"), 0, log)
    assert error.endswith("shutting down quietly")
    assert len(sdt.first_error_line("Error: " + "x" * 500)) == 200


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
    role = sdt.Role(name="developer", tier="mid", vision=False, engines=[], body="BODY\n")
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
    monkeypatch.setattr(orch, "pooled_worktree", lambda role, ref: tmp_path)
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


def fail_triage(sdt: ModuleType, orch: Any, request: dict[str, Any]) -> None:
    run = SimpleNamespace(role=SimpleNamespace(name="manager"), tag="triage", payload=request)
    orch.on_manager(run, sdt.RunResult(ok=False, error="engine exited 1"))


def test_failed_triage_of_held_items_retries_then_blocks(
    sdt: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    orch, requests = triage_orchestrator(sdt, tmp_path, monkeypatch, ["P1-a", "P2-b"])
    hold = {"action": "hold", "reason": "waits on in-flight work"}
    orch.intake()
    fail_triage(sdt, orch, requests[-1])
    orch.intake()
    answer_triage(sdt, orch, requests[-1], [{"slug": "P1-a", **hold}, {"slug": "P2-b", **hold}])
    assert orch.triage_failures == {}, "a triage that settles its items resets their bound"

    (orch.p.backlog / "P3-c.md").write_text("# P3-c\n")
    commit_all(sdt, orch.p.root, "chore(backlog): file P3-c")
    for _ in range(orch.cfg.adopt_attempts):
        orch.intake()
        assert triaged_slugs(requests[-1]) == ["P1-a", "P2-b", "P3-c"]
        fail_triage(sdt, orch, requests[-1])
        assert orch.retriage
        assert orch.items["P1-a"].held and orch.items["P2-b"].held and "P3-c" not in orch.items
        sent = len(requests)
        orch.dispatch_ready()
        assert len(requests) == sent, "a failed triage dispatches nothing"

    orch.intake()
    fail_triage(sdt, orch, requests[-1])
    assert not orch.retriage and orch.triage_failures == {}
    assert sorted(orch.items) == ["P1-a", "P2-b", "P3-c"]
    reason = f"triage failed after {orch.cfg.adopt_attempts + 1} attempt(s): engine exited 1"
    for slug in ("P1-a", "P2-b", "P3-c"):
        assert orch.items[slug].stage == "blocked" and not orch.items[slug].held
        assert reason in (orch.p.backlog / "blocked" / f"{slug}.md").read_text()
        assert not (orch.p.backlog / f"{slug}.md").exists()


# ---- QA gate


def gate_orchestrator(
    sdt: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    config: str = '[gate]\nfull = ["test ! -e red.txt"]\n[qa]\nknown_failures = "known-failures.txt"\n',
    gitignore: str = ".delivery-team/*\n!.delivery-team/config.toml\n",
) -> tuple[Any, list[Any]]:
    """An orchestrator whose full gate fails once `red.txt` exists; its QA dispatches are recorded, never spawned."""
    repo = tmp_path / "repo"
    (repo / ".delivery-team").mkdir(parents=True)
    (repo / ".delivery-team" / "config.toml").write_text(config)
    (repo / ".gitignore").write_text(gitignore)
    sdt.git("init", "-q", "-b", "main", cwd=repo)
    for key, value in (("user.email", "t@example.com"), ("user.name", "Test"), ("commit.gpgsign", "false")):
        sdt.git("config", key, value, cwd=repo)
    commit_all(sdt, repo, "chore: seed")
    orch = sdt.Orchestrator(sdt.Project(repo), engine=None, watch=False, label="t", args_text="")
    orch.p.ensure_dirs()
    dispatched: list[Any] = []
    monkeypatch.setattr(orch.p, "start_run", lambda role_name, payload, **kw: payload)
    monkeypatch.setattr(orch, "start", dispatched.append)
    return orch, dispatched


def land_outside(sdt: ModuleType, repo: Path, name: str) -> str:
    """A direct-lane commit on the default branch, made behind the orchestrator's back."""
    (repo / name).write_text(name + "\n")
    commit_all(sdt, repo, f"feat: add {name}")
    return str(sdt.git("rev-parse", "main", cwd=repo))


def record_known_failure(orch: Any) -> None:
    orch.p.record_known_failures(["no-such-output"], "test")


def gated(orch: Any) -> set[str]:
    return {log.stem.removeprefix("qa-gate-") for log in orch.p.runs_dir.glob("qa-gate-*.log")}


def until_gated(orch: Any, step: Callable[[], None]) -> None:
    """Run `step` until no full gate is running: the gate runs in the background and a later step applies its verdict."""
    deadline = time.monotonic() + 30
    step()
    while orch.gate is not None:
        assert time.monotonic() < deadline, "the full gate never finished"
        time.sleep(0.02)
        step()


def test_outside_tip_is_gated_and_housekeeping_is_not(
    sdt: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    orch, dispatched = gate_orchestrator(sdt, tmp_path, monkeypatch)
    repo = orch.p.root
    orch.tick()
    orch.housekeep("record known failures", partial(record_known_failure, orch))
    orch.tick()
    assert gated(orch) == set(), "neither the opening tip nor the run's own housekeeping is gated"

    green = land_outside(sdt, repo, "plain.txt")
    until_gated(orch, orch.tick)
    assert orch.qa_green_tip == green

    outside = land_outside(sdt, repo, "outside.txt")
    orch.housekeep("record known failures", partial(record_known_failure, orch))
    until_gated(orch, orch.tick)
    assert orch.qa_green_tip == outside, "a housekeeping commit stacked on an outside tip does not hide it"
    assert gated(orch) == {green[:8], outside[:8]}

    red = land_outside(sdt, repo, "red.txt")
    until_gated(orch, orch.tick)
    assert [payload["message"] for payload in dispatched] == ["REGRESSION-REQUEST"]
    assert dispatched[0]["tip"] == red
    assert dispatched[0]["last_green_tip"] == outside


def test_outside_tip_racing_housekeeping_is_gated(
    sdt: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    orch, _ = gate_orchestrator(sdt, tmp_path, monkeypatch)
    repo = orch.p.root
    orch.tick()

    def outside_then_housekeeping() -> None:
        land_outside(sdt, repo, "before.txt")
        record_known_failure(orch)

    orch.housekeep("record known failures", outside_then_housekeeping)
    stacked = str(sdt.git("rev-parse", "main", cwd=repo))
    until_gated(orch, orch.tick)
    assert orch.qa_green_tip == stacked, "an outside commit beneath the housekeeping commit is gated through it"

    def housekeeping_then_outside() -> None:
        record_known_failure(orch)
        land_outside(sdt, repo, "after.txt")

    orch.housekeep("record known failures", housekeeping_then_outside)
    on_top = str(sdt.git("rev-parse", "main", cwd=repo))
    until_gated(orch, orch.tick)
    assert orch.qa_green_tip == on_top, "an outside commit on top of the housekeeping commit is gated"


@pytest.mark.parametrize(
    ("output", "code", "new"),
    [
        (["FAILED tests/a.py::test_known_flaky - ConnectionError", "1 failed, 3 passed in 0.1s"], 1, False),
        (["\x1b[31mFAILED\x1b[0m tests/a.py::\x1b[1mtest_known_flaky\x1b[0m", "\x1b[31m1 failed\x1b[0m"], 1, False),
        (["FAILED tests/a.py::test_known_flaky", "FAILED tests/b.py::test_brand_new_regression"], 1, True),
        (["collecting tests/a.py::test_known_flaky", "Segmentation fault"], 1, True),
        (["tests/a.py::test_known_flaky FAILED"], 137, True),
        ([" FAIL  src/net.test.js", "  ● api › fetches the feed", "Tests: 1 failed, 2 passed"], 1, False),
        ([" FAIL  src/net.test.js", "  ● api › fetches the feed", "  ● api › parses the feed"], 1, True),
    ],
    ids=[
        "only-known",
        "coloured-only-known",
        "known-and-new",
        "crash-naming-a-known-test",
        "killed-after-a-known-failure",
        "jest-only-known",
        "jest-known-and-new-in-one-file",
    ],
)
def test_full_gate_filters_each_failure_not_each_command(
    sdt: ModuleType, tmp_path: Path, output: list[str], code: int, new: bool
) -> None:
    project = make_project(sdt, tmp_path)
    known = "# 2026-10-31 qa: flaky network\ntest_known_flaky\n# 2026-10-31 qa: feed host unreachable\nsrc/net.test.js\napi › fetches the feed\n"
    (project.root / project.cfg.known_failures).write_text(known)
    cmd = "; ".join(f"echo '{line}'" for line in output) + f"; exit {code}"
    project.cfg.gate_full = ["true", cmd]
    gate = project.start_full_gate("tip", project.root, project.runs_dir / "gate.log")
    deadline = time.monotonic() + 30
    while not gate.poll():
        assert time.monotonic() < deadline, "the full gate never finished"
        time.sleep(0.02)
    assert gate.failures == ([cmd] if new else [])
    assert ("(new failure: " if new else "(known failure)") in gate.log_path.read_text()


def test_full_gate_runs_in_the_background(sdt: ModuleType, tmp_path: Path) -> None:
    project = make_project(sdt, tmp_path, '[gate]\nfull = ["sleep 3"]\n[limits.liveness]\npoll_seconds = 1\n')
    o = sdt.Orchestrator(project, engine=None, watch=False, label="t", args_text="")
    polls: list[int] = []

    def poll() -> bool:
        polls.append(1)
        return False

    role, adapter = SimpleNamespace(name="developer"), SimpleNamespace(name="fake")
    developer = SimpleNamespace(role=role, tag="P2-a", adapter=adapter, model="", cwd=tmp_path, poll=poll)
    developer.alive_for, developer.last_signal = int, 0
    o.start(developer)
    o.write_ledger()
    state = project.board_dir / "state.json"
    before = json.loads(state.read_text())["generatedAt"]
    project.ensure_detached_worktree("qa")
    tip = commit(sdt, project.root, "landed")
    o.qa_pending_tips.append(tip)

    started = time.monotonic()
    o.run_qa_gate()
    assert time.monotonic() - started < 2, "run_qa_gate waited for the gate command"
    assert o.gate is not None and o.gate.tip == tip and o.qa_green_tip != tip
    assert o.ports_held(), "a running gate holds the exclusive-resource slot"
    later = commit(sdt, project.root, "landed-later")
    o.qa_pending_tips.append(later)
    o.run_qa_gate()
    assert o.gate.tip == tip and o.qa_pending_tips == [later], "one gate at a time"

    # generatedAt has one-second resolution.
    time.sleep(o.cfg.poll_seconds + 0.1)
    o.tick()
    assert polls, "a tick during the gate polls the role runs"
    assert json.loads(state.read_text())["generatedAt"] > before, "a tick during the gate rewrites the ledger"
    assert not o.drained()

    deadline = time.monotonic() + 30
    while o.qa_green_tip != tip:
        assert time.monotonic() < deadline, "the gate's verdict was never applied"
        time.sleep(0.05)
        o.tick()
    assert o.gate is not None and o.gate.tip == later, "the queued tip is gated next"
    o.gate.kill()


@pytest.mark.parametrize("tracked", [True, False], ids=["tracked", "git-ignored"])
def test_environment_ruling_is_recorded_without_a_known_failures_key(
    sdt: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tracked: bool
) -> None:
    config = """[gate]\nfull = ['test ! -e red.txt || { echo "FAILED tests/env.py::test_needs_gpu"; exit 1; }']\n"""
    ignore = ".delivery-team/*\n!.delivery-team/config.toml\n" + (
        "!.delivery-team/known-failures.txt\n" if tracked else ""
    )
    orch, dispatched = gate_orchestrator(sdt, tmp_path, monkeypatch, config=config, gitignore=ignore)
    repo = orch.p.root
    orch.tick()
    red = land_outside(sdt, repo, "red.txt")
    until_gated(orch, orch.tick)
    (request,) = dispatched
    ruling = {"message": "ENVIRONMENT", "patterns": ["test_needs_gpu"], "reason": "no GPU on this machine"}
    orch.on_qa(SimpleNamespace(payload=request, tag=red[:8]), sdt.RunResult(True, payload=ruling))

    known = repo / ".delivery-team" / "known-failures.txt"
    assert "test_needs_gpu" in known.read_text().splitlines()
    assert bool(sdt.git("ls-files", "--", str(known), cwd=repo)) == tracked
    landed = "recorded in .delivery-team/known-failures.txt"
    if not tracked:
        landed += ", which git ignores, so it is not committed"
    assert f"{red[:8]}: {landed}" in [e["text"] for e in orch.events if e["kind"] == "qa-environment"]

    again = land_outside(sdt, repo, "again.txt")
    until_gated(orch, orch.tick)
    assert len(dispatched) == 1, "the recorded failure paged QA again"
    assert orch.qa_green_tip == again
    assert "(known failure)" in (orch.p.runs_dir / f"qa-gate-{again[:8]}.log").read_text()


def test_qa_runs_read_a_copy_of_the_gate_log_inside_their_own_tree(
    sdt: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    orch, dispatched = gate_orchestrator(sdt, tmp_path, monkeypatch)
    monkeypatch.delattr(orch.p, "start_run")
    monkeypatch.setattr(sdt, "RoleRun", lambda **kw: SimpleNamespace(**kw))
    orch.tick()
    red = land_outside(sdt, orch.p.root, "red.txt")
    until_gated(orch, orch.tick)
    original = orch.p.gate_log(red)

    def reads_the_log_inside_its_tree(run: Any) -> None:
        assert run.add_dirs == [orch.p.git_common], "a QA run is granted the git common directory and nothing else"
        log_path = Path(run.payload["log_path"])
        assert log_path.is_relative_to(run.cwd)
        assert log_path.read_text() == original.read_text()

    (first,) = dispatched
    reads_the_log_inside_its_tree(first)
    Path(first.payload["log_path"]).write_text("stale\n")
    orch.on_qa(first, sdt.RunResult(ok=False, error="engine exited 1"))
    (_, retry) = dispatched
    reads_the_log_inside_its_tree(retry)
    assert "test ! -e red.txt" in original.read_text(), "the runs/ original is kept for the owner"


# ---- role worktrees and routing


STUB_ADAPTER = """
name = "{name}"
tested = true
vision = {vision}
command = ["{command}"]
{extra}
[tiers]
frontier = "f"
mid = "m"
small = "s"
"""


def make_project(
    sdt: ModuleType, tmp_path: Path, config: str = "", adapters: dict[str, dict[str, str]] | None = None
) -> Any:
    """A Project on a fresh one-commit repository, its runtime dirs created, a profile and stub `adapters` in place."""
    repo = tmp_path / "repo"
    (repo / ".delivery-team" / "adapters").mkdir(parents=True)
    (repo / ".delivery-team" / "config.toml").write_text(config)
    (repo / ".delivery-team" / "profile.md").write_text("# Profile\n")
    for name, fields in (adapters or {}).items():
        values = {"name": name, "vision": "false", "command": "python3", "extra": "", **fields}
        (repo / ".delivery-team" / "adapters" / f"{name}.toml").write_text(STUB_ADAPTER.format(**values))
    (repo / ".gitignore").write_text(".delivery-team/*\n!.delivery-team/config.toml\n")
    sdt.git("init", "-q", "-b", "main", cwd=repo)
    sdt.git("config", "user.email", "t@example.com", cwd=repo)
    sdt.git("config", "user.name", "Test", cwd=repo)
    sdt.git("config", "commit.gpgsign", "false", cwd=repo)
    commit(sdt, repo, "seed")
    project = sdt.Project(repo)
    project.ensure_dirs()
    return project


def commit(sdt: ModuleType, repo: Path, name: str, text: str = "") -> str:
    (repo / f"{name}.txt").write_text(text or name)
    commit_all(sdt, repo, name)
    return head(sdt, repo)


def head(sdt: ModuleType, path: Path) -> str:
    return str(sdt.git("rev-parse", "HEAD", cwd=path))


@pytest.fixture
def orch(sdt: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """An orchestrator whose role runs are recorded in `orch.started`, never spawned."""
    project = make_project(sdt, tmp_path, "[board]\nenabled = false\n")
    o = sdt.Orchestrator(project, engine=None, watch=False, label="t", args_text="")
    o.started = []

    def start_run(role_name: str, payload: dict[str, Any], *, cwd: Path, tag: str = "", **_: Any) -> Any:
        run = SimpleNamespace(role=SimpleNamespace(name=role_name), cwd=cwd, tag=tag, payload=payload, id="", model="")
        o.started.append(run)
        return run

    monkeypatch.setattr(project, "start_run", start_run)
    return o


def review_item(sdt: ModuleType, o: Any, slug: str) -> Any:
    sdt.git("branch", f"item/{slug}", cwd=o.p.root)
    it = sdt.Item(slug=slug, slugs=[slug], priority="P2", paths=[], texts={slug: slug})
    it.branch = f"item/{slug}"
    it.enter("review")
    o.items[slug] = it
    return it


def test_consistency_never_works_in_a_live_qa_tree(sdt: ModuleType, orch: Any) -> None:
    qa = orch.p.ensure_detached_worktree("qa")
    (qa / "bisect-in-progress").write_text("")
    orch.start(SimpleNamespace(role=SimpleNamespace(name="qa"), cwd=qa, tag="t"))
    orch.consistency_due = True
    orch.run_consistency()
    (audit,) = orch.started
    assert audit.role.name == "consistency-check"
    assert audit.cwd != qa
    assert audit.cwd == orch.p.worktree_path("consistency-check")
    assert (qa / "bisect-in-progress").exists(), "the live QA run's tree was reset"


def test_gate_leaves_a_live_consistency_tree_alone(sdt: ModuleType, orch: Any) -> None:
    orch.consistency_due = True
    orch.run_consistency()
    (audit,) = orch.started
    audited = head(sdt, audit.cwd)
    (audit.cwd / "audit-notes").write_text("")
    tip = commit(sdt, orch.p.root, "landed")
    orch.cfg.gate_full = ["true"]
    orch.qa_pending_tips.append(tip)
    until_gated(orch, orch.run_qa_gate)
    assert orch.qa_green_tip == tip
    assert head(sdt, orch.p.worktree_path("qa")) == tip
    assert head(sdt, audit.cwd) == audited
    assert (audit.cwd / "audit-notes").exists(), "the gate reset the live consistency tree"


def test_role_worktree_refuses_a_tree_a_live_run_works_in(sdt: ModuleType, orch: Any) -> None:
    wt = orch.role_worktree("merge-clerk", "main")
    (wt / "mid-rebase").write_text("")
    orch.start(SimpleNamespace(role=SimpleNamespace(name="merge-clerk"), cwd=wt, tag="t"))
    assert orch.role_worktree("merge-clerk", "main") is None
    assert (wt / "mid-rebase").exists()


def test_failed_run_redispatch_waits_for_a_held_tree(sdt: ModuleType, orch: Any) -> None:
    tip = head(sdt, orch.p.root)
    orch.p.gate_log(tip).write_text("gate log\n")
    qa = orch.p.ensure_detached_worktree("qa")
    holder = SimpleNamespace(role=SimpleNamespace(name="qa"), cwd=qa, tag="other")
    orch.start(holder)
    failed = SimpleNamespace(role=SimpleNamespace(name="qa"), tag=tip[:8], payload={"tip": tip, "failed_commands": []})
    orch.on_qa(failed, sdt.RunResult(ok=False, error="engine exited 1"))
    assert orch.started == [] and orch.qa_failures == {tip: 1}
    orch.dispatch_deferred()
    assert orch.started == []
    orch.runs.remove(holder)
    assert not orch.drained(), "a deferred re-dispatch was dropped"
    orch.dispatch_deferred()
    (retry,) = orch.started
    assert retry.cwd == qa and orch.deferred_runs == []
    assert retry.payload == {**failed.payload, "log_path": str(qa / "qa-gate.log")}


def test_sweep_map_that_keeps_failing_ends_the_sweep(sdt: ModuleType, tmp_path: Path) -> None:
    project = make_project(sdt, tmp_path, "[limits.liveness]\nadopt_attempts = 1\n")
    sweep = sdt.Sweep(project, engine=None)
    run = SimpleNamespace(tag="sweep-map", payload=sweep.payload("map"))
    # A result of the wrong shape is a failed run, as an engine failure is.
    wrong = sdt.RunResult(ok=True, payload={"message": "FINDINGS", "items": []})
    sweep.on_done(run, wrong)
    assert sweep.queue == [("sweep-map", run.payload)] and sweep.attempts == {"sweep-map": 1}
    with pytest.raises(sdt.SdtError, match=r"after 2 attempt\(s\): expected INVENTORY"):
        sweep.on_done(run, wrong)


def test_manager_starts_at_the_moved_tip(sdt: ModuleType, orch: Any) -> None:
    backlog = orch.p.backlog
    backlog.mkdir(parents=True)
    (backlog / "P1-x.md").write_text("# x\n")
    first_tip = commit(sdt, orch.p.root, "file-item")
    orch.intake()
    (triage,) = orch.started
    assert head(sdt, triage.cwd) == first_tip
    (triage.cwd / "left-behind").write_text("")
    orch.runs.remove(triage)
    orch.manager_busy = False
    moved_tip = commit(sdt, orch.p.root, "moved")
    it = sdt.Item(slug="P1-x", slugs=["P1-x"], priority="P1", paths=["docs/backlog/P1-x.md"], texts={"P1-x": ""})
    orch.ask_manager(it, "BLOCKED", {})
    decision = orch.started[-1]
    assert decision.cwd == triage.cwd
    assert head(sdt, decision.cwd) == moved_tip
    assert not (decision.cwd / "left-behind").exists(), "the previous run's leftovers survived the reset"


def test_concurrent_runs_of_one_role_get_their_own_trees(sdt: ModuleType, orch: Any) -> None:
    fresh = {s: sdt.BacklogItem(s, orch.p.backlog / f"{s}.md", "P2", s) for s in ("P2-a", "P2-b")}
    orch.apply_triage({"items": [{"slug": s, "action": "research", "reason": "q"} for s in fresh]}, fresh)
    assert [r.cwd.name for r in orch.started] == ["researcher-1", "researcher-2"]
    orch.ask_manager(orch.items["P2-a"], "BLOCKED", {})
    orch.ask_manager(orch.items["P2-b"], "BLOCKED", {})
    assert [r.cwd.name for r in orch.started[2:]] == ["manager-1", "manager-2"]


def test_research_retired_regression_is_closed_but_never_done(
    sdt: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slug = "P0-regression-gate"
    orch, _ = triage_orchestrator(sdt, tmp_path, monkeypatch, [slug])
    orch.open_regressions["gate"] = slug
    path = orch.p.backlog / f"{slug}.md"
    fresh = {slug: sdt.BacklogItem(slug, path, "P0", path.read_text())}
    orch.apply_triage({"items": [{"slug": slug, "action": "research", "reason": "q"}]}, fresh)
    (research,) = orch.runs
    orch.runs.remove(research)
    orch.on_researcher(research, sdt.RunResult(True, payload={"message": "NO-ITEM", "finding": "f", "why": "w"}))
    assert not path.exists()
    assert orch.items[slug].stage != "done", "only a merging commit marks an item done"
    assert not orch.regression_open("gate"), "the next red with the same failures must reach QA again"
    assert orch.drained(), "a retired item held the run open"
    monkeypatch.setattr(orch.cfg, "board_enabled", True)
    orch.write_ledger()
    state = json.loads((orch.p.board_dir / "state.json").read_text())
    assert state["items"] == [], "a retired item is on the board"


def test_research_refiled_under_its_own_filename_survives_and_is_retriaged(
    sdt: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slug = "P2-rough-ask"
    orch, _ = triage_orchestrator(sdt, tmp_path, monkeypatch, [slug])
    path = orch.p.backlog / f"{slug}.md"
    fresh = {slug: sdt.BacklogItem(slug, path, "P2", path.read_text())}
    orch.apply_triage({"items": [{"slug": slug, "action": "research", "reason": "q"}]}, fresh)
    (research,) = orch.runs
    orch.runs.remove(research)
    filed = {"message": "FILED", "items": [{"filename": f"{slug}.md", "body": "# Sharpened\n\nResearched text."}]}
    orch.on_researcher(research, sdt.RunResult(True, payload=filed))
    orch.flush_housekeeping()
    assert path.read_text() == "# Sharpened\n\nResearched text.\n"
    subjects = sdt.git("log", "--no-show-signature", "--format=%s", cwd=orch.p.root).splitlines()
    assert not any(s.startswith("chore(backlog): retire") for s in subjects), "a rewritten file was retired"
    assert slug not in orch.items, "the slug stays known, so the run would never triage the rewrite"
    orch.runs.clear()
    orch.manager_busy = False
    orch.intake()
    (triage,) = orch.runs
    (sent,) = triage.payload["items"]
    assert sent["slug"] == slug and "Researched text." in sent["text"]


def test_review_batches_run_concurrently_up_to_reviewers(sdt: ModuleType, orch: Any) -> None:
    orch.cfg.reviewers = 2
    for slug in ("P2-a", "P2-b", "P2-c"):
        review_item(sdt, orch, slug)
        orch.review_batch.append(slug)
        orch.dispatch_reviews()
    assert [r.cwd.name for r in orch.started] == ["reviewer-1", "reviewer-2"]
    assert [orch.items[s].agent for s in ("P2-a", "P2-b")] == ["reviewer-1", "reviewer-2"]
    assert orch.review_batch == ["P2-c"], "a third batch waits for a free reviewer"


def test_only_changes_requested_counts_as_a_review_round(sdt: ModuleType, orch: Any) -> None:
    orch.cfg.review_rounds = 1
    it = review_item(sdt, orch, "P2-a")
    run = SimpleNamespace(tag="P2-a", payload={"requests": [{"items": ["P2-a"]}]})

    def verdict(message: str) -> Any:
        return sdt.RunResult(True, payload={"message": message, "items": ["P2-a"], "branch": it.branch})

    for _ in range(3):
        it.enter("review")
        orch.on_reviewer(run, verdict("REBASE-REQUIRED"))
        assert (it.rounds, it.stage, it.pending["message"]) == (0, "queued", "REBASE")
    orch.on_merge_clerk(run, verdict("REBASE-REQUIRED"))
    assert (it.rounds, it.pending["message"]) == (0, "REBASE")
    it.enter("review")
    orch.on_reviewer(run, verdict("CHANGES-REQUESTED"))
    assert (it.rounds, it.stage, it.pending["message"], it.deciding) == (1, "queued", "FEEDBACK", False)
    it.enter("review")
    orch.on_reviewer(run, verdict("CHANGES-REQUESTED"))
    assert it.deciding and orch.started[-1].payload["event"] == "REVIEW-ROUNDS-EXCEEDED"


def test_install_without_lockfile_runs_only_at_creation(sdt: ModuleType, tmp_path: Path) -> None:
    installs = tmp_path / "installs"
    project = make_project(sdt, tmp_path, f"[repo]\ninstall = 'echo ran >> {installs}'\n")
    wt = project.ensure_detached_worktree("qa")
    tip = commit(sdt, project.root, "moved")
    project.reset_detached(wt, tip)
    project.reset_detached(wt, "main")
    assert installs.read_text().splitlines() == ["ran"]


def test_install_reruns_when_the_lockfile_changes(sdt: ModuleType, tmp_path: Path) -> None:
    installs = tmp_path / "installs"
    project = make_project(sdt, tmp_path, f"[repo]\ninstall = 'echo ran >> {installs}'\nlockfile = 'deps.txt'\n")
    commit(sdt, project.root, "deps", "v1")
    wt = project.ensure_detached_worktree("qa")
    project.reset_detached(wt, "main")
    assert installs.read_text().splitlines() == ["ran"]
    commit(sdt, project.root, "deps", "v2")
    project.reset_detached(wt, "main")
    assert installs.read_text().splitlines() == ["ran", "ran"]


def test_ledger_last_signal_is_the_last_log_growth(
    sdt: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    orch, _ = triage_orchestrator(sdt, tmp_path, monkeypatch, [])
    monkeypatch.setattr(orch.cfg, "board_enabled", True)
    started = sdt.now() - 300
    role = SimpleNamespace(name="developer")
    adapter = SimpleNamespace(name="fake")
    silent = SimpleNamespace(role=role, tag="a", adapter=adapter, model="", alive_for=lambda: 300, last_signal=started)
    orch.runs = [silent]
    orch.write_ledger()
    state = json.loads((orch.p.board_dir / "state.json").read_text())
    rows = {a["role"]: a for a in state["agents"]}
    assert rows["developer a"]["lastSignalAt"] == started
    assert rows["developer a"]["lastSignalAt"] < state["generatedAt"]
    assert "lastSignalAt" not in rows["QA"], "an idle QA row carries no signal"


# ---- invariants


def test_sdt_never_pushes() -> None:
    """The orchestrator lands and files; pushing stays the root instance's alone."""
    source = (ROOT / "bin" / "sdt").read_text()
    assert '"push"' not in source
    assert "git push" not in source


def test_no_bypass_flags() -> None:
    source = (ROOT / "bin" / "sdt").read_text()
    assert "--no-verify" not in source


def test_run_id_stays_short_for_long_tags(sdt: ModuleType) -> None:
    """A review batch of many slugs must not produce a run id longer than a filename allows."""
    source = (ROOT / "bin" / "sdt").read_text()
    assert "short_tag" in source
    tag = "+".join(f"P2-some-fairly-long-item-slug-number-{i}" for i in range(8))
    short = tag if len(tag) <= 60 else tag[:48] + "-" + __import__("hashlib").sha256(tag.encode()).hexdigest()[:8]
    assert len(short) < 64


def test_board_dir_is_fixed_whatever_the_config_says(sdt: ModuleType, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".delivery-team").mkdir(parents=True)
    (repo / ".delivery-team" / "config.toml").write_text('[board]\ndir = "elsewhere"\n')
    sdt.git("init", "-q", "-b", "main", cwd=repo)
    project = sdt.Project(repo, [ROOT / "tests" / "adapters"])
    assert project.board_dir == project.root / ".delivery-team" / "progress"


# ---- statusline script

STATUSLINE = ROOT / "extras" / "claude" / "skills" / "statusline" / "statusline.sh"


def ledger_orchestrator(sdt: ModuleType, tmp_path: Path) -> Any:
    """An orchestrator over a fresh repo with the board on and items whose history spans several stages."""
    project = make_project(sdt, tmp_path)
    orch = sdt.Orchestrator(project, engine=None, watch=False, label="t", args_text="")
    path: list[tuple[str, list[str]]] = [
        ("P1-done-one", ["implementing", "review", "landing", "done"]),
        ("P2-done-two", ["implementing", "review", "landing", "done"]),
        ("P2-in-review", ["implementing", "review"]),
        ("P3-implementing", ["implementing"]),
        ("P3-blocked", ["implementing", "review", "blocked"]),
        ("P3-queued", []),
    ]
    for slug, stages in path:
        it = sdt.Item(slug=slug, slugs=[slug], priority=slug[:2], paths=[], texts={slug: slug})
        it.agent, it.model = "developer", "m1"
        it.note = "needs [owner] input" if slug == "P3-blocked" else ""
        it.checks = [{"name": "lint", "stage": "review", "result": "pass"}]
        for stage in stages:
            it.enter(stage, 'said "stage": "landing" {x}')
        orch.items[slug] = it
    return orch


def render(project_dir: Path) -> list[str]:
    stdin = json.dumps({"workspace": {"project_dir": str(project_dir)}})
    out = subprocess.run(["sh", str(STATUSLINE)], input=stdin, capture_output=True, text=True, check=True).stdout
    return out.splitlines()


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
@pytest.mark.parametrize("twin", ["state.json", "state.js"])
def test_counts_and_detail_come_from_items_not_their_history(sdt: ModuleType, tmp_path: Path, twin: str) -> None:
    orch = ledger_orchestrator(sdt, tmp_path)
    orch.write_ledger()
    board = orch.p.board_dir
    if twin == "state.js":
        (board / "state.json").unlink()
    elif (board / "state.js").exists():
        (board / "state.js").unlink()

    lines = render(orch.p.root)

    assert len(lines) == 2
    assert re.search(r"team 2/6 ", lines[0])
    assert "impl:1 review:1 land:0 blocked:1" in lines[0]
    assert "P2-in-review" in lines[1]
    assert "blocked P3-blocked" in lines[1]
    assert "needs [owner] input" in lines[1]


def test_merge_clerk_failed_retry_returns_to_the_clerk(sdt: ModuleType, orch: Any) -> None:
    it = review_item(sdt, orch, "P2-a")
    it.head = "abc"
    it.enter("landing")
    orch.cfg.adopt_attempts = 0
    clerk = SimpleNamespace(tag="P2-a", payload={})
    orch.on_merge_clerk(clerk, sdt.RunResult(ok=False, error="timeout"))
    (ask,) = orch.started
    assert ask.role.name == "manager" and ask.payload["event"] == "MERGE-CLERK-FAILED"
    orch.runs.remove(ask)
    orch.manager_busy = False
    decision = sdt.RunResult(True, payload={"action": "retry", "reason": "transient"})
    orch.on_manager(ask, decision)
    assert it.stage == "landing" and not it.pending
    assert (it.head, it.branch) == ("abc", "item/P2-a")
    orch.dispatch_landing()
    assert [r.role.name for r in orch.started] == ["manager", "merge-clerk"]
