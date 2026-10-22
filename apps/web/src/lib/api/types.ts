/** App-facing API types. Response shapes come from the backend's OpenAPI contract (schema.d.ts). */
import type { components } from "./schema";

type Schemas = components["schemas"];

export type Unit = "in" | "cm";
export type Brand = Schemas["Brand"];
export type Profile = Schemas["ProfileOut"];
export type ProfileIn = Schemas["ProfileIn"];
export type CheckResult = Schemas["CheckResult"];
export type CheckSummary = Schemas["CheckSummary"];
export type OptionOut = Schemas["OptionOut"];
export type PriceCheck = Schemas["PriceCheck"];
export type FitCheck = Schemas["FitCheck"];
export type FitRow = Schemas["FitRow"];
export type SellerRisk = Schemas["SellerRisk"];
export type Verdict = "BUY" | "CONSIDER" | "SKIP";

/** Server-Sent Event payloads (not part of OpenAPI). Mirrors app/pipeline/progress.py. */
export type StepId = "product" | "prices" | "fit" | "seller";
export type ProgressEvent = {
  type: "step" | "complete" | "failed" | "cancelled";
  step?: StepId;
  status?: "active" | "done";
  index?: number;
  total?: number;
  label?: string;
  detail?: string;
  message?: string;
};

/** Post-purchase feedback (backend endpoint arrives in Phase 4). */
export type FitOutcome = "too_tight" | "fits_well" | "too_loose";
export type HeldBackReason = "price" | "fit_concern" | "seller_risk";
export type Feedback =
  | {
      purchased: true;
      option_rank: number;
      fit: FitOutcome;
      fit_dimension: string | null;
    }
  | { purchased: false; option_rank: number; reasons: HeldBackReason[] };

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export interface ApiClient {
  mode: "mock" | "live";
  getProfile(): Promise<Profile | null>;
  saveProfile(profile: ProfileIn): Promise<void>;
  searchBrands(query?: string, limit?: number): Promise<Brand[]>;
  createCheck(url: string): Promise<{ id: string }>;
  /** Streams progress for a check; returns an unsubscribe function. */
  subscribe(id: string, onEvent: (event: ProgressEvent) => void): () => void;
  cancelCheck(id: string): Promise<void>;
  getCheck(id: string): Promise<CheckResult | null>;
  recentChecks(limit?: number): Promise<CheckSummary[]>;
  getFeedback(id: string): Promise<Feedback | null>;
  submitFeedback(id: string, feedback: Feedback): Promise<void>;
}
