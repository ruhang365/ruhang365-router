#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
skill_dir="$repo_root/skills/ruhang365-router"
router_script="$skill_dir/scripts/route_ruhang365.py"
matcher_script="$skill_dir/scripts/community_catalog.py"
catalog_builder="$repo_root/scripts/build_catalog.py"
snapshot_updater="$repo_root/scripts/update_catalog_snapshot.py"

python3 -m py_compile "$router_script" "$matcher_script" "$catalog_builder" "$snapshot_updater"
python3 -c "import sys; sys.path.insert(0, '$skill_dir/scripts'); from community_catalog import load_catalog; load_catalog()"
python3 -m unittest discover -s "$repo_root/tests" -p 'test_*.py' -v

validator="${CODEX_SKILL_VALIDATOR:-${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py}"
if [[ -f "$validator" ]]; then
  python3 "$validator" "$skill_dir"
else
  printf 'Official Skill validator not found; skipped: %s\n' "$validator"
fi
