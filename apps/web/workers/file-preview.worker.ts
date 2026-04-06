/// <reference lib="webworker" />

import { buildPreviewPayload } from "@/lib/preview/build-preview";
import { createWasmNullScanner } from "@/lib/preview/wasm-null-scan";
import type { FilePreviewData } from "@/lib/preview/types";

type InMsg = {
  requestId: number;
  name: string;
  bytes: Uint8Array;
  maxDataRows: number;
};

declare const self: DedicatedWorkerGlobalScope;

let nullScanner: ((c: Uint8Array) => boolean) | null = null;

async function ensureScanner(): Promise<(c: Uint8Array) => boolean> {
  if (!nullScanner) {
    nullScanner = await createWasmNullScanner();
  }
  return nullScanner;
}

self.onmessage = async (ev: MessageEvent<InMsg>) => {
  const { requestId, name, bytes, maxDataRows } = ev.data;
  try {
    const scan = await ensureScanner();
    const r = buildPreviewPayload(name, bytes, maxDataRows, scan);
    if (r.ok) {
      const payload: FilePreviewData = r.data;
      self.postMessage({ ok: true as const, requestId, data: payload });
    } else {
      self.postMessage({
        ok: false as const,
        requestId,
        message: r.message,
      });
    }
  } catch (e) {
    self.postMessage({
      ok: false as const,
      requestId,
      message: e instanceof Error ? e.message : String(e),
    });
  }
};
