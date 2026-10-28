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

## Where things stand (handoff, 28 Oct 2026 - replace this section at every handoff)

- **In production: your_purpose_is_a** - GIN's Frame.io "Your Purpose is a Lie: The Ancient Truth
  You're Missing" (item 25 of 25 in GIN's folder, NOT an episode number - Kamay called it "Episode 25
  of the Classified Files"; KT Show Ep. 25 Gary Spivey was a wrong guess, removed). Rumble 1198 s, 2160p.
  9 clips planned. PASSED and on the Mac: YOU-SIGNED-A-CONTRACT, FOCUS-ONLY-ON-TODAY, PATTON-AND-BRADLEY,
  DUTY-AND-BLISS, KEEP-YOUR-AGREEMENTS. Re-cut 28 Oct and rebuilding: DHARMA-IS-DUTY, TAKE-THE-NEXT-STEP
  (never rendered: close not heard as planned), NOTHING-OUTSIDE-FILLS-IT (ended mid-sentence) and
  THE-CHRISTMAS-CRASH (opened mid-sentence) - re-split at "...will ever satisfy you. | Things on the
  external world...". Next: read every caption line of all 9 (`<clip>__caps.json`), push fixes once.
  DUTY-AND-BLISS and KEEP-YOUR-AGREEMENTS share 18 s (995-1013) - decide before delivery.
- **Identify a GIN assignment by its TITLE on Frame.io** (the catalogue had it word for word), then
  start vsc-new WITHOUT a rumble URL or with one from the catalogue - since 28 Oct new_batch.py takes
  the catalogue's `rumble_hls` either way (a hand-given URL used to drop it; prep then failed with
  "Rumble refused every attempt").
- hollywood_insider_reveals_secret: delivered; its encrypted source is KEPT in `sources` until GIN
  approves the 8, then `retire` with only that key. why_your_prayers_fail: delivered, fully retired.
- GIN wants a perfect batch before giving more than one assignment at a time.

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
- No `[BLANK_AUDIO]`, no words whisper invented ("Sorry."), no speech from someone else
  (in an interview the guest's question or reaction is fine; the clip is Kevin's).
- Emphasis capitals never cost a word.
- **Hook:** two short lines, one idea, concrete (a number, a name, an amount).
- **No story-only clips** (Kamay, 25 Oct): every clip must carry a lesson or real value. A funny
  anecdote with no teaching is not a clip, however clean its edges (NINE-MEANS-NINE,
  HURT-HIM-DANNY and THE-EAGLE-CLAW were built and then dropped for this).
- **Format 1080x1920 (9:16), 20-90 s** (Naomi, 18 Oct 2026 - was 120 s; `MAX_LEN = 88`,
  `FLOOR = 20`). **Length follows the teaching, never the machine.** A clip runs from the
  start of the thought to where it lands, setup + proof + landing, usually 40-85 s. Under
  40 s needs `"short_ok": "<why it is complete>"` in the plan; `cloud/check_plan.py` enforces
  both ends and runs first in every build. A teaching over 88 s is split where a second
  complete idea begins - both halves whole - never cut short.
- **Interviews focus on KEVIN** (Naomi, 18 Oct): "it can be talking with John but we don't
  want clips focusing only on John". prep's `speakers-<key>.json` (`cloud/speakers.py`,
  voiceprints against `assets/kevin_voice.npy`) tags the guest's lines; autoplan refuses a
  clip where Kevin has under 60 % of the speech or the guest has the close.
- **In a wide two-shot, frame whoever is talking** (Naomi, 18 Oct: "reframe to show the
  person that he's speaking during those moments"). `vsc_render.speaker_shots` hands the
  shared `vsc_frame.speaker_turns` the clip; it switches on sentence starts, only where both
  faces are on screen. The render log says "speaker turns: ..." where it acted. (Kamay, 5 Oct: the first batch came out 21-60 s
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
- **A release asset's name is rewritten by GitHub** (spaces -> dots): prep uploads
  `TRANSCRIPT_Why Millionaires millionaires_full.txt`, the release holds
  `TRANSCRIPT_Why.Millionaires.millionaires_full.txt`. autoplan asked for the spaced name,
  planned nothing and run 48 (7 Oct) went GREEN with zero clips. autoplan now matches names
  on letters and digits; a batch still waiting for clips turns the run RED (autoplan's last
  step, and verify), and "0/0 published" is never "BATCH COMPLETE".
- **A clip's length is its SPEECH, not its region.** The renderer cuts from the first place
  the `open` words are spoken to the last place the `close` words are, anywhere from 22 s
  before the region to 28 s after it. The delivered batch padded 21-38 s of speech into
  40 s regions, so check_plan's region test passed the very clips Kamay called too short.
  autoplan replays that search on the transcript before it keeps a plan: 40-118 s of speech
  (or `short_ok`), and open/close words spoken only once in the window.
- **A source uploaded from the Mac must be checked on the release, part by part** (12 Oct):
  why_your_prayers_fail went up as `.part00` + `.part01`; the 2 GB part00 upload died
  with the session that started it, nothing noticed, and prep called the cache
  "unreadable" for half a day. It was also locked with `VSC_KEY_B` (the plan's
  `"source_key"` names the secret) and that one-line decrypt change sat uncommitted.
  Verify with `gh release view sources --json assets` that every part is there at its size.
- **Every clip that renders is recorded in `built.json`, whatever its verdict** (12 Oct).
  Only PASS was recorded, so LOOK/FAIL clips were re-rendered in rounds 2 and 3 of every
  run, to the same verdict (TWO-WRONG-BELIEFS: six times in one day). A plan change still
  rebuilds; a clip that rendered nothing is still retried.
- **Edge listening allows whisper's name bias on the FIRST word only** (12 Oct): "Steven"
  heard for caption "Steve" failed FIRED-FROM-HIS-OWN-COMPANY, which opens cleanly. A word
  cut at the start is heard shorter, never longer; the last word stays exact.
- **The Mac gate judges with the live shared `kt_qc`** (fetched into `~/VSC/.engine`,
  checked against the MANIFEST), not a hand copy in `~/Kamay` - they drifted once already.
- **Plan on the pauses** (13 Oct). why_your_prayers_fail's first plan put 13 of 15 opens/
  closes where Kevin had no pause and 2 closes the renderer could not find: the planner read a
  transcript that cannot show silence, checked against text the renderer never searches.
  prep now publishes `pauses-<key>.json` (`cloud/pauses.py`, quiet_runs' rule); autoplan gives
  the planner the word stream with a line break at every real pause, checks each open/close
  with the renderer's own `_find` on that stream, and needs >= 0.15 s of pause before the open
  and >= 0.20 s after the close. After the last repair round it keeps the clips that pass
  (>= 6) instead of dropping the batch.
- **The caption pass's punctuation is repaired** (`vsc_v2caps.tidy`, 13 Oct): a full stop
  followed by a lowercase word becomes a comma before a joining word, goes before a word no
  sentence starts on, and otherwise keeps the stop and capitalises; a capitalised starter
  after an unpunctuated word gets a stop; "that's That's" gets a comma. On that batch's
  captions: 27 kt_qc text faults -> 0 (2 more were kt_qc false alarms, fixed in kt-machine #24).
- **The renderer's word search spells out whisper's contractions** (13 Oct): OUR-NOT-MY-
  FATHER's open "If you're going to pray" was heard "If you're gonna pray" by the 12 s chunk -
  one word for two - and never rendered. `vsc_pick._find` expands gonna/wanna/gotta/'cause/
  kinda/outta on both sides and takes the close's last word from the match.
- **Cut on measured breath gaps, not only full pauses** (15 Oct). Kevin left a renderer-grade
  pause at only 40 of 261 sentence ends in why_your_prayers_fail, so the pause-only planner
  placed 8 clips in 27 min. `pauses.py` v2 adds `cuts` (>= 0.15 s at 30 dB under the voice,
  dipping to 38 dB under, or >= 0.12 s near-silence); autoplan plans on them and writes each
  clip's exact `start_at` / `end_at`; the cloud's edge listening still judges the file. 8 hand
  cuts were whisper-verified on the source first; the automatic times match them within 0.1 s.
  The episode went from 8 to 13 clips. PLANNING.md now asks for every complete teaching.
- **prep never lets one episode block the others** (15 Oct): a refused source is named, the
  run goes red, the other batches build; `mac/vsc_source.py` uploads every missing source,
  then starts ONE run.
- **One cut per clip in the Mac folder** (15 Oct): when a re-cut passes the gate, older
  cuts of that clip move to `~/Archive/vsc-replaced` (never deleted).
- **prep's pause map can drift from the renderer's clock** (20 Oct, hollywood_insider):
  around 28-31 min `pauses-<key>.json` and prep's word times ran 0.6-1.0 s EARLY against
  ffmpeg's `-ss` on the same source (gap after "book form." 1832.65 in prep, 1833.14-1833.76
  heard by `edges.py probe`), so autoplan's start_at/end_at landed inside words. Cause not
  found yet (a 720p source with an audio start offset is the first suspect). Until it is:
  when an edge fails on a planned start_at/end_at, take the times from a probe, not prep.
- **The plan's measured times are the cut when the words are not heard** (28 Oct). DHARMA-IS-DUTY and
  TAKE-THE-NEXT-STEP failed three builds each ("missing closing") with exact start_at/end_at in the
  plan: the 12 s pass heard "missing. on the inside" differently, and `locate` threw the clip away.
  `vsc_pick.locate_at` now cuts on start_at/end_at; edges.py still judges the file.
- **autoplan picks the gap NEXT TO the words, not the longest in reach** (28 Oct). The end gap must
  finish by 0.5 s after the next word starts (CHRISTMAS-CRASH's end_at kept "because" of "because you
  have it all"); the start gap must not have a whole word between it and the open (DHARMA would have
  opened on the interviewer's "Is it?"); a last word over 0.8 s is searched inside for its gap ("all."
  ran 2 s). Replayed on all 9 clips: the 5 that passed keep identical times.
- **A clip never ends on a clause that continues** ("temporary happiness, but it's fleeting" - the
  sentence went on into Christmas). Split a long teaching where a SENTENCE ends.
- Runners are pinned to `ubuntu-24.04` (GitHub moves `ubuntu-latest` to 26 on 19 Oct).
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
   word, the renderer's search replayed on the transcript gives 40-118 s of speech with no
   repeated open/close words, and `check_plan.py` passes (two repair rounds, brief and
   transcript cached). The chosen clips are listed on the run's summary page. If no batch
   passes, the stub stays a stub and the run is RED, never green. Only `plans/` is committed; a fresh
   run builds it. A failed autoplan never blocks the batches already planned.
4. **build -> collect -> verify** as always; the clips land in the `clips` release.

One-time setup: repository secret `ANTHROPIC_API_KEY` (console.anthropic.com, pay per use,
roughly $0.20-0.60 a batch). Optional variable `VSC_PLANNER_MODEL`. No key = the stub
waits and the run says so. Still human: watching the clips, caption `fixes` after the
first render, and uploading to Frame.io (automatic once `FRAMEIO_TOKEN` exists).
**`ANTHROPIC_API_KEY` is set (Kamay, 6 Oct).**

**How a batch starts now (Kamay, 6 Oct):** Kamay sends a chat "New VSC: <title>, <length>".
Claude starts `vsc_new.yml` itself (GitHub Actions `workflow_dispatch`, inputs `title`,
`duration`, optional `rumble`), checks it started, and ends the turn - no clicking for Kamay.
Full autopilot (a watcher polling GIN's Frame.io) waits on a `FRAMEIO_TOKEN`, and GIN may
have to allow that token: it is GIN's workspace. Only build it if assignments come often.

Shared engine, 6 Oct (kt-machine PRs 18, 19): `kt_render` now drops whisper markup -
`(laughing)`, `[BLANK_AUDIO]`, `*music*` - before building captions, and honours a
`CAPTION_SHIFT` env (unset here, so VSC renders are otherwise unchanged).

**Redo of a delivered episode (Kamay, 7 Oct):** a stub plan with `"redo_of": "<old key>"` and the old
`source` (reuses the cached video). autoplan is told it is the same episode, cut too short, and must keep
each whole teaching; every clip name must be new across ALL plans (the release is keyed by name, so a
reused name would overwrite what GIN has). First one: `plans/millionaires_full.json`.

Loose ends:
- Three stacked fix pairs remain in `millionaires_problems` (NO-SUCH 1/4 and 2/5,
  MORE-PROBLEMS 1/7). Those clips are delivered; clean them before any `only` rebuild.
- The `prep` release publishes transcripts UNENCRYPTED in this public repository (the
  autopilot reads them there); every other copy of Kevin's material is encrypted.
- A source over 2 GiB is cached as `<key>.mp4.enc.part00, .part01...` (source.py joins them).

## Keep it clean, always (Kamay, 15 Oct 2026 - a standing order)

"Always be organized with all files ... and always delete stuff that is confirmed not needed
anymore, that is very important to run smooth forever."
- **The Desktop holds only `~/Desktop/VSC/Clips`**, and Clips holds only the CURRENT project's
  clips - the ones not yet uploaded to GIN. Nothing else: no handoff notes, no old batches.
- **When Kamay confirms a project is uploaded:** move its plan to `plans/done/`, delete its
  clips / prep / source from the three releases, and move its local clips to the Trash. A
  finished plan in `plans/done/` is invisible to every build and to the Mac pull.
- **Trash, never hard-delete.** Emptying the Trash is his. Replaced cuts go there by themselves.
- No second copies of the repo, no scratch folders in ~ (all of these were retired 15 Oct:
  ~/vsc-machine, ~/vsc-work, ~/VSCwork, ~/Desktop/VSC/vsc-machine, ~/Archive/vsc-*).

## Delivery to the Mac (`mac/`, moved here from ~/Kamay on 12 Oct 2026)

**The Mac is not part of production** (15 Oct 2026). Sources come from Rumble's direct stream
in the cloud (`source.py`, proven by the `fetch-test` workflow: 2160p from a runner, where the
page answers 403), planning and rendering run on GitHub, and the finished clips wait in the
`clips` release. The Mac only RECEIVES them: whenever it is awake - on battery or charger,
lid open - the pull runs within 15 minutes (and at wake), so clips appear the next time it is
opened. No charger needed. `vsc_source.py` is now only a backup for a source the stream fails.

`~/Desktop/VSC/Clips` is a shortcut to `~/VSC/Clips`; **a clip in there can be submitted.**
The LaunchAgent `com.kamay.vscpull` runs `mac/vsc_pull.py` every 15 min while the Mac is
awake (`com.kamay.keep-awake` = `caffeinate -s`: awake only ON THE CHARGER):
- `vsc_pull.py` pulls the newest cut of each clip from the `clips` release into
  `~/VSC/.incoming`, git-pulls this repo (so fixes to `mac/` deploy themselves), fetches
  `verdicts.json`, runs the gate, and shows a macOS notification when clips land.
- `vsc_gate.py` passes a clip into `Clips/` or holds it in `Clips/_needs_work/` with a
  `__WHY.txt`: file opens at 1080x1920 with sound, plan corrections on screen, live shared
  `kt_qc`, and the cloud's edge-listening FAILs (`verdicts.json`).
- `vsc_source.py` (started detached by the pull): when a plan's Rumble source is missing
  from the `sources` release and no vsc run is active, the Mac downloads it (Rumble refuses
  the runners, not the Mac), locks it with `~/.vsc_key` (= `VSC_KEY`), uploads verified
  parts, and starts `vsc.yml`. Log: `~/Kamay/logs/vsc_source.log`.

## Shared engine

Word timings, caption breaks, framing, edges and the quality check (`kt_qc.py`,
`QC_AGENT.md`) come from `kamaycampos/kt-machine/shared/`, pulled live at setup.
**Never keep a local copy of a shared file here** - a local copy overrides the shared
one and forks silently (this happened twice on 30 Sept). Improve the shared file in
kt-machine instead, and say so in the commit message.
