"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Check, CircleAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { useApp } from "@/app/providers";
import { Button, cx } from "@/components/ui/primitives";
import type { ProgressEvent, StepId } from "@/lib/api";

const STEPS: { id: StepId; active: string; done: string; pending: string }[] = [
  {
    id: "product",
    active: "Finding product details",
    done: "Product details found",
    pending: "Name, price and size chart",
  },
  {
    id: "prices",
    active: "Comparing prices",
    done: "Prices compared",
    pending: "Totals across the stores we check",
  },
  {
    id: "fit",
    active: "Checking your fit",
    done: "Fit checked",
    pending: "Waist, inseam, and available size data",
  },
  {
    id: "seller",
    active: "Reviewing seller risk",
    done: "Seller risk reviewed",
    pending: "Reviews and return policy up next",
  },
];
const LABEL: Record<StepId, string> = {
  product: "Finding product details",
  prices: "Comparing prices",
  fit: "Comparing your measurements",
  seller: "Reviewing seller risk",
};

type StepState = { status: "pending" | "active" | "done"; detail?: string };
const INITIAL: Record<StepId, StepState> = {
  product: { status: "pending" },
  prices: { status: "pending" },
  fit: { status: "pending" },
  seller: { status: "pending" },
};

export function ProgressDialog({
  runId,
  linkLabel,
  onCancel,
  onComplete,
  onClose,
}: {
  /** Remount with `key={runId}` so each check starts with fresh state. */
  runId: string | null;
  linkLabel: string;
  onCancel: () => void;
  onComplete: (id: string) => void;
  onClose: () => void;
}) {
  const { api } = useApp();
  const [steps, setSteps] = useState(INITIAL);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    return api.subscribe(runId, (e: ProgressEvent) => {
      if (e.type === "step" && e.step) {
        const step = e.step;
        setSteps((s) => ({
          ...s,
          [step]: {
            status: e.status === "done" ? "done" : "active",
            detail: e.detail,
          },
        }));
      } else if (e.type === "complete") onComplete(runId);
      else if (e.type === "failed")
        setFailure(e.message ?? "Something went wrong. Please try again.");
      else if (e.type === "cancelled") onClose();
    });
  }, [runId, api, onComplete, onClose]);

  const doneCount = STEPS.filter((s) => steps[s.id].status === "done").length;
  const active = STEPS.find((s) => steps[s.id].status === "active");
  const current = active ?? STEPS[Math.min(doneCount, 3)];
  const progress = (doneCount + (active ? 0.5 : 0)) / STEPS.length;
  const productLine =
    steps.product.status === "done" ? steps.product.detail : linkLabel;

  return (
    <Dialog.Root
      open={runId !== null}
      onOpenChange={(open) => !open && (failure ? onClose() : onCancel())}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-[#19181d]/35" />
        <Dialog.Content
          onInteractOutside={(e) => e.preventDefault()}
          className="fixed top-[12vh] left-1/2 z-50 w-[calc(100%-32px)] max-w-[520px] -translate-x-1/2 rounded-2xl bg-bg p-6 shadow-2xl sm:top-[20vh] sm:p-9"
        >
          <div className="flex items-center justify-between">
            <p className="eyebrow text-muted">
              {failure ? "Check stopped" : "Check in progress"}
            </p>
            {!failure && (
              <button
                type="button"
                onClick={onCancel}
                className="text-sm text-muted hover:text-ink"
              >
                Cancel
              </button>
            )}
          </div>

          {failure ? (
            <>
              <Dialog.Title className="mt-6 font-serif text-[30px] leading-tight sm:text-[34px]">
                We couldn’t finish this check.
              </Dialog.Title>
              <Dialog.Description className="mt-4 flex items-start gap-2 text-sm text-skip">
                <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />{" "}
                {failure}
              </Dialog.Description>
              <Button className="mt-8 w-full" onClick={onClose}>
                Try another link
              </Button>
            </>
          ) : (
            <>
              <Dialog.Title className="mt-6 font-serif text-[30px] leading-tight sm:text-[34px]">
                Reading between the product lines.
              </Dialog.Title>
              <Dialog.Description className="mt-4 truncate text-sm text-muted">
                {productLine}
              </Dialog.Description>

              <div className="mt-7 h-[3px] w-full bg-line" aria-hidden>
                <div
                  className="h-full bg-ink transition-[width] duration-700"
                  style={{ width: `${progress * 100}%` }}
                />
              </div>
              <p className="mt-2.5 text-xs text-muted" aria-live="polite">
                Step {STEPS.indexOf(current) + 1} of 4 · {LABEL[current.id]}
              </p>

              <ol className="mt-6 space-y-5">
                {STEPS.map((s) => {
                  const st = steps[s.id];
                  return (
                    <li key={s.id} className="flex gap-3">
                      <StepIcon status={st.status} />
                      <div>
                        <p
                          className={cx(
                            "text-sm",
                            st.status === "pending" && "text-faint",
                          )}
                        >
                          {st.status === "done" ? s.done : s.active}
                        </p>
                        <p
                          className={cx(
                            "mt-0.5 text-xs",
                            st.status === "pending"
                              ? "text-faint"
                              : "text-muted",
                          )}
                        >
                          {st.status === "done" && st.detail
                            ? st.detail
                            : s.pending}
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ol>
              <p className="mt-7 text-xs text-muted">
                Usually ready in about 20 seconds. Stay on this page.
              </p>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function StepIcon({ status }: { status: StepState["status"] }) {
  if (status === "done")
    return (
      <Check
        className="mt-0.5 size-4 shrink-0"
        strokeWidth={2}
        aria-label="Done"
      />
    );
  if (status === "active")
    return (
      <span
        className="mt-1 flex size-4 shrink-0 items-center justify-center"
        aria-label="In progress"
      >
        <span className="size-2.5 animate-[spin-slow_1.2s_linear_infinite] rounded-full border border-ink border-t-transparent" />
      </span>
    );
  return (
    <span
      className="mt-0.5 size-4 shrink-0 rounded-full border border-faint"
      aria-label="Pending"
    />
  );
}
