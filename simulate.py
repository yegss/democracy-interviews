"""
Pipeline test: let LLM "personas" answer the AI interviewer, to check that the
interviewer probes well and that the analysis step runs end to end.

IMPORTANT: synthetic respondents are NOT data about real people. They are only
a way to stress-test the interviewer and the analysis before real fieldwork.

    python simulate.py              # one interview per persona
    python simulate.py --runs 3     # three interviews per persona
"""

import argparse
import datetime

from interview_core import (MAX_QUESTIONS, OPENING, WRAP_UP_NOTE, chat,
                            interviewer_turn, save_interview)

# Deliberately varied, including "paradoxical" profiles: abstract support for
# democracy combined with willingness to give up its core rules.
PERSONAS = {
    "committed_liberal": "a 26-year-old law student who strongly values courts, minority rights and free media, and argues carefully with examples",
    "frustrated_pragmatist": "a 45-year-old small business owner who says democracy is the best system, but is fed up with slow politics and would quite like someone who 'just gets things done'",
    "populist": "a 52-year-old factory worker who believes politicians and judges ignore ordinary people and that the will of the majority should always win",
    "disengaged": "a 30-year-old who is not interested in politics, gives short answers and often says 'I don't know'",
    "social_democrat": "a 60-year-old retired teacher for whom democracy is mainly about equality, fair wages and public services",
    "order_first": "a 70-year-old who values stability and order above all and is sceptical of protests and constant debate",
}

RESPONDENT_RULES = """You are taking part in a research interview. You are {persona}.
Answer as this real person would in a spoken interview: 1-4 sentences, everyday language, no lists.
Be as consistent or inconsistent as such a person realistically would be. Never mention that you are an AI."""


def respondent_turn(persona, messages):
    """`messages` from the respondent's perspective (user = interviewer)."""
    return chat(RESPONDENT_RULES.format(persona=persona), messages, max_tokens=200)


def run_one(persona_id, persona):
    started = datetime.datetime.now()
    interviewer_msgs = [{"role": "user", "content": OPENING}]
    respondent_msgs = []
    transcript = []

    for turn in range(1, MAX_QUESTIONS + 2):
        question, ended = interviewer_turn(interviewer_msgs)
        transcript.append({"speaker": "interviewer", "text": question})
        interviewer_msgs.append({"role": "assistant", "content": question})
        if ended:
            break

        respondent_msgs.append({"role": "user", "content": question})
        answer = respondent_turn(persona, respondent_msgs)
        respondent_msgs.append({"role": "assistant", "content": answer})
        transcript.append({"speaker": "respondent", "text": answer})
        interviewer_msgs.append({"role": "user",
                                 "content": answer + (WRAP_UP_NOTE if turn >= MAX_QUESTIONS else "")})

    return save_interview(transcript, started,
                          extra={"synthetic": True, "persona": persona_id})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1, help="interviews per persona")
    args = parser.parse_args()

    for persona_id, persona in PERSONAS.items():
        for _ in range(args.runs):
            path = run_one(persona_id, persona)
            print(f"{persona_id:<22} -> {path}")


if __name__ == "__main__":
    main()
