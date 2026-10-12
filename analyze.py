"""
Analyse saved interviews in two ways and compare them:

1. Dictionary coding - which conception of democracy a respondent uses
   (procedural / liberal / social / output), counted per 100 words.
2. LLM coding (optional) - an LLM reads the whole transcript and rates
   conception, elaboration, abstract vs. concrete support, and whether support
   looks "meaningful" or "superficial" (democrat in name only).

The comparison is the point: a dictionary only finds what its authors put in
it; the LLM coder can pick up reasoning and contradictions, but needs to be
validated against human coding before it can be trusted.

    python analyze.py                  # dictionary + LLM coding (needs API key)
    python analyze.py --no-llm         # dictionary only, works offline
    python analyze.py --folder examples
"""

import argparse
import csv
import glob
import json
import os
import re

# Word stems per conception of democracy (English; extend for other languages).
DICTIONARY = {
    "procedural": ["elect", "vote", "voting", "ballot", "majority", "represent", "parliament", "parties"],
    "liberal": ["right", "freedom", "free speech", "court", "constitution", "minorit",
                "independen", "checks", "separation", "rule of law", "press"],
    "social": ["equal", "fair", "poverty", "welfare", "wage", "pension", "school",
               "health", "public service"],
    "output": ["efficien", "result", "deliver", "get things done", "faster", "stability",
               "order", "strong leader", "solve"],
}

CODER_PROMPT = """You are coding a research interview about democracy. Read the transcript and return ONLY a JSON object with these keys:
"conception": the respondent's dominant conception of democracy, one of "procedural", "liberal", "social", "output", "none";
"elaboration": 1-5, how much the respondent gives reasons and concrete examples (1 = none, 5 = rich);
"abstract_support": 1-5, how strongly they endorse democracy in the abstract;
"concrete_support": 1-5, how strongly they stick to democratic rules in the concrete trade-off questions (courts vs. majority, strong leader);
"classification": "meaningful" (support is coherent and holds up in the trade-offs), "superficial" (endorses democracy in the abstract but gives up its rules in concrete cases, or cannot say what it means), or "unclear";
"evidence": a list of at most 2 short quotes from the respondent that support your classification.

Transcript:
{transcript}"""


def load_interviews(folder):
    interviews = []
    for path in sorted(glob.glob(os.path.join(folder, "*.json"))):
        with open(path, encoding="utf-8") as f:
            record = json.load(f)
        record["file"] = os.path.basename(path)
        interviews.append(record)
    return interviews


def respondent_text(record):
    return " ".join(t["text"] for t in record["transcript"] if t["speaker"] == "respondent")


def dictionary_code(text):
    lowered = text.lower()
    n_words = max(len(re.findall(r"\w+", lowered)), 1)
    scores = {}
    for category, terms in DICTIONARY.items():
        # word-boundary at the start, so 'right' matches 'rights' but not 'bright'
        hits = sum(len(re.findall(r"\b" + re.escape(term), lowered)) for term in terms)
        scores[category] = round(100 * hits / n_words, 2)
    dominant = max(scores, key=scores.get) if any(scores.values()) else "none"
    return scores, dominant, n_words


def llm_code(record):
    from interview_core import chat, extract_json
    transcript = "\n".join(f"{t['speaker'].upper()}: {t['text']}" for t in record["transcript"])
    raw = chat("You are a careful qualitative coder. Reply with JSON only.",
               [{"role": "user", "content": CODER_PROMPT.format(transcript=transcript)}],
               max_tokens=500)
    coded = extract_json(raw)
    return coded if isinstance(coded, dict) else {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", default="interviews")
    parser.add_argument("--no-llm", action="store_true", help="dictionary coding only")
    parser.add_argument("--out", default="results.csv")
    args = parser.parse_args()

    interviews = load_interviews(args.folder)
    if not interviews:
        print(f"No interviews found in '{args.folder}'.")
        return

    use_llm = not args.no_llm

    rows = []
    for record in interviews:
        scores, dominant, n_words = dictionary_code(respondent_text(record))
        row = {"file": record["file"], "persona": record.get("persona", ""),
               "words": n_words, "dict_conception": dominant,
               **{f"dict_{k}": v for k, v in scores.items()}}
        if use_llm:
            coded = llm_code(record)
            row.update({f"llm_{k}": (json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v)
                        for k, v in coded.items()})
        rows.append(row)

    fields = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0]).index(k) if k in rows[0] else 99)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{'file':<34} {'persona':<22} {'dictionary':<11} {'llm':<11} classification")
    for r in rows:
        print(f"{r['file']:<34} {r['persona']:<22} {r['dict_conception']:<11} "
              f"{str(r.get('llm_conception', '-')):<11} {r.get('llm_classification', '-')}")

    if use_llm:
        pairs = [(r["dict_conception"], r.get("llm_conception")) for r in rows if r.get("llm_conception")]
        if pairs:
            agree = sum(a == b for a, b in pairs) / len(pairs)
            print(f"\nDictionary vs. LLM agreement on conception: {agree:.0%} ({len(pairs)} interviews)")
    print(f"Results written to {args.out}")


if __name__ == "__main__":
    main()
