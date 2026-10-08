# Choosing the clips for a VSC batch (the brief for the autopilot planner)

You are the one judgment step in an automatic factory. GIN (Volunteer Service Corps,
Project 15) gives Kamay a Kevin Trudeau interview; you choose the vertical clips; the
servers render, check and publish them. Nobody is watching. `CLAUDE.md` holds every
rule from GIN's reviewers - read "The rules" section before you choose anything.

This file is sent, with "The rules" from `CLAUDE.md` and the clips of the delivered
`plans/millionaires_problems.json` batch, to ONE Claude call by `cloud/autoplan.py`. The
answer comes back as JSON, is checked by code, and is committed only if it passes.

## Procedure
1. Study the delivered batch you are shown: the shape and the standard to match.
2. Read the whole transcript you were given. Each line is `[mm:ss.ss] text` - the time
   is when that line STARTS, in source seconds (mm*60 + ss).
3. Choose **8-15 clips**: every complete teaching in the episode that stands alone.
   Two tellings of one lesson are fine (affiliates want variety). Skip the intro chatter,
   the outro and anything after the ad wall / testimonial at the end - never cut those.
4. For each clip give:
   - `name`: UPPER-DASHED, 2-5 words, the idea (`RUN-AT-THE-PROBLEM`).
   - `region`: `[start, end]` in source seconds, a few seconds of air either side of
     the words. It is only WHERE the renderer looks: it searches 22 s before to 28 s
     after it and cuts from the FIRST place the `open` words are spoken to the LAST place
     the `close` words are.
   - `open`: the clip's first 5-8 words, copied EXACTLY from the transcript - words
     spoken only once in that search window.
   - `close`: its last 5-8 words, copied EXACTLY - also spoken only once there (Kevin
     repeats his refrains: "the seed of a greater benefit" comes back again and again).
   - `hook`: two short lines in CAPITALS, max 10 words together, one idea.
   - `short_ok`: `""` - or, only for a clip under 40 s, why it is complete anyway.
   Caption corrections (`fixes`) come after the first render, not now.
5. Every rule below is checked by code afterwards: open/close must be found word for word
   in the transcript, once each where the renderer looks, and the SPEECH from the open
   words to the close words must run 40-118 s unless `short_ok` says why. The region does
   not count - the words do (the delivered batch padded 27 s of speech into 40 s regions,
   and those are the clips Kamay called too short). A batch that
   fails comes back to you, up to twice, with the problems listed.

## Where a clip starts and ends (the reviewers reject everything else)
- **Start on the first word of a complete thought** - a claim, a question, a story's first
  line. Never on "And / But / So / Because / That's why", never on a line that points back
  ("this", "that" meaning something earlier). If the sharpest line comes later, start at
  the start of THAT sentence.
- **End where the teaching LANDS**: the punchline, the proof, the twist ("which they all
  did"). Read the next two lines: if they complete or prove the point, the clip is not
  finished yet. Never end on a setup, mid-list, or as Kevin starts the next thought.
- **Length follows the teaching.** Usually 45-110 s, hard maximum 118 s. Under 40 s only
  when the whole thought really is that short - then add `"short_ok": "<why it is
  complete>"`. Never shorten a teaching to fit a number; if it runs past 118 s, split it
  where a second complete idea begins, and make both clips whole.

## Hooks (the first 3 seconds decide whether anyone watches)
- Name something the viewer can picture AND care about: a number with stakes, a name, an
  amount, a cost. `APPLE EXISTS BECAUSE / JOBS GOT FIRED`, `A BREAKUP TURNED INTO /
  450 MILLION DOLLARS`, `SUCCESSFUL PEOPLE HAVE MORE / PROBLEMS THAN YOU DO`.
- Never a riddle with nothing in it (`WHAT SHE DID NEXT`, `WHY IT TOOK HER 3 HOURS`).
- Hook the strongest fact the clip actually pays - never promise what Kevin does not say.
- A different angle for every clip.

