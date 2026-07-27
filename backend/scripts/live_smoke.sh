#!/usr/bin/env bash
# Ζωντανός E2E έλεγχος με το κλειδί που ΗΔΗ υπάρχει στον διακομιστή.
# Το ANTHROPIC_API_KEY φορτώνεται από το πρώτο .env που το περιέχει —
# δεν περνά ποτέ από argv ή από το ιστορικό εντολών.
#
#   cd <repo>/backend && git pull -q && bash scripts/live_smoke.sh
set -euo pipefail
cd "$(dirname "$0")/.."   # -> backend/

if [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -z "${ANTHROPIC_AUTH_TOKEN:-}" ]; then
  for f in .env ../.env ../../.env /etc/nomos-one/.env /etc/nomos-audit/.env; do
    if [ -f "$f" ] && grep -q '^ANTHROPIC_API_KEY=' "$f"; then
      echo "→ Φόρτωση κλειδιού από: $f"
      set -a; # shellcheck disable=SC1090
      . "$f"; set +a
      break
    fi
  done
fi

PY="$(command -v python3 || command -v python)"
exec "$PY" scripts/live_smoke.py "$@"
