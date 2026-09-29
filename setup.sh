#!/bin/bash
# Rebuild Kamay's Mac layout (~/Kamay) on a GitHub server so the VSC pipeline runs
# here UNCHANGED. Same idea as kt-machine's setup: every script must find its tools
# and fonts exactly where it looks for them on the Mac, because these are the
# scripts that produced the clips GIN's reviewers approved. Nothing is ported.
set -euo pipefail
K="$HOME/Kamay"
mkdir -p "$K/bin" "$K/whisper.cpp/build/bin" "$K/whisper.cpp/models" \
         "$HOME/Desktop/VSC/Source" "$HOME/Desktop/VSC/Clips" "$HOME/Desktop/VSC/.work"

sudo apt-get -qq update >/dev/null
sudo apt-get -qq install -y ffmpeg fonts-liberation cmake >/dev/null
pip install -q opencv-python-headless numpy pillow

ln -sf /usr/bin/ffmpeg  "$K/bin/ffmpeg"
ln -sf /usr/bin/ffprobe "$K/bin/ffprobe"
ln -sf "$(command -v gh)" "$K/bin/gh"
cp assets/yunet.onnx "$K/bin/"

# THE FONTS GO WHERE THE SCRIPT LOOKS. vsc_render.py names the Mac's own path for
# DIN Condensed Bold, and the look it produces is what Cali and Naomi signed off,
# so the font is not substituted - it is placed at that path. This repository is
# PRIVATE for exactly this reason: Apple's font file could not ship in a public one.
sudo mkdir -p "/System/Library/Fonts/Supplemental"
# THE FONT ARRIVES ENCRYPTED. This repository is PUBLIC, for the unlimited Actions
# minutes - a private one ran out of its 2,000 free minutes in two days because a
# rebuild costs 400-600. Apple's DIN Condensed Bold cannot be published, and the look
# it produces is the one GIN's reviewers approved, so it travels the same way
# kt-machine's copyrighted episodes do: encrypted, opened at build time with a secret.
openssl enc -d -aes-256-cbc -pbkdf2 -pass "env:VSC_KEY" \
  -in assets/din_condensed_bold.ttf.enc -out /tmp/din.ttf
sudo cp /tmp/din.ttf "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf"
rm -f /tmp/din.ttf
sudo cp /usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf \
        "/System/Library/Fonts/Supplemental/Arial Black.ttf"

# THE SHARED ENGINE, PULLED LIVE from kt-machine (public, so no token needed). This
# is what makes an improvement automatic in both directions: anything fixed for
# Kamay's or Yaren's factory is here, and anything invented here (caption timing
# anchored to the sound, the on-screen check) is pushed to the same place and reaches
# them. Project-specific files are copied AFTER, so this project always wins on its
# own style, hooks and plans - the details that must not leak between brands.
RAW="https://raw.githubusercontent.com/kamaycampos/kt-machine/main/shared"
curl -sfL "$RAW/MANIFEST.json" -o /tmp/shared_manifest.json
python3 - <<'EOF'
import json, os, urllib.request
raw = "https://raw.githubusercontent.com/kamaycampos/kt-machine/main/shared"
man = json.load(open("/tmp/shared_manifest.json"))["files"]
K = os.path.expanduser("~/Kamay")
for f in man:
    urllib.request.urlretrieve(f"{raw}/{f}", os.path.join(K, f))
print(f"shared engine pulled: {len(man)} modules from kt-machine")
EOF
cp pipeline/*.py "$K/"
mkdir -p "$K/vsc-machine"; ln -sfn "$GITHUB_WORKSPACE" "$K/vsc-machine" 2>/dev/null || true
ln -sfn "$PWD/plans" "$K/vsc_plans" 2>/dev/null || true

# whisper.cpp pinned to the SAME commit the Mac runs. Word timings are compared
# against the waveform to a tenth of a second; a different build would move them.
W="$HOME/wcache"
if [ ! -x "$W/whisper-cli" ]; then
  mkdir -p "$W"
  git clone -q https://github.com/ggml-org/whisper.cpp /tmp/whisper.cpp
  git -C /tmp/whisper.cpp checkout -q 2ca53bb45e38748d07b310eeb36245a7157ac882
  # BUILD IT PORTABLE, NOT FAST. 29 Sept 2026: the binary is built once and CACHED,
  # and GitHub hands out runners with different CPUs - so a build tuned to the machine
  # that made it dies with SIGILL (exit -4) on the next machine that restores it. Seven
  # of ten build shards died that way in one run while three succeeded, which is exactly
  # what a cache full of the wrong instruction set looks like. GGML_NATIVE=OFF costs a
  # little speed and makes the binary run anywhere.
  cmake -S /tmp/whisper.cpp -B /tmp/whisper.cpp/build -DCMAKE_BUILD_TYPE=Release \
        -DGGML_NATIVE=OFF -DBUILD_SHARED_LIBS=OFF -DWHISPER_BUILD_TESTS=OFF >/dev/null
  cmake --build /tmp/whisper.cpp/build -j"$(nproc)" --config Release --target whisper-cli >/dev/null
  cp /tmp/whisper.cpp/build/bin/whisper-cli "$W/"
fi
# THE MODEL MUST BE WHOLE, NOT MERELY PRESENT. `-s` only asks whether a file is
# non-empty, so a truncated download passes it - and then whisper exits without writing
# anything, which surfaced as a missing-file error three frames away in a function that
# had nothing to do with transcription. Nine build shards died of it on this repo's
# first run, because a new repository has no build cache and fetched the model fresh.
MODEL="$W/ggml-small.en.bin"
if [ ! -s "$MODEL" ] || [ "$(stat -c%s "$MODEL" 2>/dev/null || stat -f%z "$MODEL")" -lt 400000000 ]; then
  rm -f "$MODEL"
  curl -sL --retry 3 --retry-delay 5 -o "$MODEL" \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin
fi
SZ="$(stat -c%s "$MODEL" 2>/dev/null || stat -f%z "$MODEL")"
[ "$SZ" -ge 400000000 ] || { echo "speech model is $SZ bytes, expected ~488M - refusing"; exit 1; }
ln -sf "$W/whisper-cli" "$K/whisper.cpp/build/bin/whisper-cli"
ln -sf "$W/ggml-small.en.bin" "$K/whisper.cpp/models/ggml-small.en.bin"

"$K/whisper.cpp/build/bin/whisper-cli" --help >/dev/null 2>&1
ffmpeg -hide_banner -loglevel error -f lavfi -i color=c=black:s=64x64 -frames:v 1 \
  -vf "drawtext=fontfile='/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf':text=A" \
  -f null - && echo "setup ok: whisper pinned, ffmpeg, DIN Condensed, yunet, pipeline"
