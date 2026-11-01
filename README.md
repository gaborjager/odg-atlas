# 🗺️ ODG Atlas - base maps for LibreOffice / Collabora

Ready-to-use **`.odg`** base maps (OpenDocument Graphics), one shape per
administrative zone, **named with the official code of the zone**: for
LibreOffice Draw, LibreOffice Calc with the [CalcMap](https://github.com/gaborjager/calcmap)
extension (thematic maps from a spreadsheet), Collabora Office and any ODF
software.

Most maps are generated automatically from open GeoJSON sources by
**GitHub Actions**, and regenerated when a source changes. Maps drawn by hand
can be added too (*static maps*). Each change of the maps is published as a
**release**.

---

## 📦 Available maps

| Map | File | Zones | `draw:name` | Source | Size |
|---|---|---|---|---|---|
| France - Regions | [`output/regions-france.odg`](output/regions-france.odg) | 13 regions | INSEE region code (e.g. `84`) | [france-geojson](https://github.com/gregoiredavid/france-geojson) | ~40 KB |
| France - Departments | [`output/departements-france.odg`](output/departements-france.odg) | 96 departments | INSEE department code (e.g. `75`) | [france-geojson](https://github.com/gregoiredavid/france-geojson) | ~90 KB |
| France - Cantons | [`output/cantons-france.odg`](output/cantons-france.odg) | ~2,300 cantons + municipal districts + municipalities of the Rhône | INSEE code (e.g. `75056`) | [france-geojson](https://github.com/gregoiredavid/france-geojson), [geo.api.gouv.fr](https://geo.api.gouv.fr/) | ~950 KB |
| France - Municipalities | [`output/communes-france.odg`](output/communes-france.odg) | ~35,000 municipalities ⚠️ heavy file | INSEE municipality code (e.g. `75056`) | [france-geojson](https://github.com/gregoiredavid/france-geojson) | ~3.2 MB |
| European Union - Countries | [`output/eu-countries.odg`](output/eu-countries.odg) | 27 member states | ISO 3166-1 alpha-2 code (e.g. `FR`) | [Natural Earth](https://www.naturalearthdata.com/) 1:50m | ~50 KB |
| World - Continents (Robinson) | [`output/world-continents-robinson.odg`](output/world-continents-robinson.odg) | 7 continents | Continent code (e.g. `EU`) | [Natural Earth](https://www.naturalearthdata.com/) 1:50m | ~90 KB |
| World - Continents (Equal Earth) | [`output/world-continents-equal-earth.odg`](output/world-continents-equal-earth.odg) | 7 continents | Continent code (e.g. `EU`) | [Natural Earth](https://www.naturalearthdata.com/) 1:50m | ~90 KB |
| World - Continents (Miller) | [`output/world-continents-miller.odg`](output/world-continents-miller.odg) | 7 continents | Continent code (e.g. `EU`) | [Natural Earth](https://www.naturalearthdata.com/) 1:50m | ~90 KB |
| World - Countries (Robinson) | [`output/world-countries-robinson.odg`](output/world-countries-robinson.odg) | 237 countries and territories | ISO 3166-1 alpha-2 code (e.g. `FR`) | [Natural Earth](https://www.naturalearthdata.com/) 1:50m | ~525 KB |
| World - Countries (Equal Earth) | [`output/world-countries-equal-earth.odg`](output/world-countries-equal-earth.odg) | 237 countries and territories | ISO 3166-1 alpha-2 code (e.g. `FR`) | [Natural Earth](https://www.naturalearthdata.com/) 1:50m | ~525 KB |
| World - Countries (Miller) | [`output/world-countries-miller.odg`](output/world-countries-miller.odg) | 237 countries and territories | ISO 3166-1 alpha-2 code (e.g. `FR`) | [Natural Earth](https://www.naturalearthdata.com/) 1:50m | ~530 KB |
| Africa - Countries | [`output/africa-countries.odg`](output/africa-countries.odg) | 55 countries and territories | ISO 3166-1 alpha-2 code (e.g. `FR`) | [Natural Earth](https://www.naturalearthdata.com/) 1:50m | ~70 KB |
| Asia - Countries | [`output/asia-countries.odg`](output/asia-countries.odg) | 52 countries and territories | ISO 3166-1 alpha-2 code (e.g. `FR`) | [Natural Earth](https://www.naturalearthdata.com/) 1:50m | ~100 KB |
| Europe - Countries | [`output/europe-countries.odg`](output/europe-countries.odg) | 51 countries and territories | ISO 3166-1 alpha-2 code (e.g. `FR`) | [Natural Earth](https://www.naturalearthdata.com/) 1:50m | ~60 KB |
| North America - Countries | [`output/north-america-countries.odg`](output/north-america-countries.odg) | 38 countries and territories | ISO 3166-1 alpha-2 code (e.g. `FR`) | [Natural Earth](https://www.naturalearthdata.com/) 1:50m | ~45 KB |
| Oceania - Countries | [`output/oceania-countries.odg`](output/oceania-countries.odg) | 21 countries and territories | ISO 3166-1 alpha-2 code (e.g. `FR`) | [Natural Earth](https://www.naturalearthdata.com/) 1:50m | ~10 KB |
| South America - Countries | [`output/south-america-countries.odg`](output/south-america-countries.odg) | 14 countries and territories | ISO 3166-1 alpha-2 code (e.g. `FR`) | [Natural Earth](https://www.naturalearthdata.com/) 1:50m | ~40 KB |

Download a single map from the links above, or all of them from the latest
[release](https://github.com/gaborjager/odg-atlas/releases/latest).

**Notes**

- French maps: metropolitan France, Lambert-93 projection, same extent for all
  of them (they can be overlaid). Paris, Lyon (Metropolis) and Marseille have
  no cantons in the source GeoJSON: the cantons map is completed by their
  municipal districts (Paris, Marseille) and the municipalities of the Rhône
  department (Lyon Metropolis).
- European Union: same frame and projection as the *Europe* map (ETRS89-LAEA
  Europe), so the two can be overlaid. The 27 member states are the zones. The
  other countries of Europe are white *optional zones*, with their borders and
  their ISO code (`draw:name`, and `svg:title` = `optional-zone`): CalcMap 0.24
  or later colors them if the data has their code and leaves them white
  otherwise; the catalog counts only the 27 members. Mainland and nearby islands; the outermost regions
  (Canary Islands, Azores, Madeira, overseas departments) are not shown. Greece is coded `GR` (ISO), not `EL` as in
  Eurostat data. Cyprus is the area under the control of the Republic of
  Cyprus, as in Natural Earth.
- World maps: each one exists in three projections, in separate files
  (`world-<continents|countries>-<projection>.odg`), Antarctica included:
  - *Robinson*: compromise between areas and shapes, the usual look of world
    atlases; the recommended choice for thematic maps.
  - *Equal Earth*: exact areas; shapes are flattened near the poles and
    sheared near the edges.
  - *Miller*: rectangular map with straight meridians; high latitudes are
    strongly enlarged (Greenland, Canada, Antarctica).
  - *Countries*: countries and territories with an ISO 3166-1 alpha-2 code.
    The few zones without one are merged into the country that holds them in
    ISO 3166: Somaliland into Somalia (`SO`), Northern Cyprus into Cyprus
    (`CY`), the Siachen Glacier into India (`IN`, which controls it).
    Australia (`AU`) includes Christmas Island, the Cocos Islands and the
    Ashmore and Cartier Islands, as in Natural Earth.
  - *Continents*: `AF` Africa, `AN` Antarctica, `AS` Asia, `EU` Europe,
    `NA` North America, `OC` Oceania, `SA` South America. Countries are grouped
    by continent as in Natural Earth (e.g. Turkey, Cyprus and the Caucasus in
    Asia), except that Russia is cut at the meridian 60°E (approximation of the
    Ural) and that overseas territories belong to their geographic continent
    (French Guiana, Antilles, Réunion, Mayotte, Caribbean Netherlands, Canary
    Islands, Madeira). Simplified for this scale: islands under 5,000 km²
    are removed (Corsica, Cyprus, Crete, Hawaii are kept) and the outlines
    are smoothed (~5 km); the borders between continents are not changed.
  - Chukotka and the islands of Fiji east of 180° are drawn next to the rest
    of Russia and Fiji, at the right edge of the map.
- Continent maps: simplified, for a page or a slide. There is one per continent
  with countries (none for Antarctica), each with its own centered projection
  (Lambert azimuthal equal-area). The very small islands are removed and the
  coasts smoothed, but no country or territory disappears, even the smallest
  ones. Countries are grouped as in the *Continents* map above, with these
  differences:
  - *Europe* is the continent, not the European Union: it has 51 countries
    and territories, among them the United Kingdom, Norway, Switzerland,
    Ukraine and the Balkans. Cyprus is included, although Natural Earth places
    it in Asia, so that all the EU members are there. Turkey and the Caucasus
    are in Asia. Overseas territories are not shown.
  - *Russia* is cut at the meridian 60°E (Ural): `RU` is in both the Europe and
    Asia maps, each with its own part.
  - *Asia*: the Australian territories of the Indian Ocean are not shown.
  - *South America*: French Guiana is included, with the code `GF`.
  - *Oceania*: the islands east of 165°W (eastern Polynesia) are not shown.

---

## 📇 JSON catalog (automatic download)

The file [`output/maps.json`](output/maps.json) lists the available maps and is
the reference for software that downloads the maps automatically:

```
https://raw.githubusercontent.com/gaborjager/odg-atlas/main/output/maps.json
```

```json
{
  "version": 1,
  "title": "ODG Atlas",
  "translations": "https://raw.githubusercontent.com/gaborjager/odg-atlas/main/output/i18n/maps.{lang}.json",
  "languages": ["ar", "bg", "cs", "…"],
  "maps": [
    {
      "id": "eu-countries",
      "title": "European Union - Countries",
      "description": "Map of the 27 member states of the European Union …",
      "area": "European Union",
      "code_type": "ISO 3166-1 alpha-2",
      "projection": "EPSG:3035 (ETRS89-LAEA Europe)",
      "source": "Natural Earth 1:50m Admin 0 - Countries",
      "license": "Public domain (Natural Earth)",
      "kind": "generated",
      "url": "https://raw.githubusercontent.com/gaborjager/odg-atlas/main/output/eu-countries.odg",
      "filename": "eu-countries.odg",
      "format": "application/vnd.oasis.opendocument.graphics",
      "size": 51234,
      "sha256": "…",
      "objects": 27,
      "code_examples": ["AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI"],
      "preview": "https://raw.githubusercontent.com/gaborjager/odg-atlas/main/output/previews/eu-countries.svg",
      "preview_sha256": "…"
    }
  ]
}
```

- `id` is stable and is the key; `sha256` is the hash of the `.odg` file (check
  it after download, and compare it to know whether an update is needed).
- `title` and `description` are in English, the default language. The
  translations are in one file per language, `output/i18n/maps.<lang>.json`
  (see below). `title_fr` and `description_fr` remain in the catalog for
  CalcMap up to 0.20.2.
- `area`: covered territory; `code_type`: codes carried by the zones
  (`draw:name`), to join the data; `source` and `license`: origin of the data.
- `kind`: `generated` (from a GeoJSON source) or `static` (drawn by hand).
- `objects`: number of zones of the map: software can leave out maps that are
  too detailed for it.
- `code_examples`: first zone codes, 10 at most (alphabetical order), to illustrate the
  expected codes.
- `codes`: all the zone codes, separated by `|` (maps of 300 zones at most):
  software can find the map that matches a column of data.
- `preview`: SVG preview of the map (300 × 250 px, in
  [`output/previews/`](output/previews/)); `preview_sha256` is its hash.
- Generated ODG files and previews are deterministic: the hash only changes
  when the content changes.
- The catalog is rewritten on every run of the generation workflow.

### Translations

[`output/maps.json`](output/maps.json) holds the technical data and the English
texts. Each language has its own small file, listed by `languages`; replace
`{lang}` in `translations` to get its address:

```json
{
  "regions": {
    "title": "France - Carte régionale",
    "description": "Carte des 13 régions de France métropolitaine. …"
  }
}
```

If a language or a map has no translation, use the English text of the catalog.

The sources are in [`translations/`](translations/), one file per language
(`<lang>.json`). They hold the texts of each map, by id; the six world maps
share `world-continents` and `world-countries`, followed by the name of the
projection (`_projection`). The translations were written by machine and have
not been reviewed by native speakers: corrections are welcome.

---

## ➕ Adding a map

**A map generated from a GeoJSON source**: add an entry to `MAPS` in
[`scripts/generate_odg.py`](scripts/generate_odg.py) (source URL, properties
holding the code and the name, projection, extent, filters), then run the
script. Add its title and description to the files of
[`translations/`](translations/) (a language without them shows the English
text). The available projections are Lambert-93 (France), ETRS89-LAEA
(Europe), Robinson, Equal Earth and Miller (world), Lambert azimuthal equal-area
(continents, `CONTINENT_CENTERS`); another one can be added to `PROJECTIONS`. The projections of the world maps are in `WORLD_PROJECTIONS`.

**A static map, drawn by hand** in LibreOffice Draw: put `static/<id>.odg` and
its description `static/<id>.json` in the [`static/`](static/) folder; the
rules (zones named with their code, required metadata) are in
[`static/README.md`](static/README.md). A pull request is checked
automatically; once merged, the map is added to the catalog and published in
a release.

---

## 🚀 Use in LibreOffice Calc (CalcMap)

[CalcMap](https://github.com/gaborjager/calcmap) colors these maps from two
columns of a spreadsheet, **code | value**: it reads the catalog, downloads
the chosen map and keeps it up to date. See its README.

> The `draw:name` field of each shape holds the **official code** of the zone,
> directly usable as a join key with your data.

---

## 🖊️ Use in LibreOffice Draw

1. **File → Open** → select the `.odg` file
2. Each zone is an independent `draw:path` object, selectable and stylable
3. To identify a zone: right-click → **Name** → the name shown is the code of the zone
4. To color it by hand: click a zone → **Format → Area**

---

## ⚙️ Automatic updates and releases (CI/CD)

A **GitHub Actions** workflow (*Generate ODG maps*) runs every night at 03:00
UTC, and on each push that changes a static map or the generator:

```
GeoJSON sources              static/ maps
        │                         │
        ▼                         │
 Same SHA-256 hash?               │
        │                         │
    No ──► Regenerate the ODG ────┤
        │                         ▼
    Yes ──────────────────► Rewrite output/maps.json ──► Automatic commit
                                                               │
                                                               ▼
                                     Maps changed since the latest release?
                                                               │
                                       Yes ──► Release "ODG Atlas 1.3.YYYYMMDD"
```

The *Release maps* workflow compares the catalog with the one of the latest
release. If a map was added, updated or removed, it publishes a release
listing the changes, with all the maps and `maps.json` attached.

Releases are numbered **`1.3.YYYYMMDD`** (tag `v1.3.YYYYMMDD`), with the date
of the day: the series (`SERIES` in
[`scripts/release_notes.py`](scripts/release_notes.py)) is raised by hand when
maps are added: `1.0` for the French and EU maps, `1.1` with the world maps,
`1.2` with one file per projection for them, `1.3` with the continent maps.
A second
release on the same day gets the suffix `.2`. The first release was tagged
`maps-2026.10.23`.

### Manual run

From the **Actions → Generate ODG maps → Run workflow** tab:

| Option | Description |
|---|---|
| **Force** | Regenerates even if the source has not changed |
| **Maps** | Choose a subset (e.g. `regions,departements`) |

The generated ODG files are also available as **workflow artifacts**
(Actions tab → run → Artifacts) for 90 days.

---

## 💻 Local generation on Windows (PowerShell)

The original PowerShell scripts are in `scripts/ps/`, for the French maps
only. They work **without any dependency** (.NET standard library only), with
the same Lambert-93 projection and the same layout as the Python script.

```powershell
# Regions
.\scripts\ps\geojson-region-to-odg.ps1

# Departments
.\scripts\ps\geojson-departement-to-odg.ps1

# Cantons (+ municipal districts + Rhône)
.\scripts\ps\geojson-canton-to-odg.ps1

# Municipalities (~35,000 zones, several minutes)
.\scripts\ps\geojson-commune-to-odg.ps1

# With a custom output path
.\scripts\ps\geojson-departement-to-odg.ps1 -OutputFile "C:\maps\france.odg"
```

---

## 🐍 Local generation on Linux / macOS / Windows (Python)

The Python script `scripts/generate_odg.py` is the one used by GitHub Actions
(all maps, `output/maps.json` and previews). It needs **Python 3.8+**, with no
external dependency:

```bash
# All the maps
python scripts/generate_odg.py

# Regenerate even if the source has not changed
python scripts/generate_odg.py --force

# Only some maps
python scripts/generate_odg.py --only regions,eu-countries

# No download: check the static maps and rewrite the catalog
python scripts/generate_odg.py --catalog-only

# Only check the static maps
python scripts/generate_odg.py --check
```

`python scripts/release_notes.py` shows what the next release would contain.

---

## 📐 Technical characteristics

| Setting | Value |
|---|---|
| Output format | ODF Graphics 1.3 (`.odg`) |
| Projections | Lambert-93 (EPSG:2154) for France, ETRS89-LAEA (EPSG:3035) for Europe, Robinson (ESRI:54030), Equal Earth (EPSG:8857) and Miller (ESRI:54003) for the world, Lambert azimuthal equal-area for the continents; same scale in X and Y |
| Page size | 30 × 25 cm, landscape |
| Fill color | `#6AAED6` (light blue) |
| Outline color | `#1A4F7A` (dark blue) |
| Outline width | `0.018 cm` (regions, departments, cantons, EU countries, continents), `0.012 cm` (countries of a continent), `0.008 cm` (world countries), `0.004 cm` (municipalities) |
| Name of each shape | `draw:name` = official code of the zone |
| Description of each shape | `svg:desc` = `code - name` (e.g. `75 - Paris`, `FR - France`) |

---

## 📚 Sources and licenses

| Source | Maps | License |
|---|---|---|
| [gregoiredavid/france-geojson](https://github.com/gregoiredavid/france-geojson) (IGN Admin Express) | France | Licence Ouverte / Open Licence 2.0 (Etalab) |
| [geo.api.gouv.fr](https://geo.api.gouv.fr/) (municipal districts, municipalities of the Rhône) | France - Cantons | Licence Ouverte / Open Licence 2.0 (Etalab) |
| [Natural Earth](https://www.naturalearthdata.com/) 1:50m Admin 0 - Countries | European Union, World, continents | Public domain |

Each map keeps the license of its source (field `license` of the catalog). The
French maps inherit the Etalab **Licence Ouverte / Open Licence 2.0**,
compatible with commercial and non-commercial reuse with attribution of the
source.
