"""
release_notes.py
Prepares the GitHub release of the ODG Atlas when the maps have changed.

Compares output/maps.json with the catalog of the latest release, then
creates the version SERIES.YYYYMMDD (e.g. tag v1.1.20261029, date of the
day; SERIES is raised by hand when maps are added). Writes release-notes.md
and, for GitHub Actions, the outputs new (true/false), tag, title and files
(assets to attach).

Usage:
    python scripts/release_notes.py
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

CATALOG_PATH = "output/maps.json"
NOTES_PATH = "release-notes.md"
# Version SERIES.YYYYMMDD; raise SERIES by hand (e.g. "1.2") with new maps
SERIES = "1.1"
TAG_PREFIX = "v"
# Tags of the first releases (maps-YYYY.MM.DD), still compared with
LEGACY_TAG_PREFIX = "maps-"
DEFAULT_REPOSITORY = "gaborjager/odg-atlas"
# Changes of these fields alone (same file) are listed as "details changed"
DETAIL_FIELDS = ("title", "description", "area", "code_type", "source", "license")


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False)


def latest_tag():
    out = git("for-each-ref", "--sort=-creatordate", "--format=%(refname:short)",
              f"refs/tags/{TAG_PREFIX}[0-9]*", f"refs/tags/{LEGACY_TAG_PREFIX}*").stdout.split()
    return out[0] if out else None


def catalog_at(tag):
    if not tag:
        return {}
    shown = git("show", f"{tag}:{CATALOG_PATH}")
    if shown.returncode != 0:
        return {}
    return {m["id"]: m for m in json.loads(shown.stdout)["maps"]}


def new_tag():
    base = f"{TAG_PREFIX}{SERIES}.{datetime.now(timezone.utc):%Y%m%d}"
    existing = set(git("tag", "-l", f"{base}*").stdout.split())
    tag, n = base, 1
    while tag in existing:   # second release of the day: v1.0.YYYYMMDD.2
        n += 1
        tag = f"{base}.{n}"
    return tag


def size(n):
    return f"{n / 1024:.0f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f} MB"


def table(maps):
    lines = ["| Map | Id | Zones | Codes | Size |", "|---|---|---|---|---|"]
    for m in maps:
        lines.append(f"| {m['title']} | `{m['id']}` | {m['objects']} | {m.get('code_type', '')} "
                     f"| {size(m['size'])} |")
    return lines


def local_path(m):
    """Path of a map file in the repository, from its catalog URL."""
    for folder in ("output", "static"):
        marker = f"/{folder}/"
        if marker in m["url"]:
            return folder + "/" + m["url"].split(marker, 1)[1]
    return None


def main():
    os.chdir(Path(__file__).parent.parent)
    current = {m["id"]: m for m in json.loads(Path(CATALOG_PATH).read_text(encoding="utf-8"))["maps"]}
    previous_tag = latest_tag()
    previous = catalog_at(previous_tag)

    added = [m for i, m in current.items() if i not in previous]
    removed = [m for i, m in previous.items() if i not in current]
    updated = [m for i, m in current.items() if i in previous and m["sha256"] != previous[i]["sha256"]]
    details = [m for i, m in current.items() if i in previous and m["sha256"] == previous[i]["sha256"]
               and any(m.get(k) != previous[i].get(k) for k in DETAIL_FIELDS)]

    outputs = {"new": "false"}
    if added or removed or updated or details:
        tag = new_tag()
        lines = []
        if previous_tag:
            repo = os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPOSITORY)
            lines.append(f"Maps changed since [{previous_tag}](https://github.com/{repo}/releases/tag/{previous_tag}).")
        else:
            lines.append("First release of the ODG Atlas.")
        if added:
            lines += ["", "### Added", ""] + table(added)
        if updated:
            lines += ["", "### Updated", ""] + table(updated)
        if details:
            lines += ["", "### Details changed (same file)", ""]
            lines += [f"- {m['title']} (`{m['id']}`)" for m in details]
        if removed:
            lines += ["", "### Removed", ""]
            lines += [f"- {m['title']} (`{m['id']}`)" for m in removed]
        lines += ["", "All the maps of the atlas are attached, with the catalog `maps.json`. "
                  "The URLs of the catalog always point to the latest version on the `main` branch.", ""]
        Path(NOTES_PATH).write_text("\n".join(lines), encoding="utf-8")
        files = [CATALOG_PATH] + [p for p in (local_path(m) for m in current.values()) if p]
        outputs = {"new": "true", "tag": tag, "title": f"ODG Atlas {tag[len(TAG_PREFIX):]}",
                   "files": " ".join(files)}
        print(f"Release {tag}: {len(added)} added, {len(updated)} updated, "
              f"{len(details)} details changed, {len(removed)} removed.")
        print("\n".join(lines))
    else:
        print(f"No map change since {previous_tag}: no release.")

    gha = os.environ.get("GITHUB_OUTPUT", "")
    if gha:
        with open(gha, "a") as f:
            for k, v in outputs.items():
                f.write(f"{k}={v}\n")


if __name__ == "__main__":
    main()
