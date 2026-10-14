#!/usr/bin/env bash
# Double-click in Finder to build the Apple Silicon app and .dmg.
cd "$(dirname "$0")"
bash scripts/build-mac.sh
status=$?
echo ""
read -r -p "按 Enter 關閉視窗…" _
exit $status
