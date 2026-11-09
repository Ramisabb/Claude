# "Visste du att…" – Reels för Teknikvän

Animerade Reels (1080×1920, 30 fps) där **Teknikväns egen karaktär** pratar och förklarar.
Karaktären är porträttet `../../varumarke/karaktar-portratt.png`, alltså exakt samma bild, inte en tecknad kopia.
I videon:
- **Läppsynk:** underkäken (läppar, pipskägg, haka) rör sig i takt med rösten, och munhålan ritas in.
- **Blinkningar:** han blinkar var tredje till femte sekund.
- **Rörelse:** han andas, nickar och rör huvudet lite när han pratar.

## Färdiga videor (`ut/`)
| Avsnitt | Längd | Filer |
|---|---|---|
| Virus på mobil och dator | 73 s | `ut/virus/` |
| Virus, kort version | 33 s | `ut/virus-kort/` |
| BankID-samtal | 56 s | `ut/bankid/` |

Varje mapp innehåller:
- `teknikvan-<avsnitt>.mp4`: röst, musik och effekter. Kan läggas upp direkt.
- `…_utan-musik.mp4`: röst och effekter. Använd den om du vill lägga på musik från Instagrams bibliotek.
- `omslag-<avsnitt>.png`: omslagsbild.
- `undertexter-<avsnitt>.srt`: textfil med tidskoder.

## Varumärke
- **Logga:** `bilder/logo.png` (från `../../varumarke/logo-original.jpg`), används i slutkortet. Ordmärket `bilder/ordmarke.png` ligger uppe till höger.
- **Loggans färger:** marinblå `#042135` och vinröd `#76051F`.

### Från teknikvan.se
- **Märkessymbol:** två personer och ett hjärta (`logo-symbol.svg`). Petrol `#164E5C`, kräm `#F6EFE6`, koppar `#B15B2F`.
- **Knappfärg:** vinröd `#880202`. Marinblå `#1F3A60`. Guldaccent `#BF8A26`.
- **Typsnitt:** Source Serif 4 (rubriker) och Atkinson Hyperlegible (text). Båda är fria (SIL OFL) och ligger i `fonts/`.

## Röst
Rösten är Piper, `sv_SE-nst-medium`, licens CC0 (KBLab / Kungliga biblioteket). Den är fri att använda kommersiellt.
Uttalet styrs i fältet `say` i `avsnitt.json`. Där stavas till exempel "Majkråsoft", "bank-i-d" och "teknikvan punkt se".

## Så byggs en video
1. `rost.py` läser in rösten och skapar tidslinje och munrörelser (`voice.json`).
2. `render.js … --utan-presentator` renderar telefoner, texter och slutkort (`motor.html`).
3. `kompositor.py` lägger in karaktären med läppsynk, blinkningar och huvudrörelser.
4. `ljud.py` mixar röst, musik och effekter, och ffmpeg slår ihop allt.

Allt detta görs av `bygg.sh`. Om porträttet byts ut: kör `karaktar_prep.py` och mät om munnens och ögonens position. Konstanterna `MOUTH_L`/`MOUTH_R` finns i `karaktar_prep.py` och `EYES` i `kompositor.py`.

## Göra ett nytt avsnitt
1. Lägg till ett avsnitt i `avsnitt.json`. Använd scentyperna `alert`, `call`, `sms`, `update`, `bankcall`, `bankid`, `callback` och `cta`.
2. Kör `./bygg.sh <avsnitt> sv_SE-nst-medium.onnx`.

Röstmodellen laddas ner från huggingface.co/rhasspy/piper-voices (sv/sv_SE/nst/medium).
Grafiken, musiken och effekterna är egengjorda. Karaktären och loggan är Teknikväns egna.
