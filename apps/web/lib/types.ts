export type JobStatus =
  | "uploaded"
  | "profiling"
  | "analyzing"
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
};

export type WebAnalysisChatResponse = {
  question: string;
  answer: string;
  source_label: string;
  focus: string;
};
