"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { LanguageSwitch } from "@/components/language-switch";
import { ResultSummary } from "@/components/result-summary";
import { UploadZone } from "@/components/upload-zone";
import {
  analyzeWebInput,
  ApiClientError,
  chatWebAnalysis,
  getHealth,
  getQuickChart,
  getJob,
  postExportZip,
  uploadFile,
  startAnalyze,
  startExportPhase,
} from "@/lib/api";
import { fullAutoAnalysisSpec } from "@/lib/analyze-default";
import { useI18n } from "@/lib/i18n";
import {
  isBusyStatus,
  isTerminalStatus,
  pollJobUntil,
  PollTimeoutError,
} from "@/lib/poll-job";
import { toastApiError } from "@/lib/toast-error";
import type { HealthInfo, JobDetail, JobStatus, QuickChartPayload, WebAnalysisMode, WebAnalysisResponse } from "@/lib/types";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";

type ChartKind = QuickChartPayload["kind"];

type ChartOption = {
  kind: ChartKind;
  labelKey: string;
  descriptionKey: string;
  badge: string;
  accent: string;
};

type AnalysisModeOption = {
  value: WebAnalysisMode;
  title: string;
  description: string;
};

type MenuTool = {
  id?: string;
  label: string;
  action?: "scroll" | "analyze" | "export";
  disabled?: boolean;
  hint: string;
};

const chartPalette = ["#0f766e", "#2563eb", "#dc2626", "#d97706", "#16a34a", "#7c3aed", "#0891b2", "#ea580c"];

const chartOptions: ChartOption[] = [
  { kind: "bar", labelKey: "job.chartTypeBar", descriptionKey: "job.chartDescBar", badge: "01", accent: "#0f766e" },
  { kind: "pie", labelKey: "job.chartTypePie", descriptionKey: "job.chartDescPie", badge: "02", accent: "#2563eb" },
  { kind: "line", labelKey: "job.chartTypeLine", descriptionKey: "job.chartDescLine", badge: "03", accent: "#7c3aed" },
  { kind: "area", labelKey: "job.chartTypeArea", descriptionKey: "job.chartDescArea", badge: "04", accent: "#d97706" },
  { kind: "donut", labelKey: "job.chartTypeDonut", descriptionKey: "job.chartDescDonut", badge: "05", accent: "#dc2626" },
];

const analysisModeOptions: AnalysisModeOption[] = [
  {
    value: "academic",
    title: "Báo cáo học thuật",
    description: "Làm rõ cấu trúc, luận điểm, ngữ cảnh và các mốc nội dung chính.",
  },
  {
    value: "marketing_seo",
    title: "Marketing / SEO",
    description: "Nhấn keyword, intent, CTA, tiêu đề và cơ hội tối ưu chuyển đổi.",
  },
  {
    value: "business",
    title: "Phân tích business",
    description: "Tập trung insight, cơ hội, rủi ro và hành động ưu tiên.",
  },
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

function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const exp = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  const converted = value / 1024 ** exp;
  return `${converted.toFixed(exp === 0 ? 0 : 2)} ${units[exp]}`;
}

function formatDateTime(value: string | null): string {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

export function HomeWorkspace() {
  const { t } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [analyzingPrompt, setAnalyzingPrompt] = useState(false);
  const [busyAnalyze, setBusyAnalyze] = useState(false);
  const [busyExport, setBusyExport] = useState(false);
  const [selectedChartColumn, setSelectedChartColumn] = useState<string>("");
  const [chartBusy, setChartBusy] = useState(false);
  const [quickChart, setQuickChart] = useState<QuickChartPayload | null>(null);
  const [webAnalysis, setWebAnalysis] = useState<WebAnalysisResponse | null>(null);
  const [webAnalysisMode, setWebAnalysisMode] = useState<WebAnalysisMode>("business");
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const pollAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!apiBase.trim()) return;
    let cancelled = false;
    getHealth()
      .then((res) => {
        if (!cancelled) {
          setHealth(res);
          setHealthError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setHealth(null);
          setHealthError(err instanceof Error ? err.message : "health_check_failed");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

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

  const onAnalyzeWebsite = useCallback(
    async (value: string) => {
      if (!apiBase.trim()) {
        toast.error(t("toast.uploadErr"), {
          description: t("errors.checkApiUrl"),
          duration: 12_000,
        });
        return;
      }

      setAnalyzingPrompt(true);
      try {
        const result = await analyzeWebInput(value, webAnalysisMode);
        setWebAnalysis(result);
        toast.success(t("toast.analyzeOk"));
      } catch (error) {
        toastApiError(error, t, t("toast.analyzeErr"));
      } finally {
        setAnalyzingPrompt(false);
      }
    },
    [t, webAnalysisMode],
  );

  const onAskAssistant = useCallback(
    async (question: string) => {
      if (!webAnalysis) {
        throw new Error("analysis_missing");
      }
      if (!apiBase.trim()) {
        throw new Error(t("errors.checkApiUrl"));
      }
      setAnalyzingPrompt(true);
      try {
        const result = await chatWebAnalysis(webAnalysis, question);
        return result.answer;
      } finally {
        setAnalyzingPrompt(false);
      }
    },
    [t, webAnalysis],
  );

  const onUploadDataFile = useCallback(
    async (file: File) => {
      if (!apiBase.trim()) {
        toast.error(t("toast.uploadErr"), {
          description: t("errors.checkApiUrl"),
          duration: 12_000,
        });
        return;
      }

      try {
        const uploaded = await uploadFile(file);
        const latest = await getJob(uploaded.job_id);
        setWebAnalysis(null);
        setQuickChart(null);
        setSelectedChartColumn("");
        setJob(latest);
        syncUrlJob(uploaded.job_id);
        toast.success(t("toast.uploadOk"));
      } catch (e) {
        toastApiError(e, t, t("toast.uploadErr"));
      }
    },
    [t, syncUrlJob],
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
    setWebAnalysis(null);
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

  const scrollToSection = (sectionId: string) => {
    const element = document.getElementById(sectionId);
    if (!element) return;
    element.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const dangerScore = webAnalysis
    ? Math.max(0, Math.min(100, webAnalysis.fraud_score ?? 0))
    : 0;
  const safeFindings = webAnalysis && Array.isArray(webAnalysis.findings) ? webAnalysis.findings : [];
  const safeHighlights = webAnalysis && Array.isArray(webAnalysis.highlights) ? webAnalysis.highlights : [];
  const safeRecommendations = webAnalysis && Array.isArray(webAnalysis.recommendations) ? webAnalysis.recommendations : [];
  const safeEvidence = webAnalysis && Array.isArray(webAnalysis.evidence) ? webAnalysis.evidence : [];
  const safeSections = webAnalysis && Array.isArray(webAnalysis.sections) ? webAnalysis.sections : [];
  const safeDataFacts = webAnalysis && Array.isArray(webAnalysis.data_facts) ? webAnalysis.data_facts : [];
  const safeRelatedWebsites = webAnalysis && Array.isArray(webAnalysis.related_websites) ? webAnalysis.related_websites : [];
  const isContentAnalysis = webAnalysis?.source_type === "text";
  const tokenizeForRelevance = (text: string): string[] =>
    String(text ?? "")
      .toLowerCase()
      .split(/\s+/)
      .map((token) => token.replace(/[^a-z0-9à-ỹ]/gi, ""))
      .filter((token) => token.length >= 4);
  const referenceTokens = Array.from(
    new Set(tokenizeForRelevance(`${webAnalysis?.summary ?? ""} ${safeFindings.join(" ")}`)),
  ).slice(0, 18);
  const getSourceHost = (url: string): string => {
    try {
      return new URL(url).hostname.replace(/^www\./i, "");
    } catch {
      return url;
    }
  };
  const relatedArticleComparison = safeRelatedWebsites
    .map((site) => {
      const siteTokens = tokenizeForRelevance(`${site.title} ${site.summary ?? ""}`);
      const overlap = referenceTokens.filter((token) => siteTokens.includes(token)).length;
      const relevance = Math.min(
        100,
        25 + overlap * 12 + (site.summary ? 14 : 0) + (site.relation === "news" ? 12 : 0),
      );
      return {
        ...site,
        sourceHost: getSourceHost(site.url),
        overlap,
        relevance,
      };
    })
    .sort((a, b) => b.relevance - a.relevance)
    .slice(0, 6);
  const reportSummaryPoints = [
    webAnalysis?.summary || "Chưa có tóm tắt tổng quan.",
    safeFindings[0] || "Chưa có phát hiện chính từ AI.",
    `Đối chiếu được ${relatedArticleComparison.length} bài liên quan để tham chiếu nội dung.`,
  ];
  const factTypeCounts = safeDataFacts.reduce<Record<string, number>>((acc, item) => {
    const key = String(item.type ?? "other");
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});
  const factChartLabels = Object.keys(factTypeCounts);
  const factChartValues = factChartLabels.map((label) => factTypeCounts[label] ?? 0);
  
  // Helper: Check if chart data is valid and meaningful
  const isValidChartData = (labels: unknown[] | undefined, values: unknown[] | undefined): boolean => {
    if (!Array.isArray(labels) || !Array.isArray(values) || labels.length === 0 || values.length === 0) {
      return false;
    }
    // Must have same length
    if (labels.length !== values.length) {
      return false;
    }
    // Must have at least 2 items
    if (labels.length < 2) {
      return false;
    }
    // Values must be numbers and at least one should be > 0
    const numValues = values.map((v) => Number(v) || 0);
    const hasNonZeroValue = numValues.some((v) => v > 0);
    return hasNonZeroValue;
  };

  const analysisText = webAnalysis
    ? [
        String(webAnalysis.source_label ?? ""),
        String(webAnalysis.page_title ?? ""),
        String(webAnalysis.summary ?? ""),
        safeFindings.join(" "),
        safeSections
          .map((s) => `${String(s?.heading ?? "")} ${String(s?.snippet ?? "")}`)
          .join(" "),
      ]
        .join(" ")
        .toLowerCase()
    : "";
  const gamblingKeywords = [
    "casino",
    "ca cuoc",
    "cá cược",
    "bet",
    "poker",
    "bacarat",
    "blackjack",
    "slot",
    "nha cai",
    "nhà cái",
    "gambling",
    "lo de",
    "lô đề",
  ];
  const adultKeywords = [
    "18+",
    "adult",
    "sex",
    "porn",
    "nude",
    "xxx",
    "khiêu dâm",
    "nhạy cảm",
    "tình dục",
  ];
  const hasGamblingContent = gamblingKeywords.some((kw) => analysisText.includes(kw));
  const hasAdultContent = adultKeywords.some((kw) => analysisText.includes(kw));
  const showSensitiveWarning = hasGamblingContent || hasAdultContent;
  const screenshotSource = webAnalysis?.website_screenshot?.startsWith("data:image/png;base64,")
    ? "real"
    : webAnalysis?.website_screenshot
      ? "fallback"
      : null;
  const quickAction = safeRecommendations[0] ?? "Tiếp tục kiểm tra nội dung trước khi ra quyết định.";
  const evidenceStrength = Math.min(
    100,
    safeEvidence.length * 18 +
      safeSections.length * 6 +
      safeDataFacts.length * 4 +
      (webAnalysis?.cta_detected ? 8 : 0),
  );
  const confidenceScore = webAnalysis
    ? Math.max(25, Math.min(95, Math.round(30 + evidenceStrength * 0.55)))
    : 0;
  const confidenceLabel =
    confidenceScore >= 75
      ? "Độ tin cậy cao"
      : confidenceScore >= 50
        ? "Độ tin cậy trung bình"
        : "Độ tin cậy thấp";
  const riskBreakdown = [
    {
      label: "Nội dung nhạy cảm",
      score: hasGamblingContent || hasAdultContent ? Math.min(100, 65 + (hasGamblingContent && hasAdultContent ? 25 : 12)) : Math.round(dangerScore * 0.35),
      reason: hasGamblingContent || hasAdultContent ? "Có tín hiệu keyword nhạy cảm trong nội dung." : "Không thấy nhiều từ khóa nhạy cảm trực tiếp.",
    },
    {
      label: "CTA và hành vi dẫn dụ",
      score: webAnalysis?.cta_detected ? (String(webAnalysis.cta_detected.action_keyword ?? "").toLowerCase().includes("buy") ? 58 : 34) : 14,
      reason: webAnalysis?.cta_detected ? "Có CTA rõ ràng, cần kiểm tra mức minh bạch và ngữ cảnh." : "Không có CTA rõ ràng, mức rủi ro từ yếu tố này thấp.",
    },
    {
      label: "Thiếu bằng chứng",
      score: Math.max(0, 70 - Math.min(70, safeDataFacts.length * 10 + safeEvidence.length * 9)),
      reason: safeDataFacts.length || safeEvidence.length ? "Đã có một phần bằng chứng để đối chiếu." : "Thiếu mốc dữ liệu rõ ràng, cần xác minh thêm.",
    },
    {
      label: "Đánh giá tổng hợp AI",
      score: Math.round(dangerScore),
      reason: "Điểm tổng hợp sau khi kết hợp heuristic và AI.",
    },
  ];
  const menuTools: MenuTool[] = [
    { id: "tool-chat", label: t("job.menuChat"), action: "scroll", hint: t("job.menuChatHint") },
    { id: "tool-mode", label: t("job.menuMode"), action: "scroll", hint: t("job.menuModeHint") },
    { label: t("job.menuAnalyze"), action: "analyze", disabled: !canRunAnalyze, hint: t("job.menuAnalyzeHint") },
    { id: "tool-ai-output", label: t("job.menuRiskScore"), action: "scroll", hint: t("job.menuRiskScoreHint") },
    { id: "tool-ai-output", label: t("job.menuFindings"), action: "scroll", hint: t("job.menuFindingsHint") },
    { id: "tool-job", label: t("job.status"), action: "scroll", hint: t("job.menuAnalyzeHint") },
    { id: "tool-charts", label: t("job.chartSectionTitle"), action: "scroll", hint: t("job.chartSectionSubtitle") },
    { id: "tool-results", label: t("result.title"), action: "scroll", hint: t("result.highlights") },
    { id: "tool-backend", label: t("job.menuBackend"), action: "scroll", hint: t("job.menuBackendHint") },
    { label: t("job.menuExport"), action: "export", disabled: busyExport || !job || job.status !== "succeeded", hint: t("job.menuExportHint") },
  ];
  const dataSidebarTools: MenuTool[] = [
    { id: "tool-job", label: "Trạng thái job", action: "scroll", hint: "Xem tiến trình upload và phân tích" },
    { id: "tool-charts", label: "Khám phá biểu đồ", action: "scroll", hint: "Chọn cột để dựng biểu đồ" },
    { id: "tool-results", label: "Kết quả có cấu trúc", action: "scroll", hint: "Xem tóm tắt phân tích" },
    { id: "tool-backend", label: "Minh bạch backend", action: "scroll", hint: "Xem metadata và provenance" },
    { label: t("job.menuAnalyze"), action: "analyze", disabled: !canRunAnalyze, hint: t("job.menuAnalyzeHint") },
    { label: t("job.menuExport"), action: "export", disabled: busyExport || !job || job.status !== "succeeded", hint: t("job.menuExportHint") },
  ];
  const showDataWorkspace = Boolean(job) && !webAnalysis;
  const sidebarTools = showDataWorkspace ? dataSidebarTools : menuTools;
  const jobStatus = job?.status;

  return (
    <div className="swiss-page">
      <header className="swiss-container flex flex-col gap-4 border-b border-(--border) pb-6 sm:flex-row sm:items-end sm:justify-between">
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

      <main className="w-full space-y-0">
        <div className="swiss-container grid w-full items-start gap-6 py-6 lg:grid-cols-[280px_minmax(0,1fr)] xl:gap-8">
          <aside className="lg:sticky lg:top-4 lg:self-start lg:h-[calc(100vh-2rem)] lg:overflow-y-auto">
            <div className="rounded-3xl border border-(--border) bg-(--surface) p-4 shadow-[0_16px_38px_rgba(15,23,42,0.06)]">
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-(--muted)">
                {showDataWorkspace ? "Bảng điều hướng dữ liệu" : t("job.menuTitle")}
              </p>
              <p className="mt-1 text-xs text-(--muted)">
                {showDataWorkspace ? "Đi tới từng phần của quy trình phân tích" : t("job.menuSubtitle")}
              </p>

              <div className="mt-3 space-y-1.5">
                {sidebarTools.map((item, index) => (
                  <button
                    key={`${item.label}-${index}`}
                    type="button"
                    disabled={item.disabled}
                    onClick={() => {
                      if (item.action === "analyze") {
                        void onAnalyze();
                        return;
                      }
                      if (item.action === "export") {
                        void onExport();
                        return;
                      }
                      if (item.id) {
                        scrollToSection(item.id);
                      }
                    }}
                    className="flex w-full items-center justify-between rounded-2xl border border-(--border) bg-(--surface-muted) px-3 py-1.5 text-left text-sm text-(--fg) transition hover:-translate-y-px hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
                    title={item.hint}
                  >
                    <span className="font-medium">{item.label}</span>
                    <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-semibold text-(--muted)">{String(index + 1).padStart(2, "0")}</span>
                  </button>
                ))}
              </div>
            </div>
          </aside>

          <div className="min-w-0 w-full space-y-6">
            {showDataWorkspace && (
              <section className="rounded-3xl border border-(--border) bg-(--surface) p-4 shadow-[0_16px_38px_rgba(15,23,42,0.06)]">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.24em] text-(--muted)">Bảng điều khiển phân tích dữ liệu</p>
                    <p className="mt-1 text-sm text-(--muted)">Giao diện này đang ở chế độ xử lý Excel/CSV, không hiển thị sidebar web-analysis.</p>
                  </div>
                  <button
                    type="button"
                    onClick={onReset}
                    className="rounded-full border border-(--border) bg-(--surface-muted) px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-(--fg)"
                  >
                    Làm mới job
                  </button>
                </div>
                <div className="mt-4 grid gap-2 md:grid-cols-5">
                  {[
                    { title: "1. Upload", active: true },
                    { title: "2. Analyze", active: isBusyStatus(jobStatus ?? "uploaded") || jobStatus === "uploaded" },
                    { title: "3. Charts", active: jobStatus === "succeeded" },
                    { title: "4. Results", active: jobStatus === "succeeded" },
                    { title: "5. Backend", active: true },
                  ].map((step) => (
                    <div
                      key={step.title}
                      className={`rounded-2xl border px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] ${step.active ? "border-(--fg) bg-white text-(--fg)" : "border-(--border) bg-(--surface-muted) text-(--muted)"}`}
                    >
                      {step.title}
                    </div>
                  ))}
                </div>
              </section>
            )}
            <section className="rounded-3xl border border-(--border) bg-[linear-gradient(135deg,rgba(15,118,110,0.08),rgba(37,99,235,0.06),rgba(255,255,255,0.95))] p-4 sm:p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">
                Luồng phân tích Bitlysis
              </p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
                {[
                  "1. Nhập dữ liệu / nội dung",
                  "2. AI hỗ trợ & nhận diện rủi ro",
                  "3. Chạy pipeline thống kê",
                  "4. Khám phá biểu đồ",
                  "5. Kết quả + minh bạch backend",
                ].map((step) => (
                  <div key={step} className="rounded-2xl border border-(--border) bg-white/85 px-3 py-2 text-xs font-medium text-(--fg)">
                    {step}
                  </div>
                ))}
              </div>
            </section>
            <section id="tool-chat" className="w-full space-y-6 scroll-mt-6">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-(--muted)">Bước 1</p>
            <h2 className="text-label text-(--muted)">Nhập dữ liệu và làm việc với AI</h2>
          </div>
          <UploadZone
            disabled={analyzingPrompt}
            analysis={webAnalysis}
            onAnalyzePrompt={onAnalyzeWebsite}
            onAskAssistant={onAskAssistant}
            onUploadDataFile={onUploadDataFile}
          />

          <div id="tool-mode" className="space-y-3 rounded-2xl border border-(--border) bg-(--surface-muted) p-3.5 scroll-mt-6">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">Chọn phong cách phân tích</p>
            <div className="grid gap-2 sm:grid-cols-3">
              {analysisModeOptions.map((option) => {
                const active = webAnalysisMode === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setWebAnalysisMode(option.value)}
                    className={`rounded-2xl border px-3 py-3 text-left transition ${active ? "border-(--fg) bg-white shadow-sm" : "border-(--border) bg-(--surface) hover:-translate-y-px hover:bg-white"}`}
                  >
                    <div className="text-sm font-semibold text-(--fg)">{option.title}</div>
                    <div className="mt-1 text-xs leading-relaxed text-(--muted)">{option.description}</div>
                  </button>
                );
              })}
            </div>
          </div>

          {webAnalysis && (
            <div
              id="tool-ai-output"
              className={`space-y-4 rounded-2xl border bg-(--surface) p-4 ${
                showSensitiveWarning ? "border-red-300 shadow-[0_0_0_2px_rgba(239,68,68,0.15)]" : "border-(--border)"
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-(--border) pb-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-(--muted)">Bước 2</p>
                  <p className="text-sm font-semibold text-(--fg)">Tổng hợp AI hỗ trợ và nhận diện nội dung</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <span className="rounded-full border border-(--border) bg-(--surface-muted) px-3 py-1 text-xs font-semibold text-(--muted)">
                    AI Support Layer
                  </span>
                  <span className="rounded-full border border-(--border) bg-(--surface-muted) px-3 py-1 text-xs font-semibold text-(--muted)">
                    {confidenceLabel}
                  </span>
                </div>
              </div>

              {showSensitiveWarning && (
                <div className="rounded-xl border border-red-300 bg-red-50 px-3 py-2.5 text-red-900">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em]">Cảnh báo nội dung nhạy cảm</p>
                  <p className="mt-1.5 text-sm leading-relaxed">
                    {hasGamblingContent && hasAdultContent
                      ? "Hệ thống phát hiện nội dung liên quan đến đánh bạc và 18+. Người dùng nên thận trọng trước khi tương tác."
                      : hasGamblingContent
                        ? "Hệ thống phát hiện nội dung liên quan đến đánh bạc/cá cược. Người dùng nên thận trọng trước khi tương tác."
                        : "Hệ thống phát hiện nội dung 18+ hoặc nhạy cảm. Vui lòng cân nhắc trước khi tiếp tục."}
                  </p>
                </div>
              )}

              <div className="grid gap-3 xl:grid-cols-[1.35fr_0.65fr]">
                <div className="space-y-3">
                  <div className="rounded-xl border border-(--border) bg-(--surface-muted) p-3.5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">Tóm tắt website</p>
                        <p className="mt-2 text-sm leading-relaxed text-(--fg)">{webAnalysis.summary}</p>
                      </div>
                      <div className="min-w-40 rounded-lg border border-(--border) bg-(--surface) px-3 py-2">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-(--muted)">Hành động ưu tiên</p>
                        <p className="mt-1 text-sm leading-relaxed text-(--fg)">{quickAction}</p>
                      </div>
                    </div>
                  </div>

                  <div className="rounded-xl border border-(--border) bg-(--surface-muted) p-3.5">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">Website liên quan</p>
                      <span className="text-[11px] uppercase tracking-[0.16em] text-(--muted)">
                        {safeRelatedWebsites.length ? `${safeRelatedWebsites.length} mục` : "0 mục"}
                      </span>
                    </div>
                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      {safeRelatedWebsites.length ? (
                        safeRelatedWebsites.slice(0, 4).map((site, idx) => (
                          <div key={`${site.url}-${idx}`} className="rounded-lg border border-(--border) bg-(--surface) p-3">
                            <div className="text-sm font-semibold text-(--fg)">{site.title}</div>
                            <a
                              href={site.url}
                              target="_blank"
                              rel="noreferrer"
                              className="mt-1 block break-all text-xs text-(--muted) underline-offset-4 hover:underline"
                            >
                              {site.url}
                            </a>
                            {site.summary ? (
                              <p className="mt-1 text-xs leading-relaxed text-(--muted)">{site.summary}</p>
                            ) : null}
                            <div className="mt-1 text-[11px] uppercase tracking-[0.14em] text-(--muted)">{site.relation}</div>
                          </div>
                        ))
                      ) : (
                        <p className="text-sm text-(--muted)">Chưa trích xuất được website liên quan từ trang đang phân tích.</p>
                      )}
                    </div>
                  </div>

                  {isContentAnalysis && (
                    <div className="rounded-xl border border-(--border) bg-(--surface-muted) p-3.5">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">Tóm tắt báo cáo</p>
                      <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-(--fg)">
                        {reportSummaryPoints.map((point, idx) => (
                          <li key={`${point}-${idx}`}>{point}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                <div className="space-y-3">
                  <div className="rounded-xl border border-(--border) bg-(--surface-muted) p-3.5">
                    <div className="flex items-baseline justify-between gap-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">Mức độ nguy hiểm</p>
                      <span className="text-2xl font-bold text-(--fg)">{dangerScore.toFixed(1)}%</span>
                    </div>
                    <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-(--surface)">
                      <div
                        className={`h-full transition-all ${
                          dangerScore >= 70
                            ? "bg-red-500"
                            : dangerScore >= 40
                              ? "bg-amber-500"
                              : "bg-green-500"
                        }`}
                        style={{ width: `${dangerScore}%` }}
                      />
                    </div>
                    <div className="mt-2 text-xs text-(--muted)">
                      {dangerScore >= 70 ? "Nguy hiểm cao" : dangerScore >= 40 ? "Nguy hiểm trung bình" : "An toàn"}
                    </div>
                    <div className="mt-3 rounded-lg border border-(--border) bg-(--surface) p-2.5">
                      <div className="flex items-center justify-between text-xs text-(--muted)">
                        <span>Confidence</span>
                        <span className="font-semibold text-(--fg)">{confidenceScore}%</span>
                      </div>
                      <div className="mt-2 h-2 overflow-hidden rounded-full bg-(--surface-muted)">
                        <div
                          className="h-full bg-[linear-gradient(90deg,#0f766e_0%,#2563eb_100%)]"
                          style={{ width: `${confidenceScore}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                    <div className="rounded-xl border border-(--border) bg-(--surface-muted) p-3.5">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">Nguồn</p>
                      <p className="mt-2 text-sm font-medium text-(--fg)">{webAnalysis.source_label}</p>
                      <p className="mt-1 text-xs text-(--muted)">{webAnalysis.source_type}</p>
                    </div>
                    <div className="rounded-xl border border-(--border) bg-(--surface-muted) p-3.5">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">CTA</p>
                      {webAnalysis.cta_detected ? (
                        <div className="mt-2 space-y-1 text-sm text-(--fg)">
                          <div className="font-medium">{webAnalysis.cta_detected.text}</div>
                          <div className="text-xs text-(--muted)">
                            {webAnalysis.cta_detected.type} · {webAnalysis.cta_detected.action_keyword}
                          </div>
                        </div>
                      ) : (
                        <p className="mt-2 text-sm text-(--muted)">Không phát hiện CTA rõ ràng.</p>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {isContentAnalysis && (
                <div className="rounded-xl border border-(--border) bg-(--surface-muted) p-3.5">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">Bảng so sánh bài báo liên quan</p>
                    <span className="text-[11px] uppercase tracking-[0.16em] text-(--muted)">
                      {relatedArticleComparison.length ? `${relatedArticleComparison.length} bài` : "0 bài"}
                    </span>
                  </div>
                  {relatedArticleComparison.length ? (
                    <div className="mt-2 overflow-x-auto">
                      <table className="min-w-full border-separate border-spacing-y-2 text-sm">
                        <thead>
                          <tr className="text-left text-xs uppercase tracking-[0.14em] text-(--muted)">
                            <th className="px-3 py-1.5">Bài báo</th>
                            <th className="px-3 py-1.5">Nguồn</th>
                            <th className="px-3 py-1.5">Tóm tắt</th>
                            <th className="px-3 py-1.5">Mức phù hợp</th>
                          </tr>
                        </thead>
                        <tbody>
                          {relatedArticleComparison.map((item, idx) => (
                            <tr key={`${item.url}-${idx}`} className="rounded-lg bg-(--surface)">
                              <td className="rounded-l-lg border border-(--border) px-3 py-2 align-top">
                                <a
                                  href={item.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="font-semibold text-(--fg) underline-offset-4 hover:underline"
                                >
                                  {item.title}
                                </a>
                              </td>
                              <td className="border-y border-(--border) px-3 py-2 align-top text-(--muted)">{item.sourceHost}</td>
                              <td className="border-y border-(--border) px-3 py-2 align-top text-(--fg)">
                                {item.summary || "Chưa có tóm tắt cho bài báo này."}
                              </td>
                              <td className="rounded-r-lg border border-(--border) px-3 py-2 align-top">
                                <div className="font-semibold text-(--fg)">{item.relevance}%</div>
                                <div className="mt-1 h-1.5 w-20 overflow-hidden rounded-full bg-(--surface-muted)">
                                  <div className="h-full bg-[linear-gradient(90deg,#0f766e_0%,#2563eb_100%)]" style={{ width: `${item.relevance}%` }} />
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-(--muted)">Chưa có bài báo để so sánh. Hãy nhập nội dung chi tiết hơn để hệ thống tìm nguồn liên quan.</p>
                  )}
                </div>
              )}

              <div className="rounded-xl border border-(--border) bg-(--surface-muted) p-3.5">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">Breakdown rủi ro</p>
                <div className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                  {riskBreakdown.map((item) => (
                    <div key={item.label} className="rounded-lg border border-(--border) bg-(--surface) p-3">
                      <div className="flex items-center justify-between gap-3 text-sm">
                        <span className="font-medium text-(--fg)">{item.label}</span>
                        <span className="font-semibold text-(--fg)">{item.score}%</span>
                      </div>
                      <div className="mt-2 h-2 overflow-hidden rounded-full bg-(--surface-muted)">
                        <div
                          className="h-full bg-[linear-gradient(90deg,#d97706_0%,#dc2626_100%)]"
                          style={{ width: `${Math.max(2, Math.min(100, item.score))}%` }}
                        />
                      </div>
                      <p className="mt-2 text-xs leading-relaxed text-(--muted)">{item.reason}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-(--border) bg-(--surface-muted) p-3.5">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">AI findings</p>
                  <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-(--fg)">
                    {safeFindings.slice(0, 4).map((item, idx) => (
                      <li key={`${item}-${idx}`}>{item}</li>
                    ))}
                  </ul>
                </div>

                <div className="rounded-xl border border-(--border) bg-(--surface-muted) p-3.5">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">Điểm nổi bật</p>
                  <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-(--fg)">
                    {safeHighlights.length ? (
                      safeHighlights.slice(0, 4).map((item, idx) => <li key={`${item}-${idx}`}>{item}</li>)
                    ) : (
                      <li className="list-none text-(--muted)">Chưa có highlight bổ sung.</li>
                    )}
                  </ul>
                </div>

                <div className="rounded-xl border border-(--border) bg-(--surface-muted) p-3.5">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">Bằng chứng</p>
                  <div className="mt-2 space-y-2">
                    {safeEvidence.length ? (
                      safeEvidence.slice(0, 4).map((item, idx) => (
                        <div key={`${item.label}-${idx}`} className="rounded-lg border border-(--border) bg-(--surface) p-3">
                          <div className="text-sm font-semibold text-(--fg)">{item.label}</div>
                          <div className="mt-1 text-xs leading-relaxed text-(--muted)">{item.detail}</div>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-(--muted)">Chưa có bằng chứng từ phân tích.</p>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-(--border) bg-(--surface-muted) p-3.5">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">AI sections</p>
                  <div className="mt-2 space-y-2">
                    {safeSections.slice(0, 3).map((section, idx) => (
                      <div key={`${section.heading}-${idx}`} className="rounded-lg border border-(--border) bg-(--surface) p-3">
                        <div className="font-semibold text-(--fg)">{section.heading}</div>
                        <div className="mt-1 text-xs leading-relaxed text-(--muted)">{section.snippet}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {webAnalysis.website_screenshot && (
                <div className="overflow-hidden rounded-2xl border border-(--border) bg-(--surface-muted) p-3.5">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">Ảnh đại diện website</p>
                      <p className="mt-1 text-sm text-(--fg)">Ảnh chụp toàn trang để người dùng nhận diện nhanh giao diện thật.</p>
                    </div>
                    <span className="rounded-full border border-(--border) bg-(--surface) px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-(--muted)">
                      {screenshotSource === "real" ? "real capture" : "fallback preview"}
                    </span>
                  </div>
                  <img
                    src={webAnalysis.website_screenshot}
                    alt={`Ảnh chụp website ${webAnalysis.source_label}`}
                    className="mt-3 w-full rounded-xl border border-(--border) object-cover shadow-[0_12px_30px_rgba(15,23,42,0.08)]"
                  />
                </div>
              )}

            </div>
          )}

          {!apiBase.trim() && (
            <p className="border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              NEXT_PUBLIC_API_URL chưa đặt. {t("errors.checkApiUrl")}
            </p>
          )}
        </section>

        {job && (
          <section id="tool-job" className="w-full space-y-6 rounded-3xl border border-(--border) bg-(--surface) p-4 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-(--muted)">Bước 3</p>
                <h2 className="text-label text-(--muted)">Chạy pipeline phân tích dữ liệu</h2>
              </div>
              <div className="flex flex-wrap gap-2">
                <a
                  className="text-xs font-semibold uppercase tracking-wider text-(--accent) underline-offset-4 hover:underline"
                  href={apiBase ? `${apiBase.replace(/\/$/, "")}/docs` : "#"}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t("job.openApi")}
                </a>
                <button
                  type="button"
                  onClick={onReset}
                  className="text-xs font-semibold uppercase tracking-wider text-(--muted) hover:text-(--fg)"
                >
                  {t("job.reset")}
                </button>
              </div>
            </div>

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
          </section>
        )}
          {job && (
            <section id="tool-backend" className="w-full rounded-[28px] border border-(--border) bg-(--surface) p-5 shadow-[0_18px_48px_rgba(15,23,42,0.06)]">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-(--muted)">Bước 5B</p>
                  <h3 className="text-sm font-semibold uppercase tracking-[0.24em] text-(--muted)">{t("job.backendTitle")}</h3>
                  <p className="mt-1 max-w-3xl text-sm text-(--muted)">{t("job.backendSubtitle")}</p>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${health?.status === "ok" ? "bg-[rgba(22,163,74,0.12)] text-[#166534]" : "bg-[rgba(220,38,38,0.12)] text-[#991b1b]"}`}>
                  {t("job.backendHealth")}: {health?.status ?? (healthError ? "error" : "-")}
                </span>
              </div>

              <div className="mt-4 grid gap-3 lg:grid-cols-3">
                <div className="rounded-2xl border border-(--border) bg-(--surface-muted) p-3.5 text-sm">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">{t("job.backendHealth")}</p>
                  <div className="mt-2 space-y-1 text-(--fg)">
                    <p>status: {health?.status ?? "-"}</p>
                    <p>service: {health?.service ?? "-"}</p>
                    <p>api: {apiBase || "-"}</p>
                  </div>
                </div>

                <div className="rounded-2xl border border-(--border) bg-(--surface-muted) p-3.5 text-sm lg:col-span-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">{t("job.backendMeta")}</p>
                  <div className="mt-2 grid gap-2 text-(--fg) sm:grid-cols-2 xl:grid-cols-3">
                    <p>{t("job.backendPath")}: {job.stored_path}</p>
                    <p>{t("job.backendSize")}: {formatBytes(job.size_bytes)}</p>
                    <p>{t("job.backendUploadedAt")}: {formatDateTime(job.uploaded_at)}</p>
                    <p>{t("job.backendUpdatedAt")}: {formatDateTime(job.status_updated_at)}</p>
                    <p>{t("job.backendManifest")}: {job.manifest_stored_as ?? "-"}</p>
                    <p>{t("job.backendExport")}: {job.export_stored_as ?? "-"}</p>
                  </div>
                  {job.error && (
                    <div className="mt-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-900">
                      <p>{t("job.backendErrorCode")}: {job.error.code}</p>
                      <p>{t("job.backendErrorMessage")}: {job.error.message}</p>
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-4 grid gap-3 lg:grid-cols-3">
                <details className="rounded-2xl border border-(--border) bg-(--surface-muted) p-3.5">
                  <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">analysis_spec</summary>
                  <pre className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap text-xs text-(--fg)">{JSON.stringify(job.analysis_spec ?? {}, null, 2)}</pre>
                </details>
                <details className="rounded-2xl border border-(--border) bg-(--surface-muted) p-3.5">
                  <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">profiling</summary>
                  <pre className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap text-xs text-(--fg)">{JSON.stringify(job.profiling ?? {}, null, 2)}</pre>
                </details>
                <details className="rounded-2xl border border-(--border) bg-(--surface-muted) p-3.5">
                  <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.2em] text-(--muted)">{t("job.backendRaw")}</summary>
                  <pre className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap text-xs text-(--fg)">{JSON.stringify(job.result_summary ?? {}, null, 2)}</pre>
                </details>
              </div>
            </section>
          )}
        </div>

        {job && job.status === "succeeded" && (
          <div className="lg:col-start-2">
            <section id="tool-charts" className="w-full border-t border-(--border) py-8 lg:py-10">
            <div className="w-full overflow-hidden rounded-[28px] border border-(--border) bg-[linear-gradient(180deg,rgba(245,242,235,0.96),rgba(255,255,255,0.94))] p-5 shadow-[0_24px_70px_rgba(15,23,42,0.06)]">
              <div className="space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-[0.24em] text-(--muted)">Bước 4</p>
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
            </section>
            <section id="tool-results" className="w-full bg-(--surface) p-6 lg:p-8">
              <div className="mb-6 max-w-screen px-0 lg:px-8">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-(--muted)">Bước 5A</p>
                <h2 className="text-label text-(--muted)">{t("result.title")}</h2>
                <p className="mt-2 text-sm text-(--muted)">
                  Lớp kết quả này phản ánh trực tiếp pipeline phân tích dữ liệu của Bitlysis, không thay thế bằng tường thuật AI.
                </p>
              </div>
              <div className="px-0 lg:px-8">
                <ResultSummary
                  jobId={job.job_id}
                  summary={
                    job.result_summary as Record<string, unknown> | null
                  }
                />
              </div>
            </section>
          </div>
        )}
          </div>
      </main>
    </div>
  );
}
