# Reels: "Visste du att…" – virus på mobil och dator

| Fil | Vad |
|---|---|
| `teknikvan-visste-du-att-virus.mp4` | Färdig Reel, 1080×1920, 66 s, med musik och ljudeffekter. Kan läggas upp direkt. |
| `teknikvan-visste-du-att-virus_utan-musik.mp4` | Samma video med bara ljudeffekter. Använd den om du vill lägga på egen röst eller musik från Instagram. |
| `omslag.png` | Omslagsbild till Reelen |
| `undertexter.srt` | Repliker med tidskoder (manus för speakerröst) |

## Lägga på röst
1. Öppna `…_utan-musik.mp4` i CapCut eller Instagrams redigerare.
2. Spela in repliken med *Voiceover*, eller använd *Text till tal* på svenska. Följ tiderna i `undertexter.srt`.
3. Lägg på musik från Instagrams bibliotek på låg volym.

## Ändra och rendera om
- Manus, tider och grafik finns i `scen.html` (listan `SCENES` och funktionen `render(t)`).
- Bild: `node render.js video ut.mp4 timeline.json 30`
- Ljud: `python3 ljud.py timeline.json mix.wav fx.wav`
- Slå ihop: `ffmpeg -i ut.mp4 -i mix.wav -map 0:v -map 1:a -c:v copy -af loudnorm=I=-14 -c:a aac -shortest final.mp4`

Presentatören, musiken och ljudeffekterna är egengjorda, så det finns inga licensfrågor.
