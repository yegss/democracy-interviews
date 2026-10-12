"""
Run one AI interview in the terminal, with you (or a test participant) as respondent.

    python interviewer.py          # type 'exit' to stop early
"""

import datetime

from interview_core import (MAX_QUESTIONS, OPENING, WRAP_UP_NOTE,
                            interviewer_turn, save_interview)


def main():
    started = datetime.datetime.now()
    messages = [{"role": "user", "content": OPENING}]
    transcript = []
    turns = 0

    while True:
        text, ended = interviewer_turn(messages)
        turns += 1
        print(f"\nInterviewer: {text}")
        transcript.append({"speaker": "interviewer", "text": text})
        messages.append({"role": "assistant", "content": text})
        if ended:
            break

        answer = input("\nYou: ").strip()
        if answer.lower() in ("exit", "quit"):
            break
        transcript.append({"speaker": "respondent", "text": answer})
        # The wrap-up note goes only to the model, never into the saved transcript.
        messages.append({"role": "user",
                         "content": answer + (WRAP_UP_NOTE if turns >= MAX_QUESTIONS else "")})

    path = save_interview(transcript, started, extra={"synthetic": False})
    print(f"\nTranscript saved to {path}")


if __name__ == "__main__":
    main()
