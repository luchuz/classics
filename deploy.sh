#!/bin/bash
# Rebuild the Classics Library site and push it (if a GitHub remote exists). Always exits 0.
cd "$(dirname "$0")" || exit 0
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
LOG=deploy.log
{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') site build ====="
  python3 build.py 2>&1 | grep -v "Warning\|warnings.warn"
  if [ -n "$(git status --porcelain)" ]; then
    git add -A && git commit -qm "build $(date '+%Y-%m-%d %H:%M')" && echo "committed"
  else
    echo "no changes"
  fi
  if git remote get-url origin >/dev/null 2>&1; then
    git push -q origin main 2>&1 && echo "pushed" || echo "push failed"
  else
    echo "no origin remote yet — see PUBLISH.md"
  fi
} >> "$LOG" 2>&1
exit 0
