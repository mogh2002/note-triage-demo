"""Note triage demo: UAT notes -> Bug / Tweak / CR / Duplicate / Not an issue / Needs clarification.

Two steps, with a human decision in between:

    python triage.py propose data/uat-notes.md data/baseline.json -o out/proposals.csv
    (open out/proposals.csv, fill the "decision" column where you disagree)
    python triage.py render out/proposals.csv data/baseline.json -o out/

`propose` asks Claude for a class, the baseline item it relies on, and a reason.
Add --offline to use simple keyword rules instead (no API key, for trying it out).
`render` uses the analyst's decision when given, else the proposal, and writes
a Jira import CSV, change-request email drafts, clarification questions and a summary.
"""

import argparse
import csv
import json
import re
import sys
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

MODEL = "claude-opus-5-5"


class NoteClass(str, Enum):
    BUG = "Bug"
    TWEAK = "Tweak"
    CR = "Change request"
    DUPLICATE = "Duplicate"
    NOT_AN_ISSUE = "Not an issue"
    CLARIFY = "Needs clarification"


class Proposal(BaseModel):
    note_class: NoteClass
    baseline_id: str = Field(description="Requirement or known-issue ID this decision relies on, or 'none'")
    reason: str = Field(description="One sentence, citing the baseline")
    impact: str = Field(description="For a change request: what it touches (screens, integrations, effort). Else empty.")


RULES = """You triage notes from a user acceptance test (UAT) session.
Classify the note against the BASELINE (the signed requirements) and the KNOWN ISSUES, using exactly one class:

- Bug: the system does not do what a requirement says.
- Tweak: a small change inside a requirement's intent (wording, label, a missing validation the requirement implies).
- Change request: the client wants something no requirement says, or says differently.
- Duplicate: the same problem is already in KNOWN ISSUES.
- Not an issue: the system works as a requirement says; the note is a misunderstanding.
- Needs clarification: you cannot decide without asking the client.

Decide in this order: duplicate? -> find the requirement (none -> change request, or needs clarification if unsure)
-> does the system match it? (no -> bug) -> wants it different (small -> tweak, else change request)
-> client misunderstood -> not an issue.
Cite the ID you relied on. Keep the reason to one sentence. Fill impact only for a change request."""


def read_notes(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [l.lstrip("-* ").strip() for l in lines if re.match(r"^\s*[-*]\s+\S", l)]


def baseline_text(baseline: dict) -> str:
    reqs = "\n".join(f"{r['id']} [{r['screen']}]: {r['text']}" for r in baseline["requirements"])
    issues = "\n".join(f"{i['id']}: {i['title']}" for i in baseline.get("known_issues", []))
    return f"BASELINE\n{reqs}\n\nKNOWN ISSUES\n{issues or '(none)'}"


def propose_with_claude(notes: list[str], baseline: dict) -> list[Proposal]:
    import anthropic

    client = anthropic.Anthropic()
    # The rules and baseline are the same for every note, so they are cached after the first call.
    system = [{"type": "text", "text": RULES + "\n\n" + baseline_text(baseline),
               "cache_control": {"type": "ephemeral"}}]
    out = []
    for i, note in enumerate(notes, 1):
        print(f"  [{i}/{len(notes)}] {note[:60]}", file=sys.stderr)
        # fallbacks="default": if the model declines, the API retries on a fallback model in the same call.
        response = client.beta.messages.parse(
            model=MODEL,
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": f"NOTE: {note}"}],
            output_format=Proposal,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal" or response.parsed_output is None:
            out.append(Proposal(note_class=NoteClass.CLARIFY, baseline_id="none",
                                reason="The model gave no answer; decide by hand.", impact=""))
        else:
            out.append(response.parsed_output)
    return out


def propose_offline(notes: list[str], baseline: dict) -> list[Proposal]:
    """Crude keyword rules, only so the demo runs without an API key."""
    stop = {"the", "a", "is", "it", "to", "and", "of", "in", "on", "for", "be", "should", "can", "we", "also"}

    def words(s):
        return {w for w in re.findall(r"[a-z]+", s.lower()) if w not in stop and len(w) > 2}

    out = []
    for note in notes:
        nw = words(note)
        dup = max(baseline.get("known_issues", []), key=lambda i: len(nw & words(i["title"])), default=None)
        if dup and len(nw & words(dup["title"])) >= 3:
            out.append(Proposal(note_class=NoteClass.DUPLICATE, baseline_id=dup["id"],
                                reason=f"Matches known issue {dup['id']}.", impact=""))
            continue
        req = max(baseline["requirements"], key=lambda r: len(nw & words(r["text"] + " " + r["screen"])))
        overlap = len(nw & words(req["text"] + " " + req["screen"]))
        low = note.lower()
        if re.search(r"not sure|what should happen|\?$", low):
            cls = NoteClass.CLARIFY
        elif overlap < 2 or re.search(r"\b(also|instead|should be able|let patients)\b", low):
            cls = NoteClass.CR
        elif re.search(r"label|wording|change it to|spelling", low):
            cls = NoteClass.TWEAK
        else:
            cls = NoteClass.BUG
        out.append(Proposal(note_class=cls, baseline_id=req["id"] if overlap >= 2 else "none",
                            reason=f"Keyword match with {req['id']} (offline rules, check by hand).",
                            impact="Estimate needed." if cls == NoteClass.CR else ""))
    return out


def cmd_propose(args):
    notes = read_notes(args.notes)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    proposals = (propose_offline if args.offline else propose_with_claude)(notes, baseline)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["n", "note", "proposed_class", "baseline_id", "reason", "impact", "decision"])
        for i, (note, p) in enumerate(zip(notes, proposals), 1):
            w.writerow([i, note, p.note_class.value, p.baseline_id, p.reason, p.impact, ""])
    print(f"Wrote {args.out}. Review it: put a class in 'decision' where you disagree, then run render.")


def cmd_render(args):
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    reqs = {r["id"]: r for r in baseline["requirements"]}
    valid = {c.value for c in NoteClass}
    with args.proposals.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["final"] = (r["decision"] or r["proposed_class"]).strip()
        if r["final"] not in valid:
            sys.exit(f"Row {r['n']}: '{r['final']}' is not one of: {', '.join(sorted(valid))}")

    out = args.out
    (out / "cr-drafts").mkdir(parents=True, exist_ok=True)

    with (out / "jira-import.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Summary", "Issue Type", "Priority", "Description", "Labels"])
        for r in rows:
            if r["final"] in ("Bug", "Tweak"):
                w.writerow([r["note"][:120], "Bug" if r["final"] == "Bug" else "Task",
                            "Medium" if r["final"] == "Bug" else "Low",
                            f"UAT note {r['n']}: {r['note']}\nBaseline: {r['baseline_id']}\nWhy: {r['reason']}",
                            f"uat {r['final'].lower()}"])

    crs = [r for r in rows if r["final"] == "Change request"]
    for k, r in enumerate(crs, 1):
        related = reqs.get(r["baseline_id"])
        (out / "cr-drafts" / f"CR-{k:02d}.md").write_text(
            f"Subject: Change request CR-{k:02d} from UAT\n\n"
            f"Hello,\n\nDuring UAT the client asked for the following, which is not in the signed requirements:\n\n"
            f"> {r['note']}\n\n"
            f"Closest requirement: {r['baseline_id']}" + (f" ({related['text']})" if related else "") + "\n"
            f"Why it is a change: {r['reason']}\n"
            f"Impact: {r['impact'] or 'to be estimated'}\n\n"
            f"Please confirm whether to estimate it. No work starts before approval.\n\n(DRAFT: review before sending)\n",
            encoding="utf-8")

    questions = [r for r in rows if r["final"] == "Needs clarification"]
    counts = {c.value: sum(r["final"] == c.value for r in rows) for c in NoteClass}
    overridden = sum(bool(r["decision"]) and r["decision"] != r["proposed_class"] for r in rows)
    lines = [f"# Triage summary: {baseline['project']}", "",
             f"{len(rows)} notes · {overridden} proposals changed by the analyst", "",
             "| Class | Notes |", "|---|---|"] + [f"| {c} | {n} |" for c, n in counts.items()]
    if questions:
        lines += ["", "## Questions for the client"] + [f"{i}. {r['note']}" for i, r in enumerate(questions, 1)]
    lines += ["", "## All notes", "| # | Note | Class | Baseline |", "|---|---|---|---|"]
    lines += [f"| {r['n']} | {r['note']} | {r['final']} | {r['baseline_id']} |" for r in rows]
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out}/jira-import.csv, {len(crs)} CR drafts, summary.md")


def cmd_score(args):
    with args.expected.open(encoding="utf-8-sig") as f:
        expected = {r["n"]: r for r in csv.DictReader(f)}
    with args.proposals.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    misses = [r for r in rows if r["proposed_class"] != expected[r["n"]]["expected_class"]]
    cited = sum(r["baseline_id"] == expected[r["n"]]["expected_baseline_id"] for r in rows)
    print(f"Class correct: {len(rows) - len(misses)}/{len(rows)}, baseline ID correct: {cited}/{len(rows)}")
    for r in misses:
        print(f"  note {r['n']}: proposed {r['proposed_class']}, expected {expected[r['n']]['expected_class']}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("propose", help="AI proposes a class for each note")
    a.add_argument("notes", type=Path)
    a.add_argument("baseline", type=Path)
    a.add_argument("-o", "--out", type=Path, default=Path("out/proposals.csv"))
    a.add_argument("--offline", action="store_true", help="keyword rules instead of Claude")
    a.set_defaults(func=cmd_propose)
    b = sub.add_parser("render", help="build outputs from the reviewed proposals")
    b.add_argument("proposals", type=Path)
    b.add_argument("baseline", type=Path)
    b.add_argument("-o", "--out", type=Path, default=Path("out"))
    b.set_defaults(func=cmd_render)
    c = sub.add_parser("score", help="compare proposals with known answers")
    c.add_argument("proposals", type=Path)
    c.add_argument("expected", type=Path)
    c.set_defaults(func=cmd_score)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
