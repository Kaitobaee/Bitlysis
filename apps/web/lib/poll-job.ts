import { getJob } from "@/lib/api";
import type { JobDetail, JobStatus } from "@/lib/types";

const INTERVAL_MS = 1500;
const MAX_MS = 120_000;

export class PollTimeoutError extends Error {
  constructor() {
    super("POLL_TIMEOUT");
    this.name = "PollTimeoutError";
  }
}

export function isTerminalStatus(s: JobStatus): boolean {
  return s === "succeeded" || s === "failed";
}

export function isBusyStatus(s: JobStatus): boolean {
  return s === "analyzing" || s === "profiling" || s === "exporting";
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const t = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(t);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });
}

/** Poll until predicate returns true or timeout. */
export async function pollJobUntil(
  jobId: string,
  done: (job: JobDetail) => boolean,
  options?: {
    onUpdate?: (job: JobDetail) => void;
    signal?: AbortSignal;
  },
): Promise<JobDetail> {
  const start = Date.now();
  const signal = options?.signal;
  while (Date.now() - start < MAX_MS) {
    const job = await getJob(jobId);
    options?.onUpdate?.(job);
    if (done(job)) return job;
    await sleep(INTERVAL_MS, signal);
  }
  throw new PollTimeoutError();
}
