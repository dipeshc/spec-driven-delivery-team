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

With ``FAKE_REVIEW_WAIT_SECONDS`` set, the first reviewer run waits up to that
long for a second one to start, so a run with two reviewer instances overlaps.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=True).stdout.strip()


def reply(payload: dict[str, object], text: str = "Done.") -> None:
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
        if any("consistency-fails" in p.name for p in (cwd / "src").glob("*.txt")):
            return fail()
        reply(
            {"message": "FINDINGS", "items": [], "received": payload, "notes_for_next_run": "audited up to stub-marker"}
        )
        return 0
    if role == "researcher":
        slug = payload.get("item", "x")
        if "research-fails" in slug:
            return fail()
        if "research-dissolves" in slug:
            reply({"message": "NO-ITEM", "finding": "already true: src/ has the behaviour", "why": "nothing to change"})
            return 0
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


def manager(payload: dict) -> int:
    if payload.get("message") == "DECISION-REQUEST":
        reply({"message": "DECISION", "action": "block", "reason": f"blocked after {payload.get('event')}"})
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
        if slug == grouped[0] if grouped else False:
            d["group"] = grouped[1:]
        decisions.append(d)
    reply({"message": "TRIAGE", "items": decisions})
    return 0


def developer(payload: dict, cwd: Path, base: str) -> int:
    items = payload.get("items", [])
    slugs = [i["slug"] for i in items]
    if any("dev-blocks" in s for s in slugs):
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
        if any("twice" in s for s in slugs) and counter("review-" + slugs[0]) == 0:
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
