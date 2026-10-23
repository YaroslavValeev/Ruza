# Backup quota recovery

Observed placement: Club Box / Ruza CRM -> production runtime -> S1
(`mywave-bot-server`) -> `/opt/icebeach` (existing checkout, not a new placement
decision) -> `YaroslavValeev/Ruza` -> `https://ruza.mywavewake.ru/api` -> operational
and intake Google Sheets; protected local backups under `/opt/mywave/backups/`.

## Incident and scope

The owner-reported backup on 2026-10-23 completed operational (18 tabs) and its
manifest/hash dry-run. Intake then failed with HTTP 429 (read quota 60/min/user).
There was no completed intake manifest or overall BACKUP_COMPLETE evidence.
Do not delete or repeat the valid operational copy to recover intake.

Only `scripts/backup_sheets.py` changes production-adjacent behavior. The live API
wrapper, Docker Compose, credentials and Google Sheets data are unchanged.

## Read policy

- Space read starts by at least two seconds, including the metadata request.
- Retry HTTP 429/500/502/503/504 and transport failures at most eight attempts.
- Exponential backoff with jitter caps at 64 seconds. Numeric Retry-After can
  extend a wait to at most 300 seconds. No infinite retry or raw error payload log.
- HTTP 400/401/403/404 fail immediately; do not mask permissions or range errors.
- Quote A1 tab names, including apostrophes.
- Keep the existing manifest format; publish it only after all tabs are saved.

This is a per-backup limit, not a shared cross-process quota coordinator. The API,
bot or another backup can still consume the same service-account quota. Run one
backup during a quiet window. Reads are sequential, not a transactional snapshot.

Google reference: https://developers.google.com/workspace/sheets/api/limits

## Validation and recovery

```powershell
$env:PYTHONPATH=(Resolve-Path icebeach-wakeclub).Path
python -m pytest icebeach-wakeclub/apps/api/tests/test_backup_sheets_quota.py icebeach-wakeclub/apps/api/tests/test_restore_sheets_backup_guard.py -q
```

For container validation, run the same tests inside an API image with this source
mounted read-only; no Google credentials/network are needed. Docker daemon
availability and CI are independent evidence gates, not implied by local pytest.

For server recovery use a pinned, hash-verified copy of the helper in a private
temporary directory, outside the clean production checkout. Back up intake only
to a new child directory next to the existing operational backup. Run the existing
restore helper without `--write` to check the new manifest and every tab hash.
Never restore into operational/intake Sheets as part of this procedure. Store
only path/count/status output in evidence, not customer rows, tokens or JSON files.

This checks backup integrity only. A real restore must target a separate approved
test spreadsheet; an independent encrypted offsite copy remains a separate gate.

Rollback: stop the one-off backup process and keep the existing completed backup.
Revert this tooling PR via a new PR if needed; no schema/data/container rollback
is required. Partial temporary directories are not completed backups.
