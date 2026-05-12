"use client";

import { Toaster } from "sonner";

import { I18nProvider } from "@/lib/i18n";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <I18nProvider>
      {children}
      <Toaster position="top-center" richColors closeButton />
    </I18nProvider>
  );
}
