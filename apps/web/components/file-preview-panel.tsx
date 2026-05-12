"use client";

import { useI18n } from "@/lib/i18n";
import type { FilePreviewData } from "@/lib/preview/types";

type Props = {
  preview: FilePreviewData | null;
  busy: boolean;
  fileLabel: string | null;
};

export function FilePreviewPanel({ preview, busy, fileLabel }: Props) {
  const { t } = useI18n();

  if (busy) {
    return (
      <div
        className="border border-[var(--border)] bg-[var(--surface-muted)] p-6"
        aria-busy="true"
      >
        <p className="text-label text-[var(--muted)]">{t("preview.scanning")}</p>
        <div className="mt-4 h-2 w-full animate-pulse bg-[var(--skeleton)]" />
      </div>
    );
  }

  if (!preview) return null;

  return (
    <div className="border border-[var(--border)] bg-[var(--surface)] p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-label text-[var(--muted)]">{t("preview.title")}</p>
        {fileLabel && (
          <span className="font-mono text-xs text-[var(--muted)]">{fileLabel}</span>
        )}
      </div>
      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-label text-[var(--muted)]">{t("preview.kind")}</dt>
          <dd className="mt-1 font-medium capitalize">{preview.kind}</dd>
        </div>
        {preview.encodingLabel && (
          <div>
            <dt className="text-label text-[var(--muted)]">
              {t("preview.encoding")}
            </dt>
            <dd className="mt-1 font-mono text-xs">{preview.encodingLabel}</dd>
          </div>
        )}
        <div>
          <dt className="text-label text-[var(--muted)]">{t("preview.bytes")}</dt>
          <dd className="mt-1 font-mono text-xs">{preview.bytesSampled}</dd>
        </div>
        <div>
          <dt className="text-label text-[var(--muted)]">{t("preview.magic")}</dt>
          <dd className="mt-1">{preview.magicOk ? "OK" : "—"}</dd>
        </div>
      </dl>
      {preview.warnings.length > 0 && (
        <ul className="mt-4 list-inside list-disc text-xs text-[var(--amber-fg)]">
          {preview.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
      {preview.rows.length > 0 && (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <tbody>
              {preview.rows.map((row, i) => (
                <tr key={i} className="border-b border-[var(--border)]">
                  {row.map((cell, j) => (
                    <td key={j} className="max-w-[12rem] truncate py-1.5 pr-3 font-mono">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-4 text-[0.7rem] leading-relaxed text-[var(--muted)]">
        {t("preview.disclaimer")}
      </p>
    </div>
  );
}
