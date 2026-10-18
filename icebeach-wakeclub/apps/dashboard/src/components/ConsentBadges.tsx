type ConsentBadgesProps = {
  consentFace?: boolean;
  consentVoice?: boolean;
  compact?: boolean;
};

export function ConsentBadges({ consentFace = false, consentVoice = false, compact = false }: ConsentBadgesProps): JSX.Element {
  const size = compact ? "text-[10px] px-2 py-0.5" : "text-xs px-2 py-1";

  return (
    <div className="flex flex-wrap gap-1.5">
      <span
        title="Согласие на распознавание лица"
        className={`rounded-full border ${consentFace ? "border-emerald-500/40 bg-emerald-50 text-emerald-800" : "border-stone-300 bg-stone-50 text-stone-600"} ${size}`}
      >
        Лицо: {consentFace ? "да" : "нет"}
      </span>
      <span
        title="Согласие на голосовую отметку"
        className={`rounded-full border ${consentVoice ? "border-teal-500/40 bg-teal-50 text-teal-800" : "border-stone-300 bg-stone-50 text-stone-600"} ${size}`}
      >
        Голос: {consentVoice ? "да" : "нет"}
      </span>
    </div>
  );
}
