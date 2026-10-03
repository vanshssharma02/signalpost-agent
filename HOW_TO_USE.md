# How to use this pack with Google Antigravity (about 10 minutes to set up)

What you have: AGENTS.md (permanent rules), .agents/workflows/00..07 (one file per phase), reference/ (tested Python helpers), config/strategies.toml, docs/ (master plan, starter traps, the email to Builderr).

## Setup
1. Create the project folder, e.g. `signalpost/`. Unpack Builderr's starter kit into it (so `src/norway_company_agent`, `scripts/`, `tests/`, `pyproject.toml` sit at the root), then copy this pack over it (AGENTS.md, .agents/, reference/, config/, docs/ at the root). Delete the macOS `._*` files.
2. Open that folder in Antigravity as the workspace. Rules in AGENTS.md load automatically (it is the cross-tool rules file Antigravity reads from the repo root; the file is under the 12,000-character limit).
3. In the agent panel type `/` and check that the workflows 00-07 appear. If they do not, rename `.agents/` to `.agent/` (older Antigravity versions use that folder) and try again. As a last resort open the workflow file and paste its contents as the prompt.
4. Keep terminal approval ON for anything that deletes, installs globally or touches the network widely. Never paste real API keys into chat; put them in a local `.env` (gitignored) and tell the agent only the variable names.

## Run the phases, one per conversation
- Conversation 1: "Read AGENTS.md and docs/MASTER_PLAN.md, then run /00-bootstrap."
- When it stops with its acceptance output, read it. Anything red or vague: tell it to fix and re-paste real output. Then new conversation: "Read AGENTS.md. Run /01-eval-harness." and so on through /07-submission.
- Ask for the plan first and read it before approving. Reject any plan that loosens the identity proof, skips tests, edits tests to make them pass, scrapes LinkedIn/Finn/proff or stores search results.
- Label companies when /01 asks you to (about 2 hours total for 150). That is the part that cannot be automated and it protects you from the disqualifying mistake.

## Rules of thumb
- Send the email in docs/BUILDERR_EMAIL.md today. The answers change the CLI, the budget and what keys exist.
- Do not submit v1 until every gate in /07 is green; early weak batches count in your average.
- If the agent says "done" without pasted command output, it is not done.
- Come back to Claude with the pasted acceptance output of each phase for an independent review before moving on.
