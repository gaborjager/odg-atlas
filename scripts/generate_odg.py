"""
generate_odg.py
Portage des 4 scripts PowerShell geojson-*-to-odg.ps1, en projection Lambert-93.
Génère des fichiers .odg (OpenDocument Graphics) pour LibreOffice / Collabora,
ainsi que le catalogue output/maps.json (URL + SHA-256 de chaque carte, nombre
d'objets) et un aperçu SVG de chaque carte (output/previews/).

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
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Projection Lambert-93 (EPSG:2154) — conique conforme sécante, ellipsoïde GRS80
# Formules IGN (NTG_71), implémentées sans dépendance externe.
# ---------------------------------------------------------------------------
L93_A     = 6378137.0
L93_F     = 1 / 298.257222101
L93_E     = math.sqrt(2 * L93_F - L93_F ** 2)
L93_LON0  = math.radians(3.0)
L93_LAT0  = math.radians(46.5)
L93_LAT1  = math.radians(44.0)
L93_LAT2  = math.radians(49.0)
L93_X0    = 700000.0
L93_Y0    = 6600000.0


def _l93_m(phi):
    return math.cos(phi) / math.sqrt(1 - (L93_E * math.sin(phi)) ** 2)


def _l93_t(phi):
    es = L93_E * math.sin(phi)
    return math.tan(math.pi / 4 - phi / 2) / ((1 - es) / (1 + es)) ** (L93_E / 2)


L93_N    = ((math.log(_l93_m(L93_LAT1)) - math.log(_l93_m(L93_LAT2)))
            / (math.log(_l93_t(L93_LAT1)) - math.log(_l93_t(L93_LAT2))))
L93_AF   = L93_A * _l93_m(L93_LAT1) / (L93_N * _l93_t(L93_LAT1) ** L93_N)
L93_RHO0 = L93_AF * _l93_t(L93_LAT0) ** L93_N


def lambert93(lon, lat):
    """(lon, lat) WGS84 en degrés -> (X, Y) Lambert-93 en mètres."""
    rho   = L93_AF * _l93_t(math.radians(lat)) ** L93_N
    theta = L93_N * (math.radians(lon) - L93_LON0)
    return L93_X0 + rho * math.sin(theta), L93_Y0 + L93_RHO0 - rho * math.cos(theta)


# ---------------------------------------------------------------------------
# Mise en page
# ---------------------------------------------------------------------------
PAGE_W = 30.0
PAGE_H = 25.0

# Emprise de la France métropolitaine (Corse incluse) en Lambert-93, en mètres,
# avec une petite marge. Identique pour toutes les cartes -> superposables.
M_X_MIN, M_X_MAX = 80000.0, 1260000.0
M_Y_MIN, M_Y_MAX = 6030000.0, 7130000.0

# Échelle unique (cm par mètre) pour X et Y : pas de déformation du ratio.
SCALE = min(PAGE_W / (M_X_MAX - M_X_MIN), PAGE_H / (M_Y_MAX - M_Y_MIN))
X_OFF = (PAGE_W - (M_X_MAX - M_X_MIN) * SCALE) / 2
Y_OFF = (PAGE_H - (M_Y_MAX - M_Y_MIN) * SCALE) / 2

# Changer cette valeur force la régénération de toutes les cartes
# (elle entre dans le hash de cache) quand l'algorithme de rendu évolue.
GENERATOR_VERSION = "2-lambert93"

FILL_COLOR   = "#6AAED6"
STROKE_COLOR = "#1A4F7A"

# ---------------------------------------------------------------------------
# Catalogue JSON publié (référence pour le téléchargement automatique)
# ---------------------------------------------------------------------------
CATALOG_PATH     = "output/maps.json"
PREVIEW_DIR      = "output/previews"
PREVIEW_PX_CM    = 10          # aperçu : 10 px par cm de page (300 x 250 px)
CATALOG_VERSION  = 1
DEFAULT_BASE_URL = "https://raw.githubusercontent.com/gaborjager/france-odg/main"

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
SOURCES = {
    "regions": {
        "title":       "France - Carte régionale",
        "description": "Carte des 13 régions de France métropolitaine. Chaque forme porte le code INSEE de la région dans draw:name.",
        "label":       "Régions de France",
        "page_name":   "Regions de France",
        "url":         "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/regions-version-simplifiee.geojson",
        "output":      "output/regions-france.odg",
        "cache":       "cache/regions.hash",
        "stroke_w":    "0.018cm",
        "extra_urls":  [],
    },
    "departements": {
        "title":       "France - Carte départementale",
        "description": "Carte des 96 départements de France métropolitaine. Chaque forme porte le code INSEE du département dans draw:name.",
        "label":       "Départements de France",
        "page_name":   "Departements de France",
        "url":         "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-version-simplifiee.geojson",
        "output":      "output/departements-france.odg",
        "cache":       "cache/departements.hash",
        "stroke_w":    "0.018cm",
        "extra_urls":  [],
    },
    "cantons": {
        "title":       "France - Carte cantonale",
        "description": "Carte des cantons de France métropolitaine, complétée par les arrondissements municipaux (Paris, Lyon, Marseille) et les communes du Rhône. Chaque forme porte le code INSEE dans draw:name.",
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
        "title":       "France - Carte communale",
        "description": "Carte des communes de France métropolitaine (~35 000 formes, fichier lourd). Chaque forme porte le code INSEE de la commune dans draw:name.",
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


def project_rings(geometry):
    """Liste des anneaux projetés en Lambert-93 : [[(x, y), ...], ...]."""
    return [[lambert93(float(pt[0]), float(pt[1])) for pt in ring]
            for ring in get_rings(geometry)]


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
    """Construit les lignes XML style + shape pour une feature GeoJSON.
    Retourne (None, None) si la geometrie est absente (geometry: null)."""
    code = escape_xml(feat["properties"].get("code", ""))
    nom  = escape_xml(feat["properties"].get("nom", ""))
    geom = feat["geometry"]
    if geom is None or not geom.get("coordinates"):
        return None, None
    rings = project_rings(geom)
    x_min, x_max, y_min, y_max = get_bbox(rings)
    x_rng = max(x_max - x_min, 1.0)
    y_rng = max(y_max - y_min, 1.0)

    x_cm = round(X_OFF + (x_min - M_X_MIN) * SCALE, 4)
    y_cm = round(Y_OFF + (M_Y_MAX - y_max) * SCALE, 4)
    w_cm = round(x_rng * SCALE, 4)
    h_cm = round(y_rng * SCALE, 4)

    vb_w = max(1, int(w_cm * 1000))
    vb_h = max(1, int(h_cm * 1000))
    s_x  = vb_w / x_rng
    s_y  = vb_h / y_rng

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

    # Horodatage fixe pour que le fichier (et donc son SHA-256) ne dépende
    # que de son contenu : même source -> même hash dans maps.json.
    def entry(name, compress):
        zi = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        zi.compress_type = compress
        return zi

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # mimetype en premier, non compressé — obligatoire ODF
        zf.writestr(entry("mimetype", zipfile.ZIP_STORED),
                    "application/vnd.oasis.opendocument.graphics")
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
    new_hash = sha256_bytes(GENERATOR_VERSION.encode() + raw_main)

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
            if sl is None: continue
            styles_lines.append(sl); shapes_lines.append(sh); i += 1

    # 2. Arrondissements municipaux (Paris, Lyon, Marseille)
    if "arrondissements" in extra_raws:
        feats_arr = json.loads(extra_raws["arrondissements"])["features"]
        print(f"  {len(feats_arr)} arrondissements municipaux.")
        for feat in feats_arr:
            sl, sh = build_shape(feat, f"a{i}", cfg["stroke_w"])
            if sl is None: continue
            styles_lines.append(sl); shapes_lines.append(sh); i += 1

    # 3. Entités principales (régions / départements / cantons / communes)
    log_step = 1000 if len(features_main) > 5000 else 25
    skipped = 0
    for feat in features_main:
        sl, sh = build_shape(feat, f"s{i}", cfg["stroke_w"])
        if sl is None:
            skipped += 1
            continue
        styles_lines.append(sl); shapes_lines.append(sh); i += 1
        if i % log_step == 0:
            print(f"  {i} traités...")
    if skipped:
        print(f"  {skipped} entités ignorées (geometry null).")

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
# Aperçu SVG
# ---------------------------------------------------------------------------
NS_DRAW = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
NS_SVG  = "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"


def _cm(valeur: str) -> float:
    return float(valeur.replace("cm", ""))


def build_preview(odg_bytes: bytes):
    """Aperçu SVG d'un ODG produit par ce script : une forme par zone, points
    arrondis au pixel (les doublons et les anneaux devenus plats sont retirés).
    Retourne (texte SVG, nombre de formes de l'ODG)."""
    with zipfile.ZipFile(io.BytesIO(odg_bytes)) as zf:
        racine = ET.fromstring(zf.read("content.xml"))
    chemins = []
    nb_formes = 0
    for forme in racine.iter(f"{{{NS_DRAW}}}path"):
        nb_formes += 1
        x0 = _cm(forme.get(f"{{{NS_SVG}}}x"))
        y0 = _cm(forme.get(f"{{{NS_SVG}}}y"))
        larg = _cm(forme.get(f"{{{NS_SVG}}}width"))
        haut = _cm(forme.get(f"{{{NS_SVG}}}height"))
        _, _, vb_l, vb_h = (float(v) for v in forme.get(f"{{{NS_SVG}}}viewBox").split())
        sx, sy = larg / vb_l * PREVIEW_PX_CM, haut / vb_h * PREVIEW_PX_CM
        ox, oy = x0 * PREVIEW_PX_CM, y0 * PREVIEW_PX_CM
        anneaux, anneau = [], []
        jetons = forme.get(f"{{{NS_SVG}}}d").split()
        i = 0
        while i < len(jetons):
            j = jetons[i]
            if j in ("M", "L"):
                pt = (round(ox + float(jetons[i + 1]) * sx), round(oy + float(jetons[i + 2]) * sy))
                if j == "M":
                    anneau = [pt]
                    anneaux.append(anneau)
                elif pt != anneau[-1]:
                    anneau.append(pt)
                i += 3
            else:
                i += 1
        morceaux = [a for a in anneaux if len(set(a)) >= 3]
        if morceaux:
            d = " ".join("M" + " L".join(f"{x} {y}" for x, y in a) + "Z" for a in morceaux)
            chemins.append(f'<path d="{d}"/>')
    l, h = round(PAGE_W * PREVIEW_PX_CM), round(PAGE_H * PREVIEW_PX_CM)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{l}" height="{h}" viewBox="0 0 {l} {h}">\n'
           f'<g fill="{FILL_COLOR}" stroke="{STROKE_COLOR}" stroke-width="0.4" stroke-linejoin="round">\n'
           + "\n".join(chemins) + "\n</g>\n</svg>\n")
    return svg, nb_formes


# ---------------------------------------------------------------------------
# Catalogue maps.json
# ---------------------------------------------------------------------------
def write_catalog(base_url: str) -> bool:
    """(Ré)écrit output/maps.json à partir des ODG présents sur disque.
    Retourne True si le fichier a changé."""
    maps = []
    for name, cfg in SOURCES.items():
        out = Path(cfg["output"])
        if not out.exists():
            continue
        data = out.read_bytes()
        svg, nb_objets = build_preview(data)
        apercu = Path(PREVIEW_DIR) / f"{name}.svg"
        apercu.parent.mkdir(parents=True, exist_ok=True)
        svg_bytes = svg.encode("utf-8")
        if not apercu.exists() or apercu.read_bytes() != svg_bytes:
            apercu.write_bytes(svg_bytes)
            print(f"Aperçu {apercu} écrit ({len(svg_bytes) // 1024} Ko).")
        maps.append({
            "id":             name,
            "title":          cfg["title"],
            "description":    cfg["description"],
            "url":            f"{base_url.rstrip('/')}/{cfg['output']}",
            "filename":       out.name,
            "format":         "application/vnd.oasis.opendocument.graphics",
            "size":           len(data),
            "sha256":         sha256_bytes(data),
            "objects":        nb_objets,
            "preview":        f"{base_url.rstrip('/')}/{apercu.as_posix()}",
            "preview_sha256": sha256_bytes(svg_bytes),
        })

    catalog = {
        "version":    CATALOG_VERSION,
        "projection": "EPSG:2154 (Lambert-93)",
        "maps":       maps,
    }
    text = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"

    path = Path(CATALOG_PATH)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        print(f"\nCatalogue {CATALOG_PATH} inchangé.")
        return False
    path.write_text(text, encoding="utf-8")
    print(f"\nCatalogue {CATALOG_PATH} mis à jour ({len(maps)} cartes).")
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

    catalog_changed = write_catalog(os.environ.get("ODG_BASE_URL", DEFAULT_BASE_URL))

    if changed:
        print(f"\nFichiers régénérés : {', '.join(changed)}")
    else:
        print("\nAucun fichier à régénérer.")

    gha = os.environ.get("GITHUB_OUTPUT", "")
    if gha:
        with open(gha, "a") as f:
            f.write(f"changed={'true' if changed or catalog_changed else 'false'}\n")
            f.write(f"changed_files={','.join(changed)}\n")

if __name__ == "__main__":
    main()