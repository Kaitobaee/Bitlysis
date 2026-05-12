export type FilePreviewData = {
  kind: "csv" | "xlsx" | "unsupported";
  encodingLabel?: string;
  hadDecodeErrors: boolean;
  rows: string[][];
  rowCountInPreview: number;
  bytesSampled: number;
  warnings: string[];
  magicOk: boolean;
};

export type FilePreviewMessage =
  | { ok: true; requestId: number; data: FilePreviewData }
  | { ok: false; requestId: number; message: string };

export const PREVIEW_MAX_BYTES = 512 * 1024;
export const PREVIEW_MAX_DATA_ROWS_DEFAULT = 12;
