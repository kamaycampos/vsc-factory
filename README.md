# vsc-machine - GIN Project 15 clips, built in the cloud

Kamay is a GIN Volunteer Service Corps member on Project 15: Kevin Trudeau's
"Classified" interviews cut into vertical clips for the Affiliate Portal. This
repository builds them on GitHub's servers, so a batch gets made with his Mac shut
and keeps working for weeks without anyone touching it.

It runs the SAME code as the Mac - `pipeline/` is a copy of ~/Kamay, and `setup.sh`
rebuilds that layout on the server, down to putting DIN Condensed Bold at the path
the renderer names. Nothing was ported or rewritten, because these are the scripts
whose output GIN's reviewers approved.

## Three steps, and only the middle one needs a person
1. **The video** goes in the `sources` release once (or comes from Frame.io when
   `FRAMEIO_TOKEN` is set). The Classified series is not on Rumble and YouTube
   refuses cloud runners, so this is the one step that is not automatic yet.
2. **The plan** - `plans/<video>.json` names each clip's exact opening and closing
   SENTENCE and its one-idea hook. This is judgement, not work: six rounds of
   automatic edge-picking were rejected because every proxy measured acoustics and
   none of them read meaning.
3. **Push it.** The workflow does the rest and publishes the batch to the `clips`
   release with a per-clip verdict. Kamay downloads it and uploads to Frame.io.

## What it checks, because success is not verification
Every clip is read back off the finished file: is the word Kevin is saying on screen
at a dozen random moments, and does any caption overlap the next. Clips that fail are
still delivered, but they are named so nobody hands one to a reviewer by accident.

## Why public, and what that costs
Unlimited Actions minutes. The first version of this was PRIVATE, for the 2,000 free
minutes a month - and it ran out in two days, because a rebuild costs 400-600 minutes,
not the 200 that was estimated. A machine that stops after two days is not a machine.

Public means this repository can never hold two things: Apple's DIN Condensed Bold (the
font whose look GIN's reviewers approved) and the source videos. Both are therefore
ENCRYPTED - the font as `assets/din_condensed_bold.ttf.enc`, each cached source as
`<key>.mp4.enc` in the `sources` release - and opened at build time with `VSC_KEY`, a
secret that lives only in this repository's settings and on Kamay's Mac outside iCloud.
It is exactly what kt-machine does with Kevin's episodes.
