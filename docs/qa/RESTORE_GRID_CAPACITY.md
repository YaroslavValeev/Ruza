# Restore grid capacity

Observed placement: Club Box / Ruza CRM -> production runtime -> S1
(`mywave-bot-server`) -> `/opt/icebeach` (existing checkout) ->
`YaroslavValeev/Ruza` -> `https://ruza.mywavewake.ru/api` -> operational and intake
Google Sheets, with private local backups under `/opt/mywave/backups/`.
Restore tests use a separate explicitly approved spreadsheet, never either
production spreadsheet. This is not a new app, Compose project or production DB.

## Gap and behavior

The current operational backup contains a 40-column `bookings` tab, while the
historical restore-test tab has only 26 columns. The old restore helper did not
prepare destination grid capacity before clearing values.

The restore helper now prepares all missing tabs and required grid growth in one
metadata batch before any value clear/update. Existing dimensions are never
shrunk. Only insufficient row/column dimensions are selected in the field mask;
existing styles, validation and other sheet properties are not restyled.
Missing tabs start with at least the normal 1000 rows / 26 columns, or the full
backup dimensions when larger. A1 ranges quote apostrophes and spaces safely.

The existing hash/dry-run and production-target guards remain unchanged. No
`--allow-prod-target` override is part of the restore-test procedure.

## Runbook

1. Verify current production source SHA and clean checkout; do not deploy this
   tool by changing the running application's checkout or container images.
2. Verify the exact non-production target title/id against settings and the
   operational/intake IDs. The owner must approve reusing a nonempty test target.
3. Back up its existing values, copy the result out of the container to a private
   host directory, and verify its manifest/hashes before any restore write.
4. Use a pinned hash-verified restore helper outside the application checkout.
   Pace Google calls and apply bounded transient retries in the one-off test
   process only. Never change the live API's shared transport.
   `scripts/restore_test.py` provides `before`, `restore`, and `after` phases.
   It requires an operational source manifest, an exact approved target title,
   the existing production-target guard, and a `snapshot-persisted` marker after
   the pre-test copy is durably saved and checked on the host. Place the pinned
   quota-aware backup helper from PR #20 alongside it as `backup_sheets.py`;
   place `restore_sheets_backup.py` and the input `source/` there too. The
   backup helper dependency is explicit; the application does not import it.
5. Restore the operational snapshot into that approved target. Read all restored
   tabs back and compare every saved JSON value with the input backup, not merely
   row counts or successful HTTP status. Keep only paths/counts/status in logs.
6. Preserve pre-test backup, input snapshot and result/evidence on the host.
   Check production health and unchanged source/container identities afterward.

Restores are sequential, not transactional across tabs. On failure, stop and
preserve evidence; the production tables must remain untouched. Roll back test
values only from the pre-test backup into the same approved test target. A
metadata preparation failure must happen before any values are cleared.

This is a values restore test. The JSON backup is not a full-fidelity backup of
formulas, formatting, scripts, file permissions, or spreadsheet-level settings.
It also does not prove encrypted offsite storage or a real club shift.

## Offline verification

```powershell
$env:PYTHONPATH=(Resolve-Path icebeach-wakeclub).Path
python -m pytest icebeach-wakeclub/apps/api/tests/test_restore_sheets_grid_capacity.py icebeach-wakeclub/apps/api/tests/test_restore_sheets_backup_guard.py -q
python scripts/test_restore_sheets_backup.py
```

The matrix covers smaller/equal/larger row and column grids, missing sheets,
no-shrink/no-empty-batch behavior, quoted A1 titles, metadata failure before clear,
offline dry-run, and protected/empty target refusal before Google access.
Docker and live restore/readback are separate gates; local pytest is not proof
that a live restore was executed.
