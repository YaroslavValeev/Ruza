from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from .config import AgentsSettings


class NotifyChannel(ABC):
    @abstractmethod
    def send(self, title: str, message: str) -> None:
        raise NotImplementedError


class FileLogChannel(NotifyChannel):
    def __init__(self, settings: AgentsSettings) -> None:
        self._path = settings.log_path

    def send(self, title: str, message: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        line = f"{timestamp} [{title}] {message}\n"
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line)


class TelegramChannel(NotifyChannel):
    def __init__(self, settings: AgentsSettings) -> None:
        self._token = settings.telegram_bot_token
        self._chat_id = settings.telegram_owner_chat_id

    def send(self, title: str, message: str) -> None:
        if not self._token or not self._chat_id:
            return
        import json
        import urllib.parse
        import urllib.request

        text = f"{title}\n\n{message}"
        payload = urllib.parse.urlencode({"chat_id": self._chat_id, "text": text}).encode("utf-8")
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        request = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(request, timeout=20):
            return


def get_notify_channels(settings: AgentsSettings) -> list[NotifyChannel]:
    channels: list[NotifyChannel] = [FileLogChannel(settings)]
    if settings.telegram_bot_token and settings.telegram_owner_chat_id:
        channels.append(TelegramChannel(settings))
    return channels


def notify_all(settings: AgentsSettings, title: str, message: str) -> None:
    for channel in get_notify_channels(settings):
        channel.send(title, message)
