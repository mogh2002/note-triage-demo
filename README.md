# note-triage-demo

After a user acceptance test (UAT), the client leaves a pile of notes. Some are bugs, some are small tweaks, some are new requests in disguise. Sorting them by hand is slow, and getting it wrong is expensive: a change request logged as a bug hides scope growth, and a bug logged as a change request makes the client pay for your defect.

This demo sorts each note against the **baseline** (the signed requirements) with an LLM, then **a human decides**. Only approved results become Jira tickets and change-request drafts.

```
uat-notes.md ─┐                        ┌──────────────── analyst ───────────────┐
              ├─► propose (Claude) ─► proposals.csv ─► fills "decision" ─► render ─┬─► jira-import.csv
baseline.json ┘                                                                 ├─► cr-drafts/CR-01.md …
                                                                                ├─► summary.md (+ questions for the client)
```

**All data here is made up** (a fictional clinic booking portal).

## The classes

| Class | Test | Goes to |
|---|---|---|
| Bug | The system does not do what a requirement says | Jira (Bug) |
| Tweak | Small change inside a requirement's intent | Jira (Task) |
| Change request | Not in the requirements, or wanted differently | CR email draft: estimate and approval first |
| Duplicate | Already a known issue | Linked, not re-logged |
| Not an issue | Works as specified | Reply to the client with the requirement |
| Needs clarification | Can't decide without asking | Question list for the client |

The full decision order is in the prompt in [`triage.py`](triage.py) and in my [note triage guide](https://github.com/mogh2002/ba-pm-templates/blob/main/templates/note-triage-guide.md).

## Run it

```bash
pip install -r requirements.txt

# 1. Propose (needs ANTHROPIC_API_KEY). Add --offline to try it with keyword rules and no key.
python triage.py propose data/uat-notes.md data/baseline.json -o out/proposals.csv

# 2. Open out/proposals.csv. Where you disagree, write the right class in the "decision" column.

# 3. Render
python triage.py render out/proposals.csv data/baseline.json -o out/
```

[`sample-output/`](sample-output/) shows the result of the offline mode with two analyst corrections, so you can see the outputs without running anything.

## Design choices

- **Human in the loop by design.** The model proposes; `render` only uses what the analyst approved (a blank decision means "accept the proposal"). The summary counts how many proposals the analyst changed, a simple measure of how far to trust the model.
- **Structured output.** Each answer is validated against a schema (class, baseline ID, reason, impact), so there is no free-text parsing.
- **Cited reasons.** Every proposal names the requirement it relies on, so the analyst can check it in seconds.
- **Prompt caching.** The rules and baseline are identical for every note, so they are cached after the first call.
- **Safe failure.** If the model gives no answer, the note becomes "Needs clarification" instead of a guess.
- **Drafts, not actions.** Nothing is sent or created: Jira gets a CSV to import, emails are drafts.

## What I'd add for real use

An evaluation set of past notes with known answers (to measure accuracy before trusting the model), batch processing for large sessions, and Arabic notes (the model handles them; the offline rules don't).

## Background

I built a fuller version of this at work for a government e-services project. This is a from-scratch public rewrite on invented data. Built with an AI coding agent (Claude Code): I designed the classes, rules and workflow, and reviewed and tested the code.

MIT license.
