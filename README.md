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

You can see the outputs without running anything:
- [`sample-output-live/`](sample-output-live/): Claude's proposals, accepted as they are.
- [`sample-output-offline/`](sample-output-offline/): the keyword rules, with two analyst corrections in the "decision" column.

## Results on the sample notes

[`data/expected.csv`](data/expected.csv) holds the right answer for each note. Check any run against it with:

```bash
python triage.py score out/proposals.csv data/expected.csv
```

| Mode | Class correct | Requirement cited correctly |
|---|---|---|
| Claude (`claude-opus-5-5`) | **12 / 12** | **12 / 12** |
| Offline keyword rules | 10 / 12 | 9 / 12 |

The two notes the keyword rules got wrong are the interesting ones:

- *"Can we also let patients log in with their national ID?"* Rules: Needs clarification (it ends with "?"). Claude: **Change request**, because REQ-01 only allows mobile login. Its impact note named the login screen, the authentication backend, a likely national-ID integration, Arabic/English texts and a privacy review.
- *"The cancel button disappeared 20 hours before the appointment. Is that correct?"* Rules: Needs clarification. Claude: **Not an issue**, because REQ-06 hides the button inside 24 hours, so the system is right.

Twelve notes is a demo, not a benchmark. With real data, I'd score a few hundred past notes before trusting the model, and keep the human decision step either way.

## Design choices

- **Human in the loop by design.** The model proposes; `render` only uses what the analyst approved (a blank decision means "accept the proposal"). The summary counts how many proposals the analyst changed, a simple measure of how far to trust the model.
- **Structured output.** Each answer is validated against a schema (class, baseline ID, reason, impact), so there is no free-text parsing.
- **Cited reasons.** Every proposal names the requirement it relies on, so the analyst can check it in seconds.
- **Prompt caching.** The rules and baseline are identical for every note, so they are cached after the first call.
- **Safe failure.** If the model gives no answer, the note becomes "Needs clarification" instead of a guess.
- **Drafts, not actions.** Nothing is sent or created: Jira gets a CSV to import, emails are drafts.

## What I'd add for real use

A larger evaluation set from real past notes, batch processing for large sessions, and Arabic notes (the model handles them; the offline rules don't).

## Background

I built a fuller version of this at work for a government e-services project. This is a from-scratch public rewrite on invented data. Built with an AI coding agent (Claude Code): I designed the classes, rules and workflow, and reviewed and tested the code.

MIT license.
