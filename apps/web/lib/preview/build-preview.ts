/**
 * Client-only preview / encoding guess. Server profiling + analyze remain authoritative.
 */

import type { FilePreviewData } from "@/lib/preview/types";
import { PREVIEW_MAX_BYTES, PREVIEW_MAX_DATA_ROWS_DEFAULT } from "@/lib/preview/types";

function extOf(name: string): string {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i + 1).toLowerCase() : "";
}

function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let field = "";
  let inQ = false;
  for (const ch of line) {
    if (ch === '"') {
      inQ = !inQ;
    } else if (ch === "," && !inQ) {
      out.push(field.trim());
      field = "";
    } else {
      field += ch;
    }
  }
  out.push(field.trim());
  return out;
}

type DecodeOut = {
  text: string;
  label: string;
  hadErrors: boolean;
  warnings: string[];
};

function decodeUtf16LE(bytes: Uint8Array): DecodeOut {
  const warnings: string[] = [];
  if (bytes.length % 2 !== 0) {
    warnings.push("utf16_odd_byte_length");
  }
  let s = "";
  for (let i = 0; i + 1 < bytes.length; i += 2) {
    s += String.fromCharCode(bytes[i]! | (bytes[i + 1]! << 8));
  }
  return { text: s, label: "UTF-16LE", hadErrors: false, warnings };
}

function decodeUtf16BE(bytes: Uint8Array): DecodeOut {
  let s = "";
  for (let i = 0; i + 1 < bytes.length; i += 2) {
    s += String.fromCharCode((bytes[i]! << 8) | bytes[i + 1]!);
  }
  return { text: s, label: "UTF-16BE", hadErrors: false, warnings: [] };
}

function decodeSample(bytes: Uint8Array): DecodeOut {
  const warnings: string[] = [];
  let s = bytes;

  if (s.length >= 3 && s[0] === 0xef && s[1] === 0xbb && s[2] === 0xbf) {
    s = s.subarray(3);
  }

  if (s.length >= 2 && s[0] === 0xff && s[1] === 0xfe) {
    const r = decodeUtf16LE(s.subarray(2));
    return { ...r, warnings: r.warnings.concat(warnings) };
  }
  if (s.length >= 2 && s[0] === 0xfe && s[1] === 0xff) {
    const r = decodeUtf16BE(s.subarray(2));
    return { ...r, warnings: warnings.concat(r.warnings) };
  }

  try {
    const text = new TextDecoder("utf-8", { fatal: true }).decode(s);
    return { text, label: "UTF-8", hadErrors: false, warnings };
  } catch {
    warnings.push("fallback_decoding_windows-1252");
    const text = new TextDecoder("windows-1252").decode(s);
    return {
      text,
      label: "windows-1252",
      hadErrors: true,
      warnings,
    };
  }
}

function previewCsv(
  head: Uint8Array,
  maxDataRows: number,
  nullScan: (chunk: Uint8Array) => boolean,
): FilePreviewData {
  const warnings: string[] = [];
  if (nullScan(head)) {
    warnings.push("null_byte_in_sample");
  }
  const dec = decodeSample(head);
  warnings.push(...dec.warnings);

  const maxLines = Math.max(2, Math.min(200, maxDataRows) + 1);
  const lines = dec.text.split(/\r\n|\n|\r/).filter((l) => l.length > 0);
  const take = lines.slice(0, maxLines);
  const rows = take.map(parseCsvLine);

  return {
    kind: "csv",
    encodingLabel: dec.label,
    hadDecodeErrors: dec.hadErrors,
    rows,
    rowCountInPreview: rows.length,
    bytesSampled: head.byteLength,
    warnings,
    magicOk: true,
  };
}

function previewXlsx(head: Uint8Array): FilePreviewData {
  const magicOk =
    head.length >= 4 &&
    head[0] === 0x50 &&
    head[1] === 0x4b &&
    (head[2] === 0x03 || head[2] === 0x05) &&
    (head[3] === 0x04 || head[3] === 0x06);
  const warnings: string[] = [];
  if (!magicOk && head.length > 0) {
    warnings.push("xlsx_expected_zip_magic");
  }
  return {
    kind: "xlsx",
    hadDecodeErrors: false,
    rows: [],
    rowCountInPreview: 0,
    bytesSampled: head.byteLength,
    warnings,
    magicOk,
  };
}

/** `nullScan` comes from WASM (`has_null_byte`) or JS fallback. */
export function buildPreviewPayload(
  name: string,
  bytes: Uint8Array,
  maxDataRows: number = PREVIEW_MAX_DATA_ROWS_DEFAULT,
  nullScan: (chunk: Uint8Array) => boolean = (u) => u.includes(0),
): { ok: true; data: FilePreviewData } | { ok: false; message: string } {
  const ext = extOf(name);
  const head =
    bytes.byteLength > PREVIEW_MAX_BYTES
      ? bytes.subarray(0, PREVIEW_MAX_BYTES)
      : bytes;

  if (ext === "csv" || ext === "txt") {
    return { ok: true, data: previewCsv(head, maxDataRows, nullScan) };
  }
  if (ext === "xlsx" || ext === "xlsm") {
    return { ok: true, data: previewXlsx(head) };
  }
  return { ok: false, message: `extension_not_previewed:${ext || "(none)"}` };
}
