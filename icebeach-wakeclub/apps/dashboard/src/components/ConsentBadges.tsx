type ConsentBadgesProps = {
  consentFace?: boolean;
  consentVoice?: boolean;
  compact?: boolean;
};

export function ConsentBadges({ consentFace = false, consentVoice = false, compact = false }: ConsentBadgesProps): JSX.Element {
  const size = compact ? "text-[10px] px-2 py-0.5" : "text-xs px-2 py-1";

  return (
    <div className="flex flex-wrap gap-1.5">
      <span className={`rounded-full border ${consentFace ? "border-emerald-400/40 bg-emerald-950/40 text-emerald-100" : "border-slate-700 bg-slate-900/80 text-slate-400"} ${size}`}>
        Face {consentFace ? "OK" : "—"}
      </span>
      <span className={`rounded-full border ${consentVoice ? "border-cyan-400/40 bg-cyan-950/40 text-cyan-100" : "border-slate-700 bg-slate-900/80 text-slate-400"} ${size}`}>
        Voice {consentVoice ? "OK" : "—"}
      </span>
    </div>
  );
}
