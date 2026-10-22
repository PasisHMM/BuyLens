import type { Metadata } from "next";

import { MeasurementsForm } from "@/components/preferences/MeasurementsForm";

export const metadata: Metadata = { title: "Your measurements · Buy Lens" };

export default function PreferencesPage() {
  return <MeasurementsForm />;
}
