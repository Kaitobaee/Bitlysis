import { Suspense } from "react";

import { HomeWorkspace } from "@/components/home-workspace";

function WorkspaceFallback() {
  return (
    <div className="swiss-page">
      <div className="swiss-container py-24">
        <div className="h-10 w-48 animate-pulse bg-(--skeleton)" />
        <div className="mt-8 h-32 w-full max-w-xl animate-pulse bg-(--skeleton)" />
      </div>
    </div>
  );
}

export default function WorkspacePage() {
  return (
    <Suspense fallback={<WorkspaceFallback />}>
      <HomeWorkspace />
    </Suspense>
  );
}