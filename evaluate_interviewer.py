"""
Evaluate how well the AI interviewer follows interviewing guidelines,
using the violation categories from Wuttke et al. (2025):

  multiple_questions  - more than one question in a single turn
  leading             - suggests answers, associations or examples
  judgmental          - praises, evaluates or agrees ("great point")
  missed_followup     - previous answer was vague/surprising/unclear, but the
                        interviewer moved on without probing (the most common
                        AI failure in their study)
  restated            - positive behaviour: restates the respondent's words

Two checks run side by side: a cheap rule-based check (question marks, praise
words) and an LLM judge. Comparing them shows where simple rules are enough.

    python evaluate_interviewer.py
    python evaluate_interviewer.py --no-llm      # rule-based only, offline
"""

import argparse
import csv
import glob
import json
import os
import re

CATEGORIES = ["multiple_questions", "leading", "judgmental", "missed_followup", "restated"]
PRAISE = re.compile(r"\b(great|interesting|insightful|excellent|good point|i agree|wonderful|fascinating)\b", re.I)

JUDGE_PROMPT = """You are auditing an AI research interviewer. Below is an interview with numbered INTERVIEWER turns.
For EVERY interviewer turn except the first greeting, decide whether it shows each behaviour:
- "multiple_questions": asks more than one distinct question
- "leading": suggests possible answers, associations or examples
- "judgmental": praises, evaluates or agrees with the respondent's answer
- "missed_followup": the respondent's previous answer was vague, very short, surprising or unclear, but this turn moves to a new topic instead of probing
- "restated": briefly restates what the respondent said in their own words

Return ONLY a JSON array, one object per audited turn, e.g.
[{{"turn": 2, "multiple_questions": false, "leading": false, "judgmental": false, "missed_followup": true, "restated": false}}]

Interview:
{transcript}"""


def numbered_transcript(transcript):
    lines, n = [], 0
    for t in transcript:
        if t["speaker"] == "interviewer":
            n += 1
            lines.append(f"[INTERVIEWER turn {n}] {t['text']}")
        else:
            lines.append(f"[RESPONDENT] {t['text']}")
    return "\n".join(lines)


def rule_check(transcript):
    turns = [t["text"] for t in transcript if t["speaker"] == "interviewer"][1:]
    return {
        "rule_multiple_questions": sum(t.count("?") > 1 for t in turns),
        "rule_judgmental": sum(bool(PRAISE.search(t)) for t in turns),
        "interviewer_turns": len(turns),
    }


def llm_check(transcript):
    from interview_core import chat, extract_json
    raw = chat("You are a strict, careful auditor. Reply with JSON only.",
               [{"role": "user", "content": JUDGE_PROMPT.format(transcript=numbered_transcript(transcript))}],
               max_tokens=1500)
    judged = extract_json(raw)
    if not isinstance(judged, list):
        return {}
    return {f"llm_{c}": sum(bool(item.get(c)) for item in judged if isinstance(item, dict))
            for c in CATEGORIES}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", default="interviews")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--out", default="interviewer_eval.csv")
    args = parser.parse_args()

    paths = sorted(glob.glob(os.path.join(args.folder, "*.json")))
    if not paths:
        print(f"No interviews found in '{args.folder}'.")
        return

    rows = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            record = json.load(f)
        row = {"file": os.path.basename(path), "persona": record.get("persona", ""),
               **rule_check(record["transcript"])}
        if not args.no_llm:
            row.update(llm_check(record["transcript"]))
        rows.append(row)

    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    total_turns = sum(r["interviewer_turns"] for r in rows) or 1
    print(f"Interviews: {len(rows)}, audited interviewer turns: {total_turns}")
    print(f"Rule-based  multiple questions: {sum(r['rule_multiple_questions'] for r in rows)}"
          f" | praise/judgment: {sum(r['rule_judgmental'] for r in rows)}")
    if not args.no_llm:
        for c in CATEGORIES:
            n = sum(r.get(f"llm_{c}", 0) for r in rows)
            print(f"LLM judge   {c:<19} {n:>3}  ({n / total_turns:.0%} of turns)")
    print(f"Results written to {args.out}")


if __name__ == "__main__":
    main()
