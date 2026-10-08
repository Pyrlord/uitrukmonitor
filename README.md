# Uitrukmonitor Zeist–De Bilt

Een webpagina die brandweeralarmeringen (P2000) in de gemeenten Zeist en De Bilt toont op een kaart, met een live lijst en grafieken. De meldingen komen van [alarmeringen.nl](https://alarmeringen.nl), gebruikt met toestemming.

## Wat zit erin

| Bestand | Wat het doet |
|---|---|
| `index.html` | De website: kaart, live lijst, grafieken |
| `scripts/collect.py` | De verzamelaar: haalt de feeds op, filtert de brandweer, voegt samen en zet straten om naar coördinaten |
| `.github/workflows/verzamelen.yml` | Laat GitHub de verzamelaar elke 10 minuten draaien |
| `data/berichten.json` | Archief van alle ruwe brandweerberichten (vanaf 1 oktober 2026) |
| `data/meldingen.json` | Wat de website leest: één regel per incident |
| `data/geocache.json` | Onthoudt gevonden straten, zodat PDOK niet steeds opnieuw gevraagd wordt |

## Online zetten

### 1. Bestanden uploaden
1. Open je repository op GitHub (of maak een nieuwe **public** repository aan).
2. Klik op **Add file → Upload files** en sleep `index.html`, `README.md`, `.nojekyll` en de mappen `data` en `scripts` erin. Klik op **Commit changes**.
3. De map `.github` is op Mac en Windows vaak verborgen en gaat dan niet mee met slepen. Maak hem daarom met de hand aan:
   - Klik op **Add file → Create new file**.
   - Typ als naam: `.github/workflows/verzamelen.yml`. De mappen ontstaan vanzelf bij elke `/`.
   - Plak de inhoud van het bestand `verzamelen.yml` uit de zip en klik op **Commit changes**.

### 2. Website aanzetten
Ga naar **Settings → Pages**. Kies bij Source: `Deploy from a branch`, branch `main`, map `/ (root)`. Klik op **Save**.

### 3. Verzamelaar testen
1. Ga naar het tabblad **Actions**. Klik op **Meldingen verzamelen** en daarna op **Run workflow**.
2. Na ongeveer een minuut zie je een groen vinkje.
3. Klik op de run en open de stap "Feeds ophalen". Daar zie je per plaats hoeveel brandweerberichten er gevonden zijn.

### 4. Automatisch laten draaien (pas na toestemming van alarmeringen.nl)
1. Ga naar **Settings → Secrets and variables → Actions → tabblad Variables**.
2. Klik op **New repository variable**: naam `VERZAMELEN_AAN`, waarde `ja`.

Vanaf dan draait de verzamelaar elke 10 minuten. Hij slaat alleen iets op als er een nieuwe melding is. Uitzetten doe je door de waarde te veranderen in `nee`.

## Goed om te weten
- **Archief:** de meldingen van 1 t/m 8 oktober 2026 zijn handmatig overgenomen van de archiefpagina's van alarmeringen.nl. Daarna komt alles uit de RSS-feeds.
- **Huis ter Heide:** deze plaats heeft waarschijnlijk geen eigen feed. Meldingen daar staan meestal onder "Zeist". Bij elke run zie je in de log welke feeds niet bereikbaar waren.
- **Locatie:** de straat wordt opgezocht bij de PDOK Locatieserver, en de stip staat op het midden van de straat. Wordt de straat niet gevonden, dan staat de stip in het midden van de plaats en meldt de website "bij benadering".
- **Samenvoegen:** berichten op dezelfde plaats en straat binnen 20 minuten worden één incident. Een "Intrekken Alarm"-bericht markeert het incident als ingetrokken.
- **Soort melding:** wordt bepaald met zoekwoorden (lijst `SOORTEN` in `collect.py`). Komt er iets onder "Overig" terecht, voeg dan een regel toe aan die lijst.
- **Lokaal opnieuw rekenen zonder iets op te halen:** `python scripts/collect.py --offline`
- **Inactiviteit:** GitHub zet geplande workflows uit als een repository 60 dagen geen activiteit heeft. Je krijgt dan een mail en kunt hem weer aanzetten.
