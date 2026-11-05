// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, type Profile } from "@/lib/api";
import { CheckForm } from "./CheckForm";

const app = vi.hoisted(() => ({
  api: {
    mode: "mock" as "mock" | "live",
    saveProfile: vi.fn(),
    createCheck: vi.fn(),
  },
  profile: null as unknown,
  reloadProfile: vi.fn(),
}));
vi.mock("@/app/providers", () => ({ useApp: () => app }));

const SWEATER = "https://merchandizable.example/p/demo-relaxed-sweater";
const onStarted = vi.fn();

function savedProfile(over: Partial<Profile> = {}): Profile {
  return {
    unit: "cm",
    fit_mode: "quick_fit",
    size_system: "eu",
    quick_sizes: {},
    measurements: [],
    waist: null,
    inseam: null,
    hips: null,
    brands: [],
    updated_at: "2026-11-05T00:00:00Z",
    ...over,
  };
}

function radio(group: string, name: string): HTMLInputElement {
  return screen
    .getByRole("group", { name: group })
    .querySelector(`input[value="${name}"]`) as HTMLInputElement;
}

function setLink(url: string) {
  fireEvent.change(screen.getByLabelText("Product link"), {
    target: { value: url },
  });
}

function analyze() {
  fireEvent.click(screen.getByRole("button", { name: "Analyze product" }));
}

beforeEach(() => {
  window.localStorage.clear();
  app.api.mode = "mock";
  app.profile = null;
  app.api.saveProfile.mockReset().mockResolvedValue(undefined);
  app.api.createCheck.mockReset().mockResolvedValue({ id: "run-1" });
  app.reloadProfile.mockReset().mockResolvedValue(undefined);
  onStarted.mockReset();
});

afterEach(cleanup);

describe("shop selection", () => {
  it("shows Merchandizable enabled and selected by default", () => {
    render(<CheckForm onStarted={onStarted} />);
    const shop = screen.getByRole("radio", { name: /^Merchandizable/ });
    expect((shop as HTMLInputElement).disabled).toBe(false);
    expect((shop as HTMLInputElement).checked).toBe(true);
  });

  it.each(["Levi's", "Madewell", "DenimMarket", "AGOLDE", "Everlane", "Nordstrom"])(
    "keeps %s visible, disabled and marked as coming soon",
    (name) => {
      render(<CheckForm onStarted={onStarted} />);
      const shop = screen.getByRole("radio", {
        name: `${name} (coming soon)`,
      }) as HTMLInputElement;
      expect(shop.disabled).toBe(true);
    },
  );

  it("can't select a disabled shop by mouse or keyboard, and nothing is submitted", () => {
    render(<CheckForm onStarted={onStarted} />);
    const levis = screen.getByRole("radio", {
      name: "Levi's (coming soon)",
    }) as HTMLInputElement;
    fireEvent.click(levis);
    fireEvent.click(levis.closest("label")!);
    fireEvent.keyDown(levis, { key: " " });
    fireEvent.keyUp(levis, { key: " " });
    expect(levis.checked).toBe(false);
    expect(radio("Shop", "merchandizable").checked).toBe(true);
    expect(levis.tabIndex).toBe(-1);
    expect(app.api.saveProfile).not.toHaveBeenCalled();
    expect(app.api.createCheck).not.toHaveBeenCalled();
  });

  it("says Merchandizable is a demonstration shop", () => {
    render(<CheckForm onStarted={onStarted} />);
    expect(screen.getByText(/fictional demonstration shop/)).toBeTruthy();
  });

  it("sends the selected shop with the check", async () => {
    render(<CheckForm onStarted={onStarted} />);
    fireEvent.click(radio("Tops", "S"));
    setLink(SWEATER);
    analyze();
    await waitFor(() => expect(onStarted).toHaveBeenCalledWith("run-1", SWEATER));
    expect(app.api.createCheck).toHaveBeenCalledWith(SWEATER, {
      shopId: "merchandizable",
    });
  });

  it("stops a link from a coming-soon shop before any backend action", () => {
    render(<CheckForm onStarted={onStarted} />);
    fireEvent.click(radio("Tops", "S"));
    setLink("https://www.levi.com/p/501");
    analyze();
    expect(screen.getByRole("alert").textContent).toContain(
      "Levi's is coming soon",
    );
    expect(app.api.saveProfile).not.toHaveBeenCalled();
    expect(app.api.createCheck).not.toHaveBeenCalled();
  });

  it("stops a link from an unknown shop", () => {
    render(<CheckForm onStarted={onStarted} />);
    fireEvent.click(radio("Tops", "S"));
    setLink("https://elsewhere.test/p/1");
    analyze();
    expect(screen.getByRole("alert").textContent).toContain(
      "isn't from Merchandizable",
    );
    expect(app.api.createCheck).not.toHaveBeenCalled();
  });

  it("leaves shop choice to the backend's allow-list in live mode", async () => {
    app.api.mode = "live";
    render(<CheckForm onStarted={onStarted} />);
    expect(screen.queryByRole("group", { name: "Shop" })).toBeNull();
    fireEvent.click(radio("Tops", "S"));
    setLink("https://www.levi.com/p/501");
    analyze();
    await waitFor(() => expect(onStarted).toHaveBeenCalled());
    expect(app.api.createCheck).toHaveBeenCalledWith(
      "https://www.levi.com/p/501",
      {},
    );
  });

  it("fills the link from a sample product", () => {
    render(<CheckForm onStarted={onStarted} />);
    fireEvent.click(screen.getByRole("button", { name: "Demo Relaxed Sweater" }));
    expect(
      (screen.getByLabelText("Product link") as HTMLInputElement).value,
    ).toBe(SWEATER);
  });
});

describe("Quick Fit", () => {
  it("asks for a link first", () => {
    render(<CheckForm onStarted={onStarted} />);
    analyze();
    expect(screen.getByRole("alert").textContent).toBe(
      "Paste a product link first.",
    );
  });

  it("offers XS to XL for Tops and Bottoms, and nothing else", () => {
    render(<CheckForm onStarted={onStarted} />);
    for (const group of ["Tops", "Bottoms"]) {
      const inputs = screen
        .getByRole("group", { name: group })
        .querySelectorAll("input");
      expect([...inputs].map((i) => i.value)).toEqual([
        "XS",
        "S",
        "M",
        "L",
        "XL",
      ]);
    }
  });

  it("saves Tops S and Bottoms M separately, with no saved profile needed", async () => {
    render(<CheckForm onStarted={onStarted} />);
    fireEvent.click(radio("Tops", "S"));
    fireEvent.click(radio("Bottoms", "M"));
    setLink(SWEATER);
    analyze();
    await waitFor(() => expect(onStarted).toHaveBeenCalled());
    expect(app.api.saveProfile).toHaveBeenCalledWith({
      fit_mode: "quick_fit",
      size_system: "eu",
      quick_sizes: { tops: "S", bottoms: "M" },
    });
    expect(app.reloadProfile).toHaveBeenCalled();
  });

  it("asks for a size when none is chosen", () => {
    render(<CheckForm onStarted={onStarted} />);
    setLink(SWEATER);
    analyze();
    expect(screen.getByRole("alert").textContent).toContain("size");
    expect(app.api.createCheck).not.toHaveBeenCalled();
  });

  it("starts from saved sizes", () => {
    app.profile = savedProfile({ quick_sizes: { bottoms: "L" } });
    render(<CheckForm onStarted={onStarted} />);
    expect(radio("Bottoms", "L").checked).toBe(true);
  });

  it("shows the server's own message when it rejects the check", async () => {
    app.api.createCheck.mockRejectedValue(new ApiError(422, "No sample data."));
    render(<CheckForm onStarted={onStarted} />);
    fireEvent.click(radio("Tops", "S"));
    setLink(SWEATER);
    analyze();
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toBe("No sample data."),
    );
  });

  it("shows a save or server error", async () => {
    app.api.createCheck.mockRejectedValue(new Error("boom"));
    render(<CheckForm onStarted={onStarted} />);
    fireEvent.click(radio("Tops", "S"));
    setLink(SWEATER);
    analyze();
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain("Something went wrong"),
    );
    expect(onStarted).not.toHaveBeenCalled();
  });
});

describe("Personal Fit", () => {
  const measured = () =>
    savedProfile({
      fit_mode: "personal_fit",
      measurements: [
        { dimension: "waist", value: 66, basis: "body", note: null },
      ],
    });

  it("hides the size chips and shows the saved summary with Edit", () => {
    app.profile = measured();
    render(<CheckForm onStarted={onStarted} />);
    expect(screen.queryByRole("group", { name: "Tops" })).toBeNull();
    expect(screen.getByText(/Waist 66 cm/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Edit" }).getAttribute("href")).toBe(
      "/preferences",
    );
  });

  it("saves only the mode, so stored sizes and measurements stay", async () => {
    app.profile = measured();
    render(<CheckForm onStarted={onStarted} />);
    setLink(SWEATER);
    analyze();
    await waitFor(() => expect(onStarted).toHaveBeenCalled());
    expect(app.api.saveProfile).toHaveBeenCalledWith({
      fit_mode: "personal_fit",
    });
  });

  it("offers to add measurements when none are saved", () => {
    render(<CheckForm onStarted={onStarted} />);
    fireEvent.click(radio("Fit mode", "personal_fit"));
    expect(screen.getByText("No measurements saved yet.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Add" })).toBeTruthy();
  });

  it("asks for measurements without redirecting anywhere", () => {
    render(<CheckForm onStarted={onStarted} />);
    fireEvent.click(radio("Fit mode", "personal_fit"));
    setLink(SWEATER);
    analyze();
    expect(screen.getByRole("alert").textContent).toContain("Add your measurements");
    expect(app.api.saveProfile).not.toHaveBeenCalled();
  });

  it("offers sample measurements that run without saving anything", async () => {
    render(<CheckForm onStarted={onStarted} />);
    fireEvent.click(radio("Fit mode", "personal_fit"));
    fireEvent.click(radio("Measurements to compare", "on-the-s-m-line"));
    setLink(SWEATER);
    analyze();
    await waitFor(() => expect(onStarted).toHaveBeenCalled());
    expect(app.api.saveProfile).not.toHaveBeenCalled();
    expect(app.api.createCheck).toHaveBeenCalledWith(SWEATER, {
      shopId: "merchandizable",
      sampleId: "on-the-s-m-line",
    });
  });

  it("offers no sample measurements in live mode", () => {
    app.api.mode = "live";
    app.profile = measured();
    render(<CheckForm onStarted={onStarted} />);
    expect(screen.queryByRole("group", { name: "Measurements to compare" })).toBeNull();
  });

  it("keeps chosen sizes when switching to Personal Fit and back", () => {
    render(<CheckForm onStarted={onStarted} />);
    fireEvent.click(radio("Tops", "S"));
    fireEvent.click(radio("Fit mode", "personal_fit"));
    fireEvent.click(radio("Fit mode", "quick_fit"));
    expect(radio("Tops", "S").checked).toBe(true);
  });
});
