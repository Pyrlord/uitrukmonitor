#!/usr/bin/env python3
"""
Verzamelaar voor de Uitrukmonitor Zeist–De Bilt.

1. Haalt de RSS-feeds per plaats op bij alarmeringen.nl (met toestemming gebruiken!).
2. Houdt alleen brandweerberichten over (code "BMD-xx").
3. Bewaart elk ruw bericht in data/berichten.json (nooit iets weggooien).
4. Bouwt daaruit data/meldingen.json: berichten van hetzelfde incident worden
   samengevoegd, de soort melding wordt bepaald en de straat wordt via PDOK
   omgezet naar coördinaten (op straatniveau, nooit een huisnummer).

Alleen de Python-standaardbibliotheek is nodig.
"""
from __future__ import annotations

import email.utils
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BERICHTEN = DATA / "berichten.json"
MELDINGEN = DATA / "meldingen.json"
GEOCACHE = DATA / "geocache.json"

START = datetime(2026, 10, 1, tzinfo=timezone(timedelta(hours=2)))  # 1 oktober 2026, 00:00 NL-tijd
USER_AGENT = "Uitrukmonitor-Zeist-DeBilt/1.0 (niet-commercieel hobbyproject)"
FEED_URL = "https://alarmeringen.nl/feeds/city/{slug}.rss"
PDOK_URL = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"

# Plaatsen: naam zoals in het P2000-bericht, slug van de feed, gemeente en een middelpunt
# (dat middelpunt gebruiken we alleen als de straat niet gevonden wordt).
PLAATSEN = [
    {"naam": "Zeist",              "slug": "zeist",              "gemeente": "Zeist",   "lat": 52.0895, "lon": 5.2330},
    {"naam": "Den Dolder",         "slug": "den-dolder",         "gemeente": "Zeist",   "lat": 52.1395, "lon": 5.2470},
    {"naam": "Huis ter Heide",     "slug": "huis-ter-heide",     "gemeente": "Zeist",   "lat": 52.1135, "lon": 5.2440},
    {"naam": "Austerlitz",         "slug": "austerlitz",         "gemeente": "Zeist",   "lat": 52.0815, "lon": 5.3120},
    {"naam": "Bosch en Duin",      "slug": "bosch-en-duin",      "gemeente": "Zeist",   "lat": 52.1190, "lon": 5.2290},
    {"naam": "Bilthoven",          "slug": "bilthoven",          "gemeente": "De Bilt", "lat": 52.1290, "lon": 5.2030},
    {"naam": "De Bilt",            "slug": "de-bilt",            "gemeente": "De Bilt", "lat": 52.1100, "lon": 5.1800},
    {"naam": "Maartensdijk",       "slug": "maartensdijk",       "gemeente": "De Bilt", "lat": 52.1555, "lon": 5.1720},
    {"naam": "Groenekan",          "slug": "groenekan",          "gemeente": "De Bilt", "lat": 52.1380, "lon": 5.1560},
    {"naam": "Westbroek",          "slug": "westbroek",          "gemeente": "De Bilt", "lat": 52.1670, "lon": 5.1300},
    {"naam": "Hollandsche Rading", "slug": "hollandsche-rading", "gemeente": "De Bilt", "lat": 52.1770, "lon": 5.1780},
]
# Langste namen eerst, zodat "De Bilt" niet per ongeluk binnen een langere naam matcht.
PLAATSEN_SORTED = sorted(PLAATSEN, key=lambda p: -len(p["naam"]))

# Soort melding: eerste regel die past wint. Volgorde is belangrijk.
SOORTEN = [
    (r"intrekken", "Alarm ingetrokken"),
    (r"reanimatie", "Reanimatie (assistentie)"),
    (r"\boms\b|automatisch|\bpac\b", "Automatisch brandalarm (OMS)"),
    (r"brandgerucht|rookmelder|rook/hitte", "Brandgerucht / rookmelding"),
    (r"\bbr\b.*\bwoning|woningbrand", "Brand woning"),
    (r"\bbr\b.*\b(buiten|container|afval|berm|natuur|bos|heide|gras)", "Buitenbrand"),
    (r"\bbr\b.*\b(wegvervoer|voertuig|auto|bus|vrachtwagen)", "Brand voertuig"),
    (r"\bbr\b", "Brand gebouw"),
    (r"gev\.? stof|gaslek|gaslucht|gasl", "Gaslek / gevaarlijke stof"),
    (r"\bco\b|co-melder|koolmonoxide", "CO-melding"),
    (r"stank|hind\.? lucht", "Stank / hinderlijke lucht"),
    (r"ongeval", "Ongeval"),
    (r"dier", "Dier in problemen"),
    (r"lift", "Liftopsluiting"),
    (r"storm|boom|wateroverlast|\bwater\b", "Storm- of waterschade"),
    (r"\bass\b|assistentie|afhijsen", "Assistentie ambulance/politie"),
    (r"nacontrole", "Nacontrole"),
]

# Woorden die nooit bij een straatnaam horen (beschrijving van de melding)
STOPWOORDEN = set("""
p bmd ongeval gev stof gaslekkage buiten binnen reanimatie afhijsen oms beheerssysteem detectie sprinkler
rook hitte br woning dak middel klein groot brandgerucht zc co melder co-melder stank hind lucht dier in problemen
veetakel ass politie ambu ambulance assistentie lift liftopsluiting storm boom wateroverlast nacontrole
container afval industrie wegvervoer voertuig intrekken alarm brw re nv bv
""".split())


# ---------------------------------------------------------------- hulpfuncties
def log(*args):
    print(*args, file=sys.stderr, flush=True)


def lees_json(path: Path, standaard):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return standaard


def schrijf_json(path: Path, data) -> bool:
    """Schrijft alleen als de inhoud echt veranderd is. Geeft True terug bij wijziging."""
    nieuw = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == nieuw:
        return False
    path.write_text(nieuw, encoding="utf-8")
    return True


def http_get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def normaliseer(tekst: str) -> str:
    """Kleine letters, haakjes weg, enkele spaties. RSS en website schrijven berichten net anders."""
    t = tekst.lower()
    t = re.sub(r"[()\[\]\"]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def bericht_sleutel(tekst: str, tijd: datetime) -> str:
    minuut = tijd.astimezone(timezone.utc).strftime("%Y%m%d%H%M")
    return hashlib.sha1(f"{minuut}|{normaliseer(tekst)}".encode()).hexdigest()[:16]


def is_brandweer(tekst: str) -> bool:
    t = normaliseer(tekst)
    return bool(re.search(r"\bbmd-\d+", t)) or "intrekken alarm brw" in t


# ---------------------------------------------------------------- 1. ophalen
def haal_feeds() -> list[dict]:
    berichten = []
    for p in PLAATSEN:
        url = FEED_URL.format(slug=p["slug"])
        try:
            xml = http_get(url)
        except Exception as e:  # noqa: BLE001
            log(f"  ! feed {p['slug']} niet bereikbaar: {e}")
            continue
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as e:
            log(f"  ! feed {p['slug']} onleesbaar: {e}")
            continue
        n = 0
        for item in root.iter("item"):
            titel = (item.findtext("title") or "").strip()
            if not is_brandweer(titel):
                continue
            pub = item.findtext("pubDate")
            try:
                tijd = email.utils.parsedate_to_datetime(pub)
            except (TypeError, ValueError):
                continue
            berichten.append({
                "tekst": titel,
                "omschrijving": (item.findtext("description") or "").strip(),
                "tijd": tijd.astimezone(timezone.utc).isoformat(),
                "feed": p["naam"],
                "link": (item.findtext("link") or "").split("?")[0],
                "bron": "rss",
            })
            n += 1
        log(f"  {p['naam']:<20} {n} brandweerberichten in feed")
        time.sleep(1)  # vriendelijk voor de server
    return berichten


# ---------------------------------------------------------------- 2. ontleden
def ontleed(b: dict) -> dict:
    t = normaliseer(b["tekst"])
    prio_m = re.match(r"p\s*([123])\b", t)
    prio = int(prio_m.group(1)) if prio_m else 2

    # roepnummers: de getallen van 6 cijfers aan het eind
    woorden = t.split()
    roep = []
    while woorden and re.fullmatch(r"\d{5,7}", woorden[-1]):
        roep.insert(0, woorden.pop())

    # plaats: de bekende plaatsnaam die het laatst in de tekst staat
    rest = " ".join(woorden)
    rest = re.sub(r"^p\s*[123]\s+", "", rest)
    rest = re.sub(r"^.*?\bbmd-\d+\s*", "", rest)  # alles t/m de BMD-code weg
    plaats = None
    for p in PLAATSEN_SORTED:
        if rest.endswith(" " + p["naam"].lower()) or rest == p["naam"].lower():
            plaats = p
            rest = rest[: -len(p["naam"])].strip()
            break
    if plaats is None:
        plaats = next((p for p in PLAATSEN if p["naam"] == b.get("feed")), PLAATSEN[0])

    soort = "Overig"
    for patroon, naam in SOORTEN:
        if re.search(patroon, t):
            soort = naam
            break

    # straatkandidaten: eerst uit de RSS-omschrijving ("Gaslek op Slotlaan in Zeist"),
    # dan de laatste 1–4 woorden vóór de plaatsnaam
    kandidaten = []
    m = re.search(r"\bop (.+?) in " + re.escape(plaats["naam"]), b.get("omschrijving", ""), re.I)
    if m:
        kandidaten.append(m.group(1).strip())
    rw = [w for w in re.split(r"\s+", rest) if w]
    for n in (4, 3, 2, 1):
        if len(rw) >= n:
            stuk = rw[-n:]
            eerste = stuk[0].strip(".:,-/").lower()
            if not eerste or eerste in STOPWOORDEN or eerste.isdigit():
                continue
            kandidaten.append(" ".join(stuk))

    return {
        "prio": prio,
        "soort": soort,
        "plaats": plaats,
        "roepnummers": roep,
        "kandidaten": list(dict.fromkeys(kandidaten)),
        "ingetrokken": "intrekken" in t,
    }


# ---------------------------------------------------------------- 3. geocoderen (PDOK)
def pdok_straat(kandidaat: str, gemeente: str) -> dict | None:
    params = [
        ("q", kandidaat),
        ("fq", "type:weg"),
        ("fq", f"gemeentenaam:\"{gemeente}\""),
        ("fl", "straatnaam,woonplaatsnaam,centroide_ll,score"),
        ("rows", "5"),
    ]
    url = PDOK_URL + "?" + urllib.parse.urlencode(params)
    docs = json.loads(http_get(url))["response"]["docs"]
    if not docs:
        return None
    k = kandidaat.lower().replace("prof.", "professor").replace("burg.", "burgemeester")
    beste = None
    for d in docs:
        naam = d.get("straatnaam", "").lower()
        if naam == k or naam == kandidaat.lower():
            beste = d
            break
    if beste is None:
        # geen exacte match: accepteer de eerste als het laatste woord overeenkomt
        laatste = kandidaat.lower().split()[-1]
        if docs[0].get("straatnaam", "").lower().endswith(laatste):
            beste = docs[0]
    if beste is None:
        return None
    lon, lat = map(float, re.findall(r"[-\d.]+", beste["centroide_ll"]))
    return {"straat": beste["straatnaam"], "woonplaats": beste.get("woonplaatsnaam"), "lat": round(lat, 5), "lon": round(lon, 5)}


def geocodeer(info: dict, cache: dict, online: bool) -> dict:
    gem = info["plaats"]["gemeente"]
    for kand in info["kandidaten"]:
        sleutel = f"{gem}|{kand.lower()}"
        if sleutel in cache:
            if cache[sleutel]:
                return {**cache[sleutel], "precisie": "straat"}
            continue
        if not online:
            continue
        try:
            res = pdok_straat(kand, gem)
        except Exception as e:  # noqa: BLE001
            log(f"  ! PDOK-fout voor '{kand}': {e}")
            online = False
            continue
        cache[sleutel] = res  # ook "niet gevonden" (None) onthouden
        time.sleep(0.2)
        if res:
            return {**res, "precisie": "straat"}
    p = info["plaats"]
    straat = info["kandidaten"][-1].title() if info["kandidaten"] else None
    return {"straat": straat, "woonplaats": p["naam"], "lat": p["lat"], "lon": p["lon"], "precisie": "plaats"}


# ---------------------------------------------------------------- 4. samenvoegen tot meldingen
def bouw_meldingen(berichten: list[dict], cache: dict, online: bool) -> list[dict]:
    berichten = sorted(berichten, key=lambda b: b["tijd"])
    meldingen: list[dict] = []
    for b in berichten:
        tijd = datetime.fromisoformat(b["tijd"])
        if tijd < START:
            continue
        info = ontleed(b)
        geo = geocodeer(info, cache, online)

        # Intrekken: markeer de laatste melding op dezelfde plaats (binnen 60 min) als ingetrokken
        if info["ingetrokken"]:
            for m in reversed(meldingen):
                dt = tijd - datetime.fromisoformat(m["time"])
                if dt > timedelta(minutes=60):
                    break
                if m["place"] == info["plaats"]["naam"] and (m["street"] == geo["straat"] or geo["precisie"] == "plaats"):
                    m["ingetrokken"] = True
                    m["raw_all"].append(b["tekst"])
                    break
            continue

        # Zelfde incident? Zelfde plaats + straat binnen 20 minuten (bv. extra voertuig of "afhijsen")
        samen = None
        for m in reversed(meldingen):
            dt = tijd - datetime.fromisoformat(m["time"])
            if dt > timedelta(minutes=20):
                break
            if m["place"] == info["plaats"]["naam"] and m["street"] == geo["straat"]:
                samen = m
                break
        if samen:
            samen["prio"] = min(samen["prio"], info["prio"])
            samen["caps"] = sorted(set(samen["caps"]) | set(info["roepnummers"]))
            samen["raw_all"].append(b["tekst"])
            continue

        meldingen.append({
            "id": bericht_sleutel(b["tekst"], tijd),
            "time": tijd.isoformat(),
            "place": info["plaats"]["naam"],
            "g": info["plaats"]["gemeente"],
            "type": info["soort"],
            "prio": info["prio"],
            "street": geo["straat"],
            "lat": geo["lat"],
            "lon": geo["lon"],
            "precisie": geo["precisie"],
            "raw": b["tekst"],
            "raw_all": [b["tekst"]],
            "caps": info["roepnummers"],
            "ingetrokken": False,
            "link": b.get("link") or None,
        })
    for m in meldingen:
        if len(m["raw_all"]) == 1:
            del m["raw_all"]
    return sorted(meldingen, key=lambda m: m["time"], reverse=True)


# ---------------------------------------------------------------- hoofdprogramma
def main() -> int:
    offline = "--offline" in sys.argv  # alleen herberekenen, niets ophalen
    DATA.mkdir(exist_ok=True)

    archief = lees_json(BERICHTEN, {"berichten": []})
    bekend = {bericht_sleutel(b["tekst"], datetime.fromisoformat(b["tijd"])) for b in archief["berichten"]}

    nieuw = 0
    if not offline:
        log("Feeds ophalen…")
        for b in haal_feeds():
            k = bericht_sleutel(b["tekst"], datetime.fromisoformat(b["tijd"]))
            if k not in bekend:
                bekend.add(k)
                archief["berichten"].append(b)
                nieuw += 1
    log(f"{nieuw} nieuwe brandweerberichten")
    archief["berichten"].sort(key=lambda b: b["tijd"], reverse=True)
    schrijf_json(BERICHTEN, archief)

    cache = lees_json(GEOCACHE, {})
    meldingen = bouw_meldingen(archief["berichten"], cache, online=not offline)
    schrijf_json(GEOCACHE, dict(sorted(cache.items())))

    oud = lees_json(MELDINGEN, {})
    if oud.get("meldingen") == meldingen:
        log("Geen wijzigingen in meldingen.json")
        return 0
    schrijf_json(MELDINGEN, {
        "bijgewerkt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bron": "alarmeringen.nl",
        "meldingen": meldingen,
    })
    log(f"meldingen.json bijgewerkt: {len(meldingen)} meldingen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
