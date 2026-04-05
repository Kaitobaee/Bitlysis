"use client";

import { useI18n } from "@/lib/i18n";

const SKIP_KEY_SUBSTR = ["narrative", "llm_story", "ai_summary", "story"];

function shouldOmitKey(key: string): boolean {
  const k = key.toLowerCase();
  return SKIP_KEY_SUBSTR.some((s) => k.includes(s));
}

function formatPrimitive(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number" && Number.isFinite(v)) return String(v);
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "string") {
    return v.length > 280 ? `${v.slice(0, 280)}…` : v;
  }
  return JSON.stringify(v);
}

function HypothesisTable({
  rows,
}: {
  rows: Record<string, unknown>[];
}) {
  const { t } = useI18n();
  if (!rows.length) return null;
  const keys = Object.keys(rows[0] ?? {}).filter((k) => !shouldOmitKey(k));
  if (!keys.length) return null;
  return (
    <div className="mt-6 overflow-x-auto">
      <p className="text-label mb-3 text-[var(--muted)]">
        {t("result.tableHypothesis")}
      </p>
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--border)]">
            {keys.map((k) => (
              <th
                key={k}
                className="py-2 pr-4 font-semibold uppercase tracking-wide text-[var(--muted)]"
              >
                {k}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-[var(--border)]">
              {keys.map((k) => (
                <td key={k} className="py-2 pr-4 align-top font-mono text-xs">
                  {formatPrimitive(row[k])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChartNote({ chart }: { chart: unknown }) {
  const { t } = useI18n();
  let summary = t("result.chartNote");
  if (chart && typeof chart === "object") {
    const o = chart as Record<string, unknown>;
    const series = o.series;
    if (Array.isArray(series)) {
      summary = `${t("result.chartNote")} (${series.length} series)`;
    }
  }
  const compact = JSON.stringify(chart, null, 0);
  const clipped =
    compact.length > 600 ? `${compact.slice(0, 600)}…` : compact;
  return (
    <div className="mt-4">
      <p className="text-label mb-2 text-[var(--muted)]">{summary}</p>
      <pre className="max-h-48 overflow-auto border border-[var(--border)] bg-[var(--surface-muted)] p-3 font-mono text-[11px] leading-relaxed text-[var(--fg)]">
        {clipped}
      </pre>
    </div>
  );
}

function KeyValueBlock({
  data,
  depth,
}: {
  data: Record<string, unknown>;
  depth: number;
}) {
  const entries = Object.entries(data).filter(([k]) => !shouldOmitKey(k));
  if (!entries.length) return null;
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {entries.map(([k, v]) => (
        <div key={k} className="border-b border-[var(--border)] pb-3">
          <div className="text-label text-[var(--muted)]">{k}</div>
          <div className="mt-1 font-mono text-sm break-all">
            {v !== null &&
            typeof v === "object" &&
            !Array.isArray(v) &&
            depth > 0 ? (
              <KeyValueBlock
                data={v as Record<string, unknown>}
                depth={depth - 1}
              />
            ) : v !== null && typeof v === "object" && !Array.isArray(v) ? (
              <pre className="max-h-32 overflow-auto text-xs">
                {JSON.stringify(v, null, 2).slice(0, 500)}
                {JSON.stringify(v).length > 500 ? "…" : ""}
              </pre>
            ) : Array.isArray(v) ? (
              <span className="text-[var(--muted)]">
                [{v.length} items]
              </span>
            ) : (
              formatPrimitive(v)
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

type Props = {
  summary: Record<string, unknown> | null;
};

export function ResultSummary({ summary }: Props) {
  const { t } = useI18n();
  if (!summary || Object.keys(summary).length === 0) {
    return (
      <p className="text-sm text-[var(--muted)]">{t("result.empty")}</p>
    );
  }

  const { hypothesis_table, chart, engine, version, ...rest } = summary;
  const tableRows = Array.isArray(hypothesis_table)
    ? (hypothesis_table as Record<string, unknown>[])
    : [];

  const restClean = Object.fromEntries(
    Object.entries(rest).filter(([k]) => !shouldOmitKey(k)),
  );

  return (
    <div className="space-y-6">
      {(engine !== undefined || version !== undefined) && (
        <div className="flex flex-wrap gap-6 border-b border-[var(--border)] pb-4">
          {engine !== undefined && (
            <div>
              <span className="text-label text-[var(--muted)]">
                {t("result.engine")}
              </span>
              <p className="mt-1 font-mono text-sm">{formatPrimitive(engine)}</p>
            </div>
          )}
          {version !== undefined && (
            <div>
              <span className="text-label text-[var(--muted)]">version</span>
              <p className="mt-1 font-mono text-sm">{formatPrimitive(version)}</p>
            </div>
          )}
        </div>
      )}
      <KeyValueBlock data={restClean} depth={2} />
      {chart !== undefined && <ChartNote chart={chart} />}
      <HypothesisTable rows={tableRows} />
    </div>
  );
}
