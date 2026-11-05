// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import catalog from "@/lib/api/mock/catalog.json";
import { MeasurementsForm } from "./MeasurementsForm";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const app = vi.hoisted(() => ({
  api: {
    getMeasurements: vi.fn(),
    saveProfile: vi.fn(),
    searchBrands: vi.fn(),
  },
  profile: null as unknown,
  profileLoaded: true,
  reloadProfile: vi.fn(),
}));
vi.mock("@/app/providers", () => ({ useApp: () => app }));

async function field(label: string): Promise<HTMLInputElement> {
  return (await screen.findByLabelText(label)) as HTMLInputElement;
}

function type(input: HTMLInputElement, value: string) {
  fireEvent.change(input, { target: { value } });
}

function save() {
  fireEvent.click(screen.getByRole("button", { name: /Save/ }));
}

beforeEach(() => {
  app.profile = null;
  app.api.getMeasurements.mockReset().mockResolvedValue(catalog);
  app.api.saveProfile.mockReset().mockResolvedValue(undefined);
  app.api.searchBrands.mockReset().mockResolvedValue([]);
  app.reloadProfile.mockReset().mockResolvedValue(undefined);
  push.mockReset();
});

afterEach(cleanup);

describe("MeasurementsForm", () => {
  it("builds its fields from the catalog, for measurements a rule uses", async () => {
    render(<MeasurementsForm />);
    for (const label of ["Chest / bust", "Waist", "Hips", "Shoulders", "Inseam"])
      expect(await field(label)).toBeTruthy();
    expect(screen.queryByLabelText(/^Height/)).toBeNull();
    expect(screen.queryByLabelText(/^Sleeve/)).toBeNull();
  });

  it("marks where each measurement is critical, from the catalog", async () => {
    render(<MeasurementsForm />);
    await field("Chest / bust");
    expect(screen.getAllByText(/Critical for Bottoms, Dresses/)).toHaveLength(2);
    expect(screen.getByText(/Secondary for Bottoms/)).toBeTruthy();
  });

  it("validates against the catalog's range and points at the unit", async () => {
    render(<MeasurementsForm />);
    type(await field("Waist"), "26");
    save();
    expect(await screen.findByText(/Waist looks off/)).toBeTruthy();
    expect(app.api.saveProfile).not.toHaveBeenCalled();
  });

  it("accepts the exact ends of the catalog's range", async () => {
    render(<MeasurementsForm />);
    type(await field("Waist"), "45");
    save();
    await waitFor(() => expect(app.api.saveProfile).toHaveBeenCalled());
  });

  it("needs at least one measurement", async () => {
    render(<MeasurementsForm />);
    await field("Waist");
    save();
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(app.api.saveProfile).not.toHaveBeenCalled();
  });

  it("saves Personal Fit without touching Quick Fit sizes", async () => {
    render(<MeasurementsForm />);
    type(await field("Waist"), "66");
    save();
    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
    const body = app.api.saveProfile.mock.calls[0][0];
    expect(body).toEqual({
      fit_mode: "personal_fit",
      unit: "cm",
      measurements: [
        { dimension: "waist", value: 66, basis: "body", note: null },
      ],
      brand_ids: [],
    });
    expect(body).not.toHaveProperty("quick_sizes");
  });

  it("converts values when the unit changes", async () => {
    render(<MeasurementsForm />);
    const waist = await field("Waist");
    type(waist, "66");
    fireEvent.click(screen.getByRole("radio", { name: "IN" }));
    expect(waist.value).toBe("26");
  });

  it("shows the garment note only for a garment measurement", async () => {
    render(<MeasurementsForm />);
    await field("Waist");
    expect(screen.queryByLabelText("Waist garment note")).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: "Waist: Garment" }));
    const note = await field("Waist garment note");
    type(note, "My blue jeans");
    type(await field("Waist"), "76");
    save();
    await waitFor(() => expect(app.api.saveProfile).toHaveBeenCalled());
    expect(app.api.saveProfile.mock.calls[0][0].measurements).toEqual([
      { dimension: "waist", value: 76, basis: "garment", note: "My blue jeans" },
    ]);
  });

  it("starts from saved measurements with their basis", async () => {
    app.profile = {
      unit: "cm",
      brands: [],
      updated_at: "2026-11-05T00:00:00Z",
      measurements: [
        { dimension: "hips", value: 98, basis: "garment", note: "Old jeans" },
      ],
    };
    render(<MeasurementsForm />);
    expect((await field("Hips")).value).toBe("98");
    expect((await field("Hips garment note")).value).toBe("Old jeans");
  });

  it("shows a server error and stays on the page", async () => {
    app.api.saveProfile.mockRejectedValue(new ApiError(422, "Unknown brand."));
    render(<MeasurementsForm />);
    type(await field("Waist"), "66");
    save();
    expect((await screen.findByRole("alert")).textContent).toBe("Unknown brand.");
    expect(push).not.toHaveBeenCalled();
  });

  it("explains when the catalog can't load", async () => {
    app.api.getMeasurements.mockRejectedValue(new Error("offline"));
    render(<MeasurementsForm />);
    expect((await screen.findByRole("alert")).textContent).toContain(
      "load the measurement list",
    );
  });
});
