#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
skill_name="ruhang365-router"
source_dir="$repo_root/skills/$skill_name"
codex_root="${CODEX_HOME:-$HOME/.codex}"
destination="$codex_root/skills/$skill_name"

if [[ ! -f "$source_dir/SKILL.md" ]]; then
  printf 'error: Skill source is incomplete: %s\n' "$source_dir" >&2
  exit 2
fi

if [[ -e "$destination" ]]; then
  printf 'error: destination already exists: %s\n' "$destination" >&2
  printf 'Remove or rename the existing Skill deliberately, then run this installer again.\n' >&2
  exit 3
fi

mkdir -p "$(dirname "$destination")"
cp -R "$source_dir" "$destination"

printf 'Installed %s to %s\n' "$skill_name" "$destination"
printf 'Open a new Codex task so the Skill metadata can be reloaded.\n'
