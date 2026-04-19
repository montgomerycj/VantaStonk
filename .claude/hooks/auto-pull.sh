#!/bin/bash
# SessionStart hook: pull latest from GitHub before working.
# Handles the case where another machine pushed changes.
# KEY: commits local changes first (never stash) so CJ's manual edits
# are preserved as real commits and merge properly.

cd "$CLAUDE_PROJECT_DIR" || exit 0

if ! git remote get-url origin &>/dev/null; then
  exit 0
fi

git fetch origin master 2>/dev/null

LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse origin/master 2>/dev/null)

if [ "$LOCAL" != "$REMOTE" ]; then
  # Commit any local changes FIRST (preserves CJ's manual edits as a real commit)
  if ! git diff --quiet HEAD 2>/dev/null || ! git diff --cached --quiet 2>/dev/null || [ -n "$(git ls-files --others --exclude-standard)" ]; then
    git add -A
    git commit -m "Local edits (pre-pull auto-commit)" --no-verify 2>/dev/null
    echo "[auto-pull] Committed local changes before pulling"
  fi

  # Merge (not rebase) so both sides are preserved
  if ! git merge origin/master -m "Merge remote changes" --no-edit 2>/dev/null; then
    echo "[auto-pull] WARNING: merge conflict. Aborting merge to protect local edits."
    git merge --abort 2>/dev/null
    echo "[auto-pull] Local edits preserved. Remote changes NOT applied. Resolve manually."
  else
    echo "[auto-pull] Merged remote changes"
  fi
fi
