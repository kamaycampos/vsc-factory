# VSC CLIP FACTORY - start here

GIN Volunteer Service Corps, **Project 15**: Kevin Trudeau's "Classified" interviews
cut into vertical clips for the **Trudeau Group Affiliate Portal**. Built on GitHub's
servers; Kamay downloads the finished batch from the `clips` release and uploads it
to Frame.io for GIN's reviewers. This is a JOB for GIN - it never feeds Kamay's or
Yaren's own accounts, and their content never comes here.

**The Connector** (Kamay's 4th chat, Claude Code session
`session_018UdrEfWJonXGVYkZvfByj6`) keeps every project in sync. When you finish a
batch, fix a bug, or learn a rule, tell it with the `send_message` tool so the fix
reaches the other projects.

## Making a batch (the whole loop)

1. **Source.** The assignment video comes from GIN / Frame.io. Find the same episode
   on Rumble by DURATION, not title: `python3 cloud/rumble_match.py <key> <seconds>`.
   Put the Rumble URL in the plan; `prep` fetches it and caches it encrypted in the
   `sources` release, so nothing depends on Rumble twice. Source must be >= 1080p.
   Fallbacks: the `sources` release (upload `<key>.mp4.enc`, needs `VSC_KEY`), or
   Frame.io when `FRAMEIO_TOKEN` is set.
2. **Plan.** `plans/<key>.json` - see `plans/millionaires_problems.json` for the shape:
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
- **Read every caption line before submission** (Naomi, Week-1 reviewer). Whisper
  breaks names: Steve Jobs (not Steven), NeXT, New York Times bestseller list,
  Carnegie Deli, American Memory Institute, the Possibility Thinker's Creed. Where
  Kevin misspeaks and the meaning is obvious, write what he meant.
- No `[BLANK_AUDIO]`, no words whisper invented ("Sorry."), no speech from someone else.
- Emphasis capitals never cost a word.
- **Hook:** two short lines, one idea, concrete (a number, a name, an amount).
- **Format 1080x1920 (9:16), hard maximum 120 s** (Naomi's ceiling; `MAX_LEN = 118`).
  In practice ~20-60 s: a clip with many shots or over ~60 s kills the runner - split
  it into two clips that each carry a full idea.
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
- The `clips` release can hold two files for one clip name (e.g.
  `THE-450-MILLION-BREAKUP_56s` and `_58s`). Deliver only the one listed in `built.json`.

## Shared engine

Word timings, caption breaks, framing, edges and the quality check (`kt_qc.py`,
`QC_AGENT.md`) come from `kamaycampos/kt-machine/shared/`, pulled live at setup.
**Never keep a local copy of a shared file here** - a local copy overrides the shared
one and forks silently (this happened twice on 30 Sept). Improve the shared file in
kt-machine instead, and tell the Connector.
