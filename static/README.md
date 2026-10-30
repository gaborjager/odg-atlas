# Static maps

This folder holds maps drawn or edited by hand, published in the atlas as
they are (not generated from a GeoJSON source). Each map is a pair of files:

```
static/<id>.odg     the map, saved with LibreOffice Draw
static/<id>.json    its description
```

`<id>` uses lowercase letters, digits and `-` (e.g. `sales-areas`). It must not
be the id or the file name of a generated map.

## The map (`.odg`)

- One shape per zone (polygon, path, rectangle…), **named with the code of the
  zone**: right-click the shape → *Name…*. This name is the key used to join
  the data (e.g. `FR`, `75`, `NORTH`). Codes must be unique in the map.
- Optionally, a description of each zone (right-click → *Description…*), e.g.
  `75 - Paris`: CalcMap adds the value after it in the alternative text.
- Other shapes (title, frame, legend) are allowed if they have **no name**.
- Shapes may be grouped; they should not be rotated.

## The description (`.json`)

```json
{
  "title": "France - Sales areas",
  "title_fr": "France - Secteurs commerciaux",
  "title_de": "Frankreich - Verkaufsgebiete",
  "description": "Sales areas of the company. Each shape carries the area code in draw:name.",
  "description_fr": "Secteurs commerciaux de l'entreprise. Chaque forme porte le code du secteur dans draw:name.",
  "description_de": "Verkaufsgebiete des Unternehmens. Jede Form trägt den Code des Gebiets in draw:name.",
  "area": "France",
  "code_type": "Area code (NORTH, SOUTH…)",
  "source": "Drawn by Jane Doe from the Admin Express departments",
  "license": "Licence Ouverte / Open Licence 2.0 (Etalab)"
}
```

Required: `title`, `description`, `area`, `code_type`, `source`, `license`.
Optional: translations `title_<lang>` and `description_<lang>` (two-letter
language code; they go to `output/i18n/maps.<lang>.json`, English is used for
the other languages), and `projection` (e.g. `EPSG:2154 (Lambert-93)`).

Only add maps whose source allows redistribution, and give it in `source` and
`license`.

## Checking and publishing

```bash
python scripts/generate_odg.py --check          # checks the static maps
python scripts/generate_odg.py --catalog-only   # adds them to output/maps.json, with a preview
```

A pull request that changes `static/` is checked automatically. Once merged,
the catalog is rebuilt and a new release of the atlas is published.
