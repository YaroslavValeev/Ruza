# Edge Voice Check-in

On-device voice admin prototype (без OpenAI API).

## FSM

`greeting → ask_phone → confirm_booking → done`

## CLI demo

**[PowerShell]**

```powershell
cd icebeach-wakeclub
$env:PYTHONPATH="."
$env:SESSION_COOKIE="icebeach_session=..."
python -m apps.edge.voice.cli --date 2026-06-01
```

Перед вызовом API проверьте `consent_voice=true` у клиента в Sheets.

Аудио не сохраняется в Sheets.
