"use client";

import type { ReactNode } from "react";
import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";

const SKIP_KEY_SUBSTR = ["narrative", "llm_story", "ai_summary", "story"];

const KEY_LABELS: Record<string, { vi: string; en: string }> = {
  version: { vi: "Phiên bản", en: "Version" },
  spec: { vi: "Đặc tả phân tích", en: "Analysis spec" },
  decision_trace: { vi: "Luồng quyết định", en: "Decision trace" },
  diagnostics: { vi: "Chẩn đoán", en: "Diagnostics" },
  metrics: { vi: "Chỉ số", en: "Metrics" },
  warnings: { vi: "Cảnh báo", en: "Warnings" },
  chart: { vi: "Dữ liệu biểu đồ", en: "Chart payload" },
  meta: { vi: "Thông tin bổ sung", en: "Metadata" },
  alpha: { vi: "Mức ý nghĩa (alpha)", en: "Significance (alpha)" },
  contingency_shape: { vi: "Kích thước bảng chéo", en: "Contingency shape" },
  degrees_of_freedom: { vi: "Bậc tự do", en: "Degrees of freedom" },
  low_expected_count_cells: { vi: "Số ô kỳ vọng thấp", en: "Low expected cells" },
  hypothesis_id: { vi: "Giả thuyết", en: "Hypothesis" },
  method: { vi: "Phương pháp", en: "Method" },
  assumptions_checked: { vi: "Giả định đã kiểm tra", en: "Assumptions checked" },
  statistic: { vi: "Thống kê kiểm định", en: "Statistic" },
  p_value: { vi: "Giá trị p", en: "p-value" },
  effect_size: { vi: "Mức ảnh hưởng", en: "Effect size" },
  effect_size_kind: { vi: "Loại mức ảnh hưởng", en: "Effect size kind" },
  ci: { vi: "Khoảng tin cậy", en: "Confidence interval" },
  decision: { vi: "Kết luận", en: "Decision" },
  descriptive_stats: { vi: "Thống kê mô tả", en: "Descriptive stats" },
  missing_values: { vi: "Giá trị thiếu", en: "Missing values" },
  outliers: { vi: "Ngoại lệ", en: "Outliers" },
  correlation_matrix: { vi: "Ma trận tương quan", en: "Correlation matrix" },
  cronbach: { vi: "Cronbach's Alpha", en: "Cronbach's Alpha" },
  composite_reliability: { vi: "Độ tin cậy tổng hợp (CR)", en: "Composite reliability" },
  ave: { vi: "Phương sai trích trung bình (AVE)", en: "AVE" },
  rho_a: { vi: "Rho_A", en: "Rho_A" },
  kmo_bartlett: { vi: "KMO & Bartlett", en: "KMO & Bartlett" },
  efa: { vi: "Phân tích EFA", en: "EFA" },
  cfa: { vi: "Phân tích CFA", en: "CFA" },
  factor_loadings: { vi: "Tải nhân tố", en: "Factor loadings" },
  communalities: { vi: "Communalities", en: "Communalities" },
  variance_explained: { vi: "% phương sai giải thích", en: "% variance explained" },
  eigenvalues: { vi: "Eigenvalues", en: "Eigenvalues" },
  scree_plot: { vi: "Scree plot", en: "Scree plot" },
  pls_sem: { vi: "PLS-SEM", en: "PLS-SEM" },
  measurement_model: { vi: "Mô hình đo lường", en: "Measurement model" },
  structural_model: { vi: "Mô hình cấu trúc", en: "Structural model" },
  path_coefficients: { vi: "Hệ số đường dẫn", en: "Path coefficients" },
  bootstrapping: { vi: "Bootstrapping", en: "Bootstrapping" },
  assumptions: { vi: "Kiểm tra giả định", en: "Assumptions" },
  regression: { vi: "Hồi quy", en: "Regression" },
  residual_plot: { vi: "Biểu đồ phần dư", en: "Residual plot" },
  qq_plot: { vi: "QQ-plot", en: "QQ-plot" },
  time_series: { vi: "Chuỗi thời gian", en: "Time series" },
  forecast: { vi: "Dự báo", en: "Forecast" },
  mape: { vi: "MAPE", en: "MAPE" },
  rmse: { vi: "RMSE", en: "RMSE" },
  what_if: { vi: "Mô phỏng What-if", en: "What-if" },
  profiling: { vi: "Hồ sơ dữ liệu", en: "Profiling" },
  hypotheses: { vi: "Giả thuyết", en: "Hypotheses" },
  results: { vi: "Kết quả phân tích", en: "Analysis results" },
  charts: { vi: "Danh sách biểu đồ", en: "Charts" },
  manifest: { vi: "Manifest", en: "Manifest" },
};

function shouldOmitKey(key: string): boolean {
  const k = key.toLowerCase();
  return SKIP_KEY_SUBSTR.some((s) => k.includes(s));
}

function keyLabel(key: string, locale: Locale): string {
  const found = KEY_LABELS[key];
  if (found) return found[locale];
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (m) => m.toUpperCase());
}

function translateMethod(value: string, locale: Locale): string {
  const mapVi: Record<string, string> = {
    "Chi-square test of independence": "Kiểm định Chi-bình phương (độc lập)",
    "Mann-Whitney U (hai mẫu độc lập)": "Mann-Whitney U (2 nhóm độc lập)",
    "Welch t-test": "Welch t-test",
    "Student t-test (pooled variance)": "Student t-test (phương sai gộp)",
    "One-way ANOVA": "ANOVA một yếu tố",
    "Kruskal-Wallis": "Kruskal-Wallis",
  };
  if (locale === "vi") return mapVi[value] ?? value;
  return value;
}

function translateDecision(value: string, locale: Locale): string {
  if (locale !== "vi") return value;
  if (value === "reject_h0") return "Có khác biệt/quan hệ có ý nghĩa thống kê";
  if (value === "fail_to_reject_h0") return "Chưa đủ bằng chứng khác biệt/quan hệ";
  if (value === "not_applicable") return "Không áp dụng";
  return value;
}

function formatByKey(key: string, value: unknown, locale: Locale): string {
  if (key === "method" && typeof value === "string") {
    return translateMethod(value, locale);
  }
  if (key === "decision" && typeof value === "string") {
    return translateDecision(value, locale);
  }
  if (key === "contingency_shape" && Array.isArray(value) && value.length >= 2) {
    if (locale === "vi") return `${value[0]} hàng × ${value[1]} cột`;
    return `${value[0]} rows x ${value[1]} cols`;
  }
  if (key === "assumptions_checked" && Array.isArray(value)) {
    if (locale !== "vi") return value.map((v) => formatPrimitive(v)).join(", ");
    const mapped = value.map((item) => {
      const raw = String(item);
      if (raw === "independent_observations") return "Quan sát độc lập";
      if (raw === "expected_frequencies") return "Tần số kỳ vọng đủ lớn";
      if (raw === "normality_per_group") return "Phân phối gần chuẩn theo nhóm";
      if (raw === "homogeneity_levene") return "Phương sai đồng nhất (Levene)";
      return raw.replace(/_/g, " ");
    });
    return mapped.join(", ");
  }
  if (Array.isArray(value)) {
    return value.map((v) => formatPrimitive(v)).join(", ");
  }
  return formatPrimitive(value);
}

function formatPrimitive(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number" && Number.isFinite(v)) {
    return Number.isInteger(v)
      ? v.toLocaleString("vi-VN")
      : v.toLocaleString("vi-VN", { maximumFractionDigits: 6 });
  }
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "string") {
    return v.length > 280 ? `${v.slice(0, 280)}…` : v;
  }
  return JSON.stringify(v);
}

function sumNumbers(values: number[]): number {
  return values.reduce((acc, v) => acc + v, 0);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asRows(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return [];
  return value.filter((v): v is Record<string, unknown> => !!asRecord(v));
}

function firstHypothesisRow(analysis: unknown): Record<string, unknown> | null {
  const a = asRecord(analysis);
  if (!a) return null;
  const rows = asRows(a.hypothesis_table);
  return rows.length ? rows[0] : null;
}

function pickKeys(
  source: Record<string, unknown> | null,
  keys: string[],
): Record<string, unknown> {
  if (!source) return {};
  const out: Record<string, unknown> = {};
  for (const k of keys) {
    if (k in source && source[k] !== null && source[k] !== undefined) {
      out[k] = source[k];
    }
  }
  return out;
}

function normalizeRBlock(
  block: Record<string, unknown> | null,
  locale: Locale,
): Record<string, unknown> {
  if (!block) return {};
  const out: Record<string, unknown> = {
    ...pickKeys(block, ["available", "preferred", "returncode", "stderr", "results"]),
  };

  const returnCode = Number(block.returncode);
  const hasResults = hasData(block.results);
  const rawError = typeof block.error === "string" ? block.error.trim() : "";

  if (Number.isFinite(returnCode) && returnCode === 0 && hasResults) {
    out.status =
      locale === "vi"
        ? "R chạy thành công, đã có kết quả; cảnh báo (nếu có) nằm ở STDERR."
        : "R completed successfully with results; warnings (if any) are in STDERR.";
  } else if (rawError) {
    out.error = rawError;
  }

  return out;
}

function hasData(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value as object).length > 0;
  return true;
}

function isPrimitiveValue(v: unknown): boolean {
  return (
    v === null ||
    v === undefined ||
    typeof v === "string" ||
    typeof v === "number" ||
    typeof v === "boolean"
  );
}

function isPrimitiveArray(v: unknown): v is Array<string | number | boolean | null> {
  return Array.isArray(v) && v.every((x) => isPrimitiveValue(x));
}

function ListOfRecordsPreview({
  rows,
  locale,
}: {
  rows: Record<string, unknown>[];
  locale: Locale;
}) {
  if (!rows.length) return <span>—</span>;
  const keys = Array.from(
    new Set(rows.flatMap((r) => Object.keys(r).filter((k) => !shouldOmitKey(k)))),
  ).slice(0, 4);
  const shownRows = rows.slice(0, 5);
  return (
    <div className="space-y-2">
      <div className="text-xs text-[var(--muted)]">
        {locale === "vi"
          ? `Bảng ${rows.length} dòng, hiển thị ${shownRows.length} dòng đầu`
          : `Table ${rows.length} rows, showing first ${shownRows.length}`}
      </div>
      <div className="overflow-auto border border-[var(--border)]">
        <table className="min-w-[420px] border-collapse text-xs">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--surface-muted)]">
              {keys.map((k) => (
                <th key={k} className="px-2 py-1 text-left font-semibold text-[var(--muted)]">
                  {keyLabel(k, locale)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shownRows.map((row, idx) => (
              <tr key={idx} className="border-b border-[var(--border)]">
                {keys.map((k) => (
                  <td key={k} className="px-2 py-1 align-top">
                    {isPrimitiveValue(row[k])
                      ? formatByKey(k, row[k], locale)
                      : locale === "vi"
                        ? "(dữ liệu phức tạp)"
                        : "(complex value)"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ValueCell({
  value,
  locale,
  field,
}: {
  value: unknown;
  locale: Locale;
  field: string;
}) {
  if (value === null || value === undefined) return <span>—</span>;
  if (Array.isArray(value)) {
    if (!value.length) return <span>—</span>;
    if (isPrimitiveArray(value)) {
      return <span>{formatByKey(field, value, locale)}</span>;
    }
    const rowObjects = value.filter((v) => !!asRecord(v)) as Record<string, unknown>[];
    if (rowObjects.length) {
      return <ListOfRecordsPreview rows={rowObjects} locale={locale} />;
    }
    return (
      <span>{locale === "vi" ? `Danh sách (${value.length})` : `List (${value.length})`}</span>
    );
  }
  if (typeof value === "object") {
    const rec = value as Record<string, unknown>;
    const keys = Object.keys(rec).filter((k) => !shouldOmitKey(k));
    if (!keys.length) return <span>—</span>;
    return (
      <div className="space-y-1 text-xs">
        {keys.slice(0, 4).map((k) => (
          <div key={k} className="flex items-start justify-between gap-2">
            <span className="text-[var(--muted)]">{keyLabel(k, locale)}</span>
            <span className="text-right">
              {isPrimitiveValue(rec[k]) || isPrimitiveArray(rec[k])
                ? formatByKey(k, rec[k], locale)
                : Array.isArray(rec[k])
                  ? locale === "vi"
                    ? `Danh sách (${(rec[k] as unknown[]).length})`
                    : `List (${(rec[k] as unknown[]).length})`
                  : locale === "vi"
                    ? `Đối tượng (${Object.keys(asRecord(rec[k]) ?? {}).length} trường)`
                    : `Object (${Object.keys(asRecord(rec[k]) ?? {}).length} fields)`}
            </span>
          </div>
        ))}
        {keys.length > 4 && (
          <div className="text-[var(--muted)]">
            {locale === "vi" ? `+${keys.length - 4} trường khác` : `+${keys.length - 4} more fields`}
          </div>
        )}
      </div>
    );
  }
  return <span>{formatByKey(field, value, locale)}</span>;
}

function ObjectGrid({
  data,
  title,
}: {
  data: Record<string, unknown>;
  title?: string;
}) {
  const { locale } = useI18n();
  const entries = Object.entries(data).filter(([k, v]) => !shouldOmitKey(k) && hasData(v));
  if (!entries.length) return null;
  return (
    <div className="border border-[var(--border)] rounded-lg p-5">
      {title && <h4 className="text-label mb-3 text-[var(--muted)]">{title}</h4>}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {entries.map(([k, v]) => (
          <div key={k} className="border-b border-[var(--border)] pb-3">
            <div className="text-xs font-semibold text-[var(--accent)] uppercase tracking-wider">
              {keyLabel(k, locale)}
            </div>
            <div className="mt-2 text-sm text-[var(--fg)] break-words">
              <ValueCell value={v} locale={locale} field={k} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SectionCard({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="space-y-5 rounded-3xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-[0_8px_24px_rgba(22,22,21,0.04)] lg:p-7">
      <h3 className="text-xs font-semibold uppercase tracking-[0.28em] text-[var(--muted)]">{title}</h3>
      {children}
    </section>
  );
}

function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-muted)] p-4 shadow-sm">
      <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">{label}</div>
      <div className="mt-2 text-lg font-semibold text-[var(--fg)]">{value}</div>
      {hint && <div className="mt-1 text-xs text-[var(--muted)]">{hint}</div>}
    </div>
  );
}

type ModuleKey = "A" | "B" | "C" | "D" | "E" | "F" | "G";

function moduleTitle(moduleKey: ModuleKey, locale: Locale): string {
  const vi: Record<ModuleKey, string> = {
    A: "A. Phân tích cơ bản",
    B: "B. Độ tin cậy & khảo sát",
    C: "C. Phân tích yếu tố (EFA/CFA)",
    D: "D. PLS-SEM",
    E: "E. Kiểm định giả thuyết",
    F: "F. Chuỗi thời gian & dự báo",
    G: "G. Output theo yêu cầu",
  };
  const en: Record<ModuleKey, string> = {
    A: "A. Basic analysis",
    B: "B. Reliability & survey",
    C: "C. Factor analysis (EFA/CFA)",
    D: "D. PLS-SEM",
    E: "E. Hypothesis testing",
    F: "F. Time series & forecasting",
    G: "G. Requested output",
  };
  return locale === "vi" ? vi[moduleKey] : en[moduleKey];
}

function HypothesisTable({
  rows,
}: {
  rows: Record<string, unknown>[];
}) {
  const { locale, t } = useI18n();
  if (!rows.length) return null;
  const keys = Array.from(
    new Set(rows.flatMap((row) => Object.keys(row).filter((k) => !shouldOmitKey(k)))),
  );
  if (!keys.length) return null;
  const tableRows = rows.slice(0, 100);

  return (
    <div className="mt-6 space-y-2 overflow-x-auto w-full">
      <p className="text-label mb-3 text-[var(--muted)]">
        {t("result.tableHypothesis")}
      </p>
      {rows.length > tableRows.length ? (
        <p className="text-xs text-[var(--muted)]">
          {locale === "vi"
            ? `Hiển thị ${tableRows.length}/${rows.length} dòng để đảm bảo hiệu năng.`
            : `Showing ${tableRows.length}/${rows.length} rows for performance.`}
        </p>
      ) : null}
      <table className="min-w-[960px] w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--border)]">
            {keys.map((k) => (
              <th
                key={k}
                className="py-2 pr-4 text-xs font-semibold text-[var(--muted)] align-top"
              >
                {keyLabel(k, locale)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tableRows.map((row, i) => (
            <tr key={i} className="border-b border-[var(--border)]">
              {keys.map((k) => (
                <td key={k} className="py-2 pr-4 align-top text-xs whitespace-normal break-words">
                  {formatByKey(k, row[k], locale)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChartView({ chart }: { chart: unknown }) {
  const { locale } = useI18n();
  if (!chart || typeof chart !== "object") return null;
  const o = chart as Record<string, unknown>;
  const kind = String(o.kind ?? "");

  if (kind === "timeseries_forecast") {
    const rawSeries = Array.isArray(o.series)
      ? (o.series as Array<Record<string, unknown>>)
      : [];
    const pointsBySeries = rawSeries.map((s) => {
      const pts = Array.isArray(s.points)
        ? (s.points as Array<Record<string, unknown>>)
        : [];
      return {
        label: String(s.label ?? s.key ?? "series"),
        points: pts
          .map((p) => Number(p.y))
          .filter((v) => Number.isFinite(v)),
      };
    });
    const allY = pointsBySeries.flatMap((s) => s.points);
    if (!allY.length) return null;
    const minY = Math.min(...allY);
    const maxY = Math.max(...allY);
    const span = Math.max(maxY - minY, 1);
    const width = 640;
    const height = 220;
    const colors = ["#0f766e", "#2563eb", "#dc2626", "#7c3aed"];

    return (
      <div className="mt-4 border border-[var(--border)] p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
          {locale === "vi" ? "Biểu đồ chuỗi thời gian" : "Time-series chart"}
        </p>
        <svg viewBox={`0 0 ${width} ${height}`} className="mt-3 w-full">
          {pointsBySeries.map((s, idx) => {
            if (s.points.length < 2) return null;
            const d = s.points
              .map((y, i) => {
                const x = (i / (s.points.length - 1)) * (width - 20) + 10;
                const py = height - 10 - ((y - minY) / span) * (height - 20);
                return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${py.toFixed(1)}`;
              })
              .join(" ");
            return (
              <path
                key={`${s.label}-${idx}`}
                d={d}
                fill="none"
                stroke={colors[idx % colors.length]}
                strokeWidth="2"
              />
            );
          })}
        </svg>
        <div className="mt-2 flex flex-wrap gap-3 text-xs">
          {pointsBySeries.map((s, idx) => (
            <span key={`${s.label}-legend`} className="inline-flex items-center gap-1">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: colors[idx % colors.length] }}
              />
              {s.label}
            </span>
          ))}
        </div>
      </div>
    );
  }

  if (kind === "categorical_association") {
    const labels = Array.isArray(o.x_labels) ? (o.x_labels as unknown[]) : [];
    const rawSeries = Array.isArray(o.series)
      ? (o.series as Array<Record<string, unknown>>)
      : [];
    if (!labels.length || !rawSeries.length) return null;
    const matrix = rawSeries.map((s) => {
      const values = Array.isArray(s.values) ? (s.values as unknown[]) : [];
      return {
        label: String(s.label ?? s.key ?? "series"),
        values: labels.map((_, idx) => {
          const v = Number(values[idx] ?? 0);
          return Number.isFinite(v) ? v : 0;
        }),
      };
    });
    const maxV = Math.max(1, ...matrix.flatMap((m) => m.values));
    const seriesTotals = matrix.map((m) => ({
      label: m.label,
      total: sumNumbers(m.values),
    }));
    const totalAll = Math.max(1, sumNumbers(seriesTotals.map((s) => s.total)));
    const colors = ["#0f766e", "#2563eb", "#dc2626", "#d97706", "#7c3aed", "#0891b2"];
    const canShowBar = seriesTotals.length >= 2 && seriesTotals.length <= 12;
    const canShowPie =
      seriesTotals.length >= 2 &&
      seriesTotals.length <= 6 &&
      seriesTotals.every((s) => s.total > 0);

    let current = 0;
    const pieStops = seriesTotals.map((item, idx) => {
      const start = (current / totalAll) * 100;
      current += item.total;
      const end = (current / totalAll) * 100;
      return `${colors[idx % colors.length]} ${start.toFixed(2)}% ${end.toFixed(2)}%`;
    });

    return (
      <div className="mt-4 border border-[var(--border)] p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
          {locale === "vi"
            ? "Biểu đồ ma trận tần suất"
            : "Frequency matrix chart"}
        </p>

        {(canShowBar || canShowPie) && (
          <div className="mt-4 grid gap-5 lg:grid-cols-2">
            {canShowBar && (
              <div className="border border-[var(--border)] bg-[var(--surface-muted)] p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                  {locale === "vi"
                    ? "Biểu đồ cột tổng theo nhóm"
                    : "Grouped totals bar chart"}
                </p>
                <div className="mt-4 space-y-3">
                  {seriesTotals.map((item, idx) => {
                    const width = Math.max(6, (item.total / totalAll) * 100);
                    return (
                      <div key={`bar-${item.label}`} className="space-y-1">
                        <div className="flex items-center justify-between gap-3 text-xs">
                          <span className="truncate text-[var(--fg)]">{item.label}</span>
                          <span className="font-semibold text-[var(--fg)]">
                            {formatPrimitive(item.total)}
                          </span>
                        </div>
                        <div className="h-2.5 w-full bg-[var(--surface)]">
                          <div
                            className="h-full"
                            style={{
                              width: `${width.toFixed(1)}%`,
                              backgroundColor: colors[idx % colors.length],
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {canShowPie && (
              <div className="border border-[var(--border)] bg-[var(--surface-muted)] p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                  {locale === "vi"
                    ? "Biểu đồ tròn tỷ trọng theo nhóm"
                    : "Group share pie chart"}
                </p>
                <div className="mt-4 flex flex-wrap items-center gap-5">
                  <div
                    className="h-40 w-40 rounded-full border border-[var(--border)]"
                    style={{
                      background: `conic-gradient(${pieStops.join(", ")})`,
                    }}
                    aria-label={locale === "vi" ? "Biểu đồ tròn" : "Pie chart"}
                  />
                  <div className="min-w-[220px] flex-1 space-y-2 text-xs">
                    {seriesTotals.map((item, idx) => {
                      const pct = (item.total / totalAll) * 100;
                      return (
                        <div key={`pie-${item.label}`} className="flex items-center justify-between gap-3">
                          <span className="inline-flex items-center gap-2 truncate">
                            <span
                              className="inline-block h-2.5 w-2.5 rounded-full"
                              style={{ backgroundColor: colors[idx % colors.length] }}
                            />
                            <span className="truncate">{item.label}</span>
                          </span>
                          <span className="font-semibold">
                            {formatPrimitive(item.total)} ({pct.toFixed(1)}%)
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {!canShowBar && !canShowPie && (
          <p className="mt-3 text-xs text-[var(--muted)]">
            {locale === "vi"
              ? "Dữ liệu quá nhiều nhóm để vẽ cột/tròn rõ ràng, đang hiển thị ma trận chi tiết."
              : "Data has too many groups for readable bar/pie charts, showing detailed matrix."}
          </p>
        )}

        <div className="mt-3 overflow-auto">
          <table className="min-w-[720px] border-collapse text-xs">
            <thead>
              <tr>
                <th className="border border-[var(--border)] bg-[var(--surface-muted)] p-2 text-left">
                  {locale === "vi" ? "Nhãn" : "Label"}
                </th>
                {matrix.map((m) => (
                  <th
                    key={`head-${m.label}`}
                    className="border border-[var(--border)] bg-[var(--surface-muted)] p-2 text-left"
                  >
                    {m.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {labels.map((lb, rowIdx) => (
                <tr key={`row-${String(lb)}-${rowIdx}`}>
                  <td className="border border-[var(--border)] p-2 align-top">
                    {String(lb)}
                  </td>
                  {matrix.map((m) => {
                    const v = m.values[rowIdx] ?? 0;
                    const opacity = 0.15 + (v / maxV) * 0.75;
                    return (
                      <td
                        key={`cell-${m.label}-${rowIdx}`}
                        className="border border-[var(--border)] p-2 text-center"
                        style={{ backgroundColor: `rgba(15,118,110,${opacity.toFixed(3)})` }}
                      >
                        {formatPrimitive(v)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return null;
}

function DiagnosticsBlock({
  data,
}: {
  data: Record<string, unknown>;
}) {
  const { locale } = useI18n();
  const entries = Object.entries(data).filter(([k]) => !shouldOmitKey(k)).filter(([, v]) => 
    typeof v !== "object" || Array.isArray(v)
  );
  if (!entries.length) return null;
  return (
    <div className="border border-[var(--border)] rounded-lg p-6">
      <h3 className="text-label mb-4 text-[var(--muted)]">
        {locale === "vi" ? "Chi tiết chẩn đoán" : "Diagnostics"}
      </h3>
      <div className="grid gap-4 sm:grid-cols-2">
        {entries.map(([k, v]) => (
          <div key={k} className="pb-3">
            <div className="text-xs font-semibold text-[var(--accent)] uppercase tracking-wider">
              {keyLabel(k, locale)}
            </div>
            <div className="mt-2 text-base font-semibold text-[var(--fg)]">
              {formatByKey(k, v, locale)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function buildAiInsights(
  summary: Record<string, unknown> | null,
  locale: Locale,
): { headline: string; bullets: string[] } {
  const empty =
    locale === "vi"
      ? {
          headline: "AI chưa đủ dữ liệu để phân tích",
          bullets: ["Hãy chạy phân tích để hệ thống tạo kết quả có cấu trúc trước khi diễn giải."],
        }
      : {
          headline: "AI needs more data",
          bullets: ["Run analysis first so structured results are available for interpretation."],
        };

  if (!summary) return empty;

  const root = asRecord(summary);
  const analysisSections = asRecord(root?.analysis_sections);
  const nestedBlocks = [
    ...asRows(analysisSections?.categorical_associations),
    ...asRows(analysisSections?.mixed_group_comparisons),
  ]
    .map((x) => asRecord(x.analysis))
    .filter((x): x is Record<string, unknown> => !!x);

  const table = Array.isArray(root?.hypothesis_table)
    ? (root?.hypothesis_table as Record<string, unknown>[])
    : nestedBlocks.flatMap((block) =>
        Array.isArray(block.hypothesis_table)
          ? (block.hypothesis_table as Record<string, unknown>[])
          : [],
      );
  const diagnostics =
    asRecord(root?.diagnostics) ??
    nestedBlocks.map((b) => asRecord(b.diagnostics)).find((x) => !!x) ??
    {};
  const results = asRecord(root?.results);
  const warnings = Array.isArray(root?.warnings)
    ? (root?.warnings as unknown[]).map((x) => String(x)).filter(Boolean)
    : [];

  const significant = table.filter((r) => String(r.decision ?? "") === "reject_h0").length;
  const tested = table.length;
  const nonsignificant = Math.max(0, tested - significant);
  const method = String(diagnostics?.selected_method ?? diagnostics?.method ?? "").trim();

  const hasForecast = Boolean(results?.forecast || root?.forecast);
  const mape = Number(results?.mape ?? root?.mape ?? Number.NaN);
  const rmse = Number(results?.rmse ?? root?.rmse ?? Number.NaN);

  const bullets: string[] = [];

  if (tested > 0) {
    bullets.push(
      locale === "vi"
        ? `Đã kiểm định ${tested} giả thuyết: ${significant} có ý nghĩa thống kê, ${nonsignificant} chưa đủ bằng chứng.`
        : `Tested ${tested} hypotheses: ${significant} significant, ${nonsignificant} not significant.`,
    );
  }

  if (method) {
    bullets.push(
      locale === "vi"
        ? `Phương pháp nổi bật được hệ thống chọn: ${method}.`
        : `Primary selected method: ${method}.`,
    );
  }

  if (hasForecast) {
    const mapeTxt = Number.isFinite(mape) ? mape.toFixed(3) : "n/a";
    const rmseTxt = Number.isFinite(rmse) ? rmse.toFixed(3) : "n/a";
    bullets.push(
      locale === "vi"
        ? `Có kết quả dự báo: MAPE=${mapeTxt}, RMSE=${rmseTxt}.`
        : `Forecast output available: MAPE=${mapeTxt}, RMSE=${rmseTxt}.`,
    );
  }

  if (warnings.length) {
    bullets.push(
      locale === "vi"
        ? `Cảnh báo dữ liệu/phương pháp: ${warnings[0]}`
        : `Data/method warning: ${warnings[0]}`,
    );
  }

  if (!bullets.length) {
    bullets.push(
      locale === "vi"
        ? "Kết quả đã sẵn sàng; mở các khối bên dưới để xem bảng thống kê và biểu đồ chi tiết."
        : "Results are ready; expand sections below for detailed tables and charts.",
    );
  }

  return {
    headline:
      locale === "vi"
        ? "AI phân tích từ output thống kê"
        : "AI interpretation from statistical output",
    bullets,
  };
}

type Props = {
  jobId?: string;
  summary: Record<string, unknown> | null;
};

export function ResultSummary({ jobId, summary }: Props) {
  const { t, locale } = useI18n();
  const [showTables, setShowTables] = useState(true);
  const [showCharts, setShowCharts] = useState(true);
  const [showExportChart, setShowExportChart] = useState(true);
  const [moduleVisibility, setModuleVisibility] = useState<Record<ModuleKey, boolean>>({
    A: true,
    B: true,
    C: true,
    D: true,
    E: true,
    F: true,
    G: true,
  });

  if (!summary || Object.keys(summary).length === 0) {
    return (
      <p className="text-sm text-[var(--muted)]">{t("result.empty")}</p>
    );
  }

  const {
    hypothesis_table,
    chart,
    engine,
    version,
    diagnostics,
  } = summary;
  const tableRows = Array.isArray(hypothesis_table)
    ? (hypothesis_table as Record<string, unknown>[])
    : [];

  const summaryRecord = asRecord(summary);
  const analysisSections = asRecord(summaryRecord?.analysis_sections);
  const overview = asRecord(analysisSections?.overview);
  const rBlock = asRecord(analysisSections?.r_block);
  const categoricalAssociations = asRows(analysisSections?.categorical_associations);
  const mixedGroupComparisons = asRows(analysisSections?.mixed_group_comparisons);

  const nestedAnalysisBlocks = [...categoricalAssociations, ...mixedGroupComparisons]
    .map((item) => asRecord(item.analysis))
    .filter((x): x is Record<string, unknown> => !!x);

  const nestedHypothesisRows = nestedAnalysisBlocks.flatMap((block) => {
    const rows = block.hypothesis_table;
    return Array.isArray(rows) ? (rows as Record<string, unknown>[]) : [];
  });

  const mergedChart =
    (chart && typeof chart === "object" ? chart : null) ??
    nestedAnalysisBlocks.find((block) => !!asRecord(block.chart))?.chart ??
    null;

  const mergedDiagnostics =
    (diagnostics && typeof diagnostics === "object" && !Array.isArray(diagnostics)
      ? diagnostics
      : null) ??
    nestedAnalysisBlocks.find((block) => !!asRecord(block.diagnostics))?.diagnostics ??
    null;

  const profiling = asRecord(summaryRecord?.profiling);
  const results = asRecord(summaryRecord?.results);
  const hypothesesApiRows = asRows(summaryRecord?.hypotheses).map((h) => {
    const result = asRecord(h.result);
    return {
      ...(result ?? {}),
      hypothesis_id: h.id ?? h.hypothesis_id,
      statement: h.statement,
      method: h.method ?? result?.method,
    };
  });
  const mergedHypothesisRows = tableRows.length
    ? tableRows
    : hypothesesApiRows.length
      ? hypothesesApiRows
      : nestedHypothesisRows;

  const sectionA = {
    ...pickKeys(overview, [
      "row_count",
      "column_count",
      "numeric_columns",
      "categorical_columns",
      "constant_columns",
      "column_details",
    ]),
    ...pickKeys(profiling, ["descriptive_stats", "missing_values", "outliers", "correlation_matrix"]),
    ...pickKeys(results, ["descriptive_stats", "missing_values", "outliers", "correlation_matrix"]),
  };
  const sectionB = {
    ...normalizeRBlock(rBlock, locale),
    ...pickKeys(results, ["cronbach", "composite_reliability", "ave", "rho_a", "kmo_bartlett"]),
  };
  const sectionC = {
    ...pickKeys(results, ["efa", "cfa", "factor_loadings", "communalities", "variance_explained", "eigenvalues", "scree_plot", "factor_correlation_matrix"]),
  };
  const sectionD = {
    ...pickKeys(results, ["pls_sem", "measurement_model", "structural_model", "path_coefficients", "bootstrapping", "r2", "q2", "f2", "htmt", "fornell_larcker", "path_diagram"]),
  };
  const sectionE = {
    ...(categoricalAssociations.length
      ? {
          categorical_associations: categoricalAssociations.map((item) => {
            const first = firstHypothesisRow(item.analysis);
            const warnings = Array.isArray(first?.warnings)
              ? (first?.warnings as unknown[]).map((x) => String(x)).filter(Boolean)
              : [];
            return {
              variable_a: item.variable_a,
              variable_b: item.variable_b,
              method: first?.method,
              statistic: first?.statistic,
              p_value: first?.p_value,
              effect_size: first?.effect_size,
              effect_size_kind: first?.effect_size_kind,
              decision: first?.decision,
              warning: warnings[0] ?? null,
            };
          }),
        }
      : {}),
    ...(mixedGroupComparisons.length
      ? {
          mixed_group_comparisons: mixedGroupComparisons.map((item) => {
            const first = firstHypothesisRow(item.analysis);
            const warnings = Array.isArray(first?.warnings)
              ? (first?.warnings as unknown[]).map((x) => String(x)).filter(Boolean)
              : [];
            return {
              variable_numeric:
                item.variable_numeric ?? item.numeric_variable ?? item.outcome ?? null,
              variable_group:
                item.variable_group ?? item.group_variable ?? item.group ?? null,
              method: first?.method,
              statistic: first?.statistic,
              p_value: first?.p_value,
              effect_size: first?.effect_size,
              effect_size_kind: first?.effect_size_kind,
              decision: first?.decision,
              warning: warnings[0] ?? null,
            };
          }),
        }
      : {}),
    ...pickKeys(results, ["t_test", "mann_whitney", "anova", "kruskal_wallis", "regression", "logistic_regression", "assumptions", "residual_plot", "qq_plot", "vif"]),
  };
  const sectionF = {
    ...pickKeys(results, ["time_series", "forecast", "mape", "rmse", "what_if"]),
  };
  const sectionG = {
    ...pickKeys(results, ["requested_output", "export_files", "selected_modules"]),
    ...pickKeys(summaryRecord, ["charts", "manifest", "zip_url"]),
  };

  const allKnownResultKeys = new Set([
    "descriptive_stats",
    "missing_values",
    "outliers",
    "correlation_matrix",
    "cronbach",
    "composite_reliability",
    "ave",
    "rho_a",
    "kmo_bartlett",
    "efa",
    "cfa",
    "factor_loadings",
    "communalities",
    "variance_explained",
    "eigenvalues",
    "scree_plot",
    "factor_correlation_matrix",
    "pls_sem",
    "measurement_model",
    "structural_model",
    "path_coefficients",
    "bootstrapping",
    "r2",
    "q2",
    "f2",
    "htmt",
    "fornell_larcker",
    "path_diagram",
    "t_test",
    "mann_whitney",
    "anova",
    "kruskal_wallis",
    "regression",
    "logistic_regression",
    "assumptions",
    "residual_plot",
    "qq_plot",
    "vif",
    "time_series",
    "forecast",
    "mape",
    "rmse",
    "what_if",
    "requested_output",
    "export_files",
    "selected_modules",
  ]);

  const extraResults = Object.fromEntries(
    Object.entries(results ?? {}).filter(
      ([k, v]) => !allKnownResultKeys.has(k) && hasData(v),
    ),
  );
  const extraProfiling = Object.fromEntries(
    Object.entries(profiling ?? {}).filter(
      ([k, v]) => !["descriptive_stats", "missing_values", "outliers", "correlation_matrix"].includes(k) && hasData(v),
    ),
  );
  const extraTopLevel = Object.fromEntries(
    Object.entries(summaryRecord ?? {}).filter(
      ([k, v]) =>
        ![
          "hypothesis_table",
          "chart",
          "engine",
          "version",
          "diagnostics",
          "profiling",
          "hypotheses",
          "results",
          "charts",
          "manifest",
          "zip_url",
        ].includes(k) && hasData(v),
    ),
  );

  const sectionGAll = {
    ...sectionG,
    ...(Object.keys(extraResults).length
      ? {
          extra_results_summary:
            locale === "vi"
              ? `${Object.keys(extraResults).length} mục kết quả mở rộng`
              : `${Object.keys(extraResults).length} extended result items`,
        }
      : {}),
    ...(Object.keys(extraProfiling).length
      ? {
          extra_profiling_summary:
            locale === "vi"
              ? `${Object.keys(extraProfiling).length} mục profiling mở rộng`
              : `${Object.keys(extraProfiling).length} extended profiling items`,
        }
      : {}),
    ...(Object.keys(extraTopLevel).length
      ? {
          extra_top_level_summary:
            locale === "vi"
              ? `${Object.keys(extraTopLevel).length} trường top-level bổ sung`
              : `${Object.keys(extraTopLevel).length} additional top-level fields`,
        }
      : {}),
  };

  const moduleData: Record<ModuleKey, Record<string, unknown>> = {
    A: sectionA,
    B: sectionB,
    C: sectionC,
    D: sectionD,
    E: sectionE,
    F: sectionF,
    G: sectionGAll,
  };

  const enabledModules = (Object.keys(moduleData) as ModuleKey[]).filter(
    (k) => moduleVisibility[k],
  );

  const toggleAllModules = (value: boolean) => {
    setModuleVisibility({ A: value, B: value, C: value, D: value, E: value, F: value, G: value });
  };
  
  const hasChart = mergedChart && typeof mergedChart === "object";
  const hasDiagnostics = mergedDiagnostics && typeof mergedDiagnostics === "object" && !Array.isArray(mergedDiagnostics);
  const apiBase = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
  const exportChartUrl =
    jobId && apiBase
      ? `${apiBase}/v1/jobs/${encodeURIComponent(jobId)}/charts/matplotlib`
      : null;
  const specRecord = asRecord(summaryRecord?.spec);
  const profilingDetail = asRecord(summaryRecord?.profiling_detail);
  const analysisKind = String(specRecord?.kind ?? "");
  const rowCount = Number(
    overview?.row_count ?? profiling?.row_count_profiled ?? tableRows.length ?? 0,
  );
  const columnCount = Number(
    overview?.column_count ??
      profiling?.column_count ??
      (Array.isArray(profilingDetail?.column_profiles) ? profilingDetail.column_profiles.length : 0) ??
      0,
  );
  const metricsHint =
    analysisKind === "timeseries_forecast"
      ? locale === "vi"
        ? "Dự báo + chỉ số sai số"
        : "Forecast + error metrics"
      : locale === "vi"
        ? "Bảng kiểm định + biểu đồ"
        : "Tests + charts";
  const aiInsights = buildAiInsights(summary, locale);

  return (
    <div className="space-y-6">
      <section className="rounded-[1.5rem] border border-[var(--border)] bg-[var(--surface)] p-5 shadow-[0_10px_28px_rgba(22,22,21,0.05)] lg:p-6">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
            AI Copilot
          </h3>
          <span className="rounded-full border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-1 text-xs font-semibold text-[var(--fg)]">
            {locale === "vi" ? "Đọc từ output" : "Output-driven"}
          </span>
        </div>
        <p className="mt-3 text-base font-semibold text-[var(--fg)]">{aiInsights.headline}</p>
        <ul className="mt-3 space-y-2 text-sm leading-relaxed text-[var(--muted)]">
          {aiInsights.bullets.map((line, idx) => (
            <li key={`ai-line-${idx}`}>• {line}</li>
          ))}
        </ul>
      </section>

      <section className="rounded-[1.75rem] border border-[var(--border)] bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(243,242,238,0.96))] p-6 shadow-[0_14px_40px_rgba(22,22,21,0.06)] lg:p-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl space-y-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.3em] text-[var(--muted)]">
              {locale === "vi" ? "Tổng quan phân tích" : "Analysis overview"}
            </p>
            <h3 className="text-2xl font-semibold tracking-tight text-[var(--fg)] lg:text-3xl">
              {locale === "vi"
                ? "Kết quả được trình bày theo khối rõ ràng, dễ đọc"
                : "Results organized into clear, readable blocks"}
            </h3>
            <p className="max-w-2xl text-sm leading-relaxed text-[var(--muted)]">
              {locale === "vi"
                ? "Ưu tiên phần có ý nghĩa, giảm raw JSON và đẩy chi tiết kỹ thuật xuống phần mở rộng."
                : "Prioritizing meaningful output, reducing raw JSON, and moving technical details into expandable sections."}
            </p>
          </div>

          <div className="flex flex-wrap gap-2 lg:justify-end">
            <span className="rounded-full border border-[var(--border)] bg-white px-3 py-1 text-xs font-semibold text-[var(--fg)]">
              {analysisKind || (locale === "vi" ? "Chưa xác định" : "Unknown")}
            </span>
            <span className="rounded-full border border-[var(--border)] bg-white px-3 py-1 text-xs font-semibold text-[var(--fg)]">
              {metricsHint}
            </span>
          </div>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label={t("result.engine")}
            value={formatPrimitive(engine)}
            hint={locale === "vi" ? "Engine xử lý" : "Processing engine"}
          />
          <StatCard
            label={locale === "vi" ? "Phiên bản" : "Version"}
            value={formatPrimitive(version)}
            hint={locale === "vi" ? "Phiên bản output" : "Output version"}
          />
          <StatCard
            label={locale === "vi" ? "Dòng dữ liệu" : "Rows"}
            value={formatPrimitive(rowCount)}
            hint={locale === "vi" ? "Dòng đã nạp vào phân tích" : "Rows included in analysis"}
          />
          <StatCard
            label={locale === "vi" ? "Số cột" : "Columns"}
            value={formatPrimitive(columnCount)}
            hint={locale === "vi" ? "Cột trong file" : "Columns in the file"}
          />
        </div>
      </section>

      <section className="rounded-[1.5rem] border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm lg:p-5">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setShowTables((v) => !v)}
            className={`rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] transition ${
              showTables
                ? "border-[var(--fg)] bg-[var(--fg)] text-[var(--surface)]"
                : "border-[var(--border)] bg-white text-[var(--fg)] hover:bg-[var(--surface-muted)]"
            }`}
          >
            {locale === "vi" ? "Bảng" : "Tables"}
          </button>
          <button
            type="button"
            onClick={() => setShowCharts((v) => !v)}
            className={`rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] transition ${
              showCharts
                ? "border-[var(--fg)] bg-[var(--fg)] text-[var(--surface)]"
                : "border-[var(--border)] bg-white text-[var(--fg)] hover:bg-[var(--surface-muted)]"
            }`}
          >
            {locale === "vi" ? "Biểu đồ" : "Charts"}
          </button>
          <button
            type="button"
            onClick={() => setShowExportChart((v) => !v)}
            className={`rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] transition ${
              showExportChart
                ? "border-[var(--fg)] bg-[var(--fg)] text-[var(--surface)]"
                : "border-[var(--border)] bg-white text-[var(--fg)] hover:bg-[var(--surface-muted)]"
            }`}
          >
            {locale === "vi" ? "Ảnh xuất" : "Export preview"}
          </button>
          <button
            type="button"
            onClick={() => toggleAllModules(true)}
            className="rounded-full border border-[var(--border)] bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-[var(--fg)] transition hover:bg-[var(--surface-muted)]"
          >
            {locale === "vi" ? "Bật hết" : "Enable all"}
          </button>
          <button
            type="button"
            onClick={() => toggleAllModules(false)}
            className="rounded-full border border-[var(--border)] bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-[var(--fg)] transition hover:bg-[var(--surface-muted)]"
          >
            {locale === "vi" ? "Tắt hết" : "Disable all"}
          </button>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {(Object.keys(moduleData) as ModuleKey[]).map((k) => {
            const active = moduleVisibility[k];
            return (
              <button
                key={k}
                type="button"
                onClick={() =>
                  setModuleVisibility((prev) => ({ ...prev, [k]: !prev[k] }))
                }
                className={`rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.16em] transition ${
                  active
                    ? "border-[var(--accent)] bg-[var(--accent)] text-white"
                    : "border-[var(--border)] bg-[var(--surface-muted)] text-[var(--fg)] hover:bg-white"
                }`}
                title={moduleTitle(k, locale)}
              >
                {moduleTitle(k, locale)}
              </button>
            );
          })}
        </div>
      </section>

      {(showCharts || showExportChart) && (
        <div className="grid gap-6 xl:grid-cols-2">
          {showCharts && hasChart ? (
            <SectionCard title={locale === "vi" ? "Biểu đồ chính" : "Primary chart"}>
              <ChartView chart={mergedChart} />
            </SectionCard>
          ) : null}

          {showExportChart && exportChartUrl ? (
            <SectionCard title={locale === "vi" ? "Biểu đồ từ file xuất" : "Export preview"}>
              <div className="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface-muted)] p-3">
                <img
                  src={exportChartUrl}
                  alt={locale === "vi" ? "Biểu đồ matplotlib" : "Matplotlib chart"}
                  className="w-full rounded-xl object-contain"
                  loading="lazy"
                  onError={(e) => {
                    (e.currentTarget as HTMLImageElement).style.display = "none";
                  }}
                />
                <p className="mt-3 text-xs text-[var(--muted)]">
                  {locale === "vi"
                    ? "Nếu ảnh không hiển thị, dữ liệu hiện tại có thể chưa có cột số phù hợp để vẽ matplotlib."
                    : "If the image is missing, the current data may not have suitable numeric columns for matplotlib."}
                </p>
              </div>
            </SectionCard>
          ) : null}
        </div>
      )}

      {showTables && hasDiagnostics ? (
        <SectionCard title={locale === "vi" ? "Chẩn đoán nhanh" : "Quick diagnostics"}>
          <DiagnosticsBlock data={mergedDiagnostics as Record<string, unknown>} />
        </SectionCard>
      ) : null}

      {showTables &&
        enabledModules.map((moduleKey) => (
          <SectionCard key={moduleKey} title={moduleTitle(moduleKey, locale)}>
            {hasData(moduleData[moduleKey]) ? (
              <ObjectGrid data={moduleData[moduleKey]} />
            ) : (
              <p className="text-sm text-[var(--muted)]">
                {locale === "vi"
                  ? "Module này hiện chưa có dữ liệu từ kết quả phân tích hiện tại."
                  : "This module has no data in the current analysis result."}
              </p>
            )}
          </SectionCard>
        ))}

      {showTables && (
        <SectionCard title={t("result.tableHypothesis")}>
          <HypothesisTable rows={mergedHypothesisRows} />
        </SectionCard>
      )}

      {showTables && (
        <SectionCard
          title={
            locale === "vi"
              ? "Dữ liệu kỹ thuật mở rộng"
              : "Extended technical payload"
          }
        >
          <details>
            <summary className="cursor-pointer text-sm font-semibold text-[var(--accent)]">
              {locale === "vi"
                ? "Mở dữ liệu JSON đầy đủ"
                : "Open full JSON payload"}
            </summary>
            <div className="mt-4 overflow-auto rounded-2xl border border-[var(--border)] bg-[var(--surface-muted)] p-4">
              <pre className="min-w-[720px] whitespace-pre-wrap text-xs leading-relaxed text-[var(--fg)]">
                {JSON.stringify(summaryRecord ?? summary, null, 2)}
              </pre>
            </div>
          </details>
        </SectionCard>
      )}
    </div>
  );
}
