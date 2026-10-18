/** Иконки снаряжения для «Как в прошлый раз» (декоративные, aria-hidden). */

type IconProps = { className?: string };

export function WetsuitIcon({ className = "h-5 w-5" }: IconProps): JSX.Element {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d="M8 3h8l1 4-2 1v13H9V8L7 7z" />
      <path d="M12 3v5" />
    </svg>
  );
}

export function BoardIcon({ className = "h-5 w-5" }: IconProps): JSX.Element {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true" focusable="false">
      <ellipse cx="12" cy="12" rx="5" ry="10" />
      <path d="M12 6v12" />
    </svg>
  );
}

export function CupIcon({ className = "h-5 w-5" }: IconProps): JSX.Element {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d="M5 9h11v5a5 5 0 0 1-5 5h-1a5 5 0 0 1-5-5z" />
      <path d="M16 10h2a2 2 0 0 1 0 4h-2" />
      <path d="M9 3c0 2 2 2 2 4M12 3c0 2 2 2 2 4" />
    </svg>
  );
}
