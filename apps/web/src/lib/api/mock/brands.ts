/** Sample brand list for the prototype's preference chips. */
import type { Brand } from "../types";

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
    .replace(/['’]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, ""),
}));
