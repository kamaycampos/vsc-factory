# The quality gate — what it knows, what it does not, and what it still needs

Kamay, 29 Sept 2026, after a batch reached him with defects in every clip:

> "the agent that is in the door of quality review in the factory will need more
> improvements and details for sure... thats critical, when there is something we want
> new or better the agent needs to be fully knowledgeable."

This file is that agent's memory. **Anything learned about what makes a clip wrong
belongs here**, and anything added to `kt_qc.py` gets a line here saying why.

## Where it sits
At the QUEUE — the last point before a clip can reach a live account. A clip it cannot
vouch for is never copied into the posting folder, so the poster cannot reach it even by
accident. Every project that pulls the shared engine gets this, including anyone given
the kit.

## Layer 1 — mechanical (built, calibrated, running)
Reads the finished file, never the plan or the log:

| Check | Catches |
|---|---|
| word on screen at sampled moments | captions drifting off the speech |
| caption overlap | two captions drawn at once |
| opening / ending | a clip that starts mid-thought or stops on a setup |
| resolution, audio, duration | a broken render |
| repeated word | "Without Without setbacks", "or I'll I'll stay" |
| word repeated after one | "It's not It's not", "forest fire Forest is" |
| scrambled phrase | "said He it said", "It was It when was" |
| two subjects together | "So you We have to" |
| stray full stop | "the number. one difference" |
| sentence with no stop before it | "down a goal Guess what" |

**Calibration, both directions (29 Sept):** 11 of 12 real defects caught; 0 of 11 of
Kevin's deliberate repetitions wrongly flagged — "tons and tons and tons", "attacking,
attacking", "freezing, freezing", "every single one, every single one", "in New York
City". The discriminator that makes this work: **his emphasis is punctuated, damage is
not.** Keep that in mind before adding any rule.

## Layer 2 — MEANING (not built yet; this is the gap)
The one defect Layer 1 misses is the one that matters most to a reviewer: a **plausible
wrong word**. "New York Times best settle list" is four ordinary English words in a
sensible order. So is "Steven Jobs". No mechanical rule can see it.

Kamay's point, and he is right: **a reader who knows the subject would catch it
instantly.** Kevin wrote *Natural Cures*, it hit the New York Times **best seller** list,
and the man who founded Apple is **Steve** Jobs. The gate needs that knowledge.

**The design:** the factory already runs a scheduled cloud agent for planning
(`factory/PLANNING.md`). The same pattern applies here — an agent that reads each
finished clip's caption text with the context of who is speaking and what about, flags
words that are wrong for the subject, and writes the corrections back into the plan so
the next build carries them. Mechanical checks stay in code because they are cheap and
deterministic; meaning goes to the agent because meaning is what it is for.

**What it must be told to know:** who the speaker is, the products and books by name
(Natural Cures, Your Wish Is Your Command, Mega Memory), the people (Steve Jobs, Bobby
Singer, J.K. Rowling, Viktor Frankl), the places (Okinawa, Ojai, Carnegie Deli, Lynn
Shore Drive, Swampscott), the organisations (FTC, GIN), and the vocabulary he actually
uses (samskaras, tummo, counter-intention, the Brotherhood).

## The standing rule for this agent
Kamay, 29 Sept: where the speaker misspeaks and the meaning is obvious — "New York Times
best settle" — **write what he meant.** An accent or a slip does not change the spelling
of a word. This is a judgement about meaning, which is exactly why it needs Layer 2.

## Known gaps, in the order they matter
1. **Layer 2 does not exist yet.** Everything above about meaning is design, not code.
2. Corrections must be written against the transcription that will actually be used —
   a fix keyed to one machine's output silently does nothing on another (29 Sept).
3. No check yet that a clip is not a near-duplicate of one already posted.
4. No check on the hook beyond length: nothing verifies it is ONE idea.
5. No check that the caption text matches the CAPTION FILE that ships with the clip.
