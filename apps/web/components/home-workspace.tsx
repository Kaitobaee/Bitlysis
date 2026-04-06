"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { LanguageSwitch } from "@/components/language-switch";
import { ResultSummary } from "@/components/result-summary";
import { UploadZone } from "@/components/upload-zone";
import {
  ApiClientError,
  getJob,
  postExportZip,
  startAnalyze,
  startExportPhase,
  uploadFile,
} from "@/lib/api";
import { defaultCategoricalSpec } from "@/lib/analyze-default";
import { useI18n } from "@/lib/i18n";
import {
  isBusyStatus,
  isTerminalStatus,
  pollJobUntil,
  PollTimeoutError,
} from "@/lib/poll-job";
import { toastApiError } from "@/lib/toast-error";
import type { JobDetail, JobStatus } from "@/lib/types";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";

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

export function HomeWorkspace() {
  const { t } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [uploading, setUploading] = useState(false);
  const [busyAnalyze, setBusyAnalyze] = useState(false);
  const [busyExport, setBusyExport] = useState(false);
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
    let spec: ReturnType<typeof defaultCategoricalSpec>;
    try {
      spec = defaultCategoricalSpec(job.columns);
    } catch {
      toast.error(t("job.needTwoColumns"), { duration: 10_000 });
      return;
    }
    pollAbortRef.current?.abort();
    const ac = new AbortController();
    pollAbortRef.current = ac;
    setBusyAnalyze(true);
    try {
      await startAnalyze(job.job_id, spec as unknown as Record<string, unknown>);
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

  const onReset = useCallback(() => {
    pollAbortRef.current?.abort();
    setJob(null);
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
      <header className="swiss-container flex flex-col gap-6 border-b border-[var(--border)] pb-10 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-serif text-4xl font-medium tracking-tight text-[var(--fg)] sm:text-5xl">
            {t("app.title")}
          </h1>
          <p className="mt-4 max-w-xl text-base leading-relaxed text-[var(--muted)]">
            {t("app.tagline")}
          </p>
        </div>
        <LanguageSwitch />
      </header>

      <main className="space-y-0">
        <div className="swiss-container space-y-10 py-12">
          <div className="grid gap-12 lg:grid-cols-2">
            <section className="space-y-6">
              <h2 className="text-label text-[var(--muted)]">{t("upload.label")}</h2>
              <UploadZone disabled={uploading} onFile={onUpload} />
              {!apiBase.trim() && (
                <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 px-4 py-3">
                  NEXT_PUBLIC_API_URL chưa đặt. {t("errors.checkApiUrl")}
                </p>
              )}
            </section>

            <section className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <h2 className="text-label text-[var(--muted)]">{t("job.status")}</h2>
              <div className="flex flex-wrap gap-2">
                <a
                  className="text-xs font-semibold uppercase tracking-wider text-[var(--accent)] underline-offset-4 hover:underline"
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
                    className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)] hover:text-[var(--fg)]"
                  >
                    {t("job.reset")}
                  </button>
                )}
              </div>
            </div>

            {!job && (
              <p className="border border-[var(--border)] bg-[var(--surface-muted)] p-8 text-sm text-[var(--muted)]">
                {t("result.empty")}
              </p>
            )}

            {job && (
              <div className="border border-[var(--border)] bg-[var(--surface)] p-8">
                <div className="flex flex-wrap items-baseline justify-between gap-4">
                  <div>
                    <p className="text-label text-[var(--muted)]">{t("job.id")}</p>
                    <p className="mt-1 font-mono text-sm break-all">{job.job_id}</p>
                  </div>
                  <button
                    type="button"
                    onClick={onCopyId}
                    className="shrink-0 border border-[var(--border)] px-3 py-1.5 text-xs font-semibold uppercase tracking-wider hover:bg-[var(--surface-muted)]"
                  >
                    {t("job.copyId")}
                  </button>
                </div>
                <dl className="mt-8 grid gap-6 sm:grid-cols-2">
                  <div>
                    <dt className="text-label text-[var(--muted)]">
                      {t("job.status")}
                    </dt>
                    <dd className="mt-2 flex items-center gap-2 text-lg font-semibold text-[var(--fg)]">
                      {statusLabel(t, job.status)}
                      {isBusyStatus(job.status) && (
                        <span
                          className="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-[var(--accent)]"
                          aria-hidden
                        />
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-label text-[var(--muted)]">
                      {t("job.filename")}
                    </dt>
                    <dd className="mt-2 text-sm text-[var(--fg)]">{job.filename}</dd>
                  </div>
                  <div className="sm:col-span-2">
                    <dt className="text-label text-[var(--muted)]">
                      {t("job.columns")}
                    </dt>
                    <dd className="mt-2 font-mono text-xs leading-relaxed text-[var(--fg)]">
                      {job.columns.join(", ")}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-label text-[var(--muted)]">
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
                    className="border border-[var(--fg)] bg-[var(--fg)] px-5 py-2.5 text-sm font-semibold uppercase tracking-wider text-[var(--surface)] disabled:cursor-not-allowed disabled:opacity-40 hover:opacity-90"
                  >
                    {busyAnalyze ? t("job.analyzing") : t("job.analyze")}
                  </button>
                  <button
                    type="button"
                    disabled={
                      busyExport || !job || job.status !== "succeeded"
                    }
                    onClick={onExport}
                    className="border border-[var(--border)] bg-transparent px-5 py-2.5 text-sm font-semibold uppercase tracking-wider text-[var(--fg)] disabled:cursor-not-allowed disabled:opacity-40 hover:bg-[var(--surface-muted)]"
                  >
                    {busyExport ? t("job.exporting") : t("job.exportZip")}
                  </button>
                </div>
                {job.columns.length < 2 && (
                  <p className="mt-3 text-xs text-[var(--amber-fg)]">
                    {t("job.needTwoColumns")}
                  </p>
                )}

                {showInlineSkeleton && (
                  <div
                    className="mt-8 space-y-3 border-t border-[var(--border)] pt-8"
                    aria-busy="true"
                    aria-live="polite"
                  >
                    <p className="text-label text-[var(--muted)]">
                      {t("job.polling")}
                    </p>
                    <div className="h-2 w-full animate-pulse bg-[var(--skeleton)]" />
                    <div className="h-2 w-4/5 animate-pulse bg-[var(--skeleton)]" />
                    <div className="h-24 w-full animate-pulse bg-[var(--skeleton)]" />
                  </div>
                )}
              </div>
            )}

            </section>
          </div>
        </div>

        {job && job.status === "succeeded" && (
          <section className="w-full bg-[var(--surface)] p-8 lg:p-12">
            <h2 className="text-label mb-8 text-[var(--muted)] px-0 lg:px-12 max-w-screen">
              {t("result.title")}
            </h2>
            <div className="px-0 lg:px-12">
              <ResultSummary
                jobId={job.job_id}
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
