---
name: code
description: Closed-loop coding via specialized subagents — use for any multi-file or delegatable code change. Main context writes a work order, sf-py-coder/sf-bash-coder executes with a mandatory oracle, sf-reviewer adversarially checks, bounded repair loop. Keeps exploration and bulk edits out of the main context.
---

# code — the closed coding loop

Run every delegated code change through this pipeline. The main context does
the THINKING (scoping, context curation, design); subagents do the dirty work.
Never let an executor explore.

## Pipeline

1. **Write the work order** (main context, before any spawn):
   - GOAL — one sentence
   - FILES — exact paths
   - CHANGE — edit spec, diff-level precision
   - CONTEXT — paste the exact snippets the executor needs (signatures,
     surrounding code, API payload shapes). The executor will NOT explore;
     missing context = BLOCKED round-trip, so curate properly.
   - ORACLE — the real check command (`bash -n`, pyright, pytest, a probe)
   - ACCEPTANCE — observable truth when done
   Keep each order small: one concern, roughly ≤300 changed lines. Bigger task
   = chain of orders, sequenced in main context.

2. **Route** by file type: `*.sh` → `sf-bash-coder`; `*.py` → `sf-py-coder`;
   mixed concern → split into two orders. Spawn via the Agent tool
   (`subagent_type` = agent name). Subagents are sonnet — never opus/fable.

3. **Check the return**: oracle output must be present and verbatim-plausible.
   Missing/failed oracle = treat as BLOCKED, do not pass to review.

4. **Review**: spawn `sf-reviewer` with the order + diff + oracle output.
   Fresh agent every time — never reuse the coder's conversation.

5. **Repair loop**: REJECT findings go back to the SAME coder type as a new
   work order quoting the findings verbatim. Max 2 repair rounds; still
   failing → main context takes over the change itself (escalation, not
   retry #3).

6. **Report** to the user: what changed, oracle result, reviewer verdict —
   short. Do not re-expand subagent transcripts into main context.

## Learning rule

When a coder repeats a mistake class or the reviewer finds something the
doctrine should have prevented: append ONE line to the relevant agent's
Doctrine section (`.claude/agents/sf-*-coder.md`). Doctrine only grows from
real failures, never speculation.

## Escalation ladder

haiku (not used here) → sonnet coders (execution) → main context (design,
ambiguity, twice-failed repairs). Route ambiguity UP before spawning, not
after a failed round-trip.
