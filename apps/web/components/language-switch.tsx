"use client";

import { useI18n } from "@/lib/i18n";

export function LanguageSwitch() {
  const { locale, setLocale, t } = useI18n();

  return (
    <div
      className="inline-flex gap-0 border border-[var(--border)] bg-[var(--surface)] p-0.5"
      role="group"
      aria-label="Language / Ngôn ngữ"
    >
      {(["vi", "en"] as const).map((code) => (
        <button
          key={code}
          type="button"
          onClick={() => setLocale(code)}
          className={
            locale === code
              ? "bg-[var(--accent-soft)] px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-[var(--accent)]"
              : "px-3 py-1.5 text-xs font-medium uppercase tracking-wider text-[var(--muted)] hover:text-[var(--fg)]"
          }
        >
          {t(`lang.${code}`)}
        </button>
      ))}
    </div>
  );
}
