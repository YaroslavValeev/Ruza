export type AuthFailureStatus = 401 | 403;

const AUTH_FAILURE_EVENT = "icebeach:auth-failure";

type AuthFailureDetail = {
  status: AuthFailureStatus;
};

export function emitAuthFailure(status: AuthFailureStatus): void {
  if (typeof window === "undefined") {
    return;
  }

  window.dispatchEvent(new CustomEvent<AuthFailureDetail>(AUTH_FAILURE_EVENT, { detail: { status } }));
}

export function subscribeAuthFailure(handler: (status: AuthFailureStatus) => void): () => void {
  if (typeof window === "undefined") {
    return () => undefined;
  }

  const listener = (event: Event) => {
    const customEvent = event as CustomEvent<AuthFailureDetail>;
    const status = customEvent.detail?.status;
    if (status === 401 || status === 403) {
      handler(status);
    }
  };

  window.addEventListener(AUTH_FAILURE_EVENT, listener as EventListener);

  return () => {
    window.removeEventListener(AUTH_FAILURE_EVENT, listener as EventListener);
  };
}
