"use client";

import { useCallback, useState } from "react";

import { useI18n } from "@/lib/i18n";

type Props = {
  disabled?: boolean;
  onFile: (file: File) => void;
};

export function UploadZone({ disabled, onFile }: Props) {
  const { t } = useI18n();
  const [over, setOver] = useState(false);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setOver(false);
      if (disabled) return;
      const f = e.dataTransfer.files[0];
      if (f) onFile(f);
    },
    [disabled, onFile],
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      className={[
        "relative border border-dashed border-[var(--border)] bg-[var(--surface)] p-10 transition-colors",
        over ? "border-[var(--accent)] bg-[var(--accent-soft)]" : "",
        disabled ? "pointer-events-none opacity-50" : "",
      ].join(" ")}
    >
      <div className="flex flex-col items-center gap-4 text-center">
        <p className="text-label text-[var(--muted)]">{t("upload.label")}</p>
        <p className="max-w-md text-sm text-[var(--muted)]">{t("upload.hint")}</p>
        <label className="cursor-pointer">
          <span className="inline-block border border-[var(--fg)] bg-[var(--fg)] px-6 py-2.5 text-sm font-semibold uppercase tracking-wider text-[var(--surface)] hover:opacity-90">
            {disabled ? t("upload.uploading") : over ? t("upload.dropping") : t("upload.cta")}
          </span>
          <input
            type="file"
            accept=".csv,.xlsx,.xlsm,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel.sheet.macroEnabled.12"
            className="sr-only"
            disabled={disabled}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onFile(f);
              e.target.value = "";
            }}
          />
        </label>
      </div>
    </div>
  );
}
