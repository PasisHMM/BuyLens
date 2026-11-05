// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SiteHeader } from "./SiteHeader";

const nav = vi.hoisted(() => ({ pathname: "/" }));
vi.mock("next/navigation", () => ({ usePathname: () => nav.pathname }));

const app = vi.hoisted(() => ({
  api: { mode: "mock" },
  profile: null as unknown,
  profileLoaded: true,
}));
vi.mock("@/app/providers", () => ({ useApp: () => app }));

beforeEach(() => {
  nav.pathname = "/";
  app.profile = null;
  app.profileLoaded = true;
});

afterEach(cleanup);

describe("SiteHeader", () => {
  it("invites a first-time visitor to add their fit", () => {
    render(<SiteHeader />);
    expect(screen.getByRole("link", { name: "Add your fit" }).textContent).toBe(
      "Add your fit",
    );
  });

  it("shows the Quick Fit sizes", () => {
    app.profile = {
      fit_mode: "quick_fit",
      quick_sizes: { tops: "S", bottoms: "M" },
    };
    render(<SiteHeader />);
    const pill = screen.getByRole("link", { name: "Edit your fit" });
    expect(pill.textContent).toBe("Quick Fit · Tops S · Bottoms M");
    expect(pill.getAttribute("href")).toBe("/preferences");
  });

  it("marks sample data in the prototype", () => {
    render(<SiteHeader />);
    expect(screen.getByText("Sample data")).toBeTruthy();
  });

  it("names the page instead of the pill on the preferences page", () => {
    nav.pathname = "/preferences";
    render(<SiteHeader />);
    expect(screen.getByText("Your preferences")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Add your fit" })).toBeNull();
  });
});
