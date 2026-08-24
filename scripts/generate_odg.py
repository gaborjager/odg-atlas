"""
generate_odg.py
Traduit fidèlement les 4 scripts PowerShell geojson-*-to-odg.ps1.
Génère des fichiers .odg (OpenDocument Graphics) pour LibreOffice / Collabora.

Usage :
    python scripts/generate_odg.py [--force] [--only departements,regions,cantons,communes]
"""

import argparse
import hashlib
import io
import json
import math
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Mise en page — identique aux scripts PS
# ---------------------------------------------------------------------------
PAGE_W = 30.0
PAGE_H = 25.0

M_LON_MIN, M_LON_MAX = -5.5, 9.7
M_LAT_MIN, M_LAT_MAX = 41.2, 51.2
M_LON_RNG = M_LON_MAX - M_LON_MIN
M_LAT_RNG = M_LAT_MAX - M_LAT_MIN

MID_LAT    = (M_LAT_MIN + M_LAT_MAX) / 2
COS_MID    = math.cos(MID_LAT * math.pi / 180)
MAP_H      = PAGE_H
MAP_W      = min(MAP_H * (M_LON_RNG * COS_MID) / M_LAT_RNG, PAGE_W)
X_OFF      = (PAGE_W - MAP_W) / 2

FILL_COLOR   = "#6AAED6"
STROKE_COLOR = "#1A4F7A"

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
SOURCES = {
    "regions": {
        "label":       "Régions de France",
        "page_name":   "Regions de France",
        "url":         "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/regions-version-simplifiee.geojson",
        "output":      "output/regions-france.odg",
        "cache":       "cache/regions.hash",
        "stroke_w":    "0.018cm",
        "extra_urls":  [],
    },
    "departements": {
        "label":       "Départements de France",
        "page_name":   "Departements de France",
        "url":         "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-version-simplifiee.geojson",
        "output":      "output/departements-france.odg",
        "cache":       "cache/departements.hash",
        "stroke_w":    "0.018cm",
        "extra_urls":  [],
    },
    "cantons": {
        "label":       "Cantons de France",
        "page_name":   "Cantons de France",
        "url":         "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/cantons-version-simplifiee.geojson",
        "output":      "output/cantons-france.odg",
        "cache":       "cache/cantons.hash",
        "stroke_w":    "0.018cm",
        # Arrondissements municipaux + communes du Rhône (Métropole de Lyon)
        # Arrondissements municipaux (Paris 75, Lyon 69, Marseille 13) et
        # communes de la Métropole de Lyon (dept 69) — zones sans cantons dans le GeoJSON source.
        # Identique à la logique du script PS original.
        "extra_urls":  [
            {
                "role":  "arrondissements",
                "url":   "https://geo.api.gouv.fr/communes?type=arrondissement-municipal&fields=nom,code&geometry=contour&format=geojson",
            },
            {
                "role":  "rhone",
                "url":   "https://geo.api.gouv.fr/communes?codeDepartement=69&fields=nom,code&geometry=contour&format=geojson",
            },
        ],
    },
    "communes": {
        "label":       "Communes de France",
        "page_name":   "Communes de France",
        "url":         "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/communes-version-simplifiee.geojson",
        "output":      "output/communes-france.odg",
        "cache":       "cache/communes.hash",
        "stroke_w":    "0.004cm",
        "extra_urls":  [],
    },
}

# ---------------------------------------------------------------------------
# Helpers géométrie — logique identique aux fonctions PS Get-BBox / Get-PathData
# ---------------------------------------------------------------------------

def get_rings(geometry):
    """Yield chaque anneau (liste de coordonnées) d'un Polygon ou MultiPolygon."""
    if geometry["type"] == "MultiPolygon":
        for poly in geometry["coordinates"]:
            yield from poly
    else:
        yield from geometry["coordinates"]


def get_bbox(geometry):
    lons, lats = [], []
    for ring in get_rings(geometry):
        for pt in ring:
            lons.append(float(pt[0]))
            lats.append(float(pt[1]))
    return min(lons), max(lons), min(lats), max(lats)


def get_path_data(geometry, origin_lon, origin_lat_max, sx, sy):
    parts = []
    for ring in get_rings(geometry):
        coords = []
        for pt in ring:
            x = round((float(pt[0]) - origin_lon) * sx, 1)
            y = round((origin_lat_max - float(pt[1])) * sy, 1)
            coords.append(f"{x} {y}")
        parts.append("M " + " L ".join(coords) + " Z")
    return " ".join(parts)


def escape_xml(s):
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))


# ---------------------------------------------------------------------------
# Génération XML ODG
# ---------------------------------------------------------------------------
MANIFEST_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"
                   manifest:version="1.3">
  <manifest:file-entry manifest:full-path="/"
                       manifest:version="1.3"
                       manifest:media-type="application/vnd.oasis.opendocument.graphics"/>
  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
  <manifest:file-entry manifest:full-path="styles.xml"  manifest:media-type="text/xml"/>
</manifest:manifest>"""

STYLES_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
  xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
  xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
  office:version="1.3">
  <office:styles>
    <style:style style:name="base" style:family="graphic">
      <style:graphic-properties draw:fill="solid" draw:fill-color="#CCCCCC"
        draw:stroke="solid" svg:stroke-color="#000000" svg:stroke-width="0.02cm"
        draw:shadow="hidden"
        xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"/>
    </style:style>
  </office:styles>
  <office:automatic-styles>
    <style:page-layout style:name="PM1">
      <style:page-layout-properties
        fo:page-width="{pw}cm" fo:page-height="{ph}cm"
        fo:margin-top="0cm" fo:margin-bottom="0cm"
        fo:margin-left="0cm" fo:margin-right="0cm"
        style:print-orientation="landscape"/>
    </style:page-layout>
  </office:automatic-styles>
  <office:master-styles>
    <style:master-page style:name="Default" style:page-layout-name="PM1"/>
  </office:master-styles>
</office:document-styles>""".format(pw=PAGE_W, ph=PAGE_H)


def build_shape(feat, style_name, stroke_w):
    """Construit les lignes XML style + shape pour une feature GeoJSON."""
    code = escape_xml(feat["properties"].get("code", ""))
    nom  = escape_xml(feat["properties"].get("nom", ""))
    geom = feat["geometry"]

    lon_min, lon_max, lat_min, lat_max = get_bbox(geom)
    lon_rng = max(lon_max - lon_min, 0.0001)
    lat_rng = max(lat_max - lat_min, 0.0001)

    x_cm = round(X_OFF + (lon_min - M_LON_MIN) / M_LON_RNG * MAP_W, 4)
    y_cm = round((M_LAT_MAX - lat_max) / M_LAT_RNG * MAP_H, 4)
    w_cm = round(lon_rng / M_LON_RNG * MAP_W, 4)
    h_cm = round(lat_rng / M_LAT_RNG * MAP_H, 4)

    vb_w = max(1, int(w_cm * 1000))
    vb_h = max(1, int(h_cm * 1000))
    s_x  = vb_w / lon_rng
    s_y  = vb_h / lat_rng

    path_data = get_path_data(geom, lon_min, lat_max, s_x, s_y)

    style_xml = (
        f'    <style:style style:name="{style_name}" style:family="graphic" '
        f'style:parent-style-name="base"><style:graphic-properties '
        f'draw:fill="solid" draw:fill-color="{FILL_COLOR}" draw:stroke="solid" '
        f'svg:stroke-color="{STROKE_COLOR}" svg:stroke-width="{stroke_w}" '
        f'draw:shadow="hidden" fo:padding="0cm"/></style:style>'
    )
    shape_xml = (
        f'      <draw:path draw:style-name="{style_name}" draw:name="{code}"'
        f' draw:layer="layout"'
        f' svg:x="{x_cm}cm" svg:y="{y_cm}cm"'
        f' svg:width="{w_cm}cm" svg:height="{h_cm}cm"'
        f' svg:viewBox="0 0 {vb_w} {vb_h}"'
        f' svg:d="{path_data}">'
        f'<svg:desc>{code} - {nom}</svg:desc></draw:path>'
    )
    return style_xml, shape_xml


def build_odg_bytes(page_name, styles_lines, shapes_lines):
    """Assemble le fichier ODG en mémoire et retourne les bytes."""
    content_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<office:document-content\n'
        '  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"\n'
        '  xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"\n'
        '  xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"\n'
        '  xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"\n'
        '  xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"\n'
        '  office:version="1.3">\n'
        '  <office:automatic-styles>\n'
        + "\n".join(styles_lines) + "\n"
        '  </office:automatic-styles>\n'
        '  <office:body>\n'
        '    <office:drawing>\n'
        f'      <draw:page draw:name="{page_name}" draw:master-page-name="Default">\n'
        + "\n".join(shapes_lines) + "\n"
        '      </draw:page>\n'
        '    </office:drawing>\n'
        '  </office:body>\n'
        '</office:document-content>'
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # mimetype en premier, non compressé — obligatoire ODF
        zf.writestr(
            zipfile.ZipInfo("mimetype"),
            "application/vnd.oasis.opendocument.graphics",
        )
        zf.writestr("META-INF/manifest.xml", MANIFEST_XML.encode("utf-8"),
                    compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("styles.xml",  STYLES_XML.encode("utf-8"),
                    compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr("content.xml", content_xml.encode("utf-8"),
                    compress_type=zipfile.ZIP_DEFLATED)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Hash / cache
# ---------------------------------------------------------------------------
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def read_hash(path: str) -> str:
    p = Path(path)
    return p.read_text().strip() if p.exists() else ""

def write_hash(path: str, h: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(h)

def fetch(url: str, label="") -> bytes:
    print(f"  Téléchargement {label or url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "carte-france-odg/1.0 (github-actions)"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = r.read()
    print(f"  -> {len(data)//1024} Ko reçus.")
    return data

# ---------------------------------------------------------------------------
# Génération d'un ODG
# ---------------------------------------------------------------------------
def generate(name: str, cfg: dict, force: bool) -> bool:
    print(f"\n=== {cfg['label']} ===")

    raw_main = fetch(cfg["url"], "GeoJSON principal")
    new_hash = sha256_bytes(raw_main)

    # Pour les cantons, inclure les URLs extra dans le hash
    extra_raws = {}
    for ex in cfg["extra_urls"]:
        extra_raws[ex["role"]] = fetch(ex["url"], ex["role"])
        new_hash = sha256_bytes(new_hash.encode() + extra_raws[ex["role"]])

    old_hash = read_hash(cfg["cache"])
    if new_hash == old_hash and not force:
        print("  Source inchangée — ODG déjà à jour.")
        return False

    print("  Source modifiée (ou forçage) — régénération...")

    features_main = json.loads(raw_main)["features"]
    print(f"  {len(features_main)} entités principales chargées.")

    styles_lines = []
    shapes_lines = []
    i = 0

    # ── Cantons : ordre d'empilement identique au script PS ──────────────────
    # 1. Communes du Rhône (69) en fond (bouche les trous Métropole de Lyon)
    if "rhone" in extra_raws:
        feats_rhone = json.loads(extra_raws["rhone"])["features"]
        print(f"  {len(feats_rhone)} communes du Rhône en fond.")
        for feat in feats_rhone:
            sl, sh = build_shape(feat, f"m{i}", cfg["stroke_w"])
            styles_lines.append(sl); shapes_lines.append(sh); i += 1

    # 2. Arrondissements municipaux (Paris, Lyon, Marseille)
    if "arrondissements" in extra_raws:
        feats_arr = json.loads(extra_raws["arrondissements"])["features"]
        print(f"  {len(feats_arr)} arrondissements municipaux.")
        for feat in feats_arr:
            sl, sh = build_shape(feat, f"a{i}", cfg["stroke_w"])
            styles_lines.append(sl); shapes_lines.append(sh); i += 1

    # 3. Entités principales (régions / départements / cantons / communes)
    log_step = 1000 if len(features_main) > 5000 else 25
    for feat in features_main:
        sl, sh = build_shape(feat, f"s{i}", cfg["stroke_w"])
        styles_lines.append(sl); shapes_lines.append(sh); i += 1
        if i % log_step == 0:
            print(f"  {i} / {len(features_main) + (i - len(features_main))} traités...")

    print(f"  -> {i} formes au total.")

    odg_bytes = build_odg_bytes(cfg["page_name"], styles_lines, shapes_lines)

    out = Path(cfg["output"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(odg_bytes)
    write_hash(cfg["cache"], new_hash)

    size_kb = len(odg_bytes) / 1024
    print(f"  ODG généré : {cfg['output']} ({size_kb:.0f} Ko)")
    return True

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force",  action="store_true",
                        help="Régénérer même si la source n'a pas changé")
    parser.add_argument("--only",   default="",
                        help="Virgule-séparé : regions,departements,cantons,communes")
    args = parser.parse_args()

    force = args.force or os.environ.get("FORCE_REGENERATE", "").lower() in ("1","true","yes")
    only  = {s.strip() for s in args.only.split(",") if s.strip()} if args.only else set(SOURCES)

    repo_root = Path(__file__).parent.parent
    os.chdir(repo_root)

    changed = []
    for name, cfg in SOURCES.items():
        if name not in only:
            continue
        try:
            if generate(name, cfg, force):
                changed.append(name)
        except Exception as exc:
            print(f"  ERREUR [{name}] : {exc}", file=sys.stderr)
            sys.exit(1)

    if changed:
        print(f"\nFichiers régénérés : {', '.join(changed)}")
    else:
        print("\nAucun fichier à régénérer.")

    gha = os.environ.get("GITHUB_OUTPUT", "")
    if gha:
        with open(gha, "a") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")
            f.write(f"changed_files={','.join(changed)}\n")

if __name__ == "__main__":
    main()
