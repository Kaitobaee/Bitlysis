import { buildPreviewPayload } from "@/lib/preview/build-preview";
import type { FilePreviewData } from "@/lib/preview/types";
import {
  PREVIEW_MAX_BYTES,
  PREVIEW_MAX_DATA_ROWS_DEFAULT,
} from "@/lib/preview/types";

export type PreviewResult =
  | { ok: true; data: FilePreviewData }
  | { ok: false; message: string };

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

async function runOnMainThread(
  name: string,
  bytes: Uint8Array,
  maxDataRows: number,
): Promise<PreviewResult> {
  const { createWasmNullScanner } = await import("@/lib/preview/wasm-null-scan");
  const scan = await createWasmNullScanner();
  return buildPreviewPayload(name, bytes, maxDataRows, scan);
}

function runWorkerPreview(
  name: string,
  bytes: Uint8Array,
  maxDataRows: number,
): Promise<PreviewResult> {
  return new Promise((resolve) => {
    try {
      const w = new Worker(
        new URL("../../workers/file-preview.worker.ts", import.meta.url),
        { type: "module" },
      );
      const id = Math.floor(Math.random() * 1e9);
      const onMsg = (ev: MessageEvent) => {
        const msg = ev.data as {
          requestId: number;
          ok: boolean;
          data?: FilePreviewData;
          message?: string;
        };
        if (msg.requestId !== id) return;
        w.removeEventListener("message", onMsg);
        w.terminate();
        if (msg.ok && msg.data) {
          resolve({ ok: true, data: msg.data });
        } else {
          resolve({
            ok: false,
            message: msg.message ?? "worker_preview_failed",
          });
        }
      };
      w.addEventListener("message", onMsg);
      w.addEventListener("error", () => {
        w.removeEventListener("message", onMsg);
        w.terminate();
        resolve({ ok: false, message: "worker_error" });
      });
      const copy = new Uint8Array(bytes);
      w.postMessage({ requestId: id, name, bytes: copy, maxDataRows });
    } catch {
      resolve({ ok: false, message: "worker_construct_failed" });
    }
  });
}

/**
 * WASM null-scan + decode runs in a dedicated worker when possible (keeps main thread responsive).
 * Falls back to main-thread preview if Worker or WASM init fails.
 */
export async function runFilePreview(
  file: File,
  opts?: {
    maxDataRows?: number;
    workerTimeoutMs?: number;
    totalTimeoutMs?: number;
    preferWorker?: boolean;
  },
): Promise<PreviewResult> {
  const maxDataRows = opts?.maxDataRows ?? PREVIEW_MAX_DATA_ROWS_DEFAULT;
  const workerTimeoutMs = opts?.workerTimeoutMs ?? 4000;
  const totalTimeoutMs = opts?.totalTimeoutMs ?? 12_000;
  const preferWorker = opts?.preferWorker ?? true;
  const slice = file.slice(0, PREVIEW_MAX_BYTES);
  const ab = await slice.arrayBuffer();
  const bytes = new Uint8Array(ab);

  const run = async (): Promise<PreviewResult> => {
    if (preferWorker && typeof Worker !== "undefined") {
      const wResult = await Promise.race([
        runWorkerPreview(file.name, bytes, maxDataRows),
        sleep(workerTimeoutMs).then(
          (): PreviewResult => ({ ok: false, message: "worker_timeout" }),
        ),
      ]);
      if (wResult.ok) return wResult;
    }
    return runOnMainThread(file.name, bytes, maxDataRows);
  };

  return Promise.race([
    run(),
    sleep(totalTimeoutMs).then(
      (): PreviewResult => ({ ok: false, message: "preview_timeout" }),
    ),
  ]);
}
