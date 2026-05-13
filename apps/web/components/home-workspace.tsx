"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import lottie, { type AnimationItem } from "lottie-web";
import { toast } from "sonner";

import { AcademicResult } from "@/components/academic-result";
import { LanguageSwitch } from "@/components/language-switch";
import { ResultSummary } from "@/components/result-summary";
import { UploadZone } from "@/components/upload-zone";
import {
  analyzeWebInput,
  ApiClientError,
  chatWebAnalysis,
  getJob,
  getQuickChart,
  postExportZip,
  startAnalyze,
  startExportPhase,
  uploadFile,
} from "@/lib/api";
import { comprehensiveAnalysisSpec } from "@/lib/analyze-default";
import { useI18n } from "@/lib/i18n";
import {
  isBusyStatus,
  isTerminalStatus,
  PollTimeoutError,
  pollJobUntil,
} from "@/lib/poll-job";
import { toastApiError } from "@/lib/toast-error";
import type {
  AcademicAnalyzeResponse,
  JobDetail,
  JobStatus,
  QuickChartPayload,
  WebAnalysisMode,
  WebAnalysisResponse,
} from "@/lib/types";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";

type ChartKind = QuickChartPayload["kind"];

const copy = {
  en: {
    home: "Home",
    title: "Analysis workspace",
    subtitle:
      "Ask, upload, and read the result as explanation first. Evidence, charts, and technical detail stay available when you need them.",
    apiTitle: "Analysis API is not configured",
    apiText:
      "Set NEXT_PUBLIC_API_URL to enable uploads and live analysis. The workspace shell is still available for review.",
    modeLabel: "Analysis lens",
    modes: {
      academic: ["Academic", "Structure, claims, sources, and learning context."],
      marketing_seo: ["Website", "Content structure, audience intent, and page signals."],
      business: ["Business", "Key findings, opportunities, and next actions."],
    },
    status: "Status",
    source: "Source",
    columns: "Columns",
    rows: "Sample rows",
    analyze: "Generate explanation",
    analyzing: "Understanding source...",
    export: "Download package",
    exporting: "Preparing package...",
    reset: "Start new analysis",
    copyId: "Copy reference",
    copied: "Reference copied",
    retry: "Try again",
    explanation: "AI Summary",
    overview: "Result Overview",
    whyMethod: "Why this method was selected",
    rationale: "Rationale",
    assumptionsApplied: "Assumptions applied",
    notable: "Notable Results / Metrics",
    factCheck: "Fact Check",
    conclusion: "Conclusion",
    screenshot: "Website Capture",
    viewMore: "View more results",
    findings: "Key Findings",
    interpretation: "Suggested Interpretation",
    evidence: "Supporting Evidence",
    confidence: "Confidence & Limits",
    nextSteps: "Suggested Next Steps",
    charts: "Charts & Visuals",
    technical: "Technical Details",
    emptyTitle: "Bring Bitlysis something to understand",
    emptyText:
      "Start with a spreadsheet, URL, document excerpt, survey result, or analysis question. The first answer will be written for a human reader.",
    noEvidence: "No explicit evidence has been returned yet. Ask Bitlysis to show supporting evidence.",
    noFindings: "Run an analysis to reveal key findings.",
    interpretationText:
      "Treat this as a guided reading, not a final verdict. Use the evidence below to decide what needs a closer look.",
    confidenceText:
      "Bitlysis explains what it can infer from the available source. Review source quality, missing context, and any technical assumptions before acting.",
    nextStepItems: [
      "Ask Bitlysis to explain the most confusing point.",
      "Open supporting evidence before sharing the result.",
      "Use charts or technical details only when you need deeper inspection.",
    ],
    progress: [
      "Reading your source",
      "Finding patterns",
      "Checking supporting evidence",
      "Preparing a plain-language explanation",
    ],
    chartHelp: "Create a quick chart only after the explanation is clear.",
    chartColumn: "Column",
    chartType: "View",
    chartCreate: "Create chart",
    chartEmpty: "Choose a column to generate a supporting visual.",
    advancedSummary: "Open analysis payload and processing metadata",
    jobProcessing:
      "The analysis engine is working. You can leave this page open while Bitlysis prepares the explanation.",
    methodExplanation:
      "Bitlysis chooses the analysis path from the file structure, available column types, missing values, and the methods supported by the current pipeline. This keeps the first reading focused on what the data can support.",
    defaultConclusion:
      "Use this as a first draft for understanding. Review the supporting evidence before adding the result to a report.",
  },
  vi: {
    home: "Trang chủ",
    title: "Không gian phân tích",
    subtitle:
      "Hỏi, tải lên và đọc kết quả dưới dạng giải thích trước. Bằng chứng, biểu đồ và chi tiết kỹ thuật vẫn có khi bạn cần.",
    apiTitle: "API phân tích chưa được cấu hình",
    apiText:
      "Đặt NEXT_PUBLIC_API_URL để bật upload và phân tích thật. Giao diện workspace vẫn có thể xem trước.",
    modeLabel: "Góc nhìn phân tích",
    modes: {
      academic: ["Học thuật", "Cấu trúc, luận điểm, nguồn và ngữ cảnh học tập."],
      marketing_seo: ["Website", "Cấu trúc nội dung, intent người đọc và tín hiệu trang."],
      business: ["Kinh doanh", "Phát hiện chính, cơ hội và hành động tiếp theo."],
    },
    status: "Trạng thái",
    source: "Nguồn",
    columns: "Cột",
    rows: "Dòng mẫu",
    analyze: "Tạo giải thích",
    analyzing: "Đang hiểu nguồn...",
    export: "Tải gói kết quả",
    exporting: "Đang chuẩn bị gói...",
    reset: "Phân tích mới",
    copyId: "Sao chép mã tham chiếu",
    copied: "Đã sao chép mã tham chiếu",
    retry: "Thử lại",
    explanation: "Tóm tắt AI",
    overview: "Tổng quan kết quả",
    whyMethod: "Vì sao chọn phương pháp này",
    rationale: "Lý do chọn",
    assumptionsApplied: "Giả định đã áp dụng",
    notable: "Kết quả / metrics đáng chú ý",
    factCheck: "Fact check",
    conclusion: "Kết luận",
    screenshot: "Ảnh trang web",
    viewMore: "Xem thêm kết quả",
    findings: "Phát hiện chính",
    interpretation: "Diễn giải gợi ý",
    evidence: "Bằng chứng hỗ trợ",
    confidence: "Độ tin cậy & giới hạn",
    nextSteps: "Bước tiếp theo",
    charts: "Biểu đồ & trực quan",
    technical: "Chi tiết kỹ thuật",
    emptyTitle: "Đưa cho Bitlysis một nguồn cần hiểu",
    emptyText:
      "Bắt đầu với bảng tính, URL, đoạn tài liệu, kết quả khảo sát hoặc câu hỏi phân tích. Câu trả lời đầu tiên sẽ viết cho người đọc.",
    noEvidence: "Chưa có bằng chứng rõ ràng. Hãy hỏi Bitlysis hiển thị bằng chứng hỗ trợ.",
    noFindings: "Chạy phân tích để xem các phát hiện chính.",
    interpretationText:
      "Hãy xem đây là phần đọc có hướng dẫn, không phải kết luận cuối cùng. Dùng bằng chứng bên dưới để quyết định điểm nào cần xem kỹ.",
    confidenceText:
      "Bitlysis giải thích điều có thể suy ra từ nguồn hiện có. Hãy kiểm tra chất lượng nguồn, ngữ cảnh còn thiếu và giả định kỹ thuật trước khi hành động.",
    nextStepItems: [
      "Hỏi Bitlysis giải thích điểm khó hiểu nhất.",
      "Mở bằng chứng hỗ trợ trước khi chia sẻ kết quả.",
      "Chỉ dùng biểu đồ hoặc chi tiết kỹ thuật khi cần kiểm tra sâu hơn.",
    ],
    progress: [
      "Đang đọc nguồn của bạn",
      "Đang tìm mẫu đáng chú ý",
      "Đang kiểm tra bằng chứng hỗ trợ",
      "Đang chuẩn bị giải thích dễ hiểu",
    ],
    chartHelp: "Chỉ tạo biểu đồ nhanh sau khi phần giải thích đã rõ.",
    chartColumn: "Cột",
    chartType: "Kiểu xem",
    chartCreate: "Tạo biểu đồ",
    chartEmpty: "Chọn một cột để tạo trực quan hỗ trợ.",
    advancedSummary: "Mở payload phân tích và metadata xử lý",
    jobProcessing:
      "Bộ máy phân tích đang xử lý. Bạn có thể giữ trang này mở trong lúc Bitlysis chuẩn bị phần giải thích.",
    methodExplanation:
      "Bitlysis chọn hướng phân tích dựa trên cấu trúc file, loại cột, dữ liệu thiếu và các phương pháp mà pipeline hiện hỗ trợ. Cách này giúp phần đọc đầu tiên tập trung vào điều dữ liệu thật sự có thể nói.",
    defaultConclusion:
      "Hãy xem đây là bản nháp đầu tiên để hiểu kết quả. Trước khi đưa vào báo cáo, nên kiểm tra thêm bằng chứng hỗ trợ.",
  },
} as const;

const chartKinds: ChartKind[] = ["bar", "pie", "line", "area", "donut"];
type WorkspaceLabels = (typeof copy)["en"] | (typeof copy)["vi"];

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 100);
}

function statusLabel(status: JobStatus): string {
  return status.replace(/_/g, " ");
}

function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const exp = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  const converted = value / 1024 ** exp;
  return `${converted.toFixed(exp === 0 ? 0 : 1)} ${units[exp]}`;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") return JSON.stringify(item);
      return "";
    })
    .filter(Boolean)
    .slice(0, 6);
}

function firstString(...values: unknown[]): string {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
}

function formatPrimitive(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 4 });
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function metricRows(value: unknown): Array<{ label: string; value: string }> {
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        const row = asRecord(item);
        if (!row) return null;
        const label = firstString(row.label, row.metric, row.name, row.key);
        const metricValue = row.value ?? row.count ?? row.total ?? row.score;
        return label ? { label, value: formatPrimitive(metricValue) } : null;
      })
      .filter((row): row is { label: string; value: string } => row !== null)
      .slice(0, 6);
  }

  const record = asRecord(value);
  if (!record) return [];
  return Object.entries(record)
    .filter(([, rowValue]) => rowValue !== null && rowValue !== undefined && typeof rowValue !== "object")
    .slice(0, 6)
    .map(([label, rowValue]) => ({ label: label.replace(/_/g, " "), value: formatPrimitive(rowValue) }));
}

function buildJobInsight(job: JobDetail | null, locale: "en" | "vi") {
  const summary = asRecord(job?.result_summary);
  const results = asRecord(summary?.results);
  const academic = asRecord(summary?.academic_summary);
  const profiling = asRecord(summary?.profiling);
  const overview = asRecord(profiling?.overview) ?? profiling;
  const rowCount = overview?.row_count ?? profiling?.row_count_profiled ?? job?.row_preview_count;
  const columnCount = overview?.column_count ?? job?.columns.length;
  const headline = firstString(
    summary?.ai_summary,
    summary?.summary,
    results?.summary,
    locale === "vi"
      ? "Bitlysis đã chuẩn bị một phần đọc có cấu trúc từ nguồn này."
      : "Bitlysis has prepared a structured reading of this source.",
  );
  const findings = [
    ...stringList(summary?.highlights),
    ...stringList(summary?.findings),
    ...stringList(results?.highlights),
  ];
  const methodRationale = firstString(academic?.rationale, summary?.rationale, results?.rationale);
  const methodAssumptions = [
    ...stringList(academic?.assumptions),
    ...stringList(summary?.assumptions),
    ...stringList(results?.assumptions),
  ];
  const fallbackFindings =
    job && findings.length === 0
      ? [
          locale === "vi"
            ? `${job.filename} có ${columnCount ?? "-"} cột và ${rowCount ?? "-"} dòng mẫu đã đọc.`
            : `${job.filename} includes ${columnCount ?? "-"} columns and ${rowCount ?? "-"} profiled sample rows.`,
          locale === "vi"
            ? `Trạng thái hiện tại: ${statusLabel(job.status)}.`
            : `Current status: ${statusLabel(job.status)}.`,
        ]
      : findings;

  return {
    headline,
    methodRationale,
    methodAssumptions: Array.from(new Set(methodAssumptions)).slice(0, 6),
    findings: fallbackFindings.slice(0, 5),
    metrics: [
      { label: locale === "vi" ? "Số cột" : "Columns", value: formatPrimitive(columnCount) },
      { label: locale === "vi" ? "Dòng mẫu" : "Sample rows", value: formatPrimitive(rowCount) },
      { label: locale === "vi" ? "Trạng thái" : "Status", value: job ? statusLabel(job.status) : "-" },
      ...metricRows(summary?.metrics).slice(0, 3),
    ],
  };
}

function ProgressAnalysis({ messages }: { messages: readonly string[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const animation: AnimationItem = lottie.loadAnimation({
      container: containerRef.current,
      renderer: "svg",
      loop: true,
      autoplay: true,
      path: "/animations/json/loading.json",
    });
    return () => animation.destroy();
  }, []);

  return (
    <div className="rounded-[24px] border border-(--border) bg-(--surface) p-4" aria-live="polite" aria-busy="true">
      <div className="flex items-center gap-4">
        <div ref={containerRef} className="h-16 w-16 motion-reduce:hidden" />
        <div className="hidden h-12 w-12 rounded-full border border-(--border) bg-(--accent-soft) motion-reduce:block" />
        <div className="space-y-1">
          {messages.map((message) => (
            <p key={message} className="text-sm text-(--muted)">
              {message}
            </p>
          ))}
        </div>
      </div>
    </div>
  );
}

function InsightCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-[24px] border border-(--border) bg-(--surface) p-5 shadow-[0_12px_32px_rgba(15,23,42,0.04)]">
      <h2 className="text-label text-(--accent)">{title}</h2>
      <div className="mt-3 text-sm leading-relaxed text-(--fg)">{children}</div>
    </section>
  );
}

function WebInsightReport({
  analysis,
  labels,
}: {
  analysis: WebAnalysisResponse;
  labels: WorkspaceLabels;
}) {
  const metrics = metricRows(analysis.metrics);
  const notable = [...analysis.highlights, ...analysis.findings].slice(0, 4);

  return (
    <div className="space-y-4">
      <InsightCard title={labels.overview}>
        <p>{analysis.summary}</p>
      </InsightCard>

      <InsightCard title={labels.notable}>
        <div className="grid gap-3 md:grid-cols-2">
          {metrics.map((metric) => (
            <div key={`${metric.label}-${metric.value}`} className="rounded-2xl bg-(--surface-muted) p-3">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-(--muted)">{metric.label}</p>
              <p className="mt-1 text-base font-semibold">{metric.value}</p>
            </div>
          ))}
          {notable.map((item) => (
            <p key={item} className="rounded-2xl bg-(--surface-muted) p-3">{item}</p>
          ))}
          {!metrics.length && !notable.length ? <p>{labels.noFindings}</p> : null}
        </div>
      </InsightCard>

      <InsightCard title={labels.conclusion}>
        <p>{labels.defaultConclusion}</p>
      </InsightCard>

      {analysis.website_screenshot ? (
        <InsightCard title={labels.screenshot}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={analysis.website_screenshot}
            alt={labels.screenshot}
            className="max-h-[720px] w-full rounded-2xl border border-(--border) object-contain"
          />
        </InsightCard>
      ) : null}

      <details className="rounded-[24px] border border-(--border) bg-(--surface) p-5">
        <summary className="cursor-pointer font-semibold text-(--accent)">{labels.viewMore}</summary>
        <div className="mt-5 space-y-4">
          <InsightCard title={labels.findings}>
            {analysis.findings.length || analysis.highlights.length ? (
              <ul className="space-y-2">
                {[...analysis.highlights, ...analysis.findings].slice(0, 8).map((item) => (
                  <li key={item} className="rounded-2xl bg-(--surface-muted) px-3 py-2">
                    {item}
                  </li>
                ))}
              </ul>
            ) : (
              <p>{labels.noFindings}</p>
            )}
          </InsightCard>
          <InsightCard title={labels.evidence}>
            {analysis.evidence.length ? (
              <ul className="space-y-2">
                {analysis.evidence.slice(0, 8).map((item) => (
                  <li key={`${item.label}-${item.detail}`} className="rounded-2xl border border-(--border) p-3">
                    <strong className="block text-(--fg)">{item.label}</strong>
                    <span className="text-(--muted)">{item.detail}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p>{labels.noEvidence}</p>
            )}
          </InsightCard>
          <InsightCard title={labels.confidence}>
            <p>{labels.confidenceText}</p>
          </InsightCard>
          <InsightCard title={labels.nextSteps}>
            <ul className="space-y-2">
              {labels.nextStepItems.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </InsightCard>
        </div>
      </details>
    </div>
  );
}

function AcademicBriefReport({
  result,
  labels,
}: {
  result: AcademicAnalyzeResponse;
  labels: WorkspaceLabels;
}) {
  const supportPct = Math.round(result.overall_support_score * 100);
  const checkedFacts = result.fact_checks.slice(0, 4);

  return (
    <div className="space-y-4">
      <InsightCard title={labels.overview}>
        <p>{result.summary}</p>
      </InsightCard>
      <InsightCard title={labels.notable}>
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-2xl bg-(--surface-muted) p-3">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-(--muted)">Papers</p>
            <p className="mt-1 text-base font-semibold">{result.papers.length}</p>
          </div>
          <div className="rounded-2xl bg-(--surface-muted) p-3">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-(--muted)">Support</p>
            <p className="mt-1 text-base font-semibold">{supportPct}%</p>
          </div>
          <div className="rounded-2xl bg-(--surface-muted) p-3">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-(--muted)">Keywords</p>
            <p className="mt-1 text-base font-semibold">{result.keywords.length}</p>
          </div>
        </div>
      </InsightCard>
      <InsightCard title={labels.factCheck}>
        {checkedFacts.length ? (
          <ul className="space-y-2">
            {checkedFacts.map((fact) => (
              <li key={fact.claim} className="rounded-2xl bg-(--surface-muted) p-3">
                <strong className="block">{fact.verdict.replace(/_/g, " ")}</strong>
                <span className="text-(--muted)">{fact.claim}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p>{labels.noEvidence}</p>
        )}
      </InsightCard>
      <InsightCard title={labels.conclusion}>
        <p>{labels.defaultConclusion}</p>
      </InsightCard>
      <details className="rounded-[24px] border border-(--border) bg-(--surface) p-5">
        <summary className="cursor-pointer font-semibold text-(--accent)">{labels.viewMore}</summary>
        <div className="mt-5">
          <AcademicResult result={result} />
        </div>
      </details>
    </div>
  );
}

function QuickChartView({ chart }: { chart: QuickChartPayload }) {
  const max = Math.max(1, ...chart.values);
  return (
    <div className="space-y-3">
      <div>
        <h3 className="font-semibold">{chart.title}</h3>
        <p className="text-sm text-(--muted)">{chart.column}</p>
      </div>
      {chart.labels.map((label, index) => {
        const value = chart.values[index] ?? 0;
        const width = `${Math.max(4, (value / max) * 100).toFixed(1)}%`;
        return (
          <div key={`${label}-${index}`} className="space-y-1">
            <div className="flex justify-between gap-3 text-xs">
              <span className="truncate">{label}</span>
              <span className="font-semibold">{value}</span>
            </div>
            <div className="h-2 rounded-full bg-(--surface-muted)">
              <div className="h-full rounded-full bg-(--accent)" style={{ width }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function HomeWorkspace() {
  const { locale } = useI18n();
  const labels = copy[locale];
  const router = useRouter();
  const searchParams = useSearchParams();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [webAnalysis, setWebAnalysis] = useState<WebAnalysisResponse | null>(null);
  const [webAnalysisMode, setWebAnalysisMode] = useState<WebAnalysisMode>("business");
  const [academicResult, setAcademicResult] = useState<AcademicAnalyzeResponse | null>(null);
  const [busyAnalyze, setBusyAnalyze] = useState(false);
  const [busyPrompt, setBusyPrompt] = useState(false);
  const [busyExport, setBusyExport] = useState(false);
  const [selectedChartColumn, setSelectedChartColumn] = useState("");
  const [selectedChartKind, setSelectedChartKind] = useState<ChartKind>("bar");
  const [quickChart, setQuickChart] = useState<QuickChartPayload | null>(null);
  const [chartBusy, setChartBusy] = useState(false);
  const pollAbortRef = useRef<AbortController | null>(null);

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
      .then((latest) => {
        if (!cancelled) setJob(latest);
      })
      .catch((error) => {
        if (!cancelled) {
          toastApiError(error, (key) => key, "Could not read analysis status.");
          if (error instanceof ApiClientError && error.status === 404) {
            syncUrlJob(null);
          }
        }
      });
    return () => {
      cancelled = true;
    };
  }, [searchParams, syncUrlJob]);

  const onAnalyzeWebsite = useCallback(
    async (value: string) => {
      if (!apiBase.trim()) {
        toast.error(labels.apiTitle, { description: labels.apiText, duration: 12_000 });
        return;
      }

      setBusyPrompt(true);
      try {
        const result = await analyzeWebInput(value, webAnalysisMode);
        setWebAnalysis(result);
        setJob(null);
        setAcademicResult(null);
        setQuickChart(null);
      } catch (error) {
        toastApiError(error, (key) => key, "Could not analyze this source.");
      } finally {
        setBusyPrompt(false);
      }
    },
    [labels.apiText, labels.apiTitle, webAnalysisMode],
  );

  const onAskAssistant = useCallback(
    async (question: string) => {
      if (!webAnalysis) throw new Error("analysis_missing");
      if (!apiBase.trim()) throw new Error(labels.apiText);
      setBusyPrompt(true);
      try {
        const result = await chatWebAnalysis(webAnalysis, question);
        return result.answer;
      } finally {
        setBusyPrompt(false);
      }
    },
    [labels.apiText, webAnalysis],
  );

  const onUploadDataFile = useCallback(
    async (file: File) => {
      if (!apiBase.trim()) {
        toast.error(labels.apiTitle, { description: labels.apiText, duration: 12_000 });
        return;
      }

      try {
        const uploaded = await uploadFile(file);
        const latest = await getJob(uploaded.job_id);
        setJob(latest);
        setWebAnalysis(null);
        setAcademicResult(null);
        setQuickChart(null);
        setSelectedChartColumn("");
        syncUrlJob(uploaded.job_id);
        pollAbortRef.current?.abort();
        const ac = new AbortController();
        pollAbortRef.current = ac;
        setBusyAnalyze(true);
        await startAnalyze(
          uploaded.job_id,
          comprehensiveAnalysisSpec() as unknown as Record<string, unknown>,
        );
        const final = await pollJobUntil(
          uploaded.job_id,
          (nextJob) => isTerminalStatus(nextJob.status),
          {
            signal: ac.signal,
            onUpdate: setJob,
          },
        );
        setJob(final);
        if (final.status === "failed") {
          toast.error(final.error?.message ?? "Analysis failed.");
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        if (error instanceof PollTimeoutError) {
          toast.error("Could not finish polling analysis status.");
          return;
        }
        toastApiError(error, (key) => key, "Upload failed.");
      } finally {
        setBusyAnalyze(false);
      }
    },
    [labels.apiText, labels.apiTitle, syncUrlJob],
  );

  const onAnalyze = useCallback(async () => {
    if (!job) return;
    pollAbortRef.current?.abort();
    const ac = new AbortController();
    pollAbortRef.current = ac;
    setBusyAnalyze(true);
    try {
      await startAnalyze(
        job.job_id,
        comprehensiveAnalysisSpec() as unknown as Record<string, unknown>,
      );
      const final = await pollJobUntil(job.job_id, (latest) => isTerminalStatus(latest.status), {
        signal: ac.signal,
        onUpdate: setJob,
      });
      setJob(final);
      if (final.status === "failed") {
        toast.error(final.error?.message ?? "Analysis failed.");
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      if (error instanceof PollTimeoutError) {
        toast.error("Could not finish polling analysis status.");
        return;
      }
      toastApiError(error, (key) => key, "Could not start analysis.");
    } finally {
      setBusyAnalyze(false);
    }
  }, [job]);

  const onExport = useCallback(async () => {
    if (!job) return;
    setBusyExport(true);
    try {
      const runPost = () => postExportZip(job.job_id);
      try {
        const blob = await runPost();
        triggerDownload(blob, `${job.job_id}_export.zip`);
      } catch (error) {
        if (
          error instanceof ApiClientError &&
          error.status === 409 &&
          error.details &&
          typeof error.details === "object" &&
          "code" in error.details &&
          (error.details as { code: string }).code === "heavy_export_requires_export_phase"
        ) {
          await startExportPhase(job.job_id);
          const blob = await runPost();
          triggerDownload(blob, `${job.job_id}_export.zip`);
        } else {
          throw error;
        }
      }
      const latest = await getJob(job.job_id);
      setJob(latest);
    } catch (error) {
      toastApiError(error, (key) => key, "Could not prepare export.");
    } finally {
      setBusyExport(false);
    }
  }, [job]);

  const onCreateChart = useCallback(async () => {
    if (!job || !selectedChartColumn) return;
    setChartBusy(true);
    try {
      const chart = await getQuickChart(job.job_id, selectedChartColumn, selectedChartKind);
      setQuickChart(chart);
    } catch (error) {
      toastApiError(error, (key) => key, "Could not create chart.");
    } finally {
      setChartBusy(false);
    }
  }, [job, selectedChartColumn, selectedChartKind]);

  const onReset = useCallback(() => {
    pollAbortRef.current?.abort();
    setJob(null);
    setWebAnalysis(null);
    setAcademicResult(null);
    setQuickChart(null);
    setSelectedChartColumn("");
    syncUrlJob(null);
  }, [syncUrlJob]);

  const onCopyId = useCallback(() => {
    if (!job) return;
    void navigator.clipboard.writeText(job.job_id);
    toast.success(labels.copied);
  }, [job, labels.copied]);

  const showProgress =
    busyAnalyze ||
    busyPrompt ||
    (job !== null && isBusyStatus(job.status) && !isTerminalStatus(job.status));
  const canRunAnalyze =
    job && (job.status === "uploaded" || job.status === "failed") && !busyAnalyze;
  const jobInsight = buildJobInsight(job, locale);

  return (
    <div className="min-h-screen bg-(--page-bg) text-(--fg)">
      <header className="sticky top-0 z-20 border-b border-(--border) bg-[rgba(250,249,246,0.9)] backdrop-blur">
        <div className="mx-auto flex min-h-18 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link href="/" className="flex items-center gap-3 font-black uppercase tracking-[0.08em]">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-(--fg) text-(--surface)">
              B
            </span>
            Bitlysis
          </Link>
          <div className="flex items-center gap-3">
            <Link href="/" className="hidden text-sm font-semibold text-(--muted) hover:text-(--fg) sm:inline">
              {labels.home}
            </Link>
            <LanguageSwitch />
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(360px,0.82fr)_minmax(0,1.18fr)] lg:px-8">
        <aside className="space-y-5 lg:sticky lg:top-24 lg:self-start">
          <section className="rounded-[28px] border border-(--border) bg-(--surface) p-5 shadow-[0_18px_48px_rgba(15,23,42,0.05)]">
            <div className="flex items-start justify-between gap-5">
              <div>
                <p className="text-label text-(--accent)">{labels.modeLabel}</p>
                <h1 className="mt-3 text-3xl font-semibold tracking-tight">{labels.title}</h1>
                <p className="mt-3 text-sm leading-relaxed text-(--muted)">{labels.subtitle}</p>
              </div>
              <Image
                src="/svg/robot-researching.svg"
                alt=""
                width={96}
                height={96}
                className="hidden h-20 w-20 object-contain opacity-80 sm:block"
              />
            </div>

            {!apiBase.trim() ? (
              <div className="mt-5 rounded-2xl border border-[rgba(146,64,14,0.28)] bg-[rgba(251,191,36,0.12)] p-4 text-sm text-(--amber-fg)">
                <strong>{labels.apiTitle}</strong>
                <p className="mt-1 leading-relaxed">{labels.apiText}</p>
              </div>
            ) : null}

          </section>

          <UploadZone
            disabled={!apiBase.trim()}
            analysis={webAnalysis}
            analysisMode={webAnalysisMode}
            onAnalysisModeChange={setWebAnalysisMode}
            onAnalyzePrompt={onAnalyzeWebsite}
            onAskAssistant={onAskAssistant}
            onUploadDataFile={onUploadDataFile}
            onAcademicResult={setAcademicResult}
          />
        </aside>

        <div className="space-y-5">
          {showProgress ? <ProgressAnalysis messages={labels.progress} /> : null}

          {!webAnalysis && !job && !academicResult ? (
            <section className="relative overflow-hidden rounded-[32px] border border-dashed border-(--border) bg-(--surface) p-8 shadow-[0_18px_48px_rgba(15,23,42,0.04)]">
              <div className="max-w-xl">
                <p className="text-label text-(--accent)">{labels.explanation}</p>
                <h2 className="mt-3 text-3xl font-semibold tracking-tight">{labels.emptyTitle}</h2>
                <p className="mt-3 text-sm leading-relaxed text-(--muted)">{labels.emptyText}</p>
              </div>
              <Image
                src="/svg/mascot-talking.svg"
                alt=""
                width={260}
                height={260}
                className="pointer-events-none ml-auto mt-6 h-44 w-44 object-contain opacity-80 sm:absolute sm:bottom-0 sm:right-4 sm:mt-0"
              />
            </section>
          ) : null}

          {webAnalysis ? <WebInsightReport analysis={webAnalysis} labels={labels} /> : null}

          {academicResult ? <AcademicBriefReport result={academicResult} labels={labels} /> : null}

          {job ? (
            <div className="space-y-5">
              <section className="rounded-[28px] border border-(--border) bg-(--surface) p-5 shadow-[0_18px_48px_rgba(15,23,42,0.05)]">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <p className="text-label text-(--accent)">{labels.source}</p>
                    <h2 className="mt-2 text-2xl font-semibold tracking-tight">{job.filename}</h2>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs">
                      <span className="rounded-full bg-(--surface-muted) px-3 py-1">
                        {labels.status}: {statusLabel(job.status)}
                      </span>
                      <span className="rounded-full bg-(--surface-muted) px-3 py-1">
                        {formatBytes(job.size_bytes)}
                      </span>
                      <span className="rounded-full bg-(--surface-muted) px-3 py-1">
                        {labels.columns}: {job.columns.length}
                      </span>
                      <span className="rounded-full bg-(--surface-muted) px-3 py-1">
                        {labels.rows}: {job.row_preview_count}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={!canRunAnalyze}
                      onClick={() => void onAnalyze()}
                      className="rounded-full border border-[#161615] bg-[#0f766e] px-4 py-2 text-xs font-black uppercase tracking-[0.12em] text-white disabled:opacity-40"
                    >
                      {busyAnalyze ? labels.analyzing : labels.analyze}
                    </button>
                    <button
                      type="button"
                      disabled={busyExport || job.status !== "succeeded"}
                      onClick={() => void onExport()}
                      className="rounded-full border border-[#161615] bg-[#f6f0e6] px-4 py-2 text-xs font-black uppercase tracking-[0.12em] text-[#161615] disabled:opacity-40"
                    >
                      {busyExport ? labels.exporting : labels.export}
                    </button>
                    <button
                      type="button"
                      onClick={onCopyId}
                      className="rounded-full border border-[#161615] bg-[#f6f0e6] px-4 py-2 text-xs font-black uppercase tracking-[0.12em] text-[#161615]"
                    >
                      {labels.copyId}
                    </button>
                    <button
                      type="button"
                      onClick={onReset}
                      className="rounded-full border border-[#161615] bg-[#f6f0e6] px-4 py-2 text-xs font-black uppercase tracking-[0.12em] text-[#161615]"
                    >
                      {labels.reset}
                    </button>
                  </div>
                </div>

                {job.error ? (
                  <div className="mt-5 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">
                    <strong>{job.error.code}</strong>
                    <p className="mt-1">{job.error.message}</p>
                    <button
                      type="button"
                      disabled={busyAnalyze}
                      onClick={() => void onAnalyze()}
                      className="mt-3 rounded-full border border-[#161615] bg-[#0f766e] px-4 py-2 text-xs font-black uppercase tracking-[0.12em] text-white disabled:opacity-40"
                    >
                      {labels.retry}
                    </button>
                  </div>
                ) : null}

                {isBusyStatus(job.status) && !isTerminalStatus(job.status) ? (
                  <p className="mt-5 rounded-2xl bg-(--surface-muted) p-4 text-sm leading-relaxed text-(--muted)">
                    {labels.jobProcessing}
                  </p>
                ) : null}
              </section>

              <InsightCard title={labels.overview}>
                <p>{jobInsight.headline}</p>
              </InsightCard>

              <InsightCard title={labels.whyMethod}>
                <div className="space-y-4">
                  <div>
                    <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-(--muted)">
                      {labels.rationale}
                    </h3>
                    <p className="mt-2">
                      {jobInsight.methodRationale || labels.methodExplanation}
                    </p>
                  </div>
                  {jobInsight.methodAssumptions.length ? (
                    <div>
                      <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-(--muted)">
                        {labels.assumptionsApplied}
                      </h3>
                      <ul className="mt-2 space-y-1">
                        {jobInsight.methodAssumptions.map((assumption) => (
                          <li key={assumption}>• {assumption}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              </InsightCard>

              <InsightCard title={labels.notable}>
                <div className="grid gap-3 md:grid-cols-2">
                  {jobInsight.metrics.map((metric) => (
                    <div key={`${metric.label}-${metric.value}`} className="rounded-2xl bg-(--surface-muted) p-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-(--muted)">{metric.label}</p>
                      <p className="mt-1 text-base font-semibold">{metric.value}</p>
                    </div>
                  ))}
                  {jobInsight.findings.slice(0, 3).map((finding) => (
                    <p key={finding} className="rounded-2xl bg-(--surface-muted) p-3">{finding}</p>
                  ))}
                </div>
              </InsightCard>

              <InsightCard title={labels.conclusion}>
                <p>{labels.defaultConclusion}</p>
              </InsightCard>

              <InsightCard title={labels.charts}>
                <p className="mb-4 text-(--muted)">{labels.chartHelp}</p>
                {job.status === "succeeded" ? (
                  <div className="space-y-4">
                    <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto]">
                      <label className="space-y-1 text-xs font-semibold uppercase tracking-[0.14em] text-(--muted)">
                        {labels.chartColumn}
                        <select
                          value={selectedChartColumn}
                          onChange={(event) => setSelectedChartColumn(event.target.value)}
                          className="block min-h-11 w-full rounded-2xl border border-(--border) bg-(--surface-muted) px-3 text-sm font-normal normal-case tracking-normal text-(--fg) outline-none"
                        >
                          <option value="">{labels.chartEmpty}</option>
                          {job.columns.map((column) => (
                            <option key={column} value={column}>
                              {column}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="space-y-1 text-xs font-semibold uppercase tracking-[0.14em] text-(--muted)">
                        {labels.chartType}
                        <select
                          value={selectedChartKind}
                          onChange={(event) => setSelectedChartKind(event.target.value as ChartKind)}
                          className="block min-h-11 rounded-2xl border border-(--border) bg-(--surface-muted) px-3 text-sm font-normal normal-case tracking-normal text-(--fg) outline-none"
                        >
                          {chartKinds.map((kind) => (
                            <option key={kind} value={kind}>
                              {kind}
                            </option>
                          ))}
                        </select>
                      </label>
                      <button
                        type="button"
                        disabled={chartBusy || !selectedChartColumn}
                        onClick={() => void onCreateChart()}
                        className="self-end rounded-full border border-[#161615] bg-[#0f766e] px-4 py-3 text-xs font-black uppercase tracking-[0.12em] text-white disabled:opacity-40"
                      >
                        {labels.chartCreate}
                      </button>
                    </div>
                    {quickChart ? <QuickChartView chart={quickChart} /> : null}
                  </div>
                ) : (
                  <p>{labels.chartEmpty}</p>
                )}
              </InsightCard>

              {job.result_summary ? (
                <InsightCard title={labels.viewMore}>
                  <details>
                    <summary className="cursor-pointer font-semibold text-(--accent)">
                      {labels.viewMore}
                    </summary>
                    <div className="mt-5">
                      <ResultSummary
                        jobId={job.job_id}
                        summary={job.result_summary as Record<string, unknown> | null}
                      />
                    </div>
                    <div className="mt-5 overflow-auto rounded-2xl border border-(--border) bg-(--surface-muted) p-4">
                      <pre className="min-w-[720px] whitespace-pre-wrap text-xs">
                        {JSON.stringify(
                          {
                            job_id: job.job_id,
                            status: job.status,
                            uploaded_at: job.uploaded_at,
                            updated_at: job.status_updated_at,
                            profiling: job.profiling,
                            analysis_spec: job.analysis_spec,
                          },
                          null,
                          2,
                        )}
                      </pre>
                    </div>
                  </details>
                </InsightCard>
              ) : null}
            </div>
          ) : null}
        </div>
      </main>
    </div>
  );
}
