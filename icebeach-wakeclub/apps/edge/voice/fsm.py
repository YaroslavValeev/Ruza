"""On-device voice check-in FSM (no cloud STT)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class VoiceState(str, Enum):
    GREETING = "greeting"
    ASK_PHONE = "ask_phone"
    CONFIRM_BOOKING = "confirm_booking"
    DONE = "done"
    ABORT = "abort"


@dataclass
class VoiceContext:
    phone: str = ""
    booking_id: str = ""
    client_name: str = ""
    consent_voice: bool = False


@dataclass
class VoiceFsm:
    state: VoiceState = VoiceState.GREETING
    context: VoiceContext = field(default_factory=VoiceContext)

    def transition(self, user_text: str) -> tuple[VoiceState, str]:
        text = user_text.strip()
        if self.state == VoiceState.GREETING:
            self.state = VoiceState.ASK_PHONE
            return self.state, "Здравствуйте! Назовите номер телефона для check-in."

        if self.state == VoiceState.ASK_PHONE:
            digits = "".join(ch for ch in text if ch.isdigit())
            if len(digits) < 10:
                return self.state, "Не удалось распознать телефон. Повторите, пожалуйста."
            self.context.phone = f"+{digits}" if not text.startswith("+") else text
            self.state = VoiceState.CONFIRM_BOOKING
            return self.state, f"Телефон {self.context.phone}. Подтвердите: да или нет."

        if self.state == VoiceState.CONFIRM_BOOKING:
            if text.lower() in {"да", "yes", "подтверждаю"}:
                self.state = VoiceState.DONE
                return self.state, "Check-in подтверждён. Приятного катания!"
            self.state = VoiceState.ABORT
            return self.state, "Check-in отменён."

        return self.state, "Сессия завершена."


def run_cli(on_checkin: Callable[[str], None] | None = None) -> None:
    fsm = VoiceFsm()
    prompt, _ = fsm.transition("")
    print(prompt)
    while fsm.state not in {VoiceState.DONE, VoiceState.ABORT}:
        user_text = input("> ")
        _, reply = fsm.transition(user_text)
        print(reply)
    if fsm.state == VoiceState.DONE and on_checkin and fsm.context.phone:
        on_checkin(fsm.context.phone)


if __name__ == "__main__":
    run_cli()
