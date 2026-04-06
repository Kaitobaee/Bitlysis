/**
 * Phase 10 DoD: ghi nhận kích thước artifact WASM (sau wasm:build).
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const wasmPath = path.join(root, "public", "wasm", "preview_core.wasm");
const outPath = path.join(root, "public", "wasm-bundle-sizes.json");

const out = {
  preview_core_wasm_bytes: fs.existsSync(wasmPath)
    ? fs.statSync(wasmPath).size
    : null,
  loader_package: "@assemblyscript/loader",
  recordedAt: new Date().toISOString(),
};
fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, `${JSON.stringify(out, null, 2)}\n`);

console.log("wasm-bundle-sizes", out);
