"use client";

import dynamic from "next/dynamic";

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

const HomeWorkspace = dynamic(
  () =>
    import("@/components/home-workspace").then((mod) => ({
      default: mod.HomeWorkspace,
    })),
  { ssr: false, loading: WorkspaceFallback },
);

export function HomeWorkspaceLoader() {
  return <HomeWorkspace />;
}
