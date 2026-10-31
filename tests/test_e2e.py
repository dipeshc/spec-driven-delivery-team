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
reviewers = 2
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

FAULT_GATE = """#!/bin/sh
# red, with a marker QA reads in the log, once an envfault item has landed
ls src/*envfault*.txt >/dev/null 2>&1 && { echo "ERROR ENV-FAULT: flaky network"; exit 1; }
exit 0
"""

KNOWN_FAILURES = "docs/known-failures.txt"

# What the stub emitted across the scenario tests below, and which scenarios have run.
SEEN: set[str] = set()
SCENARIOS_RUN: set[str] = set()
SCENARIOS = {"decision-paths", "hold", "environment-ruling", "qa-blocked", "no-item", "regression", "stub-paths"}

GATE = "#!/bin/sh\n# red once an item whose slug contains 'red' has landed\nls src/*red*.txt >/dev/null 2>&1 && exit 1\nexit 0\n"


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=True).stdout.strip()


def make_repo(tmp_path: Path, slugs: list[str], *, gate: str = "", extra_config: str = "") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git("init", "-q", "-b", "main", cwd=repo)
    git("config", "user.email", "t@example.com", cwd=repo)
    git("config", "user.name", "Test", cwd=repo)
    git("config", "commit.gpgsign", "false", cwd=repo)
    (repo / "docs" / "backlog").mkdir(parents=True)
    (repo / "src").mkdir()
    (repo / "src" / ".keep").write_text("")
    (repo / "gate.sh").write_text(gate or GATE)
    (repo / ".delivery-team").mkdir()
    (repo / ".delivery-team" / "config.toml").write_text(CONFIG + extra_config)
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
    proc = subprocess.run(
        ["python3", str(SDT), *args, "--adapter-dir", str(ROOT / "tests" / "adapters")],
        cwd=repo,
        text=True,
        capture_output=True,
        env=env,
        timeout=300,
    )
    produced = repo.parent / "fake-state" / "produced.log"
    if produced.is_file():
        SEEN.update(produced.read_text().split())
    return proc


def role_runs(repo: Path, role: str) -> list[str]:
    """The run ids of every run of `role`, from the prompts the orchestrator keeps."""
    names = (p.name.removesuffix(".prompt.md") for p in (repo / ".delivery-team" / "runs").glob("*.prompt.md"))
    return sorted(n for n in names if n.split("-", 1)[1].startswith(role + "-"))


def drained(proc: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert proc.returncode == 0, proc.stdout + proc.stderr
    final = json.loads(proc.stdout.strip().splitlines()[-1])
    assert final["message"] == "DRAINED"
    return final


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return make_repo(
        tmp_path, ["P1-plain", "P2-twice", "P3-group-a", "P3-group-b", "P2-block-me", "P1-red-item", "P2-dev-blocks"]
    )


def test_doctor_ready(repo: Path) -> None:
    proc = run_sdt(repo, "doctor")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ready" in proc.stdout


def test_unrunnable_per_role_engine_blocks_preflight(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["P1-plain"])
    config = repo / ".delivery-team" / "config.toml"
    config.write_text(CONFIG.replace('default = "fake"\n', 'default = "fake"\n[engine.roles]\ndeveloper = "ghost"\n'))
    adapters = repo / ".delivery-team" / "adapters"
    adapters.mkdir()
    (adapters / "ghost.toml").write_text('name = "ghost"\ntested = true\ncommand = ["ghost-cli-not-on-path"]\n')

    proc = run_sdt(repo, "doctor")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "engines: fake, ghost" in proc.stdout
    assert "'ghost-cli-not-on-path' is not on PATH" in proc.stdout and "not ready" in proc.stdout

    proc = run_sdt(repo, "run")
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "MUTATIONS-BLOCKED" in proc.stderr and "ghost-cli-not-on-path" in proc.stderr
    assert not list((repo / ".delivery-team" / "runs").glob("*.prompt.md")), "nothing was dispatched"


def test_full_pipeline(repo: Path) -> None:
    proc = run_sdt(repo, "run", "--label", "e2e", env_extra={"FAKE_REVIEW_WAIT_SECONDS": "10"})
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
    assert {"reviewer-1", "reviewer-2"} <= names, "two review batches ran concurrently"
    branches = set(git("branch", "--list", "item/*", "--format=%(refname:short)", cwd=repo).splitlines())
    assert branches == {"item/P2-dev-blocks"}, branches
    assert git("status", "--porcelain", cwd=repo) == ""
    assert git("config", "--get", "rerere.enabled", cwd=repo) == "false"
    assert "REGRESSION" in produced(repo) and "DECISION:block" in produced(repo)
    SCENARIOS_RUN.update({"regression", "stub-paths"})


def produced(repo: Path) -> list[str]:
    return (repo.parent / "fake-state" / "produced.log").read_text().split()


def test_decision_and_verdict_paths(tmp_path: Path) -> None:
    slugs = [
        "P1-dev-retry",
        "P1-dev-adopt",
        "P2-rounds",
        "P2-merge-blocked",
        "P2-rebase-conflict",
        "P2-stale-land",
        "P2-research-me",
    ]
    repo = make_repo(tmp_path, slugs)
    proc = run_sdt(repo, "run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    SCENARIOS_RUN.add("decision-paths")
    final = json.loads(proc.stdout.strip().splitlines()[-1])
    # retry, adopt, rounds, rebase-conflict, stale-land and the item the Researcher filed
    assert final["landed"] == 6, proc.stdout
    assert "P2-merge-blocked" in final["blocked"]
    assert "P2-researched-P2-origin" not in final["blocked"]

    emitted = produced(repo)
    for entry in (
        "DECISION:retry",
        "DECISION:adopt",
        "DECISION:block",
        "TRIAGE:research",
        "FILED",
        "MERGE-BLOCKED",
        "REBASE-REQUIRED",
    ):
        assert entry in emitted, (entry, emitted)

    # the merge-blocked item went to blocked/ with the reason
    backlog = repo / "docs" / "backlog"
    assert (backlog / "blocked" / "P2-merge-blocked.md").is_file()
    subjects = git("log", "--no-show-signature", "--format=%s", "main", cwd=repo).splitlines()

    # research: the Researcher's item is filed, the originating item retired, then the filed item lands
    assert any("file 1 item(s) — research for P2-research-me" in s for s in subjects), subjects
    assert any("retire P2-research-me — superseded by researched item(s)" in s for s in subjects), subjects
    assert any(s.startswith("feat(P2-researched-P2-origin)") for s in subjects), subjects
    assert not (backlog / "P2-research-me.md").exists()

    # the merge-clerk's stale sha is rejected and verified again; the rebase request is worked
    assert "re-verifying on the new tip" in proc.stdout, proc.stdout
    assert "IMPLEMENT-RESUME:REBASE:P2-rebase-conflict" in emitted, emitted
    # retry and adopt resume the developer differently
    assert "IMPLEMENT-RESUME:RETRY:P1-dev-retry" in emitted, emitted
    assert "IMPLEMENT-RESUME:ADOPT:P1-dev-adopt" in emitted, emitted
    # the review-round cap escalates to the Manager, who answers retry
    assert "DECISION-REQUEST:REVIEW-ROUNDS-EXCEEDED:P2-rounds" in emitted, emitted
    assert git("rev-list", "--count", "--merges", "main", cwd=repo) == "0"
    assert git("status", "--porcelain", cwd=repo) == ""


def test_environment_ruling_is_recorded_then_filtered(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["P1-envfault"], gate=FAULT_GATE, extra_config=f'known_failures = "{KNOWN_FAILURES}"\n')
    proc = run_sdt(repo, "run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout.strip().splitlines()[-1])["landed"] == 1
    assert produced(repo).count("ENVIRONMENT") == 1

    # QA's ruling is appended to the known-failures file and committed on its own
    known = (repo / KNOWN_FAILURES).read_text()
    assert "ENV-FAULT: flaky network" in known
    subjects = git("log", "--no-show-signature", "--format=%s", "main", cwd=repo).splitlines()
    assert any(s.startswith("chore(qa): record known failure") for s in subjects), subjects
    assert git("status", "--porcelain", cwd=repo) == ""

    # the same red on a later tip is filtered: the gate goes green and QA is not asked again
    later = repo / "docs" / "backlog" / "P2-later.md"
    later.parent.mkdir(parents=True, exist_ok=True)
    later.write_text("# P2-later\n\nAppend 'done' to src/P2-later.txt.\n")
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", "chore(backlog): file P2-later", cwd=repo)
    proc = run_sdt(repo, "run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout.strip().splitlines()[-1])["landed"] == 1
    assert "qa-green" in proc.stdout and "qa-red" not in proc.stdout, proc.stdout
    assert produced(repo).count("ENVIRONMENT") == 1
    SCENARIOS_RUN.add("environment-ruling")


def test_stalled_developer_is_adopted(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["P2-stall-me"])
    proc = run_sdt(repo, "run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    final = json.loads(proc.stdout.strip().splitlines()[-1])
    assert final["landed"] == 1
    assert "stalled" in proc.stdout and "adopt" in proc.stdout


def test_held_item_waits_for_what_it_waits_on(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["P1-first", "P2-held"])
    proc = run_sdt(repo, "run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    final = json.loads(proc.stdout.strip().splitlines()[-1])
    assert final["landed"] == 2, proc.stdout
    held = proc.stdout.index("held: P2-held: waits on P1-first")
    landed = proc.stdout.index("merged: P1-first landed")
    dispatched = proc.stdout.index("dispatch: P2-held")
    assert held < landed < dispatched, "the held item is dispatched only once what it waits on has landed"
    assert proc.stdout.count("dispatch: P2-held") == 1
    SCENARIOS_RUN.add("hold")


def test_role_keeps_notes_and_sends_run_consistency(repo: Path) -> None:
    proc = run_sdt(repo, "role", "consistency-check", "--file-items")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout[proc.stdout.index("{") :])
    assert result["received"]["message"] == "RUN-CONSISTENCY"
    assert result["received"]["tip"] == git("rev-parse", "main", cwd=repo)
    notes = repo / ".delivery-team" / "notes" / "consistency-check.md"
    assert "audited up to stub-marker" in notes.read_text()


def test_failed_triage_dispatches_nothing(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["P2-triage-fails"])
    final = drained(run_sdt(repo, "run"))
    assert final["landed"] == 0
    assert final["blocked"] == ["P2-triage-fails"]
    # adopt_attempts = 1: the failed triage is asked once more, then the item blocks
    assert len([r for r in role_runs(repo, "manager") if r.endswith("-triage")]) == 2
    assert role_runs(repo, "developer") == []
    assert git("branch", "--list", "item/*", cwd=repo) == ""
    text = (repo / "docs" / "backlog" / "blocked" / "P2-triage-fails.md").read_text()
    assert "⛔" in text and "triage failed after 2 attempt(s): no fenced json block" in text


def test_failing_reviewer_escalates(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["P2-review-fails"])
    final = drained(run_sdt(repo, "run"))
    assert final["blocked"] == ["P2-review-fails"]
    assert len(role_runs(repo, "reviewer")) == 2, "re-dispatched adopt_attempts times, never forever"
    decisions = [r for r in role_runs(repo, "manager") if r.endswith("-P2-review-fails")]
    assert len(decisions) == 1
    prompt = (repo / ".delivery-team" / "runs" / f"{decisions[0]}.prompt.md").read_text()
    assert '"event": "REVIEWER-FAILED"' in prompt and '"attempts": 2' in prompt
    text = (repo / "docs" / "backlog" / "blocked" / "P2-review-fails.md").read_text()
    assert "⛔" in text and "blocked after REVIEWER-FAILED" in text


def test_failed_qa_run_releases_the_failure(tmp_path: Path) -> None:
    # The second item needs a second review round, so it lands after the red one.
    repo = make_repo(tmp_path, ["P1-red-qa-fails", "P2-twice-after"])
    proc = run_sdt(repo, "run")
    final = drained(proc)
    assert "qa-failed: red at" in proc.stdout and "qa failed after 2 attempt(s)" in proc.stdout
    # two failed runs on the first red tip, then the second red with the same failure reached QA again
    assert len(role_runs(repo, "qa")) == 3
    subjects = git("log", "--no-show-signature", "--format=%s", "main", cwd=repo).splitlines()
    assert any(s.startswith("chore(backlog): file 1 item(s) — regression") for s in subjects), subjects
    assert final["landed"] == 3  # the red item, the second item, and the regression fix


def test_qa_blocked_reason_is_surfaced(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["P1-red-qa-blocks"])
    proc = run_sdt(repo, "run")
    final = drained(proc)
    assert final["landed"] == 1 and final["blocked"] == []
    reason = "the gate needs a service this environment lacks"
    state = json.loads((repo / ".delivery-team" / "progress" / "state.json").read_text())
    qa = next(a for a in state["agents"] if a["role"] == "QA")
    assert qa["state"].endswith("qa blocked: " + reason), qa
    assert any(e["kind"] == "qa-blocked" and reason in e["text"] for e in state["events"]), state["events"]
    assert "regression filed" not in proc.stdout
    SCENARIOS_RUN.add("qa-blocked")


def test_research_failure_blocks_and_no_item_retires(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["P2-research-fails", "P2-research-dissolves", "P2-plain"])
    final = drained(run_sdt(repo, "run"))
    assert final["landed"] == 1
    assert final["blocked"] == ["P2-research-fails"]
    backlog = repo / "docs" / "backlog"

    # a failed research run is asked once more, then its item blocks with the engine error
    assert len([r for r in role_runs(repo, "researcher") if r.endswith("-P2-research-fails")]) == 2
    text = (backlog / "blocked" / "P2-research-fails.md").read_text()
    assert "⛔" in text and "research failed after 2 attempt(s): no fenced json block" in text

    # NO-ITEM retires the item in one commit that says why
    assert not (backlog / "P2-research-dissolves.md").exists()
    assert not (backlog / "blocked" / "P2-research-dissolves.md").exists()
    rel = "docs/backlog/P2-research-dissolves.md"
    sha = git("log", "--no-show-signature", "-1", "--format=%H", "main", "--", rel, cwd=repo)
    message = git("log", "--no-show-signature", "-1", "--format=%B", sha, cwd=repo)
    assert message.startswith("chore(backlog): retire P2-research-dissolves — already true")
    assert "Finding: already true: src/ has the behaviour" in message and "Why: nothing to change" in message
    assert git("show", "--no-show-signature", "--name-status", "--format=", sha, cwd=repo) == f"D\t{rel}"
    SCENARIOS_RUN.add("no-item")

    # a retired item is closed without landing: the board counts only what DRAINED counts as landed
    state = json.loads((repo / ".delivery-team" / "progress" / "state.json").read_text())
    done = [it["slug"] for it in state["items"] if it["stage"] == "done"]
    assert len(done) == final["landed"], state["items"]
    assert "P2-research-dissolves" not in done


def test_failed_consistency_check_is_retried_then_reported(tmp_path: Path) -> None:
    # consistency_every = 2: the second landing starts the check, on a tip holding the marked item.
    repo = make_repo(tmp_path, ["P1-consistency-fails", "P2-plain"])
    final = drained(run_sdt(repo, "run"))
    assert final["landed"] == 2
    assert len(role_runs(repo, "consistency-check")) == 2, "re-dispatched adopt_attempts times, then reported"
    state = json.loads((repo / ".delivery-team" / "progress" / "state.json").read_text())
    failed = [e for e in state["events"] if e["kind"] == "consistency-failed"]
    assert len(failed) == 1 and "after 2 attempt(s)" in failed[0]["text"], state["events"]


def test_researcher_role_sends_research_request(repo: Path) -> None:
    payload = json.dumps({"item": "some ask", "question": "q?", "item_text": "the ask"})
    proc = run_sdt(repo, "role", "researcher", "--payload", payload)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout[proc.stdout.index("{") :])
    assert result["received"]["message"] == "RESEARCH-REQUEST"


def set_profile(repo: Path, text: str) -> str:
    """Commit a new profile; returns the resulting tip."""
    (repo / ".delivery-team" / "profile.md").write_text(text)
    git("commit", "-q", "-am", "docs: profile", cwd=repo)
    return git("rev-parse", "HEAD", cwd=repo)


def sweep_prompts(repo: Path, step: str) -> list[Path]:
    return sorted((repo / ".delivery-team" / "runs").glob(f"*-consistency-check-sweep-{step}*.prompt.md"))


def test_sweep_files_confirmed_findings_only(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, ["P3-doc-rot"])
    backlog = repo / "docs" / "backlog"
    existing = (backlog / "P3-doc-rot.md").read_text()
    seed = set_profile(repo, "# Profile\n\nDocs are spec: yes.\n")
    proc = run_sdt(repo, "sweep")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    assert result["message"] == "SWEEP" and result["applicable"] and result["failed"] == []
    assert result["classes"] == [
        "contradictions",
        "terminology",
        "references",
        "decision-records",
        "self-contradiction",
        "residue",
        "spec-vs-code",
    ]

    # a map run, an audit per class, a skeptic per finding
    assert len(sweep_prompts(repo, "map")) == 1
    audits = sweep_prompts(repo, "audit-")
    assert all('"phase": "audit"' in p.read_text() and '"docs/spec.md"' in p.read_text() for p in audits)
    assert len(sweep_prompts(repo, "verify-")) == 9

    # the flaky audit failed once and was re-dispatched; its finding is filed below
    assert len(audits) == 8 and len(sweep_prompts(repo, "audit-decision-records")) == 2
    assert "sweep step sweep-audit-decision-records failed (no fenced json block" in proc.stdout

    # the confirmed are filed, the refuted are not, and nothing is overwritten
    confirmed = {f"P2-sweep-{c}.md" for c in ("contradictions", "references", "decision-records", "self-contradiction")}
    confirmed |= {"P2-sweep-spec-vs-code.md", "P3-doc-rot-2.md", "P3-doc-rot-3.md"}
    assert set(result["filed"]) == confirmed
    assert {r["filename"] for r in result["refuted"]} == {"P2-sweep-terminology.md", "P2-sweep-residue.md"}
    assert {p.name for p in backlog.glob("*.md")} == confirmed | {"P3-doc-rot.md"}
    assert (backlog / "P3-doc-rot.md").read_text() == existing
    assert (backlog / "P3-doc-rot-2.md").read_text() != (backlog / "P3-doc-rot-3.md").read_text()

    # in one commit, leaving the main tree clean
    assert git("rev-list", "--count", f"{seed}..main", cwd=repo) == "1"
    subject = git("log", "--no-show-signature", "-1", "--format=%s", cwd=repo)
    assert subject == "chore(backlog): file 7 item(s) — consistency sweep"
    assert git("status", "--porcelain", cwd=repo) == ""


def test_sweep_reports_a_step_that_keeps_failing(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, [])  # docs are not spec: no spec-vs-code class
    seed = git("rev-parse", "main", cwd=repo)
    proc = run_sdt(repo, "sweep", env_extra={"FAKE_SWEEP_FAILS": "references"})
    assert proc.returncode == 1, proc.stdout + proc.stderr
    result = json.loads(proc.stdout.strip().splitlines()[-1])

    # adopt_attempts = 1: the audit is re-dispatched once, then reported, never retried forever
    assert len(sweep_prompts(repo, "audit-references")) == 2
    [failed] = result["failed"]
    assert failed["phase"] == "audit" and failed["class"] == "references" and failed["attempts"] == 2
    assert failed["error"].startswith("no fenced json block"), failed
    assert "sweep-failed: sweep-audit-references failed after 2 attempt(s)" in proc.stdout

    # every other class's confirmed finding is still filed, in one commit
    confirmed = {f"P2-sweep-{c}.md" for c in ("contradictions", "decision-records", "self-contradiction")}
    assert set(result["filed"]) == confirmed | {"P3-doc-rot.md"}
    assert git("rev-list", "--count", f"{seed}..main", cwd=repo) == "1"


def test_sweep_stops_where_the_audit_does_not_apply(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, [])
    seed = set_profile(repo, "# Profile\n\nDocs root: n/a\n")
    proc = run_sdt(repo, "sweep")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    assert result["message"] == "SWEEP" and result["applicable"] is False
    assert sweep_prompts(repo, "audit-") == []
    assert git("rev-parse", "main", cwd=repo) == seed


def test_status_without_run(repo: Path) -> None:
    proc = run_sdt(repo, "status")
    assert proc.returncode == 0
    assert "no run state" in proc.stdout


def test_refuses_a_second_run(repo: Path) -> None:
    runs = repo / ".delivery-team" / "runs"
    runs.mkdir(parents=True)
    (runs / "sdt.pid").write_text(str(os.getpid()))
    proc = run_sdt(repo, "run")
    assert proc.returncode == 2
    assert "MUTATIONS-BLOCKED" in proc.stderr and "another run" in proc.stderr


def test_paths(repo: Path) -> None:
    proc = run_sdt(repo, "paths")
    assert proc.returncode == 0
    assert "charter:" in proc.stdout and "team-charter.md" in proc.stdout


def test_install_links_skills_and_snippet(repo: Path) -> None:
    proc = run_sdt(repo, "install", "--harness", "codex")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    link = repo / ".agents" / "skills" / "team"
    assert link.is_symlink() and (link / "SKILL.md").is_file()
    assert "Add this to AGENTS.md" in proc.stdout
    assert not (repo / "AGENTS.md").exists()

    proc = run_sdt(repo, "install", "--harness", "codex", "--write")
    assert proc.returncode == 0
    text = (repo / "AGENTS.md").read_text()
    assert text.count("## Delivery team") == 1
    proc = run_sdt(repo, "install", "--harness", "codex", "--write")
    assert "already present" in proc.stdout
    assert (repo / "AGENTS.md").read_text() == text

    proc = run_sdt(repo, "install", "--harness", "claude")
    assert (repo / ".claude" / "skills" / "board").is_symlink()


def test_every_charter_payload_was_produced() -> None:
    """The stub produced every Manager, Merge-Clerk, QA and Researcher message and action in the charter."""
    if not SCENARIOS <= SCENARIOS_RUN:
        pytest.skip("needs the other end-to-end scenarios to have run first")
    required = {
        "TRIAGE:dispatch",
        "TRIAGE:hold",
        "TRIAGE:block",
        "TRIAGE:research",
        "DECISION:block",
        "DECISION:retry",
        "DECISION:adopt",
        "LANDABLE",
        "MERGE-BLOCKED",
        "REBASE-REQUIRED",
        "REGRESSION",
        "ENVIRONMENT",
        "QA-BLOCKED",
        "FILED",
        "NO-ITEM",
    }
    assert required <= SEEN, sorted(required - SEEN)
