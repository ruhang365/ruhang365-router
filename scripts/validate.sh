#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
skill_dir="$repo_root/skills/ruhang365-router"
router_script="$skill_dir/scripts/route_ruhang365.py"
matcher_script="$skill_dir/scripts/community_catalog.py"
catalog_builder="$repo_root/scripts/build_catalog.py"
rhzl_exporter="$repo_root/scripts/export_rhzl_import.py"

python3 -m py_compile "$router_script" "$matcher_script" "$catalog_builder" "$rhzl_exporter"
python3 "$catalog_builder" --check
python3 "$rhzl_exporter" >/dev/null
python3 -m unittest discover -s "$repo_root/tests" -p 'test_*.py' -v

validator="${CODEX_SKILL_VALIDATOR:-${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py}"
if [[ -f "$validator" ]]; then
  python3 "$validator" "$skill_dir"
else
  printf 'Official Skill validator not found; skipped: %s\n' "$validator"
fi
