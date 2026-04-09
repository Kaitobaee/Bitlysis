"use client";

import { useI18n } from "@/lib/i18n";

const SKIP_KEY_SUBSTR = ["narrative", "llm_story", "ai_summary", "story"];

function shouldOmitKey(key: string): boolean {
  const k = key.toLowerCase();
  return SKIP_KEY_SUBSTR.some((s) => k.includes(s));
}

function formatPrimitive(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number" && Number.isFinite(v)) {
    return Number.isInteger(v) ? String(v) : v.toLocaleString(undefined, { maximumFractionDigits: 6 });
  }
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "string") return v;
  return JSON.stringify(v);
}

function isPrimitive(v: unknown): boolean {
  return (
    v === null ||
    v === undefined ||
    typeof v === "string" ||
    typeof v === "number" ||
    typeof v === "boolean"
  );
}

function humanizeKey(key: string): string {
  return key
    .replace(/[_-]+/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .trim()
    .split(/\s+/)
    .map((part) => part.toUpperCase())
    .join(" ");
}

function translatedLabel(t: (path: string) => string, key: string): string {
  const p = `result.labels.${key}`;
  const translated = t(p);
  return translated === p ? humanizeKey(key) : translated;
}

function translatedValue(
  t: (path: string) => string,
  key: string,
  value: string,
): string {
  const p = `result.values.${key}.${value}`;
  const translated = t(p);
  return translated === p ? value.replace(/[_-]+/g, " ") : translated;
}

function isAutoAnalysisEngine(engine: unknown): boolean {
  return engine === "auto_full_analysis" || engine === "auto_full_analysis_r";
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function isIgnorableAutoWarning(message: string): boolean {
  const text = message.toLowerCase();
  return (
    text.includes("không tìm thấy rscript trên path") ||
    text.includes("r bị tắt") ||
    text.includes("không đủ cột numeric") ||
    text.includes("cắt bớt cặp categorical") ||
    text.includes("cắt bớt so sánh numeric/categorical")
  );
}

function pickCategoricalPair(item: Record<string, unknown>): { left: string; right: string } {
  const left = typeof item.variable_a === "string" ? item.variable_a : "";
  const right = typeof item.variable_b === "string" ? item.variable_b : "";
  if (left || right) {
    return { left: left || "—", right: right || "—" };
  }

  const vars = asStringArray(item.variables);
  if (vars.length >= 2) {
    return { left: vars[0]!, right: vars[1]! };
  }

  return { left: "—", right: "—" };
}

function pickMixedPair(item: Record<string, unknown>): { outcome: string; group: string } {
  const outcome = typeof item.outcome === "string" ? item.outcome : "";
  const group = typeof item.group === "string" ? item.group : "";
  if (outcome || group) {
    return { outcome: outcome || "—", group: group || "—" };
  }

  const vars = asStringArray(item.variables);
  if (vars.length >= 2) {
    return { outcome: vars[0]!, group: vars[1]! };
  }

  return { outcome: "—", group: "—" };
}

function CardGrid({
  items,
}: {
  items: Array<{ label: string; value: string }>;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="rounded border border-[var(--border)] bg-[var(--surface)] p-4">
          <p className="text-label text-[var(--muted)]">{item.label}</p>
          <p className="mt-2 text-sm font-semibold leading-relaxed wrap-anywhere">{item.value}</p>
        </div>
      ))}
    </div>
  );
}

function StatusPill({ ok, label }: { ok: boolean | null; label: string }) {
  const classes =
    ok === null
      ? "border-[var(--border)] bg-[var(--surface-muted)] text-[var(--fg)]"
      : ok
        ? "border-emerald-300 bg-emerald-50 text-emerald-900"
        : "border-amber-300 bg-amber-50 text-amber-900";
  return (
    <span className={`inline-flex rounded border px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${classes}`}>
      {label}
    </span>
  );
}

function SectionTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-3 flex items-end justify-between gap-4">
      <div>
        <p className="text-label text-[var(--muted)]">{title}</p>
        {subtitle && <p className="mt-1 text-sm text-[var(--muted)]">{subtitle}</p>}
      </div>
    </div>
  );
}

function AnalysisResultCard({
  title,
  body,
  meta,
}: {
  title: string;
  body: React.ReactNode;
  meta?: React.ReactNode;
}) {
  return (
    <details className="rounded border border-[var(--border)] bg-[var(--surface)]" open={false}>
      <summary className="cursor-pointer list-none px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm font-semibold text-[var(--fg)]">{title}</p>
          {meta}
        </div>
      </summary>
      <div className="border-t border-[var(--border)] px-4 py-4">{body}</div>
    </details>
  );
}

function AutoAnalysisSummary({ summary }: { summary: Record<string, unknown> }) {
  const { t } = useI18n();
  const sections = (summary.analysis_sections as Record<string, unknown>) ?? {};
  const overview = (sections.overview as Record<string, unknown>) ?? {};
  const rBlock = (sections.r_block as Record<string, unknown>) ?? {};
  const categorical = Array.isArray(sections.categorical_associations)
    ? (sections.categorical_associations as Record<string, unknown>[])
    : [];
  const mixed = Array.isArray(sections.mixed_group_comparisons)
    ? (sections.mixed_group_comparisons as Record<string, unknown>[])
    : [];

  const numericColumns = asStringArray(overview.numeric_columns);
  const categoricalColumns = asStringArray(overview.categorical_columns);
  const constantColumns = asStringArray(overview.constant_columns);
  const highlights = asStringArray(summary.highlights);
  const warnings = asStringArray(summary.warnings);
  const visibleWarnings = warnings.filter((w) => !isIgnorableAutoWarning(w));

  const columnDetails = Array.isArray(overview.column_details)
    ? (overview.column_details as Record<string, unknown>[])
    : [];

  const rResults = Array.isArray(rBlock.results) ? (rBlock.results as Record<string, unknown>[]) : [];

  return (
    <div className="space-y-6">
      {highlights.length > 0 && (
        <section className="space-y-3">
          <SectionTitle title={t("result.highlights")} />
          <div className="flex flex-wrap gap-2">
            {highlights.map((item, idx) => (
              <span key={`${item}-${idx}`} className="rounded border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm">
                {item}
              </span>
            ))}
          </div>
        </section>
      )}

      <section className="space-y-3">
        <SectionTitle title="Overview" subtitle="Tổng quan dữ liệu được profile từ file đã upload" />
        <CardGrid
          items={[
            { label: "Rows", value: formatPrimitive(overview.row_count) },
            { label: "Columns", value: formatPrimitive(overview.column_count) },
            { label: "Numeric", value: String(numericColumns.length) },
            { label: "Categorical", value: String(categoricalColumns.length) },
          ]}
        />
        <div className="grid gap-3 lg:grid-cols-3">
          <div className="rounded border border-[var(--border)] bg-[var(--surface)] p-4">
            <p className="text-label text-[var(--muted)]">Numeric columns</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {numericColumns.length ? numericColumns.map((c) => <span key={c} className="rounded bg-[var(--surface-muted)] px-2 py-1 text-xs">{c}</span>) : <span className="text-sm text-[var(--muted)]">—</span>}
            </div>
          </div>
          <div className="rounded border border-[var(--border)] bg-[var(--surface)] p-4">
            <p className="text-label text-[var(--muted)]">Categorical columns</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {categoricalColumns.length ? categoricalColumns.map((c) => <span key={c} className="rounded bg-[var(--surface-muted)] px-2 py-1 text-xs">{c}</span>) : <span className="text-sm text-[var(--muted)]">—</span>}
            </div>
          </div>
          <div className="rounded border border-[var(--border)] bg-[var(--surface)] p-4">
            <p className="text-label text-[var(--muted)]">Constant columns</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {constantColumns.length ? constantColumns.map((c) => <span key={c} className="rounded bg-[var(--surface-muted)] px-2 py-1 text-xs">{c}</span>) : <span className="text-sm text-[var(--muted)]">—</span>}
            </div>
          </div>
        </div>

        {columnDetails.length > 0 && (
          <details className="rounded border border-[var(--border)] bg-[var(--surface)]">
            <summary className="cursor-pointer list-none px-4 py-3 text-sm font-semibold">Column details</summary>
            <div className="border-t border-[var(--border)] p-4 overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)]">
                    <th className="py-2 pr-4">Name</th>
                    <th className="py-2 pr-4">Role</th>
                    <th className="py-2 pr-4">Type</th>
                    <th className="py-2 pr-4">Missing</th>
                    <th className="py-2 pr-4">Unique</th>
                  </tr>
                </thead>
                <tbody>
                  {columnDetails.map((row, idx) => (
                    <tr key={idx} className="border-b border-[var(--border)] last:border-b-0">
                      <td className="py-2 pr-4">{formatPrimitive(row.name)}</td>
                      <td className="py-2 pr-4">{formatPrimitive(row.role)}</td>
                      <td className="py-2 pr-4">{formatPrimitive(row.dtype)}</td>
                      <td className="py-2 pr-4">{formatPrimitive(row.missing_count)}</td>
                      <td className="py-2 pr-4">{formatPrimitive(row.nunique)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}
      </section>

      <section className="space-y-3">
        <SectionTitle title="R block" subtitle="Khối numeric chạy bằng R nếu máy có Rscript" />
        <div className="flex flex-wrap gap-2">
          <StatusPill ok={rBlock.available === true} label={rBlock.available ? "R ready" : "R fallback"} />
          <StatusPill ok={rBlock.preferred === true} label={rBlock.preferred ? "Prefer R" : "Prefer Python"} />
          {typeof rBlock.returncode === "number" && <StatusPill ok={rBlock.returncode === 0} label={`rc=${rBlock.returncode}`} />}
        </div>
        {typeof rBlock.reason === "string" && rBlock.reason && (
          <p className="text-sm text-[var(--muted)]">{rBlock.reason}</p>
        )}
        {rResults.length > 0 ? (
          <div className="space-y-3">
            {rResults.map((item, idx) => (
              <AnalysisResultCard
                key={idx}
                title={formatPrimitive(item.type ?? `R result ${idx + 1}`)}
                meta={item.ok !== undefined ? <StatusPill ok={Boolean(item.ok)} label={Boolean(item.ok) ? "OK" : "Skipped"} /> : undefined}
                body={
                  <div className="space-y-4">
                    <CardGrid
                      items={[
                        { label: "Scale / type", value: formatPrimitive(item.scale_id ?? item.type) },
                        { label: "n", value: formatPrimitive(item.n) },
                        { label: "raw alpha", value: formatPrimitive(item.raw_alpha) },
                        { label: "std alpha", value: formatPrimitive(item.std_alpha) },
                      ]}
                    />
                    {Array.isArray(item.warnings) && item.warnings.length > 0 && (
                      <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                        {item.warnings.map((w, i) => (
                          <p key={i}>{formatPrimitive(w)}</p>
                        ))}
                      </div>
                    )}
                    {Array.isArray(item.loadings) && item.loadings.length > 0 && (
                      <JsonBlock value={item.loadings} maxHeight="max-h-48" />
                    )}
                    {Array.isArray(item.path_coef) && item.path_coef.length > 0 && (
                      <JsonBlock value={item.path_coef} maxHeight="max-h-48" />
                    )}
                  </div>
                }
              />
            ))}
          </div>
        ) : (
          <p className="text-sm text-[var(--muted)]">Không có kết quả R.</p>
        )}
      </section>

      <section className="space-y-3">
        <SectionTitle title="Categorical associations" subtitle="Các cặp biến phân loại được kiểm tra" />
        <div className="space-y-3">
          {categorical.length > 0 ? categorical.map((item, idx) => {
            const pair = pickCategoricalPair(item);
            const analysis = (item.analysis as Record<string, unknown>) ?? {};
            const trace = (analysis.decision_trace as Record<string, unknown>) ?? {};
            const hypothesis = Array.isArray(analysis.hypothesis_table) ? (analysis.hypothesis_table[0] as Record<string, unknown> | undefined) : undefined;
            const diagnostics = (analysis.diagnostics as Record<string, unknown>) ?? {};
            const itemError = typeof item.error === "string" ? item.error : "";
            return (
              <AnalysisResultCard
                key={idx}
                title={`${pair.left} × ${pair.right}`}
                meta={trace.selected_method ? <StatusPill ok={null} label={formatPrimitive(trace.selected_method)} /> : undefined}
                body={
                  <div className="space-y-4">
                    {itemError && (
                      <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                        {itemError}
                      </div>
                    )}
                    {typeof trace.fallback === "string" && trace.fallback ? (
                      <p className="text-sm text-[var(--muted)]">{trace.fallback}</p>
                    ) : null}
                    <CardGrid
                      items={[
                        { label: "Method", value: formatPrimitive(hypothesis?.method) },
                        { label: "Statistic", value: formatPrimitive(hypothesis?.statistic) },
                        { label: "p-value", value: formatPrimitive(hypothesis?.p_value) },
                        { label: "Effect size", value: formatPrimitive(hypothesis?.effect_size) },
                      ]}
                    />
                    <JsonBlock value={diagnostics} maxHeight="max-h-40" />
                  </div>
                }
              />
            );
          }) : <p className="text-sm text-[var(--muted)]">—</p>}
        </div>
      </section>

      <section className="space-y-3">
        <SectionTitle title="Mixed comparisons" subtitle="So sánh numeric theo nhóm categorical" />
        <div className="space-y-3">
          {mixed.length > 0 ? mixed.map((item, idx) => {
            const pair = pickMixedPair(item);
            const analysis = (item.analysis as Record<string, unknown>) ?? {};
            const trace = (analysis.decision_trace as Record<string, unknown>) ?? {};
            const hypothesis = Array.isArray(analysis.hypothesis_table) ? (analysis.hypothesis_table[0] as Record<string, unknown> | undefined) : undefined;
            const itemError = typeof item.error === "string" ? item.error : "";
            return (
              <AnalysisResultCard
                key={idx}
                title={`${pair.outcome} by ${pair.group}`}
                meta={trace.selected_method ? <StatusPill ok={null} label={formatPrimitive(trace.selected_method)} /> : undefined}
                body={
                  <div className="space-y-4">
                    {itemError && (
                      <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                        {itemError}
                      </div>
                    )}
                    {typeof trace.fallback === "string" && trace.fallback ? (
                      <p className="text-sm text-[var(--muted)]">{trace.fallback}</p>
                    ) : null}
                    <CardGrid
                      items={[
                        { label: "Method", value: formatPrimitive(hypothesis?.method) },
                        { label: "Statistic", value: formatPrimitive(hypothesis?.statistic) },
                        { label: "p-value", value: formatPrimitive(hypothesis?.p_value) },
                        { label: "Effect size", value: formatPrimitive(hypothesis?.effect_size) },
                      ]}
                    />
                  </div>
                }
              />
            );
          }) : <p className="text-sm text-[var(--muted)]">—</p>}
        </div>
      </section>

      {visibleWarnings.length > 0 && (
        <section className="rounded border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
          <p className="mb-2 text-label">Warnings</p>
          <div className="space-y-1">
            {visibleWarnings.map((w, idx) => <p key={idx}>{w}</p>)}
          </div>
        </section>
      )}
    </div>
  );
}

function JsonBlock({
  value,
  maxHeight = "max-h-80",
}: {
  value: unknown;
  maxHeight?: string;
}) {
  const pretty = JSON.stringify(value, null, 2) ?? formatPrimitive(value);
  return (
    <pre
      className={`${maxHeight} overflow-auto rounded border border-[var(--border)] bg-[var(--surface-muted)] p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap break-all`}
    >
      {pretty}
    </pre>
  );
}

function PrimitiveValue({ value }: { value: unknown }) {
  if (typeof value === "boolean") {
    return (
      <span
        className={`inline-flex rounded px-2 py-1 text-xs font-semibold uppercase tracking-wide ${
          value
            ? "bg-[var(--accent-soft)] text-[var(--accent)]"
            : "bg-[var(--surface-muted)] text-[var(--muted)]"
        }`}
      >
        {value ? "True" : "False"}
      </span>
    );
  }

  return (
    <p className="text-sm leading-relaxed whitespace-pre-wrap wrap-anywhere">
      {formatPrimitive(value)}
    </p>
  );
}

function compactValue(
  t: (path: string) => string,
  key: string,
  value: unknown,
) {
  if (key === "decision" && typeof value === "string") {
    return translatedValue(t, "decision", value);
  }
  if (key === "method" && typeof value === "string") {
    return translatedValue(t, "method", value);
  }
  return formatPrimitive(value);
}

function Highlights({ summary }: { summary: Record<string, unknown> }) {
  const { t } = useI18n();
  const table = summary.hypothesis_table;
  if (!Array.isArray(table) || !table.length) return null;
  const first = table[0] as Record<string, unknown>;

  const pValueRaw =
    typeof first.p_value === "number"
      ? first.p_value
      : typeof first.p_value === "string"
        ? Number(first.p_value)
        : null;
  const isSignificant =
    typeof pValueRaw === "number" && Number.isFinite(pValueRaw)
      ? pValueRaw < 0.05
      : null;

  const cards = [
    {
      label: t("result.method"),
      value:
        first.method !== undefined
          ? compactValue(t, "method", first.method)
          : "—",
    },
    {
      label: t("result.pValue"),
      value:
        pValueRaw !== null && Number.isFinite(pValueRaw)
          ? pValueRaw.toLocaleString(undefined, { maximumFractionDigits: 6 })
          : "—",
    },
    {
      label: t("result.decision"),
      value:
        first.decision !== undefined
          ? compactValue(t, "decision", first.decision)
          : "—",
    },
    {
      label: t("result.effectSize"),
      value:
        first.effect_size !== undefined
          ? formatPrimitive(first.effect_size)
          : "—",
    },
  ];

  return (
    <section className="space-y-3">
      <p className="text-label text-[var(--muted)]">{t("result.highlights")}</p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card) => (
          <div key={card.label} className="rounded border border-[var(--border)] bg-[var(--surface)] p-4">
            <p className="text-label text-[var(--muted)]">{card.label}</p>
            <p className="mt-2 text-sm font-semibold leading-relaxed wrap-anywhere">{String(card.value)}</p>
          </div>
        ))}
      </div>
      <div
        className={`rounded border p-3 text-sm ${
          isSignificant === null
            ? "border-[var(--border)] bg-[var(--surface)]"
            : isSignificant
              ? "border-emerald-300 bg-emerald-50 text-emerald-900"
              : "border-amber-300 bg-amber-50 text-amber-900"
        }`}
      >
        <span className="font-semibold">{t("result.significance")}: </span>
        {isSignificant === null
          ? "—"
          : isSignificant
            ? t("result.significant")
            : t("result.notSignificant")}
      </div>
    </section>
  );
}

function ValueView({
  value,
  depth,
}: {
  value: unknown;
  depth: number;
}) {
  const { t } = useI18n();

  if (isPrimitive(value)) {
    return <PrimitiveValue value={value} />;
  }

  if (Array.isArray(value)) {
    const primitiveItems = value.every((item) => isPrimitive(item));
    if (!value.length) {
      return <p className="text-sm text-[var(--muted)]">{t("result.emptyArray")}</p>;
    }

    if (primitiveItems && value.length <= 12) {
      return (
        <ul className="grid gap-2 text-sm sm:grid-cols-2">
          {value.map((item, idx) => (
            <li
              key={idx}
              className="rounded border border-[var(--border)] bg-[var(--surface)] px-3 py-2 whitespace-pre-wrap wrap-anywhere"
            >
              {isPrimitive(item) ? <PrimitiveValue value={item} /> : formatPrimitive(item)}
            </li>
          ))}
        </ul>
      );
    }

    const objectItems = value.filter((item) => item && typeof item === "object");
    if (
      objectItems.length === value.length &&
      value.length <= 16
    ) {
      const keys = Array.from(
        new Set(
          objectItems.flatMap((item) => Object.keys(item as Record<string, unknown>)),
        ),
      ).filter((k) => !shouldOmitKey(k));

      if (keys.length && keys.length <= 8) {
        return (
          <div className="overflow-x-auto rounded border border-[var(--border)] bg-[var(--surface)]">
            <table className="w-full min-w-[640px] border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[var(--surface-muted)]">
                  {keys.map((k) => (
                    <th key={k} className="px-3 py-2 font-semibold text-[var(--muted)] whitespace-nowrap">
                      {translatedLabel(t, k)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {value.map((row, idx) => {
                  const item = row as Record<string, unknown>;
                  return (
                    <tr key={idx} className="border-b border-[var(--border)] last:border-b-0">
                      {keys.map((k) => (
                        <td key={k} className="px-3 py-2 align-top whitespace-pre-wrap wrap-anywhere">
                          <PrimitiveValue value={item[k]} />
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        );
      }
    }

    return (
      <div className="space-y-2">
        <p className="text-xs text-[var(--muted)]">
          [{value.length} {t("result.items")}]
        </p>
        <JsonBlock value={value} maxHeight="max-h-72" />
      </div>
    );
  }

  const obj = value as Record<string, unknown>;
  const entries = Object.entries(obj).filter(([k]) => !shouldOmitKey(k));
  if (!entries.length) {
    return <p className="text-sm text-[var(--muted)]">{t("result.emptyObject")}</p>;
  }

  if (depth <= 0) {
    return <JsonBlock value={value} maxHeight="max-h-72" />;
  }

  return (
    <div className="space-y-3 rounded border border-[var(--border)] bg-[var(--surface-muted)] p-3">
      {entries.map(([k, v]) => (
        <div key={k} className="border-b border-[var(--border)] pb-3 last:border-b-0 last:pb-0">
          <p className="text-label text-[var(--muted)]">{translatedLabel(t, k)}</p>
          <div className="mt-2">
            <ValueView value={v} depth={depth - 1} />
          </div>
        </div>
      ))}
    </div>
  );
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

  const renderCell = (key: string, value: unknown) => {
    if (isPrimitive(value)) {
      return <PrimitiveValue value={compactValue(t, key, value)} />;
    }
    if (Array.isArray(value)) {
      const items = value.slice(0, 4);
      return (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-1.5">
            {items.map((item, idx) => (
              <span
                key={idx}
                className="inline-block rounded border border-[var(--border)] bg-[var(--surface-muted)] px-2 py-1 text-xs"
              >
                {formatPrimitive(item)}
              </span>
            ))}
          </div>
          {value.length > 4 && (
            <p className="text-xs text-[var(--muted)]">+{value.length - 4} {t("result.moreItems")}</p>
          )}
        </div>
      );
    }
    if (value && typeof value === "object") {
      return (
        <details>
          <summary className="cursor-pointer text-xs font-semibold text-[var(--accent)]">
            {t("result.viewDetails")}
          </summary>
          <div className="mt-2">
            <JsonBlock value={value} maxHeight="max-h-40" />
          </div>
        </details>
      );
    }
    return <PrimitiveValue value={value} />;
  };

  return (
    <div className="mt-6 overflow-x-auto">
      <p className="text-label mb-3 text-[var(--muted)]">
        {t("result.tableHypothesis")}
      </p>
      <table className="w-full min-w-[720px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--border)]">
            {keys.map((k) => (
              <th
                key={k}
                className="py-2 pr-4 font-semibold uppercase tracking-wide text-[var(--muted)] whitespace-nowrap"
              >
                {translatedLabel(t, k)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-[var(--border)]">
              {keys.map((k) => (
                <td
                  key={k}
                  className="max-w-[22rem] py-2 pr-4 align-top text-sm whitespace-pre-wrap wrap-anywhere"
                >
                  {renderCell(k, row[k])}
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
  return (
    <div className="mt-4">
      <p className="text-label mb-2 text-[var(--muted)]">{summary}</p>
      <details className="rounded border border-[var(--border)] bg-[var(--surface)] p-3" open>
        <summary className="cursor-pointer text-sm font-semibold">{t("result.viewChartPayload")}</summary>
        <div className="mt-3">
          <JsonBlock value={chart} maxHeight="max-h-96" />
        </div>
      </details>
    </div>
  );
}

function KeyValueBlock({ data, depth }: { data: Record<string, unknown>; depth: number }) {
  const { t } = useI18n();
  const entries = Object.entries(data).filter(([k]) => !shouldOmitKey(k));
  if (!entries.length) return null;

  return (
    <div className="space-y-4">
      {entries.map(([k, v], idx) => {
        const openByDefault = idx < 2;
        return (
          <details
            key={k}
            open={openByDefault}
            className="rounded border border-[var(--border)] bg-[var(--surface)]"
          >
            <summary className="cursor-pointer list-none px-4 py-3">
              <div className="flex items-center justify-between gap-4">
                <p className="text-label text-[var(--muted)]">{translatedLabel(t, k)}</p>
                <span className="text-xs text-[var(--muted)]">{t("result.clickToToggle")}</span>
              </div>
            </summary>
            <div className="border-t border-[var(--border)] px-4 py-4">
              <ValueView value={v} depth={depth} />
            </div>
          </details>
        );
      })}
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

  if (isAutoAnalysisEngine(summary.engine)) {
    return <AutoAnalysisSummary summary={summary} />;
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
      <Highlights summary={summary} />
      {(engine !== undefined || version !== undefined) && (
        <div className="grid gap-4 border-b border-[var(--border)] pb-4 sm:grid-cols-2">
          {engine !== undefined && (
            <div className="rounded border border-[var(--border)] bg-[var(--surface)] p-4">
              <span className="text-label text-[var(--muted)]">
                {t("result.engine")}
              </span>
              <p className="mt-2 text-base font-semibold">
                {typeof engine === "string" ? compactValue(t, "engine", engine) : formatPrimitive(engine)}
              </p>
            </div>
          )}
          {version !== undefined && (
            <div className="rounded border border-[var(--border)] bg-[var(--surface)] p-4">
              <span className="text-label text-[var(--muted)]">{t("result.version")}</span>
              <p className="mt-2 text-base font-semibold">{formatPrimitive(version)}</p>
            </div>
          )}
        </div>
      )}
      <div>
        <p className="text-label mb-3 text-[var(--muted)]">{t("result.details")}</p>
        <KeyValueBlock data={restClean} depth={2} />
      </div>
      {chart !== undefined && <ChartNote chart={chart} />}
      <HypothesisTable rows={tableRows} />
    </div>
  );
}
