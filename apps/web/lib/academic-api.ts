import type { AcademicAnalyzeRequest, AcademicAnalyzeResponse } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export async function analyzeAcademicContent(
  req: AcademicAnalyzeRequest,
  signal?: AbortSignal,
): Promise<AcademicAnalyzeResponse> {
  const url = `${API_URL}/v1/academic/analyze`;
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal,
  });

  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const err = await resp.json();
      detail = err?.detail ?? detail;
    } catch {
      // ignore parse error
    }
    throw new Error(detail);
  }

  return resp.json() as Promise<AcademicAnalyzeResponse>;
}
