#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

usage() {
  echo 'Usage: restore-proof.sh --source-backup-dir DIR --target-spreadsheet-id ID --expected-target-title TITLE --tools-sha SHA --restore-sha256 HASH --driver-sha256 HASH'
  echo 'Writes only the approved TEST spreadsheet after saving its current values on the host.'
}

SOURCE="" TARGET="" TITLE="" TOOLS_SHA="" RESTORE_HASH="" DRIVER_HASH=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --source-backup-dir) SOURCE="${2:?Missing source directory}"; shift 2 ;;
    --target-spreadsheet-id) TARGET="${2:?Missing target id}"; shift 2 ;;
    --expected-target-title) TITLE="${2:?Missing target title}"; shift 2 ;;
    --tools-sha) TOOLS_SHA="${2:?Missing tools SHA}"; shift 2 ;;
    --restore-sha256) RESTORE_HASH="${2:?Missing restore hash}"; shift 2 ;;
    --driver-sha256) DRIVER_HASH="${2:?Missing driver hash}"; shift 2 ;;
    *) usage >&2; exit 2 ;;
  esac
done
[[ -n "$SOURCE" && -n "$TARGET" && -n "$TITLE" ]] || { usage >&2; exit 2; }
[[ "$TOOLS_SHA" =~ ^[0-9a-f]{40}$ && "$RESTORE_HASH" =~ ^[0-9a-f]{64}$ && "$DRIVER_HASH" =~ ^[0-9a-f]{64}$ ]] || { usage >&2; exit 2; }

PROJECT_DIR="${RUZA_PROJECT_DIR:-/opt/icebeach}"
EVIDENCE_ROOT="${RUZA_EVIDENCE_ROOT:-/opt/mywave/backups}"
RAW_BASE="${RUZA_RAW_BASE:-https://raw.githubusercontent.com/YaroslavValeev/Ruza}"
STEP=baseline
RUN=not-created
trap 'rc=$?; printf "FAILED step=%s line=%s exit=%s evidence=%s\n" "$STEP" "$LINENO" "$rc" "$RUN" >&2; exit "$rc"' ERR
cd "$PROJECT_DIR"
test -z "$(git status --porcelain)"
test -f "$SOURCE/manifest.json"
mkdir -p "$EVIDENCE_ROOT"
exec 9>"$EVIDENCE_ROOT/.ruza-restore-test.lock"
flock -n 9
dc() { docker compose --env-file .env.docker "$@" </dev/null; }
BASE_SHA=$(git rev-parse HEAD)
API_ID=$(dc ps -q api)
DASHBOARD_ID=$(dc ps -q dashboard)
test -n "$API_ID" && test -n "$DASHBOARD_ID"

STEP=verified-helpers
RUN=$(mktemp -d "$EVIDENCE_ROOT/ruza-restore-proof-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXXXX")
printf 'RESTORE_EVIDENCE_DIR=%s\n' "$RUN"
printf '%s\n' "$BASE_SHA" > "$RUN/production-source-sha"
printf '%s\n' "$TOOLS_SHA" > "$RUN/proof-tools-sha"
for FILE in restore_sheets_backup.py restore_test.py; do
  curl -fsSL --connect-timeout 10 --max-time 60 "$RAW_BASE/$TOOLS_SHA/scripts/$FILE" -o "$RUN/$FILE"
done
curl -fsSL --connect-timeout 10 --max-time 60 \
  "$RAW_BASE/a774f91e1e37bc554c11ca40868c2dcd556e1eee/scripts/backup_sheets.py" -o "$RUN/backup_sheets.py"
printf '%s  %s\n' "$RESTORE_HASH" "$RUN/restore_sheets_backup.py" "$DRIVER_HASH" "$RUN/restore_test.py" \
  e90ad3a197973ce33d413b6df1d851060406e8d3367a24322ab6b1af4548f2ef "$RUN/backup_sheets.py" | sha256sum -c -
python3 "$RUN/restore_sheets_backup.py" --backup-dir "$SOURCE"

TMP=$(dc exec -T api mktemp -d /tmp/ruza-restore.XXXXXXXX)
printf '%s\n' "$TMP" > "$RUN/container-temp-path"
for FILE in restore_sheets_backup.py restore_test.py backup_sheets.py; do dc cp "$RUN/$FILE" "api:$TMP/$FILE"; done
dc cp "$SOURCE" "api:$TMP/source"
phase() {
  dc exec -T --workdir /app api python "$TMP/restore_test.py" \
    --phase "$1" --work-dir "$TMP" --target-spreadsheet-id "$TARGET" --expected-target-title "$TITLE"
}

STEP=save-test-target-first
phase before
dc cp "api:$TMP/before" "$RUN/before"
dc cp "api:$TMP/target-metadata-before.json" "$RUN/target-metadata-before.json"
MANIFEST=$(find "$RUN/before" -type f -name manifest.json -print -quit)
test -n "$MANIFEST"
python3 "$RUN/restore_sheets_backup.py" --backup-dir "$(dirname "$MANIFEST")"
sync -f "$MANIFEST"
MANIFEST_HASH=$(sha256sum "$MANIFEST" | awk '{print $1}')
dc exec -T api python -c 'import json,sys; from pathlib import Path; Path(sys.argv[1],"snapshot-persisted").write_text(json.dumps({"target":sys.argv[2].strip(),"manifest_sha256":sys.argv[3]}))' "$TMP" "$TARGET" "$MANIFEST_HASH"

STEP=restore-approved-test-target
phase restore
STEP=verify-every-restored-value
phase after
dc cp "api:$TMP/after" "$RUN/after"
dc cp "api:$TMP/proof.json" "$RUN/proof.json"

STEP=unchanged-production-runtime
test "$(git rev-parse HEAD)" = "$BASE_SHA"
test -z "$(git status --porcelain)"
test "$(dc ps -q api)" = "$API_ID"
test "$(dc ps -q dashboard)" = "$DASHBOARD_ID"
curl -fsS --max-time 15 http://127.0.0.1:8000/health
printf '\n'
cat "$RUN/proof.json"
# Keep private container snapshots on failure; remove only this run on success.
dc exec -T api python -c 'import shutil,sys; from pathlib import Path; p=Path(sys.argv[1]).resolve(); assert p.parent==Path("/tmp") and p.name.startswith("ruza-restore."); shutil.rmtree(p)' "$TMP"
printf '\nRESTORE_PROOF_COMPLETE evidence=%s\n' "$RUN"
