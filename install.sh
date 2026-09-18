#!/usr/bin/env bash
LOUTER_PACKAGE_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
LOUTER_VERSION="$(
  node -e 'const p=require(process.argv[1]); process.stdout.write(String(p.version))' \
  "$LOUTER_PACKAGE_ROOT/package.json"
)"
LOUTER_ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y) LOUTER_ASSUME_YES=1 ;;
  esac
done
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$HERE/scripts/install.py" "$@"
