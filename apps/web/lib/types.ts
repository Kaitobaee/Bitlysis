export type JobStatus =
  | "uploaded"
  | "profiling"
  | "analyzing"
  | "exporting"
  | "succeeded"
  | "failed";

export type JobError = {
  code: string;
  message: string;
};

export type JobDetail = {
  job_id: string;
  status: JobStatus;
  filename: string;
  stored_path: string;
  size_bytes: number;
  columns: string[];
  row_preview_count: number;
  uploaded_at: string | null;
  status_updated_at: string | null;
  error: JobError | null;
  result_summary: Record<string, unknown> | null;
  export_stored_as: string | null;
};

export type UploadResponse = {
  job_id: string;
  status: JobStatus;
  filename: string;
  stored_path: string;
  size_bytes: number;
  columns: string[];
  row_preview_count: number;
};
