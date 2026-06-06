from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "_site"
PUBLIC_FILES = ("index.html", "app.js", "styles.css", "news.json")


def main() -> int:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir()

    for name in PUBLIC_FILES:
        source = ROOT / name
        if not source.is_file():
            raise FileNotFoundError(f"Required public file is missing: {name}")
        shutil.copy2(source, OUTPUT / name)

    (OUTPUT / ".nojekyll").touch()
    print(f"Built {len(PUBLIC_FILES)} public files in {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
