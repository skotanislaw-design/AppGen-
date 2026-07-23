#!/usr/bin/env bash
# Deploy / update του Nomos Audit στον server (Hetzner 116.203.100.94).
# Εκτέλεση ΣΤΟΝ server, από τον φάκελο του repo: ./deploy/deploy.sh [branch]
set -euo pipefail

cd "$(dirname "$0")/.."
BRANCH="${1:-claude/legal-document-compliance-check-ry9o8w}"
PORT="${NOMOS_AUDIT_PORT:-8080}"

echo "==> Ενημέρωση κώδικα (branch: $BRANCH)"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

if [[ ! -f .env ]]; then
  echo "ΣΦΑΛΜΑ: δεν υπάρχει .env — εκτελέστε: cp .env.example .env και συμπληρώστε το ANTHROPIC_API_KEY" >&2
  exit 1
fi
if ! grep -Eq '^ANTHROPIC_API_KEY=sk-ant-' .env; then
  echo "ΠΡΟΣΟΧΗ: το ANTHROPIC_API_KEY στο .env δεν μοιάζει έγκυρο (sk-ant-…)." >&2
fi

echo "==> Build & εκκίνηση containers"
docker compose build
docker compose up -d

echo "==> Έλεγχος λειτουργίας"
for i in $(seq 1 15); do
  if curl -fsS "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
    echo "OK: $(curl -fsS "http://127.0.0.1:${PORT}/api/health")"
    echo "==> Το Nomos Audit τρέχει στο 127.0.0.1:${PORT} (πίσω από το reverse proxy)."
    exit 0
  fi
  sleep 2
done

echo "ΣΦΑΛΜΑ: το /api/health δεν αποκρίθηκε — δείτε: docker compose logs api" >&2
exit 1
