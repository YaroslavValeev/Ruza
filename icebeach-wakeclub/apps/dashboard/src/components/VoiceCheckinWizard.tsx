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

type SpeechRecognitionResultEvent = {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
};

type SpeechRecognitionInstance = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: SpeechRecognitionResultEvent) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance;

type SpeechRecognitionWindow = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
};

export function VoiceCheckinWizard({ date, token, onSuccess, onError }: VoiceCheckinWizardProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<WizardStep>("greeting");
  const [prompt, setPrompt] = useState("Нажмите «Начать», чтобы отметить прибытие голосом.");
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
    setPrompt("Нажмите «Начать», чтобы отметить прибытие голосом.");
  };

  const startWizard = () => {
    setOpen(true);
    reset();
    setStep("ask_phone");
    const text = "Здравствуйте! Назовите номер телефона, чтобы отметиться.";
    setPrompt(text);
    speak(text);
  };

  const lookupClient = async (phoneValue: string) => {
    const rows = await getClients(phoneValue, token);
    return rows[0] ?? null;
  };

  const submitCheckin = async () => {
    if (!client?.consent_voice) {
      onError("Клиент не давал согласия на голосовую отметку. Отметьте прибытие по телефону.");
      setStep("abort");
      return;
    }
    setLoading(true);
    try {
      await createCheckin({ method: "phone", phone: client.phone, date, status: "arrived" }, token);
      setStep("done");
      const text = "Прибытие отмечено. Приятного катания!";
      setPrompt(text);
      speak(text);
      onSuccess("Прибытие отмечено голосом");
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
      const text = `Телефон ${found.phone}, ${found.full_name}. Подтвердите прибытие.`;
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
    const speechWindow = window as SpeechRecognitionWindow;
    const SpeechRecognitionCtor = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) {
      return;
    }
    const recognition = new SpeechRecognitionCtor();
    recognition.lang = "ru-RU";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    setListening(true);
    recognition.onresult = (event: SpeechRecognitionResultEvent) => {
      const transcript = event.results[0]?.[0]?.transcript ?? "";
      if (step === "ask_phone") {
        void handlePhoneInput(transcript);
      } else if (step === "confirm") {
        const yes = /да|yes|подтверж/i.test(transcript);
        if (yes) {
          void submitCheckin();
        } else {
          setStep("abort");
          setPrompt("Отметка отменена.");
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
        Отметиться голосом
      </button>
    );
  }

  return (
    <div className="rounded-2xl border border-[color:var(--accent-border)] bg-[color:var(--accent-soft)] p-4 space-y-3">
      <div className="text-xs font-black uppercase tracking-[0.12em] text-[color:var(--ink-muted)]">Голосовая отметка о прибытии</div>
      <p className="text-sm text-[color:var(--ink)]">{prompt}</p>
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
            aria-label="Телефон клиента"
            placeholder="+7 999 000-00-01"
            inputMode="tel"
          />
          <div className="grid gap-2 sm:grid-cols-2">
            <button type="submit" className="game-button min-h-[48px]" disabled={loading}>
              Далее
            </button>
            <button type="button" className="game-button-secondary min-h-[48px]" disabled={listening} onClick={startListening}>
              {listening ? "Слушаю…" : "Назвать телефон"}
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
        className="inline-flex min-h-11 items-center text-xs text-[color:var(--ink-muted)] underline"
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
