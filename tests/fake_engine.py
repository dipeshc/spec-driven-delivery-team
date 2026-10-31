#!/usr/bin/env python3
"""A scripted stand-in for a coding CLI, used by the end-to-end test.

It reads the orchestrator's prompt on stdin, finds the role and the dispatch
payload, performs the role's git-visible side effects in the working directory,
and prints a final message ending in the fenced JSON block the result contract
asks for. Behaviour is keyed on item slugs so a test can stage every path:

- a slug containing ``twice``    → the reviewer requests changes once, then approves
- a slug containing ``block-me`` → triage blocks it
- a slug containing ``held``     → triage holds it until every other item has landed or blocked
- a slug containing ``dev-blocks`` → the developer reports BLOCKED (triage then blocks it)
- slugs starting ``P3-group-``   → triage groups them into one branch
- a slug containing ``stall``    → the developer sleeps past the stall limit once
- a slug containing ``red``      → implemented so the test's gate fails (a regression)
- a slug containing ``triage-fails`` → every triage run carrying it fails (no result block)
- a slug containing ``review-fails`` → every review of it fails
- a slug containing ``research-fails`` / ``research-dissolves`` → triage sends it to
  research; the Researcher fails every run / returns ``NO-ITEM``
- a slug containing ``qa-fails``  → every QA run on the first red tip holding it fails
- a slug containing ``qa-blocks`` → QA answers ``QA-BLOCKED`` on the first red tip holding it
- a slug containing ``consistency-fails`` → every consistency-check run on a tip holding it fails

- a slug containing ``research-me`` → triage sends it to research; the Researcher files a new item
- a slug containing ``dev-retry`` / ``dev-adopt`` → the developer reports BLOCKED once; the Manager
  then answers ``retry`` / ``adopt`` and the second attempt succeeds
- a slug containing ``rounds``   → the reviewer requests changes until the round limit is exceeded;
  the Manager answers ``retry`` to the REVIEW-ROUNDS-EXCEEDED request
- a slug containing ``merge-blocked`` → the Merge-Clerk answers MERGE-BLOCKED (the Manager blocks it)
- a slug containing ``rebase-conflict`` → the Merge-Clerk answers REBASE-REQUIRED once
- a slug containing ``stale-land`` → the Merge-Clerk first names a sha that is not a fast-forward
- a slug containing ``envfault`` → the test's gate fails with a marker QA reads in the log, and QA
  answers ENVIRONMENT

With ``FAKE_REVIEW_WAIT_SECONDS`` set, the first reviewer run waits up to that
long for a second one to start, so a run with two reviewer instances overlaps.

The consistency check answers each `sdt sweep` phase: the map reads the profile
for applicability and docs-as-spec; every audited class returns one finding,
which the skeptic refutes for the classes in ``REFUTED_CLASSES``; the classes in
``ROT_CLASSES`` also each return a ``P3-doc-rot.md``. The audit of a class in
``FLAKY_CLASSES`` fails its first run, and with ``FAKE_SWEEP_FAILS`` naming a
class, every audit of that class fails.

Every message and action the stub emits is appended to ``$FAKE_STATE_DIR/produced.log`` so a test
can prove which charter payloads the end-to-end runs exercised.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REFUTED_CLASSES = {"terminology", "residue"}
ROT_CLASSES = {"references", "self-contradiction"}
FLAKY_CLASSES = {"decision-records"}


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=True).stdout.strip()


def record_entry(*entries: str) -> None:
    state = Path(os.environ.get("FAKE_STATE_DIR", "/tmp/fake-engine"))
    state.mkdir(parents=True, exist_ok=True)
    with open(state / "produced.log", "a") as fh:
        fh.write("\n".join(entries) + "\n")


def record(payload: dict[str, object]) -> None:
    """Append what this reply says, as ``Message`` or ``Message:action``, to the produced log."""
    entries = [str(payload.get("message"))]
    if payload.get("action"):
        entries.append(f"{payload['message']}:{payload['action']}")
    items = payload.get("items") if payload.get("message") == "TRIAGE" else None
    for item in items if isinstance(items, list) else []:
        entries.append(f"TRIAGE:{item['action']}")
    record_entry(*entries)


def reply(payload: dict[str, object], text: str = "Done.") -> None:
    record(payload)
    print(text)
    print("```json")
    print(json.dumps(payload, indent=2))
    print("```")


def counter(name: str) -> int:
    """A per-test counter persisted under FAKE_STATE_DIR; returns the value before increment."""
    state = Path(os.environ.get("FAKE_STATE_DIR", "/tmp/fake-engine"))
    state.mkdir(parents=True, exist_ok=True)
    path = state / name
    value = int(path.read_text()) if path.is_file() else 0
    path.write_text(str(value + 1))
    return value


def wait_for(name: str, value: int, seconds: float) -> None:
    """Poll a counter until it reaches `value` or `seconds` pass, printing so the log keeps growing."""
    path = Path(os.environ.get("FAKE_STATE_DIR", "/tmp/fake-engine")) / name
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.is_file() and int(path.read_text() or 0) >= value:
            return
        print("waiting", flush=True)
        time.sleep(0.2)


def first_seen(name: str, value: str) -> str:
    """The value first recorded under `name` in FAKE_STATE_DIR; records `value` when there is none."""
    state = Path(os.environ.get("FAKE_STATE_DIR", "/tmp/fake-engine"))
    state.mkdir(parents=True, exist_ok=True)
    path = state / name
    if not path.is_file():
        path.write_text(value)
    return path.read_text()


def fail() -> int:
    """End the run without a result block, as an engine that died mid-run does."""
    print("Error: the stub engine stopped before producing a result.")
    return 1


def main() -> int:
    prompt = sys.stdin.read()
    role_match = re.search(r"^- role: (\S+)$", prompt, re.MULTILINE)
    role = role_match.group(1) if role_match else "unknown"
    dispatch = prompt.split("## Dispatch", 1)[1] if "## Dispatch" in prompt else "{}"
    block = re.search(r"```json\n(.*?)\n```", dispatch, re.DOTALL)
    payload = json.loads(block.group(1)) if block else {}
    cwd = Path.cwd()
    base_match = re.search(r"^- default branch: (\S+)$", prompt, re.MULTILINE)
    base = base_match.group(1) if base_match else "main"

    if role == "manager":
        return manager(payload)
    if role == "developer":
        return developer(payload, cwd, base)
    if role == "reviewer":
        return reviewer(payload)
    if role == "merge-clerk":
        return merge_clerk(payload, cwd, base)
    if role == "qa":
        return qa(payload, cwd)
    if role == "consistency-check":
        return consistency_check(payload, prompt, cwd)
    if role == "researcher":
        slug = str(payload.get("item", "x"))
        if "research-fails" in slug:
            return fail()
        if "research-dissolves" in slug:
            reply({"message": "NO-ITEM", "finding": "already true: src/ has the behaviour", "why": "nothing to change"})
            return 0
        # The filed name must not carry the marker, or triage would send it to research again.
        slug = slug.replace("research-me", "origin")
        reply(
            {
                "message": "FILED",
                "received": payload,
                "items": [
                    {
                        "filename": f"P2-researched-{slug}.md",
                        "body": f"# Researched {slug}\n\nImplement by appending to src/{slug}.txt.\n",
                    }
                ],
            }
        )
        return 0
    reply({"message": "UNKNOWN-ROLE", "role": role})
    return 0


def consistency_check(payload: dict, prompt: str, cwd: Path) -> int:
    phase = payload.get("phase")
    if phase is None:
        if any("consistency-fails" in p.name for p in (cwd / "src").glob("*.txt")):
            return fail()
        reply(
            {"message": "FINDINGS", "items": [], "received": payload, "notes_for_next_run": "audited up to stub-marker"}
        )
        return 0
    if phase == "map":
        profile_match = re.search(r"^- profile: (.+)$", prompt, re.MULTILINE)
        profile = Path(profile_match.group(1)).read_text() if profile_match else ""
        reply(
            {
                "message": "INVENTORY",
                "applicable": "Docs root: n/a" not in profile,
                "reason": "stub",
                "docs_are_spec": "Docs are spec: yes" in profile,
                "files": ["docs/spec.md"],
            }
        )
        return 0
    if phase == "audit":
        cls = payload["class"]
        if cls == os.environ.get("FAKE_SWEEP_FAILS") or (cls in FLAKY_CLASSES and counter("sweep-" + cls) == 0):
            return fail()
        verdict = "refute" if cls in REFUTED_CLASSES else "confirm"
        files = ", ".join(payload["files"])
        items = [{"filename": f"P2-sweep-{cls}.md", "body": f"# {cls} finding\n\nIn {files}.\n\nverdict: {verdict}\n"}]
        if cls in ROT_CLASSES:
            items.append({"filename": "P3-doc-rot.md", "body": f"# Doc rot found by {cls}\n\nverdict: confirm\n"})
        reply({"message": "FINDINGS", "items": items})
        return 0
    refuted = "verdict: refute" in payload["finding"]["body"]
    reply({"message": "VERDICT", "verdict": "refuted" if refuted else "confirmed", "reason": "stub"})
    return 0


def manager(payload: dict) -> int:
    if payload.get("message") == "DECISION-REQUEST":
        slug = str(payload.get("item", ""))
        record_entry(f"DECISION-REQUEST:{payload.get('event')}:{slug}")
        action = "block"
        if "dev-retry" in slug and payload.get("event") == "BLOCKED":
            action = "retry"
        elif "dev-adopt" in slug and payload.get("event") == "BLOCKED":
            action = "adopt"
        elif "rounds" in slug and payload.get("event") == "REVIEW-ROUNDS-EXCEEDED":
            action = "retry"
        verb = "blocked" if action == "block" else action
        reply({"message": "DECISION", "action": action, "reason": f"{verb} after {payload.get('event')}"})
        return 0
    if any("triage-fails" in i["slug"] for i in payload.get("items", [])):
        return fail()
    decisions = []
    grouped = [i["slug"] for i in payload.get("items", []) if str(i["slug"]).startswith("P3-group-")]
    open_slugs = [str(i["slug"]) for i in payload.get("items", [])] + [
        str(f["slug"]) for f in payload.get("in_flight", []) if f.get("stage") not in ("done", "blocked")
    ]
    waited_on = sorted(s for s in open_slugs if "held" not in s)
    for item in payload.get("items", []):
        slug = item["slug"]
        if slug in grouped[1:]:
            continue
        d: dict[str, object] = {
            "slug": slug,
            "action": "dispatch",
            "tier": "mid",
            "ports": False,
            "governing_docs": [],
            "guards": [],
        }
        if "block-me" in slug:
            d.update(action="block", reason="needs an owner decision")
        if "held" in slug and waited_on:
            d.update(action="hold", reason="waits on " + ", ".join(waited_on))
        if "research-fails" in slug or "research-dissolves" in slug:
            d.update(action="research", reason="is this already true?")
        if "research-me" in slug:
            d.update(action="research", reason="the approach is unclear")
        if slug == grouped[0] if grouped else False:
            d["group"] = grouped[1:]
        decisions.append(d)
    reply({"message": "TRIAGE", "items": decisions})
    return 0


def developer(payload: dict, cwd: Path, base: str) -> int:
    items = payload.get("items", [])
    slugs = [i["slug"] for i in items]
    first_try = any(("dev-retry" in s or "dev-adopt" in s) and counter("dev-" + s) == 0 for s in slugs)
    if first_try or any("dev-blocks" in s for s in slugs):
        reply(
            {
                "message": "BLOCKED",
                "item": slugs[0],
                "branch": payload.get("branch"),
                "worktree": str(cwd),
                "reason": "spec gap",
                "needs": "owner decision",
            }
        )
        return 0
    if any("stall" in s for s in slugs) and counter("stall-" + slugs[0]) == 0:
        time.sleep(int(os.environ.get("FAKE_STALL_SECONDS", "30")))
    resume = payload.get("resume") or {}
    if resume.get("message"):
        record_entry(f"IMPLEMENT-RESUME:{resume['message']}:{slugs[0]}")
    if resume.get("message") == "REBASE":
        rebase = subprocess.run(["git", "rebase", base], cwd=cwd, text=True, capture_output=True, check=False)
        if rebase.returncode != 0:
            subprocess.run(["git", "rebase", "--abort"], cwd=cwd, check=False)
            reply(
                {
                    "message": "BLOCKED",
                    "item": slugs[0],
                    "branch": payload.get("branch"),
                    "worktree": str(cwd),
                    "reason": "rebase conflict",
                    "needs": "hand resolution",
                }
            )
            return 0
    for item in items:
        if str(item["slug"]).startswith("P0-regression"):
            # The regression fix: remove what made the gate red.
            for red in (cwd / "src").glob("*red*.txt"):
                red.unlink()
        src = cwd / "src" / f"{item['slug']}.txt"
        src.parent.mkdir(exist_ok=True)
        with open(src, "a") as fh:
            fh.write("done\n")
        path = cwd / item["path"]
        if path.exists():
            git("rm", "-q", "--", item["path"], cwd=cwd)
    git("add", "-A", cwd=cwd)
    ahead = int(git("rev-list", "--count", f"{base}..HEAD", cwd=cwd))
    msg = f"feat({slugs[0]}): implement " + ", ".join(slugs)
    if ahead >= 1:
        git("commit", "-q", "--amend", "-m", msg, cwd=cwd)
    else:
        git("commit", "-q", "-m", msg, cwd=cwd)
    head = git("rev-parse", "HEAD", cwd=cwd)
    reply(
        {
            "message": "READY-FOR-REVIEW",
            "items": slugs,
            "branch": payload.get("branch"),
            "worktree": str(cwd),
            "head": head,
            "rebased_onto": git("rev-parse", base, cwd=cwd),
            "single_commit": True,
            "verification": [{"cmd": "true", "result": "pass"}],
            "ports_used": False,
            "notes": "stub",
        }
    )
    return 0


def reviewer(payload: dict) -> int:
    if any("review-fails" in s for req in payload.get("requests", []) for s in req["items"]):
        return fail()
    wait = float(os.environ.get("FAKE_REVIEW_WAIT_SECONDS", "0"))
    if counter("reviewer-runs") == 0 and wait:
        wait_for("reviewer-runs", 2, wait)
    verdicts = []
    for req in payload.get("requests", []):
        slugs = req["items"]
        if any("rounds" in s for s in slugs) and counter("review-" + slugs[0]) < 3:
            verdicts.append(
                {
                    "message": "CHANGES-REQUESTED",
                    "items": slugs,
                    "branch": req["branch"],
                    "comments": ["again"],
                    "required": ["one more pass"],
                }
            )
        elif any("twice" in s for s in slugs) and counter("review-" + slugs[0]) == 0:
            verdicts.append(
                {
                    "message": "CHANGES-REQUESTED",
                    "items": slugs,
                    "branch": req["branch"],
                    "comments": ["tighten it"],
                    "required": ["one more pass"],
                }
            )
        else:
            verdicts.append(
                {
                    "message": "APPROVED",
                    "items": slugs,
                    "branch": req["branch"],
                    "head": req["head"],
                    "verification": [{"cmd": "true", "result": "pass"}],
                    "notes": "stub",
                }
            )
    reply({"message": "REVIEW-VERDICTS", "verdicts": verdicts})
    return 0


def qa(payload: dict, cwd: Path) -> int:
    tip = str(payload.get("tip", ""))
    marks = [p.name for p in (cwd / "src").glob("*.txt")]
    if any("qa-fails" in m for m in marks) and first_seen("qa-fails-tip", tip) == tip:
        return fail()
    if any("qa-blocks" in m for m in marks) and first_seen("qa-blocks-tip", tip) == tip:
        reply({"message": "QA-BLOCKED", "reason": "the gate needs a service this environment lacks"})
        return 0
    tail = str(payload.get("log_tail", ""))
    if "ENV-FAULT" in tail:
        reply({"message": "ENVIRONMENT", "patterns": ["ENV-FAULT: flaky network"], "reason": "flaky network"})
        return 0
    reply(
        {
            "message": "REGRESSION",
            "items": [
                {
                    "filename": f"P0-regression-{tip[:8]}.md",
                    "body": f"# Regression at {tip}\n\nFailed: {payload.get('failed_commands')}\n",
                }
            ],
        }
    )
    return 0


def merge_clerk(payload: dict, cwd: Path, base: str) -> int:
    head = payload["head"]
    slugs = [str(s) for s in payload["items"]]
    if any("merge-blocked" in s for s in slugs):
        reply({"message": "MERGE-BLOCKED", "reason": "the guard named in the dispatch fails"})
        return 0
    if any("rebase-conflict" in s for s in slugs) and counter("clerk-rebase-" + slugs[0]) == 0:
        reply(
            {
                "message": "REBASE-REQUIRED",
                "items": payload["items"],
                "branch": payload["branch"],
                "base": git("rev-parse", base, cwd=cwd),
                "reason": "conflicts with the current base",
            }
        )
        return 0
    if any("stale-land" in s for s in slugs) and counter("clerk-stale-" + slugs[0]) == 0:
        # A root commit is never a fast-forward of the default branch.
        stale = git("commit-tree", f"{head}^{{tree}}", "-m", "stale", cwd=cwd)
        reply({"message": "LANDABLE", "items": payload["items"], "sha": stale, "rebased": False, "verification": []})
        return 0
    base_sha = git("rev-parse", base, cwd=cwd)
    if subprocess.run(["git", "merge-base", "--is-ancestor", base_sha, head], cwd=cwd, check=False).returncode == 0:
        reply({"message": "LANDABLE", "items": payload["items"], "sha": head, "rebased": False, "verification": []})
        return 0
    git("checkout", "-q", "--detach", base_sha, cwd=cwd)
    pick = subprocess.run(["git", "cherry-pick", head], cwd=cwd, text=True, capture_output=True, check=False)
    if pick.returncode != 0:
        subprocess.run(["git", "cherry-pick", "--abort"], cwd=cwd, check=False)
        reply(
            {
                "message": "REBASE-REQUIRED",
                "items": payload["items"],
                "branch": payload["branch"],
                "base": base_sha,
                "reason": pick.stderr[-300:],
            }
        )
        return 0
    reply(
        {
            "message": "LANDABLE",
            "items": payload["items"],
            "sha": git("rev-parse", "HEAD", cwd=cwd),
            "rebased": True,
            "verification": [],
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
