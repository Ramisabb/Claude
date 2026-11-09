# "Visste du att…" – Reels för Teknikvän

Animerade Reels (1080×1920, 30 fps) där en egenritad presentatör pratar och förklarar.
Han har kort mörkt hår, kort helskägg, mörka glasögon och tröja i Teknikväns petrolfärg med märkessymbolen på bröstet.

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

## Varumärke (hämtat från teknikvan.se)
- **Märkessymbol:** två personer och ett hjärta (`logo-symbol.svg`). Petrol `#164E5C`, kräm `#F6EFE6`, koppar `#B15B2F`.
- **Knappfärg:** vinröd `#880202`. Marinblå `#1F3A60`. Guldaccent `#BF8A26`.
- **Typsnitt:** Source Serif 4 (rubriker) och Atkinson Hyperlegible (text). Båda är fria (SIL OFL) och ligger i `fonts/`.

## Röst
Rösten är Piper, `sv_SE-nst-medium`, licens CC0 (KBLab / Kungliga biblioteket). Den är fri att använda kommersiellt.
Uttalet styrs i fältet `say` i `avsnitt.json`. Där stavas till exempel "Majkråsoft", "bank-i-d" och "teknikvan punkt se".

## Göra ett nytt avsnitt
1. Lägg till ett avsnitt i `avsnitt.json`. Använd scentyperna `alert`, `call`, `sms`, `update`, `bankcall`, `bankid`, `callback` och `cta`.
2. Kör `./bygg.sh <avsnitt> sv_SE-nst-medium.onnx`.

Röstmodellen laddas ner från huggingface.co/rhasspy/piper-voices (sv/sv_SE/nst/medium).
Presentatören, grafiken, musiken och effekterna är egengjorda, så det finns inga licensfrågor.
