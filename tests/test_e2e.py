"""End-to-end run of the orchestrator on a scratch repository with the stub engine."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SDT = ROOT / "bin" / "sdt"

CONFIG = """
[repo]
default_branch = "main"
[backlog]
dir = "docs/backlog"
[gate]
scoped = ["true"]
full = ["sh ./gate.sh"]
[engine]
default = "fake"
[limits]
max_parallel_developers = 2
review_rounds = 2
[limits.timeouts]
developer = 600
[limits.liveness]
poll_seconds = 1
stall_seconds = 4
adopt_attempts = 1
[qa]
consistency_every = 2
"""

GATE = "#!/bin/sh\n# red once an item whose slug contains 'red' has landed\nls src/*red*.txt >/dev/null 2>&1 && exit 1\nexit 0\n"


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=True).stdout.strip()


def make_repo(tmp_path: Path, slugs: list[str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git("init", "-q", "-b", "main", cwd=repo)
    git("config", "user.email", "t@example.com", cwd=repo)
    git("config", "user.name", "Test", cwd=repo)
    git("config", "commit.gpgsign", "false", cwd=repo)
    (repo / "docs" / "backlog").mkdir(parents=True)
    (repo / "src").mkdir()
    (repo / "src" / ".keep").write_text("")
    (repo / "gate.sh").write_text(GATE)
    (repo / ".delivery-team").mkdir()
    (repo / ".delivery-team" / "config.toml").write_text(CONFIG)
    (repo / ".delivery-team" / "profile.md").write_text("# Profile\n\nDocs are spec: no.\n")
    (repo / ".gitignore").write_text(".delivery-team/*\n!.delivery-team/config.toml\n!.delivery-team/profile.md\n")
    for slug in slugs:
        (repo / "docs" / "backlog" / f"{slug}.md").write_text(f"# {slug}\n\nAppend 'done' to src/{slug}.txt.\n")
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", "chore: seed", cwd=repo)
    return repo


def run_sdt(repo: Path, *args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, FAKE_STATE_DIR=str(repo.parent / "fake-state"), FAKE_STALL_SECONDS="8")
    env.update(env_extra or {})
    return subprocess.run(
        ["python3", str(SDT), *args, "--adapter-dir", str(ROOT / "tests" / "adapters")],
        cwd=repo,
        text=True,
        capture_output=True,
        env=env,
        timeout=300,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return make_repo(
        tmp_path, ["P1-plain", "P2-twice", "P3-group-a", "P3-group-b", "P2-block-me", "P1-red-item", "P2-dev-blocks"]
    )


def test_doctor_ready(repo: Path) -> None:
    proc = run_sdt(repo, "doctor")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ready" in proc.stdout


def test_full_pipeline(repo: Path) -> None:
    proc = run_sdt(repo, "run", "--label", "e2e")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    final = json.loads(proc.stdout.strip().splitlines()[-1])
    assert final["message"] == "DRAINED"
    assert final["landed"] == 5, proc.stdout  # plain, twice, group pair (one commit), red, the regression fix
    assert set(final["blocked"]) == {"P2-block-me", "P2-dev-blocks"}

    # linear history: one commit per landed item/group plus housekeeping commits
    subjects = git("log", "--no-show-signature", "--format=%s", "main", cwd=repo).splitlines()
    assert all(not s.startswith("Merge") for s in subjects)
    feats = [s for s in subjects if s.startswith("feat(")]
    assert len(feats) == 5
    assert any("P3-group-a, P3-group-b" in s for s in feats), feats
    assert git("rev-list", "--count", "--merges", "main", cwd=repo) == "0"

    # item files: landed ones deleted, blocked ones moved with the reason appended
    backlog = repo / "docs" / "backlog"
    assert sorted(p.name for p in backlog.glob("*.md")) == []
    blocked = sorted(p.name for p in (backlog / "blocked").glob("*.md"))
    assert blocked == ["P2-block-me.md", "P2-dev-blocks.md"]
    assert "⛔" in (backlog / "blocked" / "P2-block-me.md").read_text()

    # the regression the red item caused was filed from QA's result, then worked and landed
    assert any(s.startswith("feat(P0-regression-") for s in feats), feats
    assert any(s.startswith("chore(backlog): file 1 item(s) — regression") for s in subjects), subjects

    # the ledger follows the charter schema
    state = json.loads((repo / ".delivery-team" / "progress" / "state.json").read_text())
    assert {it["stage"] for it in state["items"]} <= set(
        ["queued", "implementing", "review", "landing", "done", "blocked"]
    )
    assert sum(1 for it in state["items"] if it["stage"] == "done") == 5
    grouped = next(it for it in state["items"] if it["slug"] == "P3-group-a")
    assert grouped["grouped"] == ["P3-group-b"]
    assert (repo / ".delivery-team" / "progress" / "state.js").read_text().startswith("window.TEAM_STATE = ")
    assert (repo / ".delivery-team" / "progress" / "dashboard.html").is_file()

    # worktrees and branches of landed items are gone; a blocked item keeps both on disk
    names = {
        Path(p).name for p in git("worktree", "list", "--porcelain", cwd=repo).splitlines() if p.startswith("worktree ")
    }
    landed = {"P1-plain", "P2-twice", "P3-group-a", "P1-red-item"}
    assert not any(n.removeprefix("dev-") in landed for n in names), names
    assert "dev-P2-dev-blocks" in names
    branches = set(git("branch", "--list", "item/*", "--format=%(refname:short)", cwd=repo).splitlines())
    assert branches == {"item/P2-dev-blocks"}, branches
    assert git("status", "--porcelain", cwd=repo) == ""
    assert git("config", "--get", "rerere.enabled", cwd=repo) == "false"


def test_stalled_developer_is_adopted(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["P2-stall-me"])
    proc = run_sdt(repo, "run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    final = json.loads(proc.stdout.strip().splitlines()[-1])
    assert final["landed"] == 1
    assert "stalled" in proc.stdout and "adopt" in proc.stdout


def test_status_without_run(repo: Path) -> None:
    proc = run_sdt(repo, "status")
    assert proc.returncode == 0
    assert "no run state" in proc.stdout
