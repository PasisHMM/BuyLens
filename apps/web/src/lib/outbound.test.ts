import { describe, expect, it } from "vitest";

import { parseOutboundUrl, resolveOutboundLink } from "./outbound";

const OFFER = {
  listingId: "listing-1",
  retailerId: "merchandizable.sumupstore.com",
  retailerName: "Merchandizable",
};

describe("parseOutboundUrl", () => {
  it.each([
    "https://merchandizable.sumupstore.com/produkt/levis-baggy-jeans",
    "http://shop.test/p/1?size=M#reviews",
    "HTTPS://SHOP.TEST/p/1",
  ])("accepts the web link %s", (url) => {
    expect(parseOutboundUrl(url)).not.toBeNull();
  });

  it("keeps the exact page, including query and fragment", () => {
    expect(parseOutboundUrl("https://shop.test/p/1?size=M#reviews")?.href).toBe(
      "https://shop.test/p/1?size=M#reviews",
    );
  });

  it.each([
    "javascript:alert(1)",
    "JaVaScRiPt:alert(1)",
    " javascript:alert(1)",
    "java\nscript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "file:///etc/passwd",
    "ftp://shop.test/p",
    "mailto:a@shop.test",
    "//shop.test/p",
    "/p/1",
    "shop.test/p/1",
    "not a url",
    "https://",
    "https://localhost/p",
    "https://user:secret@shop.test/p",
    "https://shop.test@evil.test/p",
    "",
    "   ",
  ])("rejects %j", (url) => {
    expect(parseOutboundUrl(url)).toBeNull();
  });

  it.each([null, undefined, 42, {}, ["https://shop.test/p"]])(
    "rejects the non-string %j",
    (value) => {
      expect(parseOutboundUrl(value)).toBeNull();
    },
  );
});

describe("resolveOutboundLink", () => {
  it("resolves to the offer's own page and names its real host", () => {
    expect(
      resolveOutboundLink({
        ...OFFER,
        url: "https://www.shop.test/p/1?utm_source=store",
      }),
    ).toEqual({
      href: "https://www.shop.test/p/1?utm_source=store",
      host: "shop.test",
    });
  });

  it("adds nothing to the link: no tracking, no redirect", () => {
    const url = "https://shop.test/p/1";
    expect(resolveOutboundLink({ ...OFFER, url })?.href).toBe(url);
  });

  it.each([null, undefined, "javascript:alert(1)"])(
    "has no link for the destination %j",
    (url) => {
      expect(resolveOutboundLink({ ...OFFER, url })).toBeNull();
    },
  );
});
