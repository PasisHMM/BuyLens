// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ViewAtRetailer } from "./ViewAtRetailer";

const OFFER = {
  listingId: "levis-baggy-jeans",
  retailerId: "merchandizable",
  retailerName: "Merchandizable",
};
const LABEL = "View product at retailer";

afterEach(cleanup);

describe("ViewAtRetailer", () => {
  it("opens the exact page in a new tab as a normal external link", () => {
    const url = "https://merchandizable.sumupstore.com/produkt/levis-baggy-jeans";
    render(<ViewAtRetailer offer={{ ...OFFER, url }} />);
    const link = screen.getByRole("link", { name: new RegExp(LABEL) });
    expect(link.getAttribute("href")).toBe(url);
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("shows the destination retailer and its real host", () => {
    render(
      <ViewAtRetailer offer={{ ...OFFER, url: "https://www.shop.test/p/1" }} />,
    );
    expect(screen.getByText(/Merchandizable/).textContent).toContain("shop.test");
  });

  it.each([null, undefined, "javascript:alert(1)", "not a url", "ftp://shop.test/p"])(
    "offers no link for the destination %j, and explains why",
    (url) => {
      render(<ViewAtRetailer offer={{ ...OFFER, url }} />);
      expect(screen.queryByRole("link")).toBeNull();
      const button = screen.getByRole("button", {
        name: LABEL,
      }) as HTMLButtonElement;
      expect(button.disabled).toBe(true);
      expect(screen.getByText(/no product page/i)).toBeTruthy();
    },
  );

  it("adds no tracking, redirect or click handling", () => {
    const url = "https://shop.test/p/1";
    render(<ViewAtRetailer offer={{ ...OFFER, url }} />);
    const link = screen.getByRole("link", { name: new RegExp(LABEL) });
    expect(link.getAttribute("href")).toBe(url);
    expect(link.getAttribute("ping")).toBeNull();
    expect(link.getAttribute("onclick")).toBeNull();
    expect(document.cookie).toBe("");
  });
});
