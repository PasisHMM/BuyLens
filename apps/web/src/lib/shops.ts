/**
 * Shops on the homepage. To re-enable a shop later, change its status here; components read this list.
 * Only Merchandizable is active: a fictional demonstration shop, not a supported retailer.
 */
import { hostOf } from "./format";

export type Shop = {
  id: string;
  name: string;
  domains: string[];
  status: "active" | "coming_soon";
  demo: boolean;
};

export const SHOPS: Shop[] = [
  {
    id: "merchandizable",
    name: "Merchandizable",
    domains: ["merchandizable.example", "merchandizable.sumupstore.com"],
    status: "active",
    demo: true,
  },
  ...(
    [
      ["levis", "Levi's", "levi.com"],
      ["madewell", "Madewell", "madewell.com"],
      ["denimmarket", "DenimMarket", "denimmarket.example"],
      ["agolde", "AGOLDE", "agolde.com"],
      ["everlane", "Everlane", "everlane.com"],
      ["nordstrom", "Nordstrom", "nordstrom.com"],
    ] as const
  ).map(
    ([id, name, domain]): Shop => ({
      id,
      name,
      domains: [domain],
      status: "coming_soon",
      demo: false,
    }),
  ),
];

export const DEFAULT_SHOP = SHOPS.find((s) => s.status === "active")!;

const STORAGE_KEY = "bl:v2:shop";

export function shopForUrl(url: string): Shop | undefined {
  const host = hostOf(url);
  return SHOPS.find((s) =>
    s.domains.some((d) => host === d || host.endsWith(`.${d}`)),
  );
}

/** The remembered shop. An unavailable or unknown value falls back to the default. */
export function readSelectedShop(): Shop {
  try {
    const id = window.localStorage.getItem(STORAGE_KEY);
    return (
      SHOPS.find((s) => s.id === id && s.status === "active") ?? DEFAULT_SHOP
    );
  } catch {
    return DEFAULT_SHOP; // no browser storage: server rendering or private mode
  }
}

export function writeSelectedShop(id: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, id);
  } catch {
    // The selection still holds for this page view.
  }
}
