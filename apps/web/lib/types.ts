export type JobStatus =
  | "uploaded"
  | "profiling"
  | "analyzing"
  | "r_queued"       // Đang chờ GitHub Actions cron xử lý R pipeline
  | "r_processing"   // GitHub Actions đang chạy Rscript
  | "exporting"
  | "succeeded"
  | "failed";

export type JobError = {
  code: string;
  message: string;
};

export type JobDetail = {
  job_id: string;
  status: JobStatus;
  filename: string;
  stored_path: string;
  size_bytes: number;
  columns: string[];
  row_preview_count: number;
  uploaded_at: string | null;
  status_updated_at: string | null;
  error: JobError | null;
  result_summary: Record<string, unknown> | null;
  profiling?: Record<string, unknown> | null;
  profiling_detail?: Record<string, unknown> | null;
  analysis_spec?: Record<string, unknown> | null;
  manifest_stored_as?: string | null;
  export_stored_as: string | null;
};

export type UploadResponse = {
  job_id: string;
  status: JobStatus;
  filename: string;
  stored_path: string;
  size_bytes: number;
  columns: string[];
  row_preview_count: number;
};

export type QuickChartPayload = {
  kind: "bar" | "pie" | "line" | "area" | "donut";
  title: string;
  column: string;
  labels: string[];
  values: number[];
  total: number;
};

export type HealthInfo = {
  status: string;
  service: string;
};

export type WebMetricRow = {
  metric: string;
  value: string | number;
};

export type WebSection = {
  heading: string;
  snippet: string;
};

export type HeadingNode = {
  level: number;
  text: string;
  children: HeadingNode[];
};

export type CTAInfo = {
  text: string;
  type: "button" | "link" | "form" | "none";
  action_keyword: string;
};

export type DataFact = {
  label: string;
  value: string;
  type: "number" | "date" | "percentage" | "currency";
};

export type RelatedWebsite = {
  title: string;
  url: string;
  relation: "internal" | "external" | string;
  summary?: string;
};

export type WebAnalysisMode = "academic" | "marketing_seo" | "business";

export type DangerBreakdownItem = {
  label: string;
  score: number;
  level: "safe" | "medium" | "high";
  note: string;
};

export type DangerBreakdown = {
  sensitive_content: DangerBreakdownItem;
  cta_manipulation: DangerBreakdownItem;
  evidence_lack: DangerBreakdownItem;
  ai_assessment: DangerBreakdownItem;
};

export type WebAnalysisResponse = {
  analysis_mode: WebAnalysisMode;
  source_type: string;
  source_label: string;
  page_title: string;
  summary: string;
  findings: string[];
  highlights: string[];
  recommendations: string[];
  evidence: {
    label: string;
    detail: string;
  }[];
  metrics: WebMetricRow[];
  sections: WebSection[];
  chart: {
    kind: string;
    title: string;
    labels: string[];
    values: number[];
    total: number;
  } | null;
  outline: HeadingNode[];
  cta_detected: CTAInfo | null;
  related_websites: RelatedWebsite[];
  data_facts: DataFact[];
  raw_text_preview: string;
  fraud_score: number;
  website_screenshot: string | null;
  danger_breakdown: DangerBreakdown | null;
};
export type WebAnalysisChatResponse = {
  question: string;
  answer: string;
  source_label: string;
  focus: string;
};

export type FileAnalysisChatResponse = {
  question: string;
  answer: string;
  job_id: string;
  focus: string;
};

// ── Academic Content Analyzer ─────────────────────────────────────────────────

export type AcademicQuartile = "Q1" | "Q2" | "Q3" | "Q4" | "Unknown";

export type FactCheckVerdictType =
  | "Supported"
  | "Contradicted"
  | "Partially_supported"
  | "Unverified";

export type AcademicPaper = {
  title: string;
  authors: string[];
  year: number | null;
  doi: string | null;
  abstract: string;
  cited_by_count: number;
  quartile: AcademicQuartile;
  source_name: string;
  open_access: boolean;
  url: string;
};

export type FactCheckVerdict = {
  claim: string;
  verdict: FactCheckVerdictType;
  confidence: number;
  reasoning: string;
  supporting_papers: string[];
  contradicting_papers: string[];
};

export type AcademicAnalyzeRequest = {
  text: string;
  language: "vi" | "en";
  max_papers?: number;
};

export type AcademicAnalyzeResponse = {
  summary: string;
  keywords: string[];
  papers: AcademicPaper[];
  fact_checks: FactCheckVerdict[];
  quartile_distribution: Record<string, number>;
  overall_support_score: number;
  search_query: string;
};
