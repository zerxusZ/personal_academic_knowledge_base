#!/usr/bin/env bash
# Pre-commit guard: reject commits that stage .env or real data files.
set -e

BLOCKED_PATTERNS=('.env$' 'profile\.json$' 'kb\.json$')
staged=$(git diff --cached --name-only)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
  match=$(echo "$staged" | grep -E "$pattern" || true)
  if [[ -n "$match" ]]; then
    echo "BLOCKED: attempting to commit sensitive file: $match"
    echo "Run: git reset HEAD $match"
    exit 1
  fi
done

# Scan staged content for key patterns
if git diff --cached | grep -qE '(sk-[a-zA-Z0-9]{20,}|AIza[a-zA-Z0-9_-]{35,}|sk-ant-)'; then
  echo "BLOCKED: staged diff appears to contain an API key."
  exit 1
fi

exit 0
