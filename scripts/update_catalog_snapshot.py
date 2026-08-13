#!/usr/bin/env python3
"""Replace the bundled snapshot with a validated RHZL public Catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import urllib.request


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = REPO_ROOT / "skills" / "ruhang365-router" / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

from community_catalog import DEFAULT_CATALOG_PATH, validate_catalog  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default="https://rhzl.ruhang365.cn/api/community/catalog",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_CATALOG_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request = urllib.request.Request(
        args.url,
        headers={"Accept": "application/json", "User-Agent": "ruhang365-snapshot-bot/0.3"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            catalog = validate_catalog(json.loads(response.read()))
    except Exception as error:
        print(f"snapshot update failed: {type(error).__name__}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"snapshot updated: {catalog['catalogVersion']} {catalog['contentDigest']} "
        f"({len(catalog['items'])} items)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
