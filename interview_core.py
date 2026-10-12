"""
Shared logic: interview guide, interviewer prompt, and a small model wrapper
that works with either the Anthropic API or any OpenAI-compatible endpoint
(e.g. a local open-weight model served by Ollama).

Choose the backend with environment variables:
    BACKEND=anthropic      (default) needs ANTHROPIC_API_KEY
    BACKEND=openai         any OpenAI-compatible server, e.g. Ollama:
                           BASE_URL=http://localhost:11434/v1  MODEL=llama3.2:3b
"""

import datetime
import json
import os
import urllib.request

BACKEND = os.environ.get("BACKEND", "anthropic")
MODEL = os.environ.get("MODEL", "claude-haiku-4-5-20251001" if BACKEND == "anthropic" else "llama3.2:3b")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:11434/v1")
MAX_QUESTIONS = 12   # after this many interviewer turns the interview is wrapped up
END_TOKEN = "[END]"

# From abstract to concrete on purpose: abstract support for democracy is
# near-universal, so the interesting variation is whether it survives trade-offs.
INTERVIEW_GUIDE = """\
1. ABSTRACT: What does democracy mean to you personally?
2. EXPERIENCE: Can you think of a concrete situation where you felt democracy was working - or not working?
3. TRADE-OFF (courts vs. majority): An elected government with broad public support passes a law, and the constitutional court strikes it down as unconstitutional. Who should have the final say, and why?
4. TRADE-OFF (strong leader): Would you accept a strong leader who does not have to bother with parliament and elections, if it meant problems got solved faster?
5. BOUNDARY: What would have to change for your country to no longer be a democracy?"""

# Guidelines follow established qualitative interviewing practice, as used by
# Wuttke et al. (2025). The explicit probing check targets the failure mode they
# found most often in AI interviewers: moving on without a needed follow-up.
SYSTEM_PROMPT = f"""You are a skilled qualitative research interviewer for a political science study on what democracy means to ordinary people.

Interview guide (cover all topics, in this order):
{INTERVIEW_GUIDE}

Before every message, silently check the respondent's last answer:
- Is it vague, abstract, very short, surprising, or does it seem to contradict something they said earlier?
- If yes, and you have not already asked two follow-ups on this topic, ask ONE follow-up instead of moving on. Useful probes: "Why is that?", "Could you say more about that?", "Can you give me an example?", "What do you mean by '<their word>'?" For an apparent contradiction, ask neutrally how the two views fit together.
- If no, move to the next guide topic.

Rules:
- Every message contains exactly ONE question mark. Never add a second question, not even a short one like "Why?".
- Ask each guide question in close to its original wording. After at most two follow-ups on a topic, move on to the next guide topic.
- Topics 3 and 4 are the core of this study. Never end the interview before you have asked both.
- Stay on the guide. If the respondent drifts to an unrelated subject (work, business, private life), bring them back to the current guide topic.
- Do not lead: never suggest answers, associations or examples of what they might say.
- Stay neutral: never praise, evaluate or agree with an answer, also not at the end (no "great point", "interesting", "helpful", "insightful", "I agree"). "Thank you" is the only acknowledgement allowed.
- When you restate, use only words the respondent actually used. Never add values, motives or conclusions they did not state, and never soften what they said.
- Write only the words you say to the respondent: no notes, labels or text in brackets.
- Keep a casual, friendly, professional tone and plain language.
- Reply in the language the respondent uses.
- When all topics are covered, or when told the interview is ending, say "Thank you" and end your message with the exact token {END_TOKEN}.
"""

OPENING = "(The respondent has joined. Greet them in one sentence and ask your first question.)"
WRAP_UP_NOTE = ("\n\n(Note for the interviewer: this was the final answer. "
                "Thank the respondent briefly and end the interview.)")


def chat(system, messages, max_tokens=300):
    """One model call. `messages` alternate user/assistant and start with user."""
    if BACKEND == "anthropic":
        import anthropic
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        response = client.messages.create(model=MODEL, max_tokens=max_tokens,
                                          system=system, messages=messages)
        return response.content[0].text.strip()

    # OpenAI-compatible chat completions (Ollama, LM Studio, vLLM, hosted providers)
    payload = {"model": MODEL, "max_tokens": max_tokens,
               "messages": [{"role": "system", "content": system}] + messages}
    request = urllib.request.Request(
        BASE_URL.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + os.environ.get("OPENAI_API_KEY", "none")},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        body = json.load(response)
    return body["choices"][0]["message"]["content"].strip()


def interviewer_turn(messages):
    """Next interviewer message. `messages`: assistant = interviewer, user = respondent.
    Returns (text, ended)."""
    text = chat(SYSTEM_PROMPT, messages)
    ended = END_TOKEN in text
    return text.replace(END_TOKEN, "").strip(), ended


def save_interview(transcript, started, extra=None, folder="interviews"):
    os.makedirs(folder, exist_ok=True)
    record = {
        "backend": BACKEND, "model": MODEL,
        "started": started.isoformat(timespec="seconds"),
        "ended": datetime.datetime.now().isoformat(timespec="seconds"),
        **(extra or {}),
        "transcript": transcript,
    }
    path = os.path.join(folder, f"interview_{started:%Y%m%d_%H%M%S_%f}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return path


def extract_json(raw):
    """Parse the first JSON object or array in a model reply; None if impossible."""
    import re
    match = re.search(r"(\{.*\}|\[.*\])", raw, re.DOTALL)
    try:
        return json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        return None
