#!/usr/bin/env bash
# Scan every 5 minutes for ~5h45m, then the workflow re-dispatches itself (GitHub's own cron is too irregular).
set -u
END=$(( $(date +%s) + ${LOOP_SECONDS:-20700} ))
git config user.name "github-actions[bot]"; git config user.email "41898699+github-actions[bot]@users.noreply.github.com"
while [ "$(date +%s)" -lt "$END" ]; do
  echo "::group::scan $(date -u +%H:%M)"
  if python scanner.py --json alert.json; then
    python alert.py || echo "alert step failed"
    python paper.py || echo "paper step failed"
    if [ -s paper_log.txt ]; then
      gh issue create --title "Paper fills $(date -u +'%b %d %H:%M UTC')" --label paper --assignee "$GITHUB_REPOSITORY_OWNER" --body "$(cat paper_log.txt)" || true
    fi
    if [ -n "$(git status --porcelain paper.json)" ]; then
      git add paper.json && git commit -q -m "paper ledger" && (git pull -q --rebase && git push -q || echo "push failed")
    fi
  else
    echo "scan failed, retrying next cycle"
  fi
  echo "::endgroup::"
  now=$(date +%s); sleep $(( 300 - now % 300 + 20 ))
done
