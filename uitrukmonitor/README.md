# Uitrukmonitor Zeist–De Bilt

Een webpagina die brandweermeldingen (P2000) in de gemeenten Zeist en De Bilt toont op een kaart, met een live lijst en grafieken.

## Online zetten met GitHub Pages (± 5 minuten)

1. Ga naar https://github.com/new en maak een **public** repository aan, bijvoorbeeld `uitrukmonitor`.
2. Klik op **"uploading an existing file"** en sleep de inhoud van deze map erin (`index.html`, `README.md`, `.nojekyll` en de map `data`). Klik op **Commit changes**.
3. Ga naar **Settings → Pages**. Kies onder *Build and deployment* bij **Source**: `Deploy from a branch`, branch `main`, map `/ (root)`. Klik op **Save**.
4. Na ongeveer een minuut staat de site op `https://<jouw-gebruikersnaam>.github.io/uitrukmonitor/`.

Lokaal bekijken kan ook: dubbelklik op `index.html`. De kaart werkt dan ook, alleen met voorbeelddata.

## Hoe de pagina aan data komt

De pagina leest elke minuut het bestand `data/meldingen.json`. Bestaat dat bestand niet, dan toont de pagina gegenereerde voorbeelddata (met een melding bovenaan).

In de volgende stap bouwen we een verzamelaar (GitHub Actions) die dit bestand automatisch vult vanuit de gekozen P2000-bron.

Formaat van `data/meldingen.json`:

```json
{
  "bijgewerkt": "2026-10-08T17:30:00+02:00",
  "bron": "naam van de P2000-bron",
  "meldingen": [
    {
      "id": "uniek-id",
      "time": "2026-10-08T17:12:00+02:00",
      "place": "Zeist",
      "g": "Zeist",
      "type": "Brand woning",
      "prio": 1,
      "street": "Slotlaan",
      "lat": 52.0890,
      "lon": 5.2330,
      "raw": "P 1 ... (originele P2000-tekst)",
      "caps": ["capcode1", "capcode2"]
    }
  ]
}
```

- `g` is de gemeente: `"Zeist"` of `"De Bilt"`.
- `type` moet een van de soorten uit de lijst in `index.html` (`TYPES`) zijn, anders valt hij buiten het soortfilter.
- Geen huisnummers opslaan: alleen straat en plaats (privacy).

## Kaartondergronden

Rechtsboven in de kaart kun je kiezen uit:
- **Topografisch (PDOK):** BRT Achtergrondkaart van het Kadaster, met straten en bossen
- **Grijs (PDOK):** een rustige variant
- **Luchtfoto (PDOK)**
- **OpenStreetMap**

Alle vier zijn gratis en hebben geen API-sleutel nodig.
