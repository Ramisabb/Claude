#!/usr/bin/env bash
# Bygger ett avsnitt från avsnitt.json:  ./bygg.sh <avsnitt> <röstmodell.onnx> [utmapp]
# Exempel: ./bygg.sh bankid sv_SE-nst-medium.onnx
# Kräver: python3 + piper-tts + numpy, node + playwright, ffmpeg.
# Röstmodell: https://huggingface.co/rhasspy/piper-voices/tree/main/sv/sv_SE/nst/medium (.onnx + .onnx.json)
set -euo pipefail
cd "$(dirname "$0")"
E="$1"; MODEL="$2"; OUT="${3:-ut/$E}"
mkdir -p "$OUT"
python3 rost.py avsnitt.json "$E" "$MODEL" "$OUT"
node render.js video "$OUT/voice.json" "$OUT/bild.mp4"
python3 ljud.py "$OUT/voice.json" "$OUT/voice.wav" "$OUT/mix.wav" "$OUT/nomus.wav"
ffmpeg -y -loglevel error -i "$OUT/bild.mp4" -i "$OUT/mix.wav" -map 0:v -map 1:a -c:v copy \
  -af "loudnorm=I=-14:TP=-1.5:LRA=11" -ar 48000 -c:a aac -b:a 192k -shortest -movflags +faststart "$OUT/teknikvan-$E.mp4"
ffmpeg -y -loglevel error -i "$OUT/bild.mp4" -i "$OUT/nomus.wav" -map 0:v -map 1:a -c:v copy \
  -af "loudnorm=I=-14:TP=-1.5:LRA=11" -ar 48000 -c:a aac -b:a 192k -shortest -movflags +faststart "$OUT/teknikvan-${E}_utan-musik.mp4"
ffmpeg -y -loglevel error -ss 3.2 -i "$OUT/bild.mp4" -frames:v 1 "$OUT/omslag-$E.png"
echo "Klart: $OUT"
