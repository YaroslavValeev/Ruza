import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { createCheckin, getClients } from "../api/client";
import { ConsentBadges } from "../components/ConsentBadges";
import { ClientItem } from "../types";

type VoiceCheckinWizardProps = {
  date: string;
  token?: string;
  onSuccess: (message: string) => void;
  onError: (message: string) => void;
};

type WizardStep = "greeting" | "ask_phone" | "confirm" | "done" | "abort";

export function VoiceCheckinWizard({ date, token, onSuccess, onError }: VoiceCheckinWizardProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<WizardStep>("greeting");
  const [prompt, setPrompt] = useState("Нажмите «Начать» для голосового check-in.");
  const [phone, setPhone] = useState("");
  const [client, setClient] = useState<ClientItem | null>(null);
  const [listening, setListening] = useState(false);
  const [loading, setLoading] = useState(false);

  const speechSupported = useMemo(() => typeof window !== "undefined" && ("webkitSpeechRecognition" in window || "SpeechRecognition" in window), []);

  const speak = useCallback((text: string) => {
    if (!("speechSynthesis" in window)) {
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "ru-RU";
    window.speechSynthesis.speak(utterance);
  }, []);

  const reset = () => {
    setStep("greeting");
    setPhone("");
    setClient(null);
    setPrompt("Нажмите «Начать» для голосового check-in.");
  };

  const startWizard = () => {
    setOpen(true);
    reset();
    setStep("ask_phone");
    const text = "Здравствуйте! Назовите номер телефона для check-in.";
    setPrompt(text);
    speak(text);
  };

  const lookupClient = async (phoneValue: string) => {
    const rows = await getClients(phoneValue, token);
    return rows[0] ?? null;
  };

  const submitCheckin = async () => {
    if (!client?.consent_voice) {
      onError("У клиента нет consent_voice. Используйте обычный check-in.");
      setStep("abort");
      return;
    }
    setLoading(true);
    try {
      await createCheckin({ method: "phone", phone: client.phone, date, status: "arrived" }, token);
      setStep("done");
      const text = "Check-in подтверждён. Приятного катания!";
      setPrompt(text);
      speak(text);
      onSuccess("Голосовой check-in выполнен");
      setOpen(false);
      reset();
    } catch (err) {
      onError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handlePhoneInput = async (value: string) => {
    const digits = value.replace(/\D/g, "");
    if (digits.length < 10) {
      setPrompt("Не удалось распознать телефон. Повторите или введите вручную.");
      return;
    }
    const normalized = value.trim().startsWith("+") ? value.trim() : `+${digits}`;
    setPhone(normalized);
    setLoading(true);
    try {
      const found = await lookupClient(normalized);
      if (!found) {
        onError("Клиент не найден по телефону");
        setStep("abort");
        return;
      }
      setClient(found);
      setStep("confirm");
      const text = `Телефон ${found.phone}, ${found.full_name}. Подтвердите check-in.`;
      setPrompt(text);
      speak(text);
    } catch (err) {
      onError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const startListening = () => {
    if (!speechSupported) {
      setPrompt("Браузер не поддерживает распознавание речи. Введите телефон вручную ниже.");
      return;
    }
    const SpeechRecognitionCtor = (window as unknown as { SpeechRecognition?: new () => SpeechRecognition; webkitSpeechRecognition?: new () => SpeechRecognition }).SpeechRecognition
      || (window as unknown as { webkitSpeechRecognition?: new () => SpeechRecognition }).webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) {
      return;
    }
    const recognition = new SpeechRecognitionCtor();
    recognition.lang = "ru-RU";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    setListening(true);
    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const transcript = event.results[0]?.[0]?.transcript ?? "";
      if (step === "ask_phone") {
        void handlePhoneInput(transcript);
      } else if (step === "confirm") {
        const yes = /да|yes|подтверж/i.test(transcript);
        if (yes) {
          void submitCheckin();
        } else {
          setStep("abort");
          setPrompt("Check-in отменён.");
        }
      }
      setListening(false);
    };
    recognition.onerror = () => {
      setListening(false);
      setPrompt("Ошибка микрофона. Введите данные вручную.");
    };
    recognition.onend = () => setListening(false);
    recognition.start();
  };

  if (!open) {
    return (
      <button type="button" className="game-button-secondary min-h-[48px] w-full" onClick={startWizard}>
        Голосовой check-in
      </button>
    );
  }

  return (
    <div className="rounded-2xl border border-cyan-400/20 bg-cyan-950/20 p-4 space-y-3">
      <div className="text-xs font-black uppercase tracking-[0.12em] text-cyan-100/70">Голосовой check-in</div>
      <p className="text-sm text-slate-200">{prompt}</p>
      {client ? <ConsentBadges consentFace={client.consent_face} consentVoice={client.consent_voice} /> : null}

      {step === "ask_phone" ? (
        <form
          className="space-y-2"
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            void handlePhoneInput(phone);
          }}
        >
          <input
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            className="game-input min-h-[48px]"
            placeholder="+79990000001"
            inputMode="tel"
          />
          <div className="grid gap-2 sm:grid-cols-2">
            <button type="submit" className="game-button min-h-[48px]" disabled={loading}>
              Далее
            </button>
            <button type="button" className="game-button-secondary min-h-[48px]" disabled={listening} onClick={startListening}>
              {listening ? "Слушаю..." : "Сказать телефон"}
            </button>
          </div>
        </form>
      ) : null}

      {step === "confirm" ? (
        <div className="grid gap-2 sm:grid-cols-2">
          <button type="button" className="game-button min-h-[48px]" disabled={loading} onClick={() => void submitCheckin()}>
            Подтвердить
          </button>
          <button type="button" className="game-button-secondary min-h-[48px]" disabled={listening} onClick={startListening}>
            Сказать «да»
          </button>
        </div>
      ) : null}

      <button
        type="button"
        className="text-xs text-slate-400 underline"
        onClick={() => {
          setOpen(false);
          reset();
        }}
      >
        Закрыть
      </button>
    </div>
  );
}
