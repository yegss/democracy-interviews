# What does democracy mean to people? — an AI interviewing prototype

A small prototype of **AI Conversational Interviewing** for democracy research: an LLM conducts a semi-structured interview, probes what respondents actually say, and the transcripts are analysed with text-as-data methods. A separate script audits the interviewer itself.

It builds on Wuttke et al. (2025), *AI Conversational Interviewing: Transforming Surveys with LLMs as Adaptive Interviewers* (LaTeCH-CLfL @ NAACL). This is a personal learning project, not a reproduction of that work.

## The research question behind it

Abstract support for democracy is almost universal in surveys. The open question is whether that support is **meaningful**, i.e. whether it holds up when democratic rules become costly. The interview guide therefore moves from abstract to concrete:

1. What does democracy mean to you?
2. A situation where democracy worked or failed
3. **Trade-off:** a popular law struck down by the constitutional court: who should have the final say?
4. **Trade-off:** a strong leader who bypasses parliament but solves problems faster
5. What would make your country stop being a democracy?

Question 3 connects to my M.A. thesis on democratic backsliding and judicial resistance: attitudes towards courts checking majorities are a hard test of whether support for liberal democracy is more than a label.

## Design choices taken from Wuttke et al. (2025)

| Finding in the paper | What this prototype does |
|---|---|
| The AI interviewer's most frequent failure was **missing follow-ups** on vague or surprising answers | The prompt adds an explicit check before every turn: probe (max. two follow-ups per topic) or move on |
| The AI sometimes **praised answers**, breaking neutrality | Explicit ban on praise and agreement; rule-based and LLM audit of every turn |
| Guidelines should come from **established interviewing practice** | Single question per turn, non-leading probes, neutral tone, occasional restating in the respondent's own words |
| **Voice input** caused transcription errors and drop-outs; spoken answers were longer but less elaborate | Text-only for now; voice is a possible extension, not a default |
| A closed model limits **replicability**; open models are named as future work | Model-agnostic: runs on the Claude API or any OpenAI-compatible endpoint, including local open-weight models via Ollama |
| An **analysis pipeline** for AI-collected text is named as future work | `analyze.py` compares dictionary coding with LLM coding |

## Files

| File | What it does |
|---|---|
| `interview_core.py` | Interview guide, interviewer prompt, model wrapper (Claude API or open models) |
| `interviewer.py` | Run a live interview in the terminal (a human answers) |
| `simulate.py` | Let LLM personas answer, to stress-test the interviewer and pipeline |
| `evaluate_interviewer.py` | Audit interviewer turns: multiple questions, leading, judgmental, missed follow-ups, restating |
| `analyze.py` | Dictionary coding + LLM coding of respondents, and their agreement |
| `examples/` | Two hand-written transcripts for testing offline |

## Run it

```bash
pip install -r requirements.txt

# Option A: Claude API
export ANTHROPIC_API_KEY="..."          # never commit your key

# Option B: local open-weight model (free), e.g. with Ollama
#   ollama pull llama3.2:3b
export BACKEND=openai
export BASE_URL=http://localhost:11434/v1
export MODEL=llama3.2:3b

python interviewer.py                   # interview yourself
python simulate.py --runs 2             # 2 synthetic interviews per persona
python evaluate_interviewer.py          # how well did the interviewer behave?
python analyze.py                       # what did respondents say?

# offline checks, no model needed
python analyze.py --folder examples --no-llm
python evaluate_interviewer.py --folder examples --no-llm
```

On Windows use `set NAME=value` (cmd) or `$env:NAME="value"` (PowerShell) instead of `export`.

## First results (12 October 2026)

> **All respondents below are synthetic.** They are LLM personas from `simulate.py`, not people. These runs test the interviewer and the pipeline; they say nothing about what anyone thinks about democracy.

**Setup.** Local open-weight model `qwen2.5:3b` via Ollama 0.40.0 on a laptop GPU (GTX 1650 Ti, 4 GB). The same model plays interviewer, respondent personas, LLM judge and LLM coder. 6 personas × 2 runs = 12 interviews per round, 144 audited interviewer turns per round. Round *before* uses the original prompt, round *after* a revised prompt (both prompts are saved next to the results). Everything is in [`results/`](results/).

**Pilot.** Before the main runs I read three pilot interviews with `llama3.2:3b` ([`results/pilot_llama3.2_3b/`](results/pilot_llama3.2_3b/)). 12 of its 27 turns (not counting greeting and closing) were restatements without a question, it twice put words into the respondent's mouth (e.g. turning "someone who's not afraid to break the rules" into a leader acting "in a more democratic and accountable way", which the persona then accepted), it leaked notes like "[Starting a new topic]", and one interview ended after seven questions without ever asking guide topics 2, 3 and 5. I switched to `qwen2.5:3b`.

**Interviewer audit, before → after the prompt revision**

| Measure (144 turns per round) | Before | After |
|---|---|---|
| Rule-based: turns with more than one `?` | 27 (19%) | 25 (17%) |
| Rule-based: praise words ("great", "interesting", "insightful", …) | 7 (5%) | 11 (8%) |
| LLM judge: multiple questions | 15 | 13 |
| LLM judge: leading | 1 | 0 |
| LLM judge: judgmental | 1 | 6 |
| LLM judge: missed follow-up | 2 | 2 |
| LLM judge: restated | 0 | 0 |
| Interviews that asked guide topic 3 (courts vs. majority)* | 3 / 12 | 4 / 12 |
| Interviews that asked guide topic 4 (strong leader)* | 3 / 12 | 1 / 12 |
| Interviews that asked guide topic 5 (boundary)* | 1 / 12 | 1 / 12 |
| Interviews that ended only at the 12-question limit | 12 / 12 | 12 / 12 |

\* Rough keyword check on interviewer turns: topic 3 = "court"; topic 4 = "leader" plus "parliament" or "election"; topic 5 = "no longer", "stop being" or "cease". It can count a topic as asked when it was only touched on, so it overstates coverage.

The revision targeted what I saw in the *before* transcripts: one question mark per message, at most two follow-ups per topic, topics 3 and 4 must be asked, stay on the guide, no praise (also not when closing), restate only in the respondent's own words, no bracketed notes. It did not work: the numbers barely moved and praise went up.

**Dictionary vs. LLM coding.** Agreement on the dominant conception of democracy was 33% (12 interviews) before and 27% (11 interviews; one LLM reply was not parseable JSON) after. This is not real agreement: the LLM coder labelled **every** interview it coded as `procedural` and `meaningful`, including the populist and disengaged personas, so the figure is just the share of interviews the dictionary also called procedural.

**Observations**

1. **A 3B model does not follow a long rule list.** Prompt revision alone did not fix multiple questions, praise or guide coverage. In one *after* interview the interviewer stopped interviewing and wrote a numbered policy proposal of its own. The next iteration should change structure rather than wording: let code track which guide topic is due and pass only that topic to the model, reject turns with more than one `?`, or compare against a larger model.
2. **The interviewer shapes what the analysis finds.** Interviews drifted away from the guide (one *before* interview spent ten turns on a persona's business deals and accounting software), so the trade-off questions that measure "paradoxical" support were mostly never asked. In the pilot the interviewer even smoothed over a respondent's willingness to break rules. Measures of democratic support built on such transcripts would be biased towards coherence.
3. **A weak model is a weak judge and coder.** The LLM judge found far fewer double questions than counting `?` (e.g. 7 by rule vs. 0 by the judge in one interview I read, where 7 was correct), and the LLM coder gave no variation at all. The judge and coder need validation against hand coding, and should not be the same small model as the interviewer. The simple dictionary at least separated some personas (`committed_liberal` → liberal and `frustrated_pragmatist` → output in both *before* runs), though its codes changed between rounds as the conversations changed.

## Limitations

- **Synthetic respondents are not data.** `simulate.py` only tests the pipeline; personas are written by me and answered by a model.
- The LLM judge and LLM coder are not yet validated against human coding; that is the obvious next step.
- The dictionary is small and English-only.
- No consent flow, anonymisation or data protection setup, which real fieldwork would require.

## Next steps

- Pilot with real respondents and hand-code a sample to validate the LLM coder and judge
- Compare interviewer behaviour across models (closed vs. open-weight)
- Extend the dictionary to German and Russian
