/** WASM: NUL-byte scan in sample (AssemblyScript). Decode/preview rows stay in TS — no server analysis fork. */

import { instantiateStreaming } from "@assemblyscript/loader";

type WasmExports = {
  memory: WebAssembly.Memory;
  __new: (size: number, id: number) => number;
  __pin: (ptr: number) => number;
  __unpin: (ptr: number) => void;
  has_null_byte: (ptr: number, len: number) => number;
};

let cached: Promise<WasmExports> | null = null;

function loadWasm(): Promise<WasmExports> {
  if (!cached) {
    cached = (async () => {
      const { exports } = await instantiateStreaming(
        fetch("/wasm/preview_core.wasm"),
        {
          env: {
            abort() {
              throw new Error("wasm_abort");
            },
          },
        },
      );
      return exports as unknown as WasmExports;
    })();
  }
  return cached;
}

export async function createWasmNullScanner(): Promise<
  (chunk: Uint8Array) => boolean
> {
  const { memory, __new, __pin, __unpin, has_null_byte } = await loadWasm();

  return (chunk: Uint8Array): boolean => {
    if (chunk.byteLength === 0) return false;
    const ptr = __new(chunk.length, 0) >>> 0;
    __pin(ptr);
    try {
      new Uint8Array(memory.buffer).set(chunk, ptr);
      return has_null_byte(ptr, chunk.length) !== 0;
    } finally {
      __unpin(ptr);
    }
  };
}
