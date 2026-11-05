/**
 * Links that leave Buy Lens. Every outbound link goes through resolveOutboundLink, so this is the one
 * place to change if outbound behaviour is ever extended. It reads only the offer, never the analysis.
 *
 * Today it returns the offer's own page unchanged: no affiliate links, redirects, cookies or click
 * recording. See docs/redesign-plan.md §11.5.
 */

/** A displayed offer's identity. Reuses existing fields: listing_id, seller.domain, url. */
export type Offer = {
  listingId: string | null;
  retailerId: string;
  retailerName: string;
  url: string | null | undefined;
};

export type OutboundLink = { href: string; host: string };

/** The URL if it's a safe web link to a named host; otherwise null. */
export function parseOutboundUrl(raw: unknown): URL | null {
  if (typeof raw !== "string") return null;
  // The URL parser silently drops surrounding spaces and inner newlines, which hides odd input.
  if (raw !== raw.trim() || /[\u0000-\u001f]/.test(raw)) return null;
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    return null;
  }
  if (url.protocol !== "https:" && url.protocol !== "http:") return null;
  if (url.username || url.password) return null; // "https://shop.test@evil.test" hides the real host
  return url.hostname.includes(".") ? url : null;
}

export function resolveOutboundLink(offer: Offer): OutboundLink | null {
  const url = parseOutboundUrl(offer.url);
  if (!url) return null;
  return { href: url.href, host: url.hostname.replace(/^www\./, "") };
}
