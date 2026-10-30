#!/bin/sh
# Delivery-team statusline: a glanceable, two-line summary of a team run.
#
# Rendered entirely from the orchestrator's state ledger — pure POSIX shell, no Node,
# no Python, no jq, and no network. It reads the caller's JSON on stdin (Claude
# Code passes {"workspace":{"project_dir":"…"}}) and prints team lines only when
# that project has live team state; otherwise it prints nothing (or defers to a
# chained statusline it was told to run first).
#
# It never errors: absent, stale, or malformed state each degrade to silence
# rather than a noisy error line. The state schema is owned by the charter's
# "Progress ledger" section — this script consumes it and never defines its own
# shape. Everything it renders (tip, ahead-of-origin, counts, elapsed) already
# lives in that file, so it performs no git read at all and stays well inside a
# 300 ms-debounced budget.

set -u

STALE_S=90     # state older than this is reported as stale, never as live
BAR_W=10       # width of the progress bar, in cells

# Read stdin once; it feeds both a chained command and our own parse.
INPUT=$(cat)

# Optional chaining. The installer wires `statusline.sh --chain '<cmd>'` when the
# user already had a statusline: we run that command first, with the same stdin,
# and print its output above our own lines — appending, never clobbering.
CHAIN=""
while [ $# -gt 0 ]; do
  case "$1" in
    --chain) CHAIN=${2:-}; shift 2 ;;
    --chain=*) CHAIN=${1#--chain=}; shift ;;
    *) shift ;;
  esac
done
if [ -n "$CHAIN" ]; then
  printf '%s' "$INPUT" | sh -c "$CHAIN" 2>/dev/null || true
fi

# Every path below ends in silence rather than an error line.
done_silent() { exit 0; }

project_dir=$(printf '%s' "$INPUT" \
  | sed -n 's/.*"project_dir"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
[ -n "$project_dir" ] || done_silent

dir="$project_dir/.delivery-team/progress"
json=""
if [ -f "$dir/state.json" ]; then
  json=$(cat "$dir/state.json" 2>/dev/null)
elif [ -f "$dir/state.js" ]; then
  # state.js is `window.TEAM_STATE = { … };` — strip the prefix and trailing `;`.
  json=$(tr '\n' ' ' < "$dir/state.js" 2>/dev/null \
    | sed 's/^[[:space:]]*window\.TEAM_STATE[[:space:]]*=[[:space:]]*//; s/[[:space:]]*;[[:space:]]*$//')
else
  done_silent
fi
[ -n "$json" ] || done_silent

# Collapse to one logical line so flat item objects can be scanned as `{…}`.
flat=$(printf '%s' "$json" | tr '\n' ' ')

# Keys are UNQUOTED identifiers in the canonical state.js (`generatedAt:`,
# `items:`, `stage:`) and QUOTED in the optional state.json twin (`"generatedAt":`).
# Every key match below tolerates both: `"\{0,1\}` is an optional leading/trailing
# quote. String VALUES are quoted in both forms; numbers are bare in both.

# Malformed guards: it must look like a complete state object. `items` must be an
# array, and the object must be closed (a truncated file will not end `}`).
printf '%s' "$flat" | grep -q '"\{0,1\}items"\{0,1\}[[:space:]]*:[[:space:]]*\[' || done_silent
trimmed=$(printf '%s' "$flat" | sed 's/[[:space:]]*$//')
[ "$(printf '%s' "$trimmed" | tail -c 1)" = "}" ] || done_silent

now=$(date +%s)

# ---- scalar extractors over the whole object (top-level keys are unique) ----
num_of() {
  printf '%s' "$flat" | grep -o "\"\{0,1\}$1\"\{0,1\}[[:space:]]*:[[:space:]]*[0-9][0-9]*" \
    | head -1 | grep -o '[0-9][0-9]*$'
}
str_of() {
  printf '%s' "$flat" \
    | sed -n "s/.*\"\{0,1\}$1\"\{0,1\}[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -1
}
count_stage() {
  printf '%s' "$flat" \
    | grep -o "\"\{0,1\}stage\"\{0,1\}[[:space:]]*:[[:space:]]*\"$1\"" | wc -l | tr -d ' '
}

# ---- pick a flat item object by stage, then read a field out of it ----
# Item objects contain only scalars and the `grouped` array, so `{[^{}]*}` isolates
# each one; filtering by stage selects items (run/repo/agents/events lack a stage).
item_obj() {
  printf '%s' "$flat" | grep -o '{[^{}]*}' \
    | grep "\"\{0,1\}stage\"\{0,1\}[[:space:]]*:[[:space:]]*\"$1\"" | head -1
}
ofield() {
  printf '%s' "$1" \
    | sed -n "s/.*\"\{0,1\}$2\"\{0,1\}[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -1
}
onum() {
  printf '%s' "$1" | grep -o "\"\{0,1\}$2\"\{0,1\}[[:space:]]*:[[:space:]]*[0-9][0-9]*" \
    | head -1 | grep -o '[0-9][0-9]*$'
}

# Elapsed since an epoch timestamp, formatted; "—" when the timestamp is absent.
since() {
  case "${1:-}" in ''|*[!0-9]*) printf '%s' '—'; return ;; esac
  fmt_dur $((now - $1))
}

fmt_dur() {
  s=${1:-}
  case "$s" in ''|-*|*[!0-9]*) printf '%s' '—'; return ;; esac
  if [ "$s" -lt 60 ]; then printf '%ss' "$s"; return; fi
  m=$((s / 60)); r=$((s % 60))
  if [ "$m" -lt 60 ]; then
    if [ "$r" -gt 0 ]; then printf '%dm %ds' "$m" "$r"; else printf '%dm' "$m"; fi
    return
  fi
  h=$((m / 60)); m=$((m % 60))
  if [ "$m" -gt 0 ]; then printf '%dh %dm' "$h" "$m"; else printf '%dh' "$h"; fi
}

gen=$(num_of generatedAt)
if [ -n "$gen" ]; then age=$((now - gen)); else age=999999; fi

label=$(str_of label)

# Stale: say so instead of rendering old numbers as if they were live.
if [ "$age" -gt "$STALE_S" ]; then
  if [ -n "$gen" ]; then
    printf '⛭ team · stale — no state update in %s%s\n' \
      "$(fmt_dur "$age")" "${label:+ · $label}"
  else
    printf '⛭ team · stale — state carries no timestamp%s\n' "${label:+ · $label}"
  fi
  done_silent
fi

total=$(printf '%s' "$flat" | grep -o '"\{0,1\}stage"\{0,1\}[[:space:]]*:' | wc -l | tr -d ' ')
c_done=$(count_stage done)
c_impl=$(count_stage implementing)
c_review=$(count_stage review)
c_landing=$(count_stage landing)
c_blocked=$(count_stage blocked)

# Progress bar: done cells, then in-flight cells, then remaining.
cells() { [ "$total" -gt 0 ] && echo $(( (BAR_W * $1 + total / 2) / total )) || echo 0; }
d_cells=$(cells "$c_done")
inflight=$((c_impl + c_review + c_landing))
i_cells=$(cells "$inflight")
[ $((d_cells + i_cells)) -gt "$BAR_W" ] && i_cells=$((BAR_W - d_cells))
[ "$i_cells" -lt 0 ] && i_cells=0
r_cells=$((BAR_W - d_cells - i_cells))
bar="▕"
n=0; while [ "$n" -lt "$d_cells" ]; do bar="${bar}█"; n=$((n + 1)); done
n=0; while [ "$n" -lt "$i_cells" ]; do bar="${bar}▓"; n=$((n + 1)); done
n=0; while [ "$n" -lt "$r_cells" ]; do bar="${bar}░"; n=$((n + 1)); done
bar="${bar}▏"

tip=$(printf '%s' "$(str_of tip)" | cut -c1-7)
[ -n "$tip" ] || tip="—"
ahead=$(num_of aheadOfOrigin)
if [ -z "$ahead" ]; then ahead_mark=""
elif [ "$ahead" = "0" ]; then ahead_mark=" ✓sync"
else ahead_mark=" ↑$ahead"; fi

started=$(num_of startedAt)
if [ -n "$started" ]; then elapsed=$(fmt_dur $((now - started))); else elapsed="—"; fi

printf '⛭ team %s/%s %s impl:%s review:%s land:%s blocked:%s · tip %s%s · %s\n' \
  "$c_done" "$total" "$bar" "$c_impl" "$c_review" "$c_landing" "$c_blocked" \
  "$tip" "$ahead_mark" "$elapsed"

# Second line: the most attention-worthy item(s) — the one blocked and/or the one
# in review, with agent, model and stage-elapsed. Omitted when neither exists.
detail=""
rev=$(item_obj review)
if [ -n "$rev" ]; then
  rs=$(ofield "$rev" slug); rp=$(ofield "$rev" priority)
  ra=$(ofield "$rev" agent); rm=$(ofield "$rev" model)
  re=$(since "$(onum "$rev" stageEnteredAt)")
  meta=$(printf '%s' "${rp:-—} · ${ra:-—} · ${rm:-—} · $re")
  detail="review ${rs:-—} ($meta)"
fi
blk=$(item_obj blocked)
if [ -n "$blk" ]; then
  bs=$(ofield "$blk" slug); ba=$(ofield "$blk" agent); bm=$(ofield "$blk" model)
  bn=$(ofield "$blk" note)
  be=$(since "$(onum "$blk" stageEnteredAt)")
  meta=$(printf '%s' "${bn:+$bn · }${ba:-—} · ${bm:-—} · $be")
  bpart="blocked ${bs:-—} ($meta)"
  if [ -n "$detail" ]; then detail="$detail · $bpart"; else detail="$bpart"; fi
fi
[ -n "$detail" ] && printf '  ⛭ %s\n' "$detail"

exit 0
