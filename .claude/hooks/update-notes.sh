#!/bin/bash
# Inserts a dated stub at the TOP of the Daily Log section (reverse chronological).
# Runs at session end (Stop hook) so there's always a slot ready to fill.

TODAY=$(date "+%Y-%m-%d")
NOTES="$CLAUDE_PROJECT_DIR/Notes.md"

if [ -f "$NOTES" ] && ! grep -qF "### $TODAY" "$NOTES"; then
  # Find the line number of "## Daily Log", insert new stub right after it
  LOG_LINE=$(grep -n "^## Daily Log" "$NOTES" | head -1 | cut -d: -f1)
  if [ -n "$LOG_LINE" ]; then
    INSERT_AFTER=$LOG_LINE
    # Use sed to insert after the Daily Log header line
    sed -i "${INSERT_AFTER}a\\
\\
### ${TODAY}\\
\\
- <!-- session log: fill in accomplishments -->" "$NOTES"
    echo "[update-notes] Added stub for $TODAY to Notes.md (top of log)"
  else
    # Fallback: append to end if header not found
    printf "\n### %s\n\n- <!-- session log: fill in accomplishments -->\n" "$TODAY" >> "$NOTES"
    echo "[update-notes] Added stub for $TODAY to Notes.md (appended)"
  fi
fi
