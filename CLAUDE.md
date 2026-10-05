# VSC CLIP FACTORY - start here

GIN Volunteer Service Corps, **Project 15**: Kevin Trudeau's "Classified" interviews
cut into vertical clips for the **Trudeau Group Affiliate Portal**. Built on GitHub's
servers; Kamay downloads the finished batch from the `clips` release and uploads it
to Frame.io for GIN's reviewers. This is a JOB for GIN - it never feeds Kamay's or
Yaren's own accounts, and their content never comes here.

**The Connector** keeps every project in sync. When you finish a batch, fix a bug, or
learn a rule, write it HERE (this file, or the commit message) - the Connector reads the
repositories. Do not `send_message` into the old Connector session
(`session_018UdrEfWJonXGVYkZvfByj6`): waking a huge session is what burned the weekly
limit (see "Token budget").

## Making a batch (the whole loop)

(The normal way is the **Autopilot** below - one form, nothing else. These are the steps it
runs, and how to do any of them by hand.)

1. **Source.** The assignment video comes from GIN / Frame.io. Find the same episode
   on Rumble by DURATION, not title: `python3 cloud/rumble_match.py <key> <seconds>`.
   Put the Rumble URL in the plan; `prep` fetches it and caches it encrypted in the
   `sources` release, so nothing depends on Rumble twice. Source must be >= 1080p.
   Fallbacks: the `sources` release (upload `<key>.mp4.enc`, needs `VSC_KEY`), or
   Frame.io when `FRAMEIO_TOKEN` is set.
2. **Plan.** `plans/<key>.json` - see `plans/millionaires_problems.json` for the shape
   (and run `python3 cloud/check_plan.py` before you push - the build runs it too):
   `key, prefix, source, note, rumble, duration, height, clips[]`, and per clip
   `name, region [s,e], open "<first words>", close "<last words>",
   hook ["LINE ONE","LINE TWO"], fixes [[t, "wrong", "right"]]`.
   A plan entry REPLACES any hand-written cut of the same name in `vsc_cuts.py`.
3. **Push to main.** `vsc.yml` runs prep -> shard -> build (every pair on its own
   server, all at once) -> collect -> two automatic retry rounds. Result: the `clips`
   release with a per-clip verdict table.
   **Every push to `plans/` cancels the build that is running** (newer run wins), so
   batch your corrections into ONE push.
4. **Read every caption line** of every clip in the verdict table (`<clip>__caps.json`
   in the release is what the SERVER burned in). Write corrections as `fixes` against
   THOSE captions, not the Mac's transcript - they must match letter for letter.
   Never let a second fix rewrite text a first fix produced: fixes apply once, in
   order, and a stacked pair duplicates words.
   Push once. Unchanged clips are skipped by content hash.
5. Watch the **first 3 seconds and the last 2** of every clip. Then it goes to Kamay.

## The rules (from GIN's reviewers, Kamay and Yaren - all hard)

- **Open on the start of a complete thought.** Never mid-sentence.
- **Close where the teaching LANDS** - on meaning, not grammar. Never end with Kevin
  about to say something, and never cut the proof or the twist ("which they all did").
- **Never freeze the picture while Kevin is still talking** (mouth open, sound fading).
- **The end is the first real silence after Kevin FINISHES the sentence in which the teaching
  lands** - never a fade over live speech to hit a planned close. No pause there? Move the
  close to the next sentence end that has one (Kamay, 3 Oct: TEAM and FALL ended on his next
  words, REACT cut "pro|blem", RUN-AT stopped before the lesson).
- **Openings start in >= 0.15 s of real silence before the first word**, never on its onset.
- **Read every caption line before submission** (Naomi, Week-1 reviewer). Whisper
  breaks names: Steve Jobs (not Steven), NeXT, New York Times bestseller list,
  Carnegie Deli, American Memory Institute, the Possibility Thinker's Creed. Where
  Kevin misspeaks and the meaning is obvious, write what he meant.
- No `[BLANK_AUDIO]`, no words whisper invented ("Sorry."), no speech from someone else.
- Emphasis capitals never cost a word.
- **Hook:** two short lines, one idea, concrete (a number, a name, an amount).
- **Format 1080x1920 (9:16), hard maximum 120 s** (Naomi's ceiling; `MAX_LEN = 118`).
  **Length follows the teaching, never the machine.** A clip runs from the start of the
  thought to where it lands, setup + proof + landing, usually 45-110 s. Under 40 s needs
  `"short_ok": "<why it is complete>"` in the plan; `cloud/check_plan.py` enforces both
  ends and runs first in every build. (Kamay, 5 Oct: the first batch came out 21-60 s
  and "cut the teaching". The cause: on 30 Sept the renderer died on clips over ~62 s and
  the plan was cut to fit it - 102 s and 128 s teachings split into 3-5 pieces, commit
  d88d8f1. The renderer was fixed on 4 Oct. A machine limit is a bug to fix, never a
  reason to shorten a teaching.)
- **Framing is checked across the WHOLE clip**, not just the first frame - the
  interviews cut between 2-4 camera angles.
- **One caption size per clip.** Reviewers: Cali and Naomi, on GIN's Frame.io.
- Never cut the ad wall / testimonial at the end of an episode (e.g. 17:35-end in
  millionaires_problems).

## Do not reintroduce (already fixed, each cost hours)

- Render seeks with `-ss` before `-i` and uses ONE filter thread - decoding the whole
  film per clip ran the VM out of memory.
- "Already built" means the content hash matches, not that a file with the name exists.
- A cancelled run must never hold the queue (`cancel-in-progress: true`), and no job may be
  gated on `if: always()` - always() is true for a CANCELLED run, so the run never dies and
  the newer run waits behind it. Use `if: ${{ !cancelled() }}` (2 Oct, runs 28 and 30).
- Clips start and end inside the silence either side of the plan's words, found in the
  SOUND (whisper's word times swallow pauses; the source has muted gaps). Quiet means
  35 dB below the speech around it. `<clip>__head.json` / `__tail.json` decide FAIL.
- The renderer never trims before `speech_end` (where the locator measured Kevin
  finishing the close). Trimming to the caption pass's close cut "It doesn't end it,
  it creates it" to "It doesn't end" (1 Oct). The caption pass drifts at the tail.
- A fix that does not match is SKIPPED with only a log line ("CORRECTION NOT
  APPLIED"). Write fixes against `<clip>__caps.json`, never the Mac transcript, and
  never write a second fix over text an earlier fix produced (they stack: "without
  problems. problems. problems,").
- **A delivered clip is never rebuilt by a scheduled or plan-push build.** Its names go in
  `cloud/delivered.json` when the batch goes to GIN; only the workflow's `only` input can
  rebuild one. A FAIL ("listen") verdict is never recorded in `built.json`, so without the
  list Monday's cron rebuilt delivered clips under new shared framing (3 Oct).
- **Listen to the rendered edges, not the levels.** `cloud/edges.py` (run in every build, and
  on demand by the `edges` workflow) has whisper transcribe the file's first and last 3 s; the
  first and last words heard must be the first and last caption words, whole, with nothing
  after. Every silence/level check had passed NOT-AFFECTED opening on "...people" (3 Oct).
- **Whisper swallows pauses AND whole words into a neighbour**: "benefit." ran 1.23 s and held
  the pause plus "Successful". A last word (or the word before the opening) over 0.8 s is
  searched inside for the real silence. Where word times cannot find a gap at all, the plan's
  `start_at` / `end_at` (SOURCE seconds, read off `python cloud/edges.py probe <key> t0:t1`)
  name it; `end_fade` fades by the cut when that pause sits under a music bed.
- **Every shot renders in its own ffmpeg, then one pass joins them at 9:16** (vsc_render).
  Trimming every shot off one decoded 4K stream queued gigabytes of frames and killed the
  runner on every clip over ~62 s (run 42: NO-SUCH 70.8 s, BANNED 66.5 s, 3 attempts each).
  Measured locally on a 75 s 4K source: one pass OOM-killed at 16 GB, shot-by-shot 0.97 GB.
- The `clips` release can hold two files for one clip name (e.g.
  `THE-450-MILLION-BREAKUP_56s` and `_58s`). Deliver only the one listed in `built.json`.

## Token budget (Kamay, 5 Oct: two sessions burned 65% of a WEEK's limit)

Measured, not guessed: "VSC video production" ran to 672K tokens of context and re-read
247 million cached tokens; "Affiliate Factory Empire" re-read 357 million. Every tool call
re-reads the WHOLE conversation, so a 600K-token session pays ~600K per `ls`. That is the
"one second spent a day's limit". It also made the work worse: the batch that came out
too short was made deep inside that context.

- **One batch = one fresh session.** Hand off with a short note (what is done, what is
  next, run id) and start a new chat once a session passes ~150K context or ~4 hours.
  Never "continue" a giant session to save explaining - explaining costs 2K tokens.
- **Never wake a big session on a timer.** No `send_later` / routine check-ins into a
  session over ~100K context; GitHub tells you when a run ends (or Kamay looks at the
  release). A check-in every 8 minutes into a 600K session is 4M tokens an hour of nothing.
- **Never `send_message` into the old Connector session to "report"** - it wakes the
  biggest context on the account. Write it in the commit message / CLAUDE.md instead.
- **No subagent fan-out, no watching renders.** Push once, end the turn, read the
  verdict table when it is done. Do not download and frame-check every clip in chat;
  `edges.py` and the verdict table already do that on GitHub's servers for free.
- Routine work (planning from a transcript, caption fixes) runs on Sonnet in a fresh
  scheduled session, like kt-machine's planners - never in an Opus conversation.

## Autopilot (built 5 Oct 2026) - give it the assignment, come back to clips

1. **Kamay:** GitHub app -> vsc-factory -> Actions -> **vsc-new** -> Run workflow: the title
   GIN gave it and the length Frame.io shows (18:10). `cloud/new_batch.py` writes a stub
   plan, finds the episode on Rumble by length (kt-machine's catalogue, refreshed every
   day), refuses an episode already planned, and starts `vsc.yml`.
2. **prep** fetches and transcribes it and publishes `TRANSCRIPT_<prefix key>.txt`.
3. **autoplan** (`cloud/autoplan.py`): ONE Claude call (Opus 5.5, high effort, no tools)
   with `PLANNING.md` + "The rules" + the delivered batch as the brief, answering JSON in a
   fixed schema. Code keeps it only if every `open`/`close` is in the transcript word for
   word and `check_plan.py` passes (one repair round). Only `plans/` is committed; a fresh
   run builds it. A failed autoplan never blocks the batches already planned.
4. **build -> collect -> verify** as always; the clips land in the `clips` release.

One-time setup: repository secret `ANTHROPIC_API_KEY` (console.anthropic.com, pay per use,
roughly $0.20-0.60 a batch). Optional variable `VSC_PLANNER_MODEL`. No key = the stub
waits and the run says so. Still human: watching the clips, caption `fixes` after the
first render, and uploading to Frame.io (automatic once `FRAMEIO_TOKEN` exists).

Loose ends:
- Three stacked fix pairs remain in `millionaires_problems` (NO-SUCH 1/4 and 2/5,
  MORE-PROBLEMS 1/7). Those clips are delivered; clean them before any `only` rebuild.
- The `prep` release publishes transcripts UNENCRYPTED in this public repository (the
  autopilot reads them there); every other copy of Kevin's material is encrypted.
- A source over 2 GiB is cached as `<key>.mp4.enc.part00, .part01...` (source.py joins them).

## Shared engine

Word timings, caption breaks, framing, edges and the quality check (`kt_qc.py`,
`QC_AGENT.md`) come from `kamaycampos/kt-machine/shared/`, pulled live at setup.
**Never keep a local copy of a shared file here** - a local copy overrides the shared
one and forks silently (this happened twice on 30 Sept). Improve the shared file in
kt-machine instead, and say so in the commit message.
