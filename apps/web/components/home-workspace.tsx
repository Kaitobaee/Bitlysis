"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { FilePreviewPanel } from "@/components/file-preview-panel";
import { LanguageSwitch } from "@/components/language-switch";
import { ResultSummary } from "@/components/result-summary";
import { UploadZone } from "@/components/upload-zone";
import {
  ApiClientError,
  getQuickChart,
  getJob,
  postExportZip,
  startAnalyze,
  startExportPhase,
  uploadFile,
} from "@/lib/api";
import { fullAutoAnalysisSpec } from "@/lib/analyze-default";
import { useI18n } from "@/lib/i18n";
import {
  isBusyStatus,
  isTerminalStatus,
  pollJobUntil,
  PollTimeoutError,
} from "@/lib/poll-job";
import { runFilePreview } from "@/lib/preview/run-preview";
import type { FilePreviewData } from "@/lib/preview/types";
import { toastApiError } from "@/lib/toast-error";
import type { JobDetail, JobStatus, QuickChartPayload } from "@/lib/types";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";

type ChartKind = QuickChartPayload["kind"];

type ChartOption = {
  kind: ChartKind;
  labelKey: string;
  descriptionKey: string;
  badge: string;
  accent: string;
};

const chartPalette = ["#0f766e", "#2563eb", "#dc2626", "#d97706", "#16a34a", "#7c3aed", "#0891b2", "#ea580c"];

const chartOptions: ChartOption[] = [
  { kind: "bar", labelKey: "job.chartTypeBar", descriptionKey: "job.chartDescBar", badge: "01", accent: "#0f766e" },
  { kind: "pie", labelKey: "job.chartTypePie", descriptionKey: "job.chartDescPie", badge: "02", accent: "#2563eb" },
  { kind: "line", labelKey: "job.chartTypeLine", descriptionKey: "job.chartDescLine", badge: "03", accent: "#7c3aed" },
  { kind: "area", labelKey: "job.chartTypeArea", descriptionKey: "job.chartDescArea", badge: "04", accent: "#d97706" },
  { kind: "donut", labelKey: "job.chartTypeDonut", descriptionKey: "job.chartDescDonut", badge: "05", accent: "#dc2626" },
];

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function statusLabel(t: (k: string) => string, s: JobStatus): string {
  const k = `status.${s}` as const;
  const out = t(k);
  return out === k ? s : out;
}

function chartKindLabel(t: (k: string) => string, kind: ChartKind): string {
  const labels: Record<ChartKind, string> = {
    bar: t("job.chartTypeBar"),
    pie: t("job.chartTypePie"),
    line: t("job.chartTypeLine"),
    area: t("job.chartTypeArea"),
    donut: t("job.chartTypeDonut"),
  };
  return labels[kind];
}

export function HomeWorkspace() {
  const { t } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [uploading, setUploading] = useState(false);
  const [busyAnalyze, setBusyAnalyze] = useState(false);
  const [busyExport, setBusyExport] = useState(false);
  const [filePreview, setFilePreview] = useState<FilePreviewData | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewFileLabel, setPreviewFileLabel] = useState<string | null>(null);
  const [selectedChartColumn, setSelectedChartColumn] = useState<string>("");
  const [chartBusy, setChartBusy] = useState(false);
  const [quickChart, setQuickChart] = useState<QuickChartPayload | null>(null);
  const pollAbortRef = useRef<AbortController | null>(null);

  const renderBarChart = (chart: QuickChartPayload) => {
    const max = Math.max(1, ...chart.values);
    return (
      <div className="space-y-3">
        {chart.labels.map((label, idx) => {
          const value = chart.values[idx] ?? 0;
          const width = Math.max(4, (value / max) * 100);
          return (
            <div key={`${label}-${idx}`} className="space-y-2">
              <div className="flex items-center justify-between gap-3 text-xs text-(--muted)">
                <span className="truncate font-medium text-(--fg)">{label}</span>
                <span className="font-semibold text-(--fg)">{value}</span>
              </div>
              <div className="h-3 w-full overflow-hidden rounded-full bg-(--surface-muted)">
                <div
                  className="h-full rounded-full transition-all duration-300"
                  style={{
                    width: `${width.toFixed(1)}%`,
                    background: "linear-gradient(90deg, #0f766e 0%, #2563eb 100%)",
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  const renderPieChart = (chart: QuickChartPayload, donut = false) => {
    const total = Math.max(1, chart.total);
    const colors = chartPalette;
    let acc = 0;
    const stops = chart.values.map((v, i) => {
      const start = (acc / total) * 100;
      acc += v;
      const end = (acc / total) * 100;
      return `${colors[i % colors.length]} ${start.toFixed(2)}% ${end.toFixed(2)}%`;
    });
    return (
      <div className="flex flex-wrap items-center gap-6">
        <div className="relative h-44 w-44 shrink-0 rounded-full border border-(--border) shadow-[0_18px_48px_rgba(0,0,0,0.08)]" style={{ background: `conic-gradient(${stops.join(", ")})` }}>
          {donut && (
            <div className="absolute inset-[22%] rounded-full border border-(--border) bg-(--surface) shadow-inner" />
          )}
        </div>
        <div className="min-w-55 flex-1 space-y-2 text-xs">
          {chart.labels.map((label, idx) => {
            const value = chart.values[idx] ?? 0;
            const pct = (value / total) * 100;
            return (
              <div key={`${label}-${idx}`} className="flex items-center justify-between gap-3 rounded-full border border-(--border) bg-(--surface) px-3 py-2">
                <span className="inline-flex min-w-0 items-center gap-2 truncate">
                  <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: colors[idx % colors.length] }} />
                  <span className="truncate font-medium text-(--fg)">{label}</span>
                </span>
                <span className="font-semibold text-(--fg)">{value} ({pct.toFixed(1)}%)</span>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const renderTrendChart = (chart: QuickChartPayload, filled: boolean) => {
    const width = 760;
    const height = 280;
    const left = 34;
    const right = 18;
    const top = 20;
    const bottom = 40;
    const plotWidth = width - left - right;
    const plotHeight = height - top - bottom;
    const max = Math.max(1, ...chart.values);
    const min = Math.min(...chart.values, 0);
    const range = Math.max(1, max - min);
    const points = chart.values.map((value, idx) => {
      const x = left + (chart.values.length === 1 ? plotWidth / 2 : (idx / (chart.values.length - 1)) * plotWidth);
      const normalized = (value - min) / range;
      const y = top + (1 - normalized) * plotHeight;
      return { x, y, value };
    });
    const linePath = points.map((point, idx) => `${idx === 0 ? "M" : "L"}${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" ");
    const lastPoint = points[points.length - 1] ?? { x: left, y: height - bottom };
    const firstPoint = points[0] ?? { x: left, y: height - bottom };
    const areaPath = `${linePath} L ${lastPoint.x.toFixed(1)} ${height - bottom} L ${firstPoint.x.toFixed(1)} ${height - bottom} Z`;

    return (
      <div className="space-y-4">
        <div className="overflow-hidden rounded-3xl border border-(--border) bg-[linear-gradient(180deg,rgba(15,118,110,0.08),rgba(255,255,255,0.92))] p-4 shadow-[0_18px_44px_rgba(15,23,42,0.08)]">
          <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" role="img" aria-label={chart.title}>
            <defs>
              <linearGradient id="trendLine" x1="0" x2="1" y1="0" y2="0">
                <stop offset="0%" stopColor="#0f766e" />
                <stop offset="55%" stopColor="#2563eb" />
                <stop offset="100%" stopColor="#7c3aed" />
              </linearGradient>
              <linearGradient id="trendArea" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="rgba(37,99,235,0.40)" />
                <stop offset="100%" stopColor="rgba(37,99,235,0.02)" />
              </linearGradient>
            </defs>
            {[0, 1, 2, 3].map((tick) => {
              const y = top + (tick / 3) * plotHeight;
              return <line key={tick} x1={left} x2={width - right} y1={y} y2={y} stroke="rgba(148,163,184,0.18)" strokeDasharray="4 6" />;
            })}
            <line x1={left} x2={width - right} y1={height - bottom} y2={height - bottom} stroke="rgba(15,23,42,0.28)" />
            <line x1={left} x2={left} y1={top} y2={height - bottom} stroke="rgba(15,23,42,0.18)" />
            {filled && <path d={areaPath} fill="url(#trendArea)" />}
            <path d={linePath} fill="none" stroke="url(#trendLine)" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
            {points.map((point, idx) => (
              <g key={`${chart.labels[idx] ?? idx}-${idx}`}>
                <circle cx={point.x} cy={point.y} r="6" fill="#fff" stroke={chartPalette[idx % chartPalette.length]} strokeWidth="4" />
                <text x={point.x} y={height - 12} textAnchor="middle" className="fill-(--muted) text-[11px] font-medium">
                  {chart.labels[idx]}
                </text>
                <text x={point.x} y={point.y - 14} textAnchor="middle" className="fill-(--fg) text-[11px] font-semibold">
                  {point.value}
                </text>
              </g>
            ))}
          </svg>
        </div>
      </div>
    );
  };

  const renderChart = (chart: QuickChartPayload) => {
    switch (chart.kind) {
      case "pie":
        return renderPieChart(chart, false);
      case "donut":
        return renderPieChart(chart, true);
      case "line":
        return renderTrendChart(chart, false);
      case "area":
        return renderTrendChart(chart, true);
      case "bar":
      default:
        return renderBarChart(chart);
    }
  };

  const syncUrlJob = useCallback(
    (id: string | null) => {
      const path = window.location.pathname;
      const next = new URLSearchParams(searchParams.toString());
      if (id) next.set("job", id);
      else next.delete("job");
      const q = next.toString();
      router.replace(q ? `${path}?${q}` : path);
    },
    [router, searchParams],
  );

  useEffect(() => {
    const id = searchParams.get("job");
    if (!id) return;
    let cancelled = false;
    getJob(id)
      .then((j) => {
        if (!cancelled) setJob(j);
      })
      .catch((e) => {
        if (!cancelled) {
          toastApiError(e, t, t("toast.pollErr"));
          if (e instanceof ApiClientError && e.status === 404) {
            syncUrlJob(null);
          }
        }
      });
    return () => {
      cancelled = true;
    };
  }, [searchParams, t, syncUrlJob]);

  const onUpload = useCallback(
    async (file: File) => {
      if (!apiBase.trim()) {
        toast.error(t("toast.uploadErr"), {
          description: t("errors.checkApiUrl"),
          duration: 12_000,
        });
        return;
      }
      setFilePreview(null);
      setPreviewFileLabel(file.name);
      setPreviewBusy(true);
      try {
        const prev = await runFilePreview(file);
        if (prev.ok) {
          setFilePreview(prev.data);
          if (prev.data.warnings.length > 0) {
            toast.message(t("preview.warnToast"), {
              description: prev.data.warnings.slice(0, 5).join("; "),
              duration: 8000,
            });
          }
        }
      } catch {
        /* preview best-effort */
      } finally {
        setPreviewBusy(false);
      }
      setUploading(true);
      try {
        const res = await uploadFile(file);
        const detail = await getJob(res.job_id);
        setJob(detail);
        syncUrlJob(res.job_id);
        toast.success(t("toast.uploadOk"));
      } catch (e) {
        if (e instanceof ApiClientError && e.apiCode === "rate_limited") {
          toast.error(t("toast.rateLimit"), { duration: 10_000 });
        } else {
          toastApiError(e, t, t("toast.uploadErr"));
        }
      } finally {
        setUploading(false);
      }
    },
    [syncUrlJob, t],
  );

  const onAnalyze = useCallback(async () => {
    if (!job) return;
    pollAbortRef.current?.abort();
    const ac = new AbortController();
    pollAbortRef.current = ac;
    setBusyAnalyze(true);
    try {
      await startAnalyze(job.job_id, fullAutoAnalysisSpec() as unknown as Record<string, unknown>);
      toast.success(t("toast.analyzeOk"));
      const final = await pollJobUntil(
        job.job_id,
        (j) => isTerminalStatus(j.status),
        {
          signal: ac.signal,
          onUpdate: setJob,
        },
      );
      setJob(final);
      if (final.status === "failed") {
        toast.error(final.error?.message ?? t("status.failed"));
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      if (e instanceof PollTimeoutError) {
        toast.error(t("toast.pollErr"), {
          description: t("errors.checkDocs"),
        });
        return;
      }
      toastApiError(e, t, t("toast.analyzeErr"));
    } finally {
      setBusyAnalyze(false);
    }
  }, [job, t]);

  const onExport = useCallback(async () => {
    if (!job) return;
    setBusyExport(true);
    try {
      const runPost = () => postExportZip(job.job_id);
      try {
        const blob = await runPost();
        triggerDownload(blob, `${job.job_id}_export.zip`);
        toast.success(t("toast.exportOk"));
      } catch (e) {
        if (
          e instanceof ApiClientError &&
          e.status === 409 &&
          e.details &&
          typeof e.details === "object" &&
          "code" in e.details &&
          (e.details as { code: string }).code ===
            "heavy_export_requires_export_phase"
        ) {
          await startExportPhase(job.job_id);
          const blob = await runPost();
          triggerDownload(blob, `${job.job_id}_export.zip`);
          toast.success(t("toast.exportOk"));
        } else {
          throw e;
        }
      }
      const j = await getJob(job.job_id);
      setJob(j);
    } catch (e) {
      toastApiError(e, t, t("toast.exportErr"));
    } finally {
      setBusyExport(false);
    }
  }, [job, t]);

  const onCreateChart = useCallback(async (chartType: ChartKind) => {
    if (!job || !selectedChartColumn) {
      toast.error(t("job.chartSelectColumn"));
      return;
    }
    setChartBusy(true);
    try {
      const chart = await getQuickChart(job.job_id, selectedChartColumn, chartType);
      setQuickChart(chart);
      toast.success(`${chartKindLabel(t, chartType)} ${t("job.chartCreated")}`);
    } catch (e) {
      toastApiError(e, t, t("toast.chartErr"));
    } finally {
      setChartBusy(false);
    }
  }, [job, selectedChartColumn, t]);

  const onReset = useCallback(() => {
    pollAbortRef.current?.abort();
    setJob(null);
    setFilePreview(null);
    setPreviewFileLabel(null);
    setQuickChart(null);
    setSelectedChartColumn("");
    syncUrlJob(null);
  }, [syncUrlJob]);

  const onCopyId = useCallback(() => {
    if (!job) return;
    void navigator.clipboard.writeText(job.job_id);
    toast.success(t("job.copied"));
  }, [job, t]);

  const showInlineSkeleton =
    job !== null &&
    (busyAnalyze || isBusyStatus(job.status)) &&
    !isTerminalStatus(job.status);

  const canRunAnalyze =
    job &&
    (job.status === "uploaded" || job.status === "failed") &&
    !busyAnalyze;

  return (
    <div className="swiss-page">
      <header className="swiss-container flex flex-col gap-6 border-b border-(--border) pb-10 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-serif text-4xl font-medium tracking-tight text-(--fg) sm:text-5xl">
            {t("app.title")}
          </h1>
          <p className="mt-4 max-w-xl text-base leading-relaxed text-(--muted)">
            {t("app.tagline")}
          </p>
        </div>
        <LanguageSwitch />
      </header>

      <main className="swiss-container grid gap-12 py-12 lg:grid-cols-2">
        <section className="space-y-6">
          <h2 className="text-label text-(--muted)">{t("upload.label")}</h2>
          <UploadZone disabled={uploading || previewBusy} onFile={onUpload} />
          <FilePreviewPanel
            preview={filePreview}
            busy={previewBusy}
            fileLabel={previewFileLabel}
          />
          {!apiBase.trim() && (
            <p className="border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              NEXT_PUBLIC_API_URL chưa đặt. {t("errors.checkApiUrl")}
            </p>
          )}
        </section>

        <section className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <h2 className="text-label text-(--muted)">{t("job.status")}</h2>
            <div className="flex flex-wrap gap-2">
              <a
                className="text-xs font-semibold uppercase tracking-wider text-(--accent) underline-offset-4 hover:underline"
                href={apiBase ? `${apiBase.replace(/\/$/, "")}/docs` : "#"}
                target="_blank"
                rel="noreferrer"
              >
                {t("job.openApi")}
              </a>
              {job && (
                <button
                  type="button"
                  onClick={onReset}
                  className="text-xs font-semibold uppercase tracking-wider text-(--muted) hover:text-(--fg)"
                >
                  {t("job.reset")}
                </button>
              )}
            </div>
          </div>

          {!job && (
            <p className="border border-(--border) bg-(--surface-muted) p-8 text-sm text-(--muted)">
              {t("result.empty")}
            </p>
          )}

          {job && (
            <div className="border border-(--border) bg-(--surface) p-8">
              <div className="flex flex-wrap items-baseline justify-between gap-4">
                <div>
                  <p className="text-label text-(--muted)">{t("job.id")}</p>
                  <p className="mt-1 font-mono text-sm break-all">{job.job_id}</p>
                </div>
                <button
                  type="button"
                  onClick={onCopyId}
                  className="shrink-0 border border-(--border) px-3 py-1.5 text-xs font-semibold uppercase tracking-wider hover:bg-(--surface-muted)"
                >
                  {t("job.copyId")}
                </button>
              </div>
              <dl className="mt-8 grid gap-6 sm:grid-cols-2">
                <div>
                  <dt className="text-label text-(--muted)">
                    {t("job.status")}
                  </dt>
                  <dd className="mt-2 flex items-center gap-2 text-lg font-semibold text-(--fg)">
                    {statusLabel(t, job.status)}
                    {isBusyStatus(job.status) && (
                      <span
                        className="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-(--accent)"
                        aria-hidden
                      />
                    )}
                  </dd>
                </div>
                <div>
                  <dt className="text-label text-(--muted)">
                    {t("job.filename")}
                  </dt>
                  <dd className="mt-2 text-sm text-(--fg)">{job.filename}</dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-label text-(--muted)">
                    {t("job.columns")}
                  </dt>
                  <dd className="mt-2 font-mono text-xs leading-relaxed text-(--fg)">
                    {job.columns.join(", ")}
                  </dd>
                </div>
                <div>
                  <dt className="text-label text-(--muted)">
                    {t("job.rowsSample")}
                  </dt>
                  <dd className="mt-2 font-mono text-sm">{job.row_preview_count}</dd>
                </div>
              </dl>

              {job.error && (
                <div className="mt-8 border border-red-200 bg-red-50 p-4 text-sm text-red-900">
                  <p className="font-semibold">{job.error.code}</p>
                  <p className="mt-1">{job.error.message}</p>
                </div>
              )}

              <div className="mt-8 flex flex-wrap gap-3">
                <button
                  type="button"
                  disabled={!canRunAnalyze}
                  onClick={onAnalyze}
                  className="border border-(--fg) bg-(--fg) px-5 py-2.5 text-sm font-semibold uppercase tracking-wider text-(--surface) disabled:cursor-not-allowed disabled:opacity-40 hover:opacity-90"
                >
                  {busyAnalyze ? t("job.analyzing") : t("job.analyzeFull")}
                </button>
                <button
                  type="button"
                  disabled={
                    busyExport || !job || job.status !== "succeeded"
                  }
                  onClick={onExport}
                  className="border border-(--border) bg-transparent px-5 py-2.5 text-sm font-semibold uppercase tracking-wider text-(--fg) disabled:cursor-not-allowed disabled:opacity-40 hover:bg-(--surface-muted)"
                >
                  {busyExport ? t("job.exporting") : t("job.exportZip")}
                </button>
              </div>
              {showInlineSkeleton && (
                <div
                  className="mt-8 space-y-3 border-t border-(--border) pt-8"
                  aria-busy="true"
                  aria-live="polite"
                >
                  <p className="text-label text-(--muted)">
                    {t("job.polling")}
                  </p>
                  <div className="h-2 w-full animate-pulse bg-(--skeleton)" />
                  <div className="h-2 w-4/5 animate-pulse bg-(--skeleton)" />
                  <div className="h-24 w-full animate-pulse bg-(--skeleton)" />
                </div>
              )}
            </div>
          )}

        </section>

        {job && job.status === "succeeded" && (
          <section className="space-y-6 lg:col-span-2">
            <div className="overflow-hidden rounded-[28px] border border-(--border) bg-[linear-gradient(180deg,rgba(245,242,235,0.96),rgba(255,255,255,0.94))] p-6 shadow-[0_24px_70px_rgba(15,23,42,0.06)]">
              <div className="space-y-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="space-y-2">
                    <h3 className="text-sm font-semibold uppercase tracking-[0.24em] text-(--muted)">{t("job.chartSectionTitle")}</h3>
                    <p className="max-w-2xl text-sm leading-relaxed text-(--muted)">{t("job.chartSectionSubtitle")}</p>
                  </div>
                  <div className="rounded-full border border-(--border) bg-(--surface) px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-(--muted)">
                    {t("job.chartCreate")}
                  </div>
                </div>
                <div className="grid gap-4 xl:grid-cols-[minmax(0,1.12fr)_minmax(280px,0.88fr)]">
                  <div className="rounded-3xl border border-(--border) bg-(--surface) p-4 shadow-[0_14px_36px_rgba(15,23,42,0.05)]">
                    <div className="mb-4 rounded-2xl border border-(--border) bg-(--surface-muted) px-4 py-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">{t("job.chartPanelTitle")}</p>
                      <p className="mt-1 text-sm text-(--muted)">{t("job.chartPanelHint")}</p>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-(--muted)">{t("job.chartStepPickColumn")}</p>
                        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">{t("job.chartColumnLabel")}</p>
                        <p className="mt-1 text-sm text-(--fg)">{selectedChartColumn || t("job.chartEmpty")}</p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <span className="rounded-full bg-[rgba(15,118,110,0.10)] px-3 py-1 text-xs font-semibold text-[#0f766e]">{quickChart?.kind ? chartKindLabel(t, quickChart.kind) : t("job.chartTypeBar")}</span>
                        {quickChart && <span className="rounded-full bg-[rgba(37,99,235,0.10)] px-3 py-1 text-xs font-semibold text-[#2563eb]">{quickChart.total} {t("job.chartTotal")}</span>}
                      </div>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-3">
                      <select
                        value={selectedChartColumn}
                        onChange={(e) => setSelectedChartColumn(e.target.value)}
                        className="min-w-55 rounded-2xl border border-(--border) bg-(--surface-muted) px-4 py-3 text-sm outline-none transition focus:border-(--fg)"
                      >
                        <option value="">Chọn cột...</option>
                        {job.columns.map((c) => (
                          <option key={c} value={c}>{c}</option>
                        ))}
                      </select>
                      <button
                        type="button"
                        disabled={chartBusy || !selectedChartColumn}
                        onClick={() => void onCreateChart("bar")}
                        className="rounded-2xl border border-(--fg) bg-(--fg) px-4 py-3 text-xs font-semibold uppercase tracking-[0.18em] text-(--surface) transition hover:-translate-y-px hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {chartBusy ? t("job.chartLoading") : t("job.chartCreate")}
                      </button>
                    </div>
                    <p className="mt-5 text-[11px] font-semibold uppercase tracking-[0.2em] text-(--muted)">{t("job.chartStepPickStyle")}</p>
                    <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                      {chartOptions.map((option) => {
                        const active = quickChart?.kind === option.kind;
                        return (
                          <button
                            key={option.kind}
                            type="button"
                            disabled={chartBusy || !selectedChartColumn}
                            onClick={() => void onCreateChart(option.kind)}
                            className={`group rounded-3xl border p-4 text-left transition ${active ? "border-transparent shadow-[0_16px_36px_rgba(15,23,42,0.12)]" : "border-(--border) bg-(--surface-muted) hover:-translate-y-0.5 hover:shadow-[0_10px_28px_rgba(15,23,42,0.08)]"} disabled:cursor-not-allowed disabled:opacity-50`}
                            style={{
                              background: active
                                ? `linear-gradient(180deg, ${option.accent} 0%, rgba(255,255,255,0.98) 72%)`
                                : undefined,
                            }}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] ${active ? "bg-white/90 text-(--fg)" : "bg-white text-(--muted)"}`}>{option.badge}</span>
                              <span className={`h-2.5 w-2.5 rounded-full ${active ? "bg-white" : "bg-(--border)"}`} />
                            </div>
                            <p className={`mt-4 text-sm font-semibold ${active ? "text-white" : "text-(--fg)"}`}>{t(option.labelKey)}</p>
                            <p className={`mt-1 text-xs leading-relaxed ${active ? "text-white/90" : "text-(--muted)"}`}>{t(option.descriptionKey)}</p>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div className="rounded-3xl border border-(--border) bg-(--surface) p-4 shadow-[0_14px_36px_rgba(15,23,42,0.05)]">
                    <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.2em] text-(--muted)">{t("job.chartStepPreview")}</p>
                    <div className="flex items-center justify-between gap-3 border-b border-(--border) pb-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">{quickChart?.title ?? t("job.chartSectionTitle")}</p>
                        <p className="mt-1 text-sm text-(--muted)">{quickChart ? quickChart.column : t("job.chartEmpty")}</p>
                      </div>
                      <div className="flex flex-wrap gap-2 text-xs">
                        {quickChart && (
                          <>
                            <span className="rounded-full border border-(--border) px-3 py-1 font-semibold text-(--fg)">{quickChart.total} {t("job.chartTotal")}</span>
                            <span className="rounded-full border border-(--border) px-3 py-1 font-semibold text-(--fg)">{Math.max(...quickChart.values, 0)} {t("job.chartPeak")}</span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="mt-4 min-h-72">
                      {chartBusy && !quickChart ? (
                        <div className="flex min-h-72 items-center justify-center rounded-3xl border border-dashed border-(--border) bg-(--surface-muted) text-sm text-(--muted)">
                          {t("job.chartLoading")}
                        </div>
                      ) : quickChart ? (
                        <div className="space-y-4">
                          <div className="rounded-3xl border border-(--border) bg-(--surface-muted) p-4">
                            {renderChart(quickChart)}
                          </div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-(--muted)">{t("job.chartStatsTitle")}</p>
                          <div className="grid gap-3 sm:grid-cols-3">
                            <div className="rounded-2xl border border-(--border) bg-(--surface-muted) px-4 py-3">
                              <p className="text-xs uppercase tracking-[0.2em] text-(--muted)">{t("job.chartTotal")}</p>
                              <p className="mt-1 text-lg font-semibold text-(--fg)">{quickChart.total}</p>
                            </div>
                            <div className="rounded-2xl border border-(--border) bg-(--surface-muted) px-4 py-3">
                              <p className="text-xs uppercase tracking-[0.2em] text-(--muted)">{t("job.chartPeak")}</p>
                              <p className="mt-1 text-lg font-semibold text-(--fg)">{Math.max(...quickChart.values, 0)}</p>
                            </div>
                            <div className="rounded-2xl border border-(--border) bg-(--surface-muted) px-4 py-3">
                              <p className="text-xs uppercase tracking-[0.2em] text-(--muted)">{t("job.chartPoints")}</p>
                              <p className="mt-1 text-lg font-semibold text-(--fg)">{quickChart.values.length}</p>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="flex min-h-72 items-center justify-center rounded-3xl border border-dashed border-(--border) bg-(--surface-muted) px-8 text-center text-sm text-(--muted)">
                          {t("job.chartEmpty")}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div className="border border-(--border) bg-(--surface) p-8">
              <h2 className="text-label mb-6 text-(--muted)">
                {t("result.title")}
              </h2>
              <ResultSummary
                summary={
                  job.result_summary as Record<string, unknown> | null
                }
              />
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
