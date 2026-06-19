from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1] / 'icebeach-wakeclub'
API_DIR = REPO_ROOT / 'apps' / 'api'

os.chdir(API_DIR)
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(REPO_ROOT))

from app.config import get_settings
from packages.sheets import SheetWrapper


def main() -> int:
    settings = get_settings()
    sheet = SheetWrapper(settings.spreadsheet_id, settings.service_account_json_path)
    rows = sheet.read_tab('bookings')
    counts = Counter(row.get('booking_id', '') for row in rows if row.get('booking_id'))
    dup_ids = sorted(booking_id for booking_id, count in counts.items() if count > 1)
    if not dup_ids:
        print('no duplicate booking_id rows found')
        return 0

    for booking_id in dup_ids:
        print(f'booking_id={booking_id}')
        for row in rows:
            if row.get('booking_id') == booking_id:
                print({
                    'date': row.get('date'),
                    'time': row.get('time'),
                    'boat_id': row.get('boat_id'),
                    'status': row.get('status'),
                    'client_id': row.get('client_id'),
                })
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
