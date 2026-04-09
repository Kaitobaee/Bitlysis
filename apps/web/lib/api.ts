import type { JobDetail, QuickChartPayload, UploadResponse } from "@/lib/types";

const base = () =>
  (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

export class ApiClientError extends Error {
  constructor(
    public status: number,
    public apiCode: string,
    message: string,
    public requestId?: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

async function readError(res: Response): Promise<ApiClientError> {
  let apiCode = `http_${res.status}`;
  let message = res.statusText || "Request failed";
  let requestId: string | undefined;
  let details: unknown;
  try {
    const body = (await res.json()) as {
      code?: string;
      message?: string;
      request_id?: string;
      details?: unknown;
    };
    if (body.code) apiCode = body.code;
    if (body.message) message = body.message;
    requestId = body.request_id;
    details = body.details;
  } catch {
    /* plain text or empty */
  }
  return new ApiClientError(res.status, apiCode, message, requestId, details);
}

async function parseJson<T>(res: Response): Promise<T> {
  if (!res.ok) throw await readError(res);
  return res.json() as Promise<T>;
}

export async function uploadFile(file: File): Promise<UploadResponse> {
  const fd = new FormData();
  fd.set("file", file);
  const res = await fetch(`${base()}/v1/upload`, {
    method: "POST",
    body: fd,
  });
  return parseJson<UploadResponse>(res);
}

export async function getJob(jobId: string): Promise<JobDetail> {
  const res = await fetch(`${base()}/v1/jobs/${encodeURIComponent(jobId)}`, {
    method: "GET",
    cache: "no-store",
  });
  return parseJson<JobDetail>(res);
}

export async function startAnalyze(
  jobId: string,
  spec: Record<string, unknown>,
): Promise<void> {
  const res = await fetch(
    `${base()}/v1/jobs/${encodeURIComponent(jobId)}/analyze`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(spec),
    },
  );
  if (!res.ok) throw await readError(res);
}

export async function startExportPhase(jobId: string): Promise<void> {
  const res = await fetch(
    `${base()}/v1/jobs/${encodeURIComponent(jobId)}/export/start`,
    { method: "POST" },
  );
  if (!res.ok) throw await readError(res);
}

export async function downloadExportZip(jobId: string): Promise<Blob> {
  const res = await fetch(
    `${base()}/v1/jobs/${encodeURIComponent(jobId)}/export/download`,
    { method: "GET" },
  );
  if (!res.ok) throw await readError(res);
  return res.blob();
}

export async function postExportZip(jobId: string): Promise<Blob> {
  const res = await fetch(
    `${base()}/v1/jobs/${encodeURIComponent(jobId)}/export`,
    { method: "POST" },
  );
  if (!res.ok) throw await readError(res);
  return res.blob();
}

export async function getQuickChart(
  jobId: string,
  column: string,
  chartType: "bar" | "pie" | "line" | "area" | "donut",
): Promise<QuickChartPayload> {
  const qs = new URLSearchParams({
    column,
    chart_type: chartType,
    max_items: "12",
  });
  const res = await fetch(
    `${base()}/v1/jobs/${encodeURIComponent(jobId)}/charts/quick?${qs.toString()}`,
    {
      method: "GET",
      cache: "no-store",
    },
  );
  return parseJson<QuickChartPayload>(res);
}
