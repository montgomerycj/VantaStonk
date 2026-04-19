#!/bin/bash
# Stop hook: commit and push any uncommitted changes at session end.
# Keeps the remote always up-to-date when switching machines.

cd "$CLAUDE_PROJECT_DIR" || exit 0

if ! git remote get-url origin &>/dev/null; then
  exit 0
fi

# Commit if there are changes
if ! git diff --quiet HEAD 2>/dev/null || ! git diff --cached --quiet 2>/dev/null || [ -n "$(git ls-files --others --exclude-standard)" ]; then
  git add -A
  git commit -m "Session sync: $(date '+%Y-%m-%d %H:%M')" --no-verify 2>/dev/null
fi

# Push if ahead of remote
if git log origin/master..HEAD --oneline 2>/dev/null | grep -q .; then
  git push origin master 2>/dev/null && echo "[auto-push] Pushed to remote"
fi
