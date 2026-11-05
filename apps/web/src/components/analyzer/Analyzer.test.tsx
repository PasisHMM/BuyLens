// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Analyzer } from "./Analyzer";

const router = vi.hoisted(() => ({ replace: vi.fn(), push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const app = vi.hoisted(() => ({
  api: {
    mode: "mock",
    recentChecks: vi.fn(),
    saveProfile: vi.fn(),
    createCheck: vi.fn(),
    cancelCheck: vi.fn(),
  },
  profile: null as unknown,
  profileLoaded: true,
  reloadProfile: vi.fn(),
}));
vi.mock("@/app/providers", () => ({ useApp: () => app }));

// The dialog streams progress; here it only reports which run it shows and finishes on demand.
vi.mock("./ProgressDialog", () => ({
  ProgressDialog: (props: {
    runId: string | null;
    linkLabel: string;
    onComplete: (id: string) => void;
    onCancel: () => void;
  }) =>
    props.runId ? (
      <div>
        <p>Running {props.linkLabel}</p>
        <button onClick={() => props.onComplete(props.runId!)}>finish</button>
        <button onClick={props.onCancel}>cancel</button>
      </div>
    ) : null,
}));

const SWEATER = "https://merchandizable.example/p/demo-relaxed-sweater";

async function start() {
  render(<Analyzer />);
  fireEvent.change(screen.getByLabelText("Product link"), {
    target: { value: SWEATER },
  });
  fireEvent.click(
    screen
      .getByRole("group", { name: "Tops" })
      .querySelector('input[value="S"]')!,
  );
  fireEvent.click(screen.getByRole("button", { name: "Analyze product" }));
  await screen.findByText(/Running/);
}

beforeEach(() => {
  window.localStorage.clear();
  app.profile = null;
  app.profileLoaded = true;
  app.api.recentChecks.mockReset().mockResolvedValue([]);
  app.api.saveProfile.mockReset().mockResolvedValue(undefined);
  app.api.createCheck.mockReset().mockResolvedValue({ id: "run-1" });
  app.api.cancelCheck.mockReset().mockResolvedValue(undefined);
  app.reloadProfile.mockReset().mockResolvedValue(undefined);
  router.replace.mockReset();
  router.push.mockReset();
});

afterEach(cleanup);

describe("Analyzer", () => {
  it("lets a first-time visitor stay on the homepage: no forced redirect", async () => {
    render(<Analyzer />);
    expect(
      screen.getByRole("button", { name: "Analyze product" }),
    ).toBeTruthy();
    await waitFor(() => expect(app.api.recentChecks).toHaveBeenCalled());
    expect(router.replace).not.toHaveBeenCalled();
    expect(router.push).not.toHaveBeenCalled();
  });

  it("waits for the saved profile before showing the form", () => {
    app.profileLoaded = false;
    render(<Analyzer />);
    expect(screen.queryByLabelText("Product link")).toBeNull();
  });

  it("shows progress with a readable link, then opens the result", async () => {
    await start();
    expect(
      screen.getByText(
        "Running merchandizable.example / demo-relaxed-sweater",
      ),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "finish" }));
    expect(router.push).toHaveBeenCalledWith("/checks/run-1");
  });

  it("cancels a running check", async () => {
    await start();
    fireEvent.click(screen.getByRole("button", { name: "cancel" }));
    expect(app.api.cancelCheck).toHaveBeenCalledWith("run-1");
    expect(screen.queryByText(/Running/)).toBeNull();
  });

  it("links the latest check", async () => {
    app.api.recentChecks.mockResolvedValue([
      {
        id: "run-9",
        status: "done",
        created_at: "2026-11-05T00:00:00Z",
        product_name: "Demo Relaxed Sweater",
        image_url: null,
        verdict: null,
        selected_size: "M",
        total_cents: 4900,
        currency: "EUR",
      },
    ]);
    render(<Analyzer />);
    const card = await screen.findByRole("link", { name: /A recent check/ });
    expect(card.getAttribute("href")).toBe("/checks/run-9");
    expect(card.textContent).toContain("€49.00");
  });
});
