/**
 * SAMPLE DATA for the clickable prototype. Prices, ratings and policies are illustrative,
 * not real store data. The CONSIDER case mirrors the design screens; the brands
 * "Rivet & Row" and the store "DenimMarket" are fictional.
 */
import type { Brand } from "../types";
import type { Scenario } from "./engine";

const levisChart = Array.from({ length: 9 }, (_, i) => 24 + i).map((n) => ({
  label: String(n),
  waist: n + 1,
}));

export const SCENARIOS: Record<string, Scenario> = {
  consider: {
    key: "consider",
    product: {
      name: "501® Original Cropped Jeans",
      brand: "Levi's",
      category: "denim",
      image_url: null,
      attributes: { wash: "Medium wash", stretch: false, fit: "straight" },
    },
    source: "levi.com · Women's original straight fit",
    chart: { basis: "garment", rows: levisChart, lengths: [28, 30, 32] }, // no hip measurement published
    stretch: false,
    fabric: "100% cotton",
    marketAvgCents: 10800,
    comparableCount: 8,
    options: [
      {
        seller: { name: "Levi's official store", domain: "levi.com" },
        url: "https://www.levi.com/",
        isOfficial: true,
        listingCents: 9800,
        shippingCents: 0,
        trust: 4.8,
        reviewRating: 4.6,
        reviewCount: 1284,
        returns: {
          verified: true,
          window_days: 30,
          free: true,
          title: "30-day free returns",
          details:
            "Unworn, tags attached. Return by mail or in store; no restocking fee.",
        },
        highlights: ["Classic straight leg", "Softens after a few wears"],
        redFlags: [],
        summary: "Best balance of price, seller trust, and free returns.",
      },
      {
        seller: { name: "Nordstrom", domain: "nordstrom.com" },
        url: "https://www.nordstrom.com/",
        isOfficial: false,
        listingCents: 10800,
        shippingCents: 0,
        trust: 4.6,
        reviewRating: 4.5,
        reviewCount: 412,
        returns: {
          verified: true,
          window_days: 30,
          free: true,
          title: "Free returns",
          details: "Free returns by mail or in store.",
        },
        highlights: [],
        redFlags: [],
        summary: "Free returns",
      },
      {
        seller: { name: "DenimMarket", domain: "denimmarket.example" },
        url: "https://denimmarket.example/",
        isOfficial: false,
        listingCents: 9300,
        shippingCents: 400,
        trust: 3.9,
        reviewRating: 4.1,
        reviewCount: 212,
        returns: {
          verified: true,
          window_days: 14,
          free: false,
          title: "14-day returns, buyer pays shipping",
          details: "Return shipping is deducted from your refund.",
        },
        highlights: [],
        redFlags: [],
        summary: "Buyer pays returns",
      },
    ],
  },
  buy: {
    key: "buy",
    product: {
      name: "High-Rise Straight Jean",
      brand: "Madewell",
      category: "denim",
      image_url: null,
      attributes: { wash: "Dark wash", stretch: true, fit: "straight" },
    },
    source: "madewell.com · High-rise, straight leg",
    chart: {
      basis: "garment",
      rows: Array.from({ length: 10 }, (_, i) => 23 + i).map((n) => ({
        label: String(n),
        waist: n + 0.5,
        hips: n + 11,
      })),
      lengths: [28, 30, 32],
    },
    stretch: true,
    fabric: "92% cotton, 6% polyester, 2% elastane",
    marketAvgCents: 13800,
    comparableCount: 7,
    options: [
      {
        seller: { name: "Madewell official store", domain: "madewell.com" },
        url: "https://www.madewell.com/",
        isOfficial: true,
        listingCents: 12800,
        shippingCents: 0,
        trust: 4.7,
        reviewRating: 4.5,
        reviewCount: 2140,
        returns: {
          verified: true,
          window_days: 30,
          free: true,
          title: "30-day free returns",
          details: "Unworn with tags; free return shipping.",
        },
        highlights: ["Holds its shape", "True to size"],
        redFlags: [],
      },
      {
        seller: { name: "Nordstrom", domain: "nordstrom.com" },
        url: "https://www.nordstrom.com/",
        isOfficial: false,
        listingCents: 13800,
        shippingCents: 0,
        trust: 4.6,
        reviewRating: 4.4,
        reviewCount: 860,
        returns: {
          verified: true,
          window_days: 30,
          free: true,
          title: "Free returns",
          details: "Free returns by mail or in store.",
        },
        highlights: [],
        redFlags: [],
      },
    ],
  },
  skip: {
    key: "skip",
    product: {
      name: "Distressed Skinny Jean",
      brand: "Rivet & Row",
      category: "denim",
      image_url: null,
      attributes: { wash: "Light wash", stretch: true, fit: "skinny" },
    },
    source: "denimmarket.example · Marketplace seller",
    chart: {
      basis: "body",
      rows: Array.from({ length: 10 }, (_, i) => 23 + i).map((n) => ({
        label: String(n),
        waist: n,
        hips: n + 10,
      })),
      lengths: [28, 30, 32],
    },
    stretch: true,
    fabric: "79% cotton, 19% polyester, 2% elastane",
    marketAvgCents: 5200,
    comparableCount: 5,
    options: [
      {
        seller: {
          name: "DenimMarket seller: Rivet & Row Outlet",
          domain: "denimmarket.example",
        },
        url: "https://denimmarket.example/",
        isOfficial: false,
        listingCents: 3900,
        shippingCents: 800,
        trust: 2.7,
        reviewRating: 3.1,
        reviewCount: 340,
        returns: {
          verified: true,
          window_days: 14,
          free: false,
          title: "14-day returns, buyer pays shipping",
          details: "Returns accepted only in original packaging.",
        },
        highlights: [],
        redFlags: [
          "Seams split after a few washes",
          "Arrived in the wrong size",
        ],
      },
    ],
  },
  blocked: {
    key: "blocked",
    product: {
      name: "",
      brand: null,
      category: null,
      image_url: null,
      attributes: {},
    },
    source: "",
    chart: { basis: "body", rows: [], lengths: [] },
    stretch: false,
    fabric: "",
    marketAvgCents: null,
    comparableCount: 0,
    options: [],
    failure: {
      atStep: "product",
      message: "The store blocked our check. Try again later.",
    },
  },
};

/** Which sample a pasted link opens. Only these domains are "supported" in the prototype. */
export const MOCK_STORES: Record<string, keyof typeof SCENARIOS> = {
  "levi.com": "consider",
  "madewell.com": "buy",
  "denimmarket.example": "skip",
  "agolde.com": "blocked",
};

/** Stores in the real allow-list that have no sample data yet. */
export const KNOWN_WITHOUT_SAMPLE = ["everlane.com", "nordstrom.com"];

export const SAMPLE_LINKS: {
  label: string;
  verdict: "CONSIDER" | "BUY" | "SKIP" | null;
  url: string;
}[] = [
  {
    label: "Consider",
    verdict: "CONSIDER",
    url: "https://www.levi.com/US/en_US/p/501-original-cropped-jeans",
  },
  {
    label: "Buy",
    verdict: "BUY",
    url: "https://www.madewell.com/p/high-rise-straight-jean",
  },
  {
    label: "Skip",
    verdict: "SKIP",
    url: "https://denimmarket.example/p/distressed-skinny-jean",
  },
  {
    label: "Store blocks us",
    verdict: null,
    url: "https://www.agolde.com/products/90s-pinch-waist",
  },
];

const BRAND_NAMES = [
  "Levi's", "Everlane", "Madewell", "AGOLDE", "Wrangler", "Lee", "Gap", "Abercrombie & Fitch", "J.Crew", "Uniqlo",
  "Zara", "H&M", "Mango", "Citizens of Humanity", "MOTHER", "FRAME", "RE/DONE", "Good American", "PAIGE",
  "7 For All Mankind", "Ralph Lauren", "Banana Republic", "Old Navy", "American Eagle", "Free People",
  "Reformation", "Hudson", "DL1961", "Nudie Jeans", "G-Star RAW",
]; // prettier-ignore

export const BRANDS: Brand[] = BRAND_NAMES.map((name, i) => ({
  id: `00000000-0000-4000-8000-${String(i + 1).padStart(12, "0")}`,
  name,
  slug: name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, ""),
}));
