from __future__ import annotations

from pathlib import Path
from types import ModuleType

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
    ok = '{"subtype": "success", "result": "final"}'
    assert sdt.extract_final_text(adapter, ok, tmp_path / "none") == "final"
    with pytest.raises(sdt.SdtError):
        sdt.extract_final_text(adapter, '{"subtype": "error_max_turns", "result": "x"}', tmp_path / "none")


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


# ---- invariants


def test_sdt_never_pushes() -> None:
    """The orchestrator lands and files; pushing stays the root instance's alone."""
    source = (ROOT / "bin" / "sdt").read_text()
    assert '"push"' not in source
    assert "git push" not in source


def test_no_bypass_flags() -> None:
    source = (ROOT / "bin" / "sdt").read_text()
    assert "--no-verify" not in source
