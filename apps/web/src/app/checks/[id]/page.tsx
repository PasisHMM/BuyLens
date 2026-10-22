import { Suspense } from "react";

import {
  CheckResultView,
  ResultSkeleton,
} from "@/components/results/CheckResultView";

// Not async: params resolve inside the Suspense boundary, so the page shell still prerenders.
export default function CheckPage({ params }: PageProps<"/checks/[id]">) {
  return (
    <Suspense fallback={<ResultSkeleton />}>
      {params.then(({ id }) => (
        <CheckResultView id={id} />
      ))}
    </Suspense>
  );
}
