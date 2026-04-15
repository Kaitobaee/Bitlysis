"use client";

import { useEffect, useRef, useState } from "react";

import { useI18n } from "@/lib/i18n";
import type { WebAnalysisResponse } from "@/lib/types";

type Props = {
  disabled?: boolean;
  analysis: WebAnalysisResponse | null;
  onAnalyzePrompt: (value: string) => Promise<void>;
  onAskAssistant: (value: string) => Promise<string>;
  onUploadDataFile: (file: File) => Promise<void>;
};

type ChatMessage = {
  role: "assistant" | "user";
  content: string;
};

function formatAssistantMessage(value: string): string {
  const cleaned = value
    .replace(/\r\n/g, "\n")
    .replace(/```(?:json|text)?\s*/gi, "")
    .replace(/```/g, "")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\*(.*?)\*/g, "$1")
    .replace(/^\s*\|/gm, "")
    .replace(/\|/g, " · ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  return cleaned;
}

export function UploadZone({ disabled, analysis, onAnalyzePrompt, onAskAssistant, onUploadDataFile }: Props) {
  const { t } = useI18n();
  const [websiteValue, setWebsiteValue] = useState("");
  const [contentValue, setContentValue] = useState("");
  const [chatValue, setChatValue] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!analysis) {
      setMessages([
        {
          role: "assistant",
          content: "Nhập URL hoặc nội dung website để bắt đầu phân tích. Sau đó bạn có thể hỏi tiếp ngay trong khung này.",
        },
      ]);
      return;
    }

    setMessages([
      {
        role: "assistant",
        content: `Tôi đang bám vào website "${analysis.source_label}". Hỏi tôi về nguy cơ, CTA, nội dung nhạy cảm, hoặc điểm cần xác minh thêm.`,
      },
    ]);
  }, [analysis]);

  const runAnalyzeFromInput = async (rawValue: string, userLabel: string) => {
    const cleaned = rawValue.trim();
    if (!cleaned || disabled || busy) return;
    setMessages((current) => [...current, { role: "user", content: `${userLabel}: ${cleaned.slice(0, 180)}` }]);
    setBusy(true);
    try {
      await onAnalyzePrompt(cleaned);
    } finally {
      setBusy(false);
    }
  };

  const submitChat = async () => {
    const cleaned = chatValue.trim();
    if (!cleaned || disabled || busy || !analysis) return;
    setChatValue("");
    setMessages((current) => [...current, { role: "user", content: cleaned }]);
    setBusy(true);
    try {
      const answer = await onAskAssistant(cleaned);
      setMessages((current) => [...current, { role: "assistant", content: answer }]);
    } finally {
      setBusy(false);
    }
  };

  const submitWebsite = async () => {
    const payload = websiteValue.trim();
    if (!payload) return;
    setWebsiteValue("");
    await runAnalyzeFromInput(payload, "Phân tích website");
  };

  const submitContent = async () => {
    const payload = contentValue.trim();
    if (!payload) return;
    setContentValue("");
    await runAnalyzeFromInput(payload, "Phân tích nội dung");
  };

  const submitQuickPrompt = async (prompt: string) => {
    if (disabled || busy || !analysis) return;
    setMessages((current) => [...current, { role: "user", content: prompt }]);
    setChatValue("");
    setBusy(true);
    try {
      const answer = await onAskAssistant(prompt);
      setMessages((current) => [...current, { role: "assistant", content: answer }]);
    } finally {
      setBusy(false);
    }
  };

  const onPickFile = () => {
    if (disabled || busy) return;
    fileInputRef.current?.click();
  };

  const onFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || disabled || busy) return;

    setBusy(true);
    try {
      const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
      const dataFileExt = new Set(["csv", "xlsx", "xlsm"]);
      const textLikeExt = new Set(["txt", "md", "csv", "json", "html", "htm", "xml", "tsv", "log", "yaml", "yml", "js", "ts", "py", "java", "c", "cpp", "cs", "go", "php", "sql"]);
      const isLikelyText = file.type.startsWith("text/") || textLikeExt.has(ext);
      const isDataFile = dataFileExt.has(ext);

      setMessages((current) => [
        ...current,
        {
          role: "user",
          content: `Đã chọn file: ${file.name}`,
        },
      ]);

      if (isDataFile) {
        await onUploadDataFile(file);
        setMessages((current) => [
          ...current,
          {
            role: "assistant",
            content: `File dữ liệu ${file.name} đã được upload vào backend phân tích. Hệ thống đang tiếp tục profile và chuẩn bị kết quả.`,
          },
        ]);
        return;
      }

      let payload = "";
      if (isLikelyText) {
        const rawText = await file.text();
        const cleaned = rawText.trim();
        if (!cleaned) {
          setMessages((current) => [
            ...current,
            {
              role: "assistant",
              content: "File rỗng hoặc không có nội dung văn bản để phân tích.",
            },
          ]);
          return;
        }
        payload = cleaned.slice(0, 20000);
      } else {
        payload = [
          "[Non-text file uploaded]",
          `filename: ${file.name}`,
          `mime_type: ${file.type || "unknown"}`,
          `size_bytes: ${file.size}`,
          "note: AI chỉ có thể phân tích metadata vì đây không phải file văn bản.",
        ].join("\n");
      }

      await runAnalyzeFromInput(payload, `Phân tích nội dung file ${file.name}`);
    } catch {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: "Không thể xử lý file này. Vui lòng thử lại với file khác.",
        },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={["relative overflow-hidden rounded-[28px] border border-(--border) bg-(--surface) p-5 shadow-[0_16px_38px_rgba(15,23,42,0.06)] sm:p-6", disabled ? "opacity-60" : ""].join(" ")}>
      <div className="space-y-4">
        <div>
          <p className="text-label text-(--muted)">{analysis ? t("upload.labelChat") : t("upload.labelAnalyze")}</p>
          <p className="mt-2 text-sm text-(--muted)">{analysis ? t("upload.scopeNote") : t("upload.hint")}</p>
        </div>

        {!analysis && (
          <div className="grid gap-3 lg:grid-cols-3">
            <div className="rounded-3xl border border-(--border) bg-(--surface-muted) p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-(--muted)">1. Phân tích website</p>
              <p className="mt-1 text-xs leading-relaxed text-(--muted)">Dán URL website để hệ thống phân tích nội dung, rủi ro, CTA và cấu trúc trang.</p>
              <input
                value={websiteValue}
                disabled={disabled || busy}
                onChange={(event) => setWebsiteValue(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    void submitWebsite();
                  }
                }}
                placeholder="https://example.com"
                className="mt-3 w-full rounded-xl border border-(--border) bg-(--surface) px-3 py-2 text-sm text-(--fg) outline-none"
              />
              <button
                type="button"
                disabled={disabled || busy || !websiteValue.trim()}
                onClick={() => void submitWebsite()}
                className="mt-3 rounded-full border border-(--fg) bg-(--fg) px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-(--surface) disabled:opacity-50"
              >
                {busy ? t("upload.analyzing") : "Phân tích website"}
              </button>
            </div>

            <div className="rounded-3xl border border-(--border) bg-(--surface-muted) p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-(--muted)">2. Phân tích file (Excel, Word)</p>
              <p className="mt-1 text-xs leading-relaxed text-(--muted)">Upload file dữ liệu hoặc tài liệu để chạy luồng phân tích đã triển khai.</p>
              <div className="mt-3 rounded-xl border border-dashed border-(--border) bg-(--surface) p-4 text-center text-xs text-(--muted)">
                Hỗ trợ: .xlsx, .xlsm, .csv, .doc, .docx, .txt...
              </div>
              <button
                type="button"
                disabled={disabled || busy}
                onClick={onPickFile}
                className="mt-3 rounded-full border border-(--border) bg-(--surface) px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-(--fg) disabled:opacity-50"
              >
                Chọn file
              </button>
            </div>

            <div className="rounded-3xl border border-(--border) bg-(--surface-muted) p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-(--muted)">3. Phân tích nội dung</p>
              <p className="mt-1 text-xs leading-relaxed text-(--muted)">Dán nội dung để AI tìm link liên quan và tóm tắt ngắn cho từng link.</p>
              <textarea
                value={contentValue}
                disabled={disabled || busy}
                onChange={(event) => setContentValue(event.target.value)}
                placeholder="Dán đoạn nội dung cần phân tích..."
                rows={4}
                className="mt-3 w-full resize-none rounded-xl border border-(--border) bg-(--surface) px-3 py-2 text-sm text-(--fg) outline-none"
              />
              <button
                type="button"
                disabled={disabled || busy || !contentValue.trim()}
                onClick={() => void submitContent()}
                className="mt-3 rounded-full border border-(--fg) bg-(--fg) px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-(--surface) disabled:opacity-50"
              >
                {busy ? t("upload.analyzing") : "Phân tích nội dung"}
              </button>
            </div>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept="*/*"
          onChange={(event) => {
            void onFileChange(event);
          }}
        />

        <div className="min-h-55 max-h-80 space-y-2 overflow-auto rounded-3xl border border-(--border) bg-(--surface-muted) p-3">
          {messages.map((message, idx) => (
            <div
              key={`${message.role}-${idx}`}
              className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-relaxed ${
                  message.role === "user"
                    ? "bg-(--fg) text-(--surface)"
                    : "border border-(--border) bg-(--surface) text-(--fg)"
                }`}
              >
                <span className="whitespace-pre-wrap wrap-break-word">
                  {message.role === "assistant" ? formatAssistantMessage(message.content) : message.content}
                </span>
              </div>
            </div>
          ))}
        </div>

        {analysis && (
          <>
            <div className="rounded-[999px] border border-(--border) bg-(--surface) px-3 py-2 shadow-[0_12px_26px_rgba(15,23,42,0.08)]">
              <div className="flex items-center gap-3">
                <input
                  value={chatValue}
                  disabled={disabled || busy}
                  onChange={(event) => setChatValue(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      void submitChat();
                    }
                  }}
                  placeholder={t("upload.placeholderChat")}
                  className="min-w-0 flex-1 bg-transparent px-1 text-sm text-(--fg) outline-none"
                />
                <button
                  type="button"
                  disabled={disabled || busy}
                  onClick={() => void submitChat()}
                  className="rounded-full border border-(--fg) bg-(--fg) px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-(--surface) disabled:opacity-50"
                >
                  {busy ? t("upload.asking") : t("upload.ctaChat")}
                </button>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 text-xs text-(--muted)">
              {[t("upload.quickRisk"), t("upload.quickCta"), t("upload.quickNext")].map((label) => (
                <button
                  key={label}
                  type="button"
                  disabled={disabled || busy}
                  onClick={() => void submitQuickPrompt(label)}
                  className="rounded-full border border-(--border) bg-(--surface-muted) px-3 py-1 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {label}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
