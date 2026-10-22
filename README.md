# 🗺️ Cartes de France ODG — LibreOffice / Collabora

Génération automatique de fichiers **`.odg`** (OpenDocument Graphics) découpés par
entité administrative française, prêts à l'emploi dans LibreOffice Draw, LibreOffice Calc
avec l'extension GeOOo, Collabora Office, et tout logiciel compatible ODF.

Les fichiers sont régénérés automatiquement via **GitHub Actions** dès que les sources
GeoJSON (IGN) sont modifiées.

---

## 📦 Fichiers disponibles

| Fichier | Entités | `draw:name` | Taille |
|---|---|---|---|
| [`output/regions-france.odg`](output/regions-france.odg) | 13 régions | code région (ex. `84`) | ~40 Ko |
| [`output/departements-france.odg`](output/departements-france.odg) | 96 départements | code INSEE (ex. `75`) | ~90 Ko |
| [`output/cantons-france.odg`](output/cantons-france.odg) | ~2 000 cantons + arrond. municipaux + communes du Rhône | code INSEE (ex. `75056`) | ~500 Ko |
| [`output/communes-france.odg`](output/communes-france.odg) | ~35 000 communes ⚠️ fichier lourd | code INSEE commune (ex. `75056`) | ~100 Mo |

### 📇 Catalogue JSON (téléchargement automatique)

Le fichier [`output/maps.json`](output/maps.json) liste les cartes disponibles et sert de
référence aux projets qui téléchargent les ODG automatiquement :

```
https://raw.githubusercontent.com/gaborjager/france-odg/main/output/maps.json
```

```json
{
  "version": 1,
  "projection": "EPSG:2154 (Lambert-93)",
  "maps": [
    {
      "id": "departements",
      "title": "France - Carte départementale",
      "description": "Carte des 96 départements de France métropolitaine. …",
      "url": "https://raw.githubusercontent.com/gaborjager/france-odg/main/output/departements-france.odg",
      "filename": "departements-france.odg",
      "format": "application/vnd.oasis.opendocument.graphics",
      "size": 87649,
      "sha256": "706b4e0b…",
      "objects": 96,
      "preview": "https://raw.githubusercontent.com/gaborjager/france-odg/main/output/previews/departements.svg",
      "preview_sha256": "31fbc494…"
    }
  ]
}
```

- `id` est stable et sert de clé ; `sha256` est l'empreinte du fichier `.odg` téléchargé
  (à vérifier après téléchargement, et à comparer pour savoir si une mise à jour est nécessaire).
- `objects` est le nombre de formes (zones) de la carte : un logiciel peut écarter les
  cartes trop détaillées pour lui.
- `preview` est un aperçu SVG de la carte (300 × 250 px, dans [`output/previews/`](output/previews/)),
  produit à partir de l'ODG ; `preview_sha256` est son empreinte.
- Les ODG et les aperçus sont générés de façon déterministe : le hash ne change que si le contenu change.
- Le catalogue est réécrit à chaque exécution du workflow.

> **Note cantons :** Paris, Lyon (Métropole) et Marseille n'ont pas de cantons dans la source GeoJSON.
> Ils sont complétés par leurs arrondissements municipaux (Paris, Marseille) et les communes
> du département du Rhône (Métropole de Lyon), dans le même ordre d'empilement que le script PowerShell original.

---

## 🚀 Utilisation dans LibreOffice Calc / Collabora Calc (avec GeOOo)

[GeOOo](http://geoooblog.blogspot.com/) est une extension gratuite pour LibreOffice Calc qui permet
de créer des **cartes thématiques / choroplèthes** en coloriant automatiquement les zones
selon des données d'un classeur.

### Installation de GeOOo

1. Télécharger l'extension depuis le [blog GeOOo](http://geoooblog.blogspot.com/)
2. Dans LibreOffice : **Outils → Gestionnaire des extensions → Ajouter**
3. Sélectionner le fichier `.oxt` téléchargé

### Utilisation avec les fichiers ODG de ce dépôt

1. **Télécharger** le fichier `.odg` souhaité (ex. `departements-france.odg`)
2. **Ouvrir votre classeur** dans LibreOffice Calc
3. Dans votre feuille, créer une colonne avec les **codes INSEE** et une colonne avec les **valeurs** :

   | Code | Valeur |
   |---|---|
   | 75 | 2 133 111 |
   | 69 | 1 426 231 |
   | 13 | 1 021 136 |
   | … | … |

4. Lancer GeOOo : **Outils → Macros → GeOOo** (ou le bouton GeOOo dans la barre)
5. Sélectionner le fichier `.odg` comme fond de carte
6. Associer la colonne codes à `draw:name` et la colonne valeurs à la coloration
7. GeOOo génère la carte colorée dans un nouvel onglet Draw

> Le champ `draw:name` de chaque polygone contient le **code INSEE officiel**,
> directement utilisable comme clé de jointure avec vos données.

---

## 🖊️ Utilisation dans LibreOffice Draw

1. **Fichier → Ouvrir** → sélectionner le fichier `.odg`
2. Chaque zone est un objet `draw:path` indépendant, sélectionnable et stylisable
3. Pour identifier une zone : clic droit → **Nom et description** → le nom affiché est le code INSEE
4. Pour colorer manuellement : clic sur une zone → **Format → Zone et ombre**

---

## ⚙️ Mise à jour automatique (CI/CD)

Un workflow **GitHub Actions** tourne toutes les nuits à 3h UTC :

```
Sources GeoJSON (IGN)
        │
        ▼
  Hash SHA-256 identique ?
        │
    Non ──► Régénération des ODG ──► Commit automatique dans output/
        │
    Oui ──► Rien à faire
```

### Déclenchement manuel

Depuis l'onglet **Actions → Génération des cartes ODG → Run workflow** :

| Option | Description |
|---|---|
| **Forcer la régénération** | Régénère même si la source n'a pas changé |
| **Cartes à générer** | Sélectionner un sous-ensemble (ex. `regions,departements`) |

Les fichiers ODG générés sont aussi disponibles comme **artefacts du workflow**
(onglet Actions → run → Artifacts) pendant 90 jours.

---

## 💻 Génération locale sous Windows (PowerShell)

Les scripts PowerShell originaux sont dans `scripts/ps/`. Ils fonctionnent
**sans aucune dépendance** (stdlib .NET uniquement). Ils utilisent la même projection
Lambert-93 et la même mise en page que le script Python.

```powershell
# Régions
.\scripts\ps\geojson-region-to-odg.ps1

# Départements
.\scripts\ps\geojson-departement-to-odg.ps1

# Cantons (+ arrondissements municipaux + Rhône)
.\scripts\ps\geojson-canton-to-odg.ps1

# Communes (~35 000 entités, plusieurs minutes)
.\scripts\ps\geojson-commune-to-odg.ps1

# Avec chemin de sortie personnalisé
.\scripts\ps\geojson-departement-to-odg.ps1 -OutputFile "C:\cartes\france.odg"
```

---

## 🐍 Génération locale sous Linux / macOS (Python)

Le script Python `scripts/generate_odg.py` est le portage des scripts PS
utilisé par GitHub Actions (projection Lambert-93, génération de `output/maps.json`). Il nécessite **Python 3.8+**, sans dépendance externe :

```bash
# Toutes les cartes
python scripts/generate_odg.py

# Forcer la régénération (ignore le cache)
python scripts/generate_odg.py --force

# Seulement certaines cartes
python scripts/generate_odg.py --only regions,departements

# Options disponibles : regions, departements, cantons, communes
```

---

## 📐 Caractéristiques techniques

| Paramètre | Valeur |
|---|---|
| Format de sortie | ODF Graphics 1.3 (`.odg`) |
| Projection | Lambert-93 (EPSG:2154), échelle identique en X et Y |
| Dimensions de la page | 30 × 25 cm, orientation paysage |
| Couleur de remplissage | `#6AAED6` (bleu clair) |
| Couleur de contour | `#1A4F7A` (bleu foncé) |
| Épaisseur contour | `0.018 cm` (régions/dép/cantons), `0.004 cm` (communes) |
| Identifiant de chaque forme | `draw:name` = code INSEE officiel |

---

## 📚 Sources et licences

| Source | Licence |
|---|---|
| [gregoiredavid/france-geojson](https://github.com/gregoiredavid/france-geojson) | Licence ouverte (IGN / Etalab) |
| [geo.api.gouv.fr](https://geo.api.gouv.fr/) (arrondissements municipaux, communes Rhône) | Licence ouverte Etalab |

Les fichiers ODG produits héritent de la **Licence ouverte / Open Licence 2.0** d'Etalab,
compatible avec la réutilisation commerciale et non commerciale avec mention de la source.

---

## 🔧 Configuration GitHub requise

Dans le dépôt GitHub :
**Settings → Actions → General → Workflow permissions**
→ Activer **Read and write permissions**

Cela permet au bot `github-actions[bot]` de commiter les fichiers ODG régénérés.
