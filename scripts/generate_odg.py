"""
generate_odg.py
Builds the ODG Atlas: .odg base maps (OpenDocument Graphics) for LibreOffice /
Collabora, generated from GeoJSON sources, plus static maps added by hand in
static/, and the catalog output/maps.json (URL, SHA-256, number of zones, code
examples and SVG preview of each map, in output/previews/).

Usage:
    python scripts/generate_odg.py [--force] [--only regions,eu-countries]
    python scripts/generate_odg.py --catalog-only   # no download: static maps and catalog
    python scripts/generate_odg.py --check          # only checks the static maps
"""

import argparse
import hashlib
import io
import json
import math
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Lambert-93 projection (EPSG:2154) - secant conformal conic, GRS80 ellipsoid
# IGN formulas (NTG_71), implemented without external dependencies.
# ---------------------------------------------------------------------------
GRS80_A = 6378137.0
GRS80_F = 1 / 298.257222101
GRS80_E = math.sqrt(2 * GRS80_F - GRS80_F ** 2)

L93_LON0 = math.radians(3.0)
L93_LAT0 = math.radians(46.5)
L93_LAT1 = math.radians(44.0)
L93_LAT2 = math.radians(49.0)
L93_X0 = 700000.0
L93_Y0 = 6600000.0


def _l93_m(phi):
    return math.cos(phi) / math.sqrt(1 - (GRS80_E * math.sin(phi)) ** 2)


def _l93_t(phi):
    es = GRS80_E * math.sin(phi)
    return math.tan(math.pi / 4 - phi / 2) / ((1 - es) / (1 + es)) ** (GRS80_E / 2)


L93_N = ((math.log(_l93_m(L93_LAT1)) - math.log(_l93_m(L93_LAT2)))
         / (math.log(_l93_t(L93_LAT1)) - math.log(_l93_t(L93_LAT2))))
L93_AF = GRS80_A * _l93_m(L93_LAT1) / (L93_N * _l93_t(L93_LAT1) ** L93_N)
L93_RHO0 = L93_AF * _l93_t(L93_LAT0) ** L93_N


def lambert93(lon, lat):
    """(lon, lat) WGS84 in degrees -> (X, Y) Lambert-93 in meters."""
    rho = L93_AF * _l93_t(math.radians(lat)) ** L93_N
    theta = L93_N * (math.radians(lon) - L93_LON0)
    return L93_X0 + rho * math.sin(theta), L93_Y0 + L93_RHO0 - rho * math.cos(theta)


# ---------------------------------------------------------------------------
# ETRS89-LAEA Europe projection (EPSG:3035) - Lambert azimuthal equal-area,
# GRS80 ellipsoid (Snyder, "Map Projections - A Working Manual", 1987).
# ---------------------------------------------------------------------------
LAEA_LON0 = math.radians(10.0)
LAEA_LAT0 = math.radians(52.0)
LAEA_X0 = 4321000.0
LAEA_Y0 = 3210000.0


def _laea_q(phi):
    s = math.sin(phi)
    e = GRS80_E
    return (1 - e * e) * (s / (1 - (e * s) ** 2) - math.log((1 - e * s) / (1 + e * s)) / (2 * e))


LAEA_QP = _laea_q(math.pi / 2)
LAEA_RQ = GRS80_A * math.sqrt(LAEA_QP / 2)
LAEA_BETA0 = math.asin(_laea_q(LAEA_LAT0) / LAEA_QP)
LAEA_D = (GRS80_A * _l93_m(LAEA_LAT0)) / (LAEA_RQ * math.cos(LAEA_BETA0))


def laea_europe(lon, lat):
    """(lon, lat) WGS84 in degrees -> (X, Y) ETRS89-LAEA in meters."""
    beta = math.asin(_laea_q(math.radians(lat)) / LAEA_QP)
    dlon = math.radians(lon) - LAEA_LON0
    b = LAEA_RQ * math.sqrt(2 / (1 + math.sin(LAEA_BETA0) * math.sin(beta)
                                 + math.cos(LAEA_BETA0) * math.cos(beta) * math.cos(dlon)))
    x = LAEA_X0 + b * LAEA_D * math.cos(beta) * math.sin(dlon)
    y = LAEA_Y0 + (b / LAEA_D) * (math.cos(LAEA_BETA0) * math.sin(beta)
                                  - math.sin(LAEA_BETA0) * math.cos(beta) * math.cos(dlon))
    return x, y


PROJECTIONS = {
    "lambert93": (lambert93, "EPSG:2154 (Lambert-93)"),
    "laea-europe": (laea_europe, "EPSG:3035 (ETRS89-LAEA Europe)"),
}

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
PAGE_W = 30.0
PAGE_H = 25.0

# Extent of metropolitan France (Corsica included) in Lambert-93, in meters,
# with a small margin. Same for all French maps -> they can be overlaid.
FRANCE_EXTENT = (80000.0, 1260000.0, 6030000.0, 7130000.0)

# Margin around an automatic extent (share of the width / height)
AUTO_MARGIN = 0.03

FILL_COLOR = "#6AAED6"
STROKE_COLOR = "#1A4F7A"

# ---------------------------------------------------------------------------
# Published catalog (reference for automatic download)
# ---------------------------------------------------------------------------
CATALOG_PATH = "output/maps.json"
PREVIEW_DIR = "output/previews"
STATIC_DIR = "static"
PREVIEW_PX_CM = 10           # preview: 10 px per cm of page (300 x 250 px)
CODE_EXAMPLES = 10           # zone codes (draw:name) published in the catalog
CATALOG_VERSION = 1
DEFAULT_BASE_URL = "https://raw.githubusercontent.com/gaborjager/odg-atlas/main"
ODG_FORMAT = "application/vnd.oasis.opendocument.graphics"

# Metadata required for a static map (static/<id>.json)
STATIC_REQUIRED = ["title", "description", "area", "code_type", "source", "license"]

# ---------------------------------------------------------------------------
# Generated maps
# ---------------------------------------------------------------------------
FRANCE_SOURCE = "IGN Admin Express, via gregoiredavid/france-geojson"
FRANCE_LICENSE = "Licence Ouverte / Open Licence 2.0 (Etalab)"

EU_MEMBERS = ("AT BE BG CY CZ DE DK EE ES FI FR GR HR HU IE IT LT LU LV MT "
              "NL PL PT RO SE SI SK").split()

MAPS = {
    "regions": {
        "title":          "France - Regions",
        "title_fr":       "France - Carte régionale",
        "description":    "Map of the 13 regions of metropolitan France. Each shape carries the INSEE code of the region in draw:name.",
        "description_fr": "Carte des 13 régions de France métropolitaine. Chaque forme porte le code INSEE de la région dans draw:name.",
        "area":           "France",
        "code_type":      "INSEE region code",
        "source":         FRANCE_SOURCE,
        "license":        FRANCE_LICENSE,
        "label":          "Regions of France",
        "page_name":      "Regions de France",
        "url":            "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/regions-version-simplifiee.geojson",
        "output":         "output/regions-france.odg",
        "cache":          "cache/regions.hash",
        "stroke_w":       "0.018cm",
        "projection":     "lambert93",
        "extent":         FRANCE_EXTENT,
        "render_version": "2-lambert93",
        "code_property":  "code",
        "name_property":  "nom",
        "extra_urls":     [],
    },
    "departements": {
        "title":          "France - Departments",
        "title_fr":       "France - Carte départementale",
        "description":    "Map of the 96 departments of metropolitan France. Each shape carries the INSEE code of the department in draw:name.",
        "description_fr": "Carte des 96 départements de France métropolitaine. Chaque forme porte le code INSEE du département dans draw:name.",
        "area":           "France",
        "code_type":      "INSEE department code",
        "source":         FRANCE_SOURCE,
        "license":        FRANCE_LICENSE,
        "label":          "Departments of France",
        "page_name":      "Departements de France",
        "url":            "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-version-simplifiee.geojson",
        "output":         "output/departements-france.odg",
        "cache":          "cache/departements.hash",
        "stroke_w":       "0.018cm",
        "projection":     "lambert93",
        "extent":         FRANCE_EXTENT,
        "render_version": "2-lambert93",
        "code_property":  "code",
        "name_property":  "nom",
        "extra_urls":     [],
    },
    "cantons": {
        "title":          "France - Cantons",
        "title_fr":       "France - Carte cantonale",
        "description":    "Map of the cantons of metropolitan France, completed by the municipal districts (Paris, Lyon, Marseille) and the municipalities of the Rhône. Each shape carries its INSEE code in draw:name.",
        "description_fr": "Carte des cantons de France métropolitaine, complétée par les arrondissements municipaux (Paris, Lyon, Marseille) et les communes du Rhône. Chaque forme porte le code INSEE dans draw:name.",
        "area":           "France",
        "code_type":      "INSEE canton code (municipality code for the added zones)",
        "source":         FRANCE_SOURCE + "; geo.api.gouv.fr",
        "license":        FRANCE_LICENSE,
        "label":          "Cantons of France",
        "page_name":      "Cantons de France",
        "url":            "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/cantons-version-simplifiee.geojson",
        "output":         "output/cantons-france.odg",
        "cache":          "cache/cantons.hash",
        "stroke_w":       "0.018cm",
        "projection":     "lambert93",
        "extent":         FRANCE_EXTENT,
        "render_version": "2-lambert93",
        "code_property":  "code",
        "name_property":  "nom",
        # Municipal districts (Paris 75, Lyon 69, Marseille 13) and the
        # municipalities of the Lyon Metropolis (department 69): zones without
        # cantons in the source GeoJSON. Same logic as the original PS script.
        "extra_urls": [
            {
                "role": "arrondissements",
                "url":  "https://geo.api.gouv.fr/communes?type=arrondissement-municipal&fields=nom,code&geometry=contour&format=geojson",
            },
            {
                "role": "rhone",
                "url":  "https://geo.api.gouv.fr/communes?codeDepartement=69&fields=nom,code&geometry=contour&format=geojson",
            },
        ],
    },
    "communes": {
        "title":          "France - Municipalities",
        "title_fr":       "France - Carte communale",
        "description":    "Map of the municipalities of metropolitan France (~35,000 shapes, heavy file). Each shape carries the INSEE code of the municipality in draw:name.",
        "description_fr": "Carte des communes de France métropolitaine (~35 000 formes, fichier lourd). Chaque forme porte le code INSEE de la commune dans draw:name.",
        "area":           "France",
        "code_type":      "INSEE municipality code",
        "source":         FRANCE_SOURCE,
        "license":        FRANCE_LICENSE,
        "label":          "Municipalities of France",
        "page_name":      "Communes de France",
        "url":            "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/communes-version-simplifiee.geojson",
        "output":         "output/communes-france.odg",
        "cache":          "cache/communes.hash",
        "stroke_w":       "0.004cm",
        "projection":     "lambert93",
        "extent":         FRANCE_EXTENT,
        "render_version": "2-lambert93",
        "code_property":  "code",
        "name_property":  "nom",
        "extra_urls":     [],
    },
    "eu-countries": {
        "title":          "European Union - Countries",
        "title_fr":       "Union européenne - Pays",
        "description":    "Map of the 27 member states of the European Union (mainland and nearby islands; outermost regions not shown). Each shape carries the ISO 3166-1 alpha-2 code of the country in draw:name (GR for Greece, coded EL by Eurostat).",
        "description_fr": "Carte des 27 États membres de l'Union européenne (territoire continental et îles proches ; régions ultrapériphériques non représentées). Chaque forme porte le code ISO 3166-1 alpha-2 du pays dans draw:name (GR pour la Grèce, codée EL par Eurostat).",
        "area":           "European Union",
        "code_type":      "ISO 3166-1 alpha-2",
        "source":         "Natural Earth 1:50m Admin 0 - Countries",
        "license":        "Public domain (Natural Earth)",
        "label":          "Countries of the European Union",
        "page_name":      "European Union",
        "url":            "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson",
        "output":         "output/eu-countries.odg",
        "cache":          "cache/eu-countries.hash",
        "stroke_w":       "0.018cm",
        "projection":     "laea-europe",
        "extent":         None,          # automatic: extent of the kept zones
        "render_version": "1-laea",
        "code_property":  "ISO_A2_EH",   # ISO_A2 is "-99" for France in Natural Earth
        "name_property":  "NAME_EN",
        "include":        EU_MEMBERS,
        # Polygons kept: those whose center lies in this box (lon min, lon max,
        # lat min, lat max) - drops the outermost regions (Canary Islands,
        # Azores, Madeira, overseas departments, Caribbean islands)
        "keep_parts":     (-12.0, 45.0, 34.0, 72.0),
        "extra_urls":     [],
    },
}

# ---------------------------------------------------------------------------
# Geometry helpers - same logic as the PS functions Get-BBox / Get-PathData
# ---------------------------------------------------------------------------

def get_polygons(geometry):
    """List of the polygons (lists of rings) of a Polygon or MultiPolygon."""
    if geometry["type"] == "MultiPolygon":
        return geometry["coordinates"]
    return [geometry["coordinates"]]


def keep_parts(geometry, box):
    """Geometry reduced to the polygons whose bounding box center is in box
    (lon min, lon max, lat min, lat max); None if no polygon is left."""
    lon_min, lon_max, lat_min, lat_max = box
    kept = []
    for poly in get_polygons(geometry):
        lons = [pt[0] for pt in poly[0]]
        lats = [pt[1] for pt in poly[0]]
        lon, lat = (min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2
        if lon_min <= lon <= lon_max and lat_min <= lat <= lat_max:
            kept.append(poly)
    return {"type": "MultiPolygon", "coordinates": kept} if kept else None


def project_rings(geometry, project):
    """List of the projected rings: [[(x, y), ...], ...]."""
    return [[project(float(pt[0]), float(pt[1])) for pt in ring]
            for poly in get_polygons(geometry) for ring in poly]


def get_bbox(rings):
    xs = [x for ring in rings for x, _ in ring]
    ys = [y for ring in rings for _, y in ring]
    return min(xs), max(xs), min(ys), max(ys)


def get_path_data(rings, origin_x, origin_y_max, sx, sy):
    parts = []
    for ring in rings:
        coords = []
        for px, py in ring:
            x = round((px - origin_x) * sx, 1)
            y = round((origin_y_max - py) * sy, 1)
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


class Frame:
    """Placement of a projected extent (meters) on the page (cm), with the
    same scale for X and Y: no distortion of the ratio."""

    def __init__(self, extent):
        self.x_min, self.x_max, self.y_min, self.y_max = extent
        self.scale = min(PAGE_W / (self.x_max - self.x_min), PAGE_H / (self.y_max - self.y_min))
        self.x_off = (PAGE_W - (self.x_max - self.x_min) * self.scale) / 2
        self.y_off = (PAGE_H - (self.y_max - self.y_min) * self.scale) / 2


def auto_extent(all_rings):
    """Extent of all the zones, with a margin."""
    x_min, x_max, y_min, y_max = get_bbox([ring for rings in all_rings for ring in rings])
    mx, my = (x_max - x_min) * AUTO_MARGIN, (y_max - y_min) * AUTO_MARGIN
    return x_min - mx, x_max + mx, y_min - my, y_max + my


# ---------------------------------------------------------------------------
# ODG XML generation
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


def build_shape(code, name, rings, frame, style_name, stroke_w):
    """XML lines (style, shape) of a zone, from its projected rings."""
    code = escape_xml(code)
    name = escape_xml(name)
    x_min, x_max, y_min, y_max = get_bbox(rings)
    x_rng = max(x_max - x_min, 1.0)
    y_rng = max(y_max - y_min, 1.0)

    x_cm = round(frame.x_off + (x_min - frame.x_min) * frame.scale, 4)
    y_cm = round(frame.y_off + (frame.y_max - y_max) * frame.scale, 4)
    w_cm = round(x_rng * frame.scale, 4)
    h_cm = round(y_rng * frame.scale, 4)

    vb_w = max(1, int(w_cm * 1000))
    vb_h = max(1, int(h_cm * 1000))
    s_x = vb_w / x_rng
    s_y = vb_h / y_rng

    path_data = get_path_data(rings, x_min, y_max, s_x, s_y)

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
        f'<svg:desc>{code} - {name}</svg:desc></draw:path>'
    )
    return style_xml, shape_xml


def build_odg_bytes(page_name, styles_lines, shapes_lines):
    """Assembles the ODG file in memory and returns its bytes."""
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

    # Fixed timestamp so that the file (and therefore its SHA-256) depends
    # only on its content: same source -> same hash in maps.json.
    def entry(name, compress):
        zi = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        zi.compress_type = compress
        return zi

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # mimetype first, uncompressed - required by ODF
        zf.writestr(entry("mimetype", zipfile.ZIP_STORED), ODG_FORMAT)
        zf.writestr(entry("META-INF/manifest.xml", zipfile.ZIP_DEFLATED),
                    MANIFEST_XML.encode("utf-8"))
        zf.writestr(entry("styles.xml", zipfile.ZIP_DEFLATED),
                    STYLES_XML.encode("utf-8"))
        zf.writestr(entry("content.xml", zipfile.ZIP_DEFLATED),
                    content_xml.encode("utf-8"))
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
    print(f"  Downloading {label or url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "odg-atlas/1.0 (github-actions)"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = r.read()
    print(f"  -> {len(data)//1024} KB received.")
    return data


# ---------------------------------------------------------------------------
# Generation of an ODG
# ---------------------------------------------------------------------------
def zone_features(raw, cfg):
    """(code, name, geometry) of the zones of a GeoJSON source, filtered and
    sorted as configured; zones without geometry are skipped."""
    zones = []
    for feat in json.loads(raw)["features"]:
        props, geom = feat["properties"], feat["geometry"]
        code = str(props.get(cfg.get("code_property", "code"), "") or "")
        if geom is None or not geom.get("coordinates"):
            continue
        if cfg.get("include") and code not in cfg["include"]:
            continue
        if cfg.get("keep_parts"):
            geom = keep_parts(geom, cfg["keep_parts"])
            if geom is None:
                continue
        zones.append((code, props.get(cfg.get("name_property", "nom"), "") or "", geom))
    if cfg.get("include"):
        zones.sort(key=lambda z: z[0])
        missing = sorted(set(cfg["include"]) - {z[0] for z in zones})
        if missing:
            raise ValueError(f"zones missing from the source: {', '.join(missing)}")
    return zones


def generate(name: str, cfg: dict, force: bool) -> bool:
    print(f"\n=== {cfg['label']} ===")

    raw_main = fetch(cfg["url"], "main GeoJSON")
    new_hash = sha256_bytes(cfg["render_version"].encode() + raw_main)

    # For the cantons, the extra URLs are part of the hash
    extra_raws = {}
    for ex in cfg["extra_urls"]:
        extra_raws[ex["role"]] = fetch(ex["url"], ex["role"])
        new_hash = sha256_bytes(new_hash.encode() + extra_raws[ex["role"]])

    old_hash = read_hash(cfg["cache"])
    if new_hash == old_hash and not force and Path(cfg["output"]).exists():
        print("  Source unchanged - ODG already up to date.")
        return False

    print("  Source changed (or forced) - regenerating...")

    # Stacking order (same as the PS script for the cantons):
    # 1. Municipalities of the Rhône (69) at the back (fill the Lyon Metropolis holes)
    # 2. Municipal districts (Paris, Lyon, Marseille)
    # 3. Main zones (regions / departments / cantons / municipalities / countries)
    layers = []
    if "rhone" in extra_raws:
        layers.append(("m", zone_features(extra_raws["rhone"], cfg)))
        print(f"  {len(layers[-1][1])} municipalities of the Rhône at the back.")
    if "arrondissements" in extra_raws:
        layers.append(("a", zone_features(extra_raws["arrondissements"], cfg)))
        print(f"  {len(layers[-1][1])} municipal districts.")
    main_zones = zone_features(raw_main, cfg)
    layers.append(("s", main_zones))
    print(f"  {len(main_zones)} main zones loaded.")

    project = PROJECTIONS[cfg["projection"]][0]
    if cfg["extent"]:
        frame = Frame(cfg["extent"])
    else:
        frame = Frame(auto_extent([project_rings(g, project) for _, zones in layers for _, _, g in zones]))

    styles_lines = []
    shapes_lines = []
    i = 0
    total = sum(len(zones) for _, zones in layers)
    log_step = 1000 if total > 5000 else 25
    for prefix, zones in layers:
        for code, zone_name, geom in zones:
            sl, sh = build_shape(code, zone_name, project_rings(geom, project), frame,
                                 f"{prefix}{i}", cfg["stroke_w"])
            styles_lines.append(sl)
            shapes_lines.append(sh)
            i += 1
            if i % log_step == 0:
                print(f"  {i} done...")

    print(f"  -> {i} shapes in total.")

    odg_bytes = build_odg_bytes(cfg["page_name"], styles_lines, shapes_lines)

    out = Path(cfg["output"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(odg_bytes)
    write_hash(cfg["cache"], new_hash)

    print(f"  ODG written: {cfg['output']} ({len(odg_bytes) / 1024:.0f} KB)")
    return True


# ---------------------------------------------------------------------------
# Reading any ODG (generated or static): page size, named zones, outlines
# ---------------------------------------------------------------------------
NS_DRAW = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
NS_SVG = "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
NS_FO = "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
NS_STYLE = "urn:oasis:names:tc:opendocument:xmlns:style:1.0"

# Shapes that can be a zone of a map (draw:name = code)
ZONE_TAGS = {f"{{{NS_DRAW}}}{t}" for t in
             ("path", "polygon", "polyline", "rect", "ellipse", "circle", "custom-shape")}

UNITS_CM = {"cm": 1.0, "mm": 0.1, "in": 2.54, "pt": 2.54 / 72, "pc": 2.54 / 6, "px": 2.54 / 96}

# Number of parameters of each SVG path command
PATH_PARAMS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}
PATH_TOKEN = re.compile(r"[MLHVCSQTAZmlhvcsqtaz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def to_cm(value: str) -> float:
    m = re.fullmatch(r"\s*([-+]?[\d.]+(?:[eE][-+]?\d+)?)\s*([a-z]*)\s*", value or "")
    if not m:
        raise ValueError(f"invalid length: {value!r}")
    return float(m.group(1)) * UNITS_CM.get(m.group(2) or "cm", 1.0)


def path_rings(d: str):
    """Rings of an SVG path (absolute coordinates): end points of each
    segment, curves approximated by their end points (enough for a preview)."""
    rings, ring = [], None
    x = y = sx = sy = 0.0
    tokens = PATH_TOKEN.findall(d or "")
    i, cmd = 0, None
    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                x, y = sx, sy
                ring = None
                continue
        if cmd is None:
            break
        n = PATH_PARAMS[cmd.upper()]
        args = [float(v) for v in tokens[i:i + n]]
        if len(args) < n:
            break
        i += n
        rel = cmd.islower()
        c = cmd.upper()
        if c == "H":
            x = x + args[0] if rel else args[0]
        elif c == "V":
            y = y + args[0] if rel else args[0]
        else:
            x, y = (x + args[-2], y + args[-1]) if rel else (args[-2], args[-1])
        if c == "M":
            ring = [(x, y)]
            rings.append(ring)
            sx, sy = x, y
            cmd = "l" if rel else "L"    # following pairs are line segments
        else:
            if ring is None:
                ring = [(sx, sy)]
                rings.append(ring)
            ring.append((x, y))
    return rings


def points_ring(points: str):
    values = [float(v) for v in re.split(r"[\s,]+", (points or "").strip()) if v]
    return [list(zip(values[0::2], values[1::2]))]


def read_odg(odg_bytes: bytes):
    """Page size (cm) and zones of an ODG: [(code, rings, (x0, y0, kx, ky))],
    rings in shape units, placed on the page (cm) by x0 + x * kx, y0 + y * ky.
    A zone is a shape with a draw:name; rings are empty if its outline is unknown."""
    with zipfile.ZipFile(io.BytesIO(odg_bytes)) as zf:
        content = ET.fromstring(zf.read("content.xml"))
        styles = ET.fromstring(zf.read("styles.xml")) if "styles.xml" in zf.namelist() else None
    page = None
    if styles is not None:
        props = styles.find(f".//{{{NS_STYLE}}}page-layout-properties")
        if props is not None and props.get(f"{{{NS_FO}}}page-width"):
            page = (to_cm(props.get(f"{{{NS_FO}}}page-width")), to_cm(props.get(f"{{{NS_FO}}}page-height")))
    zones = []
    for shape in content.iter():
        if shape.tag not in ZONE_TAGS or not shape.get(f"{{{NS_DRAW}}}name"):
            continue
        rings, place = [], (0.0, 0.0, 1.0, 1.0)
        try:
            x0 = to_cm(shape.get(f"{{{NS_SVG}}}x", "0cm"))
            y0 = to_cm(shape.get(f"{{{NS_SVG}}}y", "0cm"))
            w = to_cm(shape.get(f"{{{NS_SVG}}}width"))
            h = to_cm(shape.get(f"{{{NS_SVG}}}height"))
            if shape.get(f"{{{NS_SVG}}}d"):
                local = path_rings(shape.get(f"{{{NS_SVG}}}d"))
            elif shape.get(f"{{{NS_DRAW}}}points"):
                local = points_ring(shape.get(f"{{{NS_DRAW}}}points"))
            else:
                local = [[(0, 0), (1, 0), (1, 1), (0, 1)]]   # rectangle, ellipse…: bounding box
            if shape.get(f"{{{NS_SVG}}}viewBox"):
                _, _, vb_w, vb_h = (float(v) for v in shape.get(f"{{{NS_SVG}}}viewBox").split())
            else:
                vb_w = vb_h = 1.0
            rings, place = local, (x0, y0, w / vb_w, h / vb_h)
        except (ValueError, TypeError, ZeroDivisionError):
            rings = []
        zones.append((shape.get(f"{{{NS_DRAW}}}name"), rings, place))
    return page, zones


# ---------------------------------------------------------------------------
# SVG preview
# ---------------------------------------------------------------------------
def build_preview(page, zones):
    """SVG preview of a map: one shape per zone, points rounded to the pixel
    (duplicates and rings that became flat are removed). The page gives the
    frame; without a page, the extent of the zones. None if nothing to draw."""
    all_pts = [(x0 + x * kx, y0 + y * ky) for _, rings, (x0, y0, kx, ky) in zones
               for ring in rings for x, y in ring]
    if not all_pts:
        return None
    if page:
        x_min, y_min, width, height = 0.0, 0.0, page[0], page[1]
    else:
        x_min, y_min = min(p[0] for p in all_pts), min(p[1] for p in all_pts)
        width = max(p[0] for p in all_pts) - x_min or 1.0
        height = max(p[1] for p in all_pts) - y_min or 1.0
    # 10 px per cm for a 30 x 25 cm page; other pages fit in 300 x 250 px
    px = min(PREVIEW_PX_CM, 300 / width, 250 / height) if (width > PAGE_W or height > PAGE_H) else PREVIEW_PX_CM
    paths = []
    for _, rings, (x0, y0, kx, ky) in zones:
        ox, oy, sx, sy = (x0 - x_min) * px, (y0 - y_min) * px, kx * px, ky * px
        pieces = []
        for ring in rings:
            pts = []
            for x, y in ring:
                pt = (round(ox + x * sx), round(oy + y * sy))
                if not pts or pt != pts[-1]:
                    pts.append(pt)
            if len(set(pts)) >= 3:
                pieces.append(pts)
        if pieces:
            d = " ".join("M" + " L".join(f"{x} {y}" for x, y in p) + "Z" for p in pieces)
            paths.append(f'<path d="{d}"/>')
    w, h = round(width * px), round(height * px)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
            f'<g fill="{FILL_COLOR}" stroke="{STROKE_COLOR}" stroke-width="0.4" stroke-linejoin="round">\n'
            + "\n".join(paths) + "\n</g>\n</svg>\n")


# ---------------------------------------------------------------------------
# Static maps (static/<id>.odg + static/<id>.json)
# ---------------------------------------------------------------------------
def static_maps():
    """[(id, odg path, metadata)] of the static maps, sorted by id."""
    folder = Path(STATIC_DIR)
    return [(odg.stem, odg, odg.with_suffix(".json")) for odg in sorted(folder.glob("*.odg"))]


def check_static_maps():
    """Errors found in the static maps (empty list if all are valid)."""
    errors = []
    for map_id, odg, meta_path in static_maps():
        where = f"{STATIC_DIR}/{odg.name}"
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", map_id):
            errors.append(f"{where}: the file name must use lowercase letters, digits and '-'")
        if map_id in MAPS:
            errors.append(f"{where}: the id '{map_id}' is already used by a generated map")
        if odg.name in {Path(cfg["output"]).name for cfg in MAPS.values()}:
            errors.append(f"{where}: the file name is already used by a generated map")
        if not meta_path.exists():
            errors.append(f"{where}: metadata file {meta_path.name} missing")
        else:
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                missing = [k for k in STATIC_REQUIRED if not str(meta.get(k, "")).strip()]
                if missing:
                    errors.append(f"{STATIC_DIR}/{meta_path.name}: missing fields: {', '.join(missing)}")
            except json.JSONDecodeError as exc:
                errors.append(f"{STATIC_DIR}/{meta_path.name}: invalid JSON ({exc})")
        try:
            data = odg.read_bytes()
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                if zf.read("mimetype").decode().strip() != ODG_FORMAT:
                    errors.append(f"{where}: not an ODF drawing (.odg)")
            _, zones = read_odg(data)
            codes = [z[0] for z in zones]
            if not codes:
                errors.append(f"{where}: no named shape (each zone must carry its code as its name)")
            duplicates = sorted({c for c in codes if codes.count(c) > 1})
            if duplicates:
                errors.append(f"{where}: duplicate zone names: {', '.join(duplicates[:10])}")
        except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
            errors.append(f"{where}: unreadable ODG ({exc})")
    for meta_path in sorted(Path(STATIC_DIR).glob("*.json")):
        if not meta_path.with_suffix(".odg").exists():
            errors.append(f"{STATIC_DIR}/{meta_path.name}: no matching .odg file")
    return errors


# ---------------------------------------------------------------------------
# Catalog maps.json
# ---------------------------------------------------------------------------
def catalog_entry(map_id, path, meta, kind, base_url):
    data = path.read_bytes()
    page, zones = read_odg(data)
    codes = sorted({z[0] for z in zones})
    entry = {"id": map_id}
    for key in ("title", "title_fr", "description", "description_fr", "area", "code_type"):
        if meta.get(key):
            entry[key] = meta[key]
    if meta.get("projection"):
        entry["projection"] = PROJECTIONS.get(meta["projection"], (None, meta["projection"]))[1]
    for key in ("source", "license"):
        if meta.get(key):
            entry[key] = meta[key]
    entry.update({
        "kind":          kind,
        "url":           f"{base_url}/{path.as_posix()}",
        "filename":      path.name,
        "format":        ODG_FORMAT,
        "size":          len(data),
        "sha256":        sha256_bytes(data),
        "objects":       len(zones),
        "code_examples": codes[:CODE_EXAMPLES],
    })
    svg = build_preview(page, zones)
    if svg:
        preview = Path(PREVIEW_DIR) / f"{map_id}.svg"
        preview.parent.mkdir(parents=True, exist_ok=True)
        svg_bytes = svg.encode("utf-8")
        if not preview.exists() or preview.read_bytes() != svg_bytes:
            preview.write_bytes(svg_bytes)
            print(f"Preview {preview} written ({len(svg_bytes) // 1024} KB).")
        entry["preview"] = f"{base_url}/{preview.as_posix()}"
        entry["preview_sha256"] = sha256_bytes(svg_bytes)
    return entry


def write_catalog(base_url: str) -> bool:
    """(Re)writes output/maps.json from the ODG files on disk.
    Returns True if the file changed."""
    base_url = base_url.rstrip("/")
    maps = []
    for name, cfg in MAPS.items():
        out = Path(cfg["output"])
        if out.exists():
            maps.append(catalog_entry(name, out, cfg, "generated", base_url))
    for map_id, odg, meta_path in static_maps():
        maps.append(catalog_entry(map_id, odg, json.loads(meta_path.read_text(encoding="utf-8")),
                                  "static", base_url))
    # Previews of maps that no longer exist
    ids = {m["id"] for m in maps}
    for preview in Path(PREVIEW_DIR).glob("*.svg"):
        if preview.stem not in ids:
            preview.unlink()
            print(f"Preview {preview} removed.")

    catalog = {
        "version": CATALOG_VERSION,
        "title":   "ODG Atlas",
        "maps":    maps,
    }
    text = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"

    path = Path(CATALOG_PATH)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        print(f"\nCatalog {CATALOG_PATH} unchanged.")
        return False
    path.write_text(text, encoding="utf-8")
    print(f"\nCatalog {CATALOG_PATH} updated ({len(maps)} maps).")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="Regenerate even if the source has not changed")
    parser.add_argument("--only", default="",
                        help="Comma-separated: " + ",".join(MAPS))
    parser.add_argument("--catalog-only", action="store_true",
                        help="No download: check the static maps and rewrite the catalog")
    parser.add_argument("--check", action="store_true",
                        help="Only check the static maps")
    args = parser.parse_args()

    force = args.force or os.environ.get("FORCE_REGENERATE", "").lower() in ("1", "true", "yes")
    only = {s.strip() for s in args.only.split(",") if s.strip()} if args.only else set(MAPS)
    unknown = only - set(MAPS)
    if unknown:
        sys.exit(f"Unknown maps: {', '.join(sorted(unknown))} (available: {', '.join(MAPS)})")

    os.chdir(Path(__file__).parent.parent)

    errors = check_static_maps()
    for error in errors:
        print(f"ERROR {error}", file=sys.stderr)
    if errors:
        sys.exit(1)
    print(f"Static maps: {len(static_maps())} valid.")
    if args.check:
        return

    changed = []
    if not args.catalog_only:
        for name, cfg in MAPS.items():
            if name not in only:
                continue
            try:
                if generate(name, cfg, force):
                    changed.append(name)
            except Exception as exc:
                print(f"  ERROR [{name}]: {exc}", file=sys.stderr)
                sys.exit(1)

    catalog_changed = write_catalog(os.environ.get("ODG_BASE_URL", DEFAULT_BASE_URL))

    if changed:
        print(f"\nRegenerated files: {', '.join(changed)}")
    else:
        print("\nNo file to regenerate.")

    gha = os.environ.get("GITHUB_OUTPUT", "")
    if gha:
        with open(gha, "a") as f:
            f.write(f"changed={'true' if changed or catalog_changed else 'false'}\n")
            f.write(f"changed_files={','.join(changed)}\n")


if __name__ == "__main__":
    main()
