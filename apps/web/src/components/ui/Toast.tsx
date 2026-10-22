"use client";

import { CircleCheck, X } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";

export type ToastApi = { show: (message: string) => void };
type ToastState = {
  message: string | null;
  api: ToastApi;
  dismiss: () => void;
};

export function useToastState(): ToastState {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const dismiss = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    setMessage(null);
  }, []);

  const show = useCallback((text: string) => {
    if (timer.current) clearTimeout(timer.current);
    setMessage(text);
    timer.current = setTimeout(() => setMessage(null), 4000);
  }, []);

  const api = useMemo(() => ({ show }), [show]);
  return { message, api, dismiss };
}

export function Toaster({ state }: { state: ToastState }) {
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 top-4 z-50 flex justify-center px-4"
    >
      {state.message && (
        <div className="pointer-events-auto flex w-full max-w-md items-center gap-3 rounded-xl bg-btn-on px-4 py-3 text-sm text-white shadow-lg">
          <CircleCheck
            aria-hidden
            className="size-5 shrink-0"
            strokeWidth={1.75}
          />
          <span className="flex-1">{state.message}</span>
          <button
            type="button"
            onClick={state.dismiss}
            aria-label="Dismiss"
            className="rounded p-0.5 opacity-80 hover:opacity-100"
          >
            <X className="size-4" />
          </button>
        </div>
      )}
    </div>
  );
}
