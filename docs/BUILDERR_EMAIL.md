# Questions for Builderr (send today; answers change the design)

To: inquiries address on https://builderr.ai/guidelines, or ask in their Discord. Subject: Signalpost - runtime contract questions before first submission

Hi Builderr team,

I'm preparing a Signalpost entry (scoring v2). A few runtime details decide how I build it; short answers are plenty.

1. Command contract. Which exact arguments, input path/format, registry snapshot path, output path and environment variables does the official harness pass to my one command? The starter's run_competition_batch.py requires --bulk and defaults --expected-count to 100; will you pass --expected-count 1000-1100, or should the agent ignore it?
2. Budgets and environment. Wall-clock limit per batch, CPU/RAM/disk, outbound network policy (open internet or allowlist? which hosts?), Python version and whether the install step is pip (requirements.txt) or uv.
3. Keys. Will you supply a search API key and an LLM key at run time, and which providers and caps? For NAV Arbeidsplassen's feed, is the public rotating token acceptable, or will you provide a token (credentials tied to my own account aren't allowed)?
4. Envelope keys. Which JSON keys does the harness read for the company-level terminal state (status vs availability vs state) and for claims/evidence? Is a superset envelope that keeps the starter's legacy keys fine?
5. Company-level states. For a company that exists in the registry snapshot, when should the company-level state be available vs not_available vs not_applicable? I plan: available if at least one verified claim exists, not_applicable for deleted/bankrupt/liquidating entities, not_available when everything checked came back empty.
6. UX. How is the UX score assessed: a hosted URL in the submission, a folder generated from the run, or screenshots? Is a static viewer committed to the repo acceptable?
7. Scoring cadence. Do all scheduled daily batches since my first frozen version enter the mean (including early ones), or only batches of the latest version? Is qualification any single official run at 65 or above?
8. Batch edge cases. Can a batch contain duplicate or malformed organisation numbers or numbers missing from the registry snapshot? If so, is one envelope per distinct number the expected behaviour?
9. Refresh. Will the harness give my agent previous envelopes/snapshots for the idempotency check, and in what format?
10. JBOX. What is JBOX and what does "built with JBOX" require for the $500 bonus?

Thanks - name, repo link and contact below.
