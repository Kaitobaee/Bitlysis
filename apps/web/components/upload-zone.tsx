"use client";

import { useEffect, useRef, useState } from "react";

import { useI18n } from "@/lib/i18n";
import { analyzeAcademicContent } from "@/lib/academic-api";
import type { AcademicAnalyzeResponse, WebAnalysisResponse } from "@/lib/types";

type Props = {
  disabled?: boolean;
  analysis: WebAnalysisResponse | null;
  onAnalyzePrompt: (value: string) => Promise<void>;
  onAskAssistant: (value: string) => Promise<string>;
  onUploadDataFile: (file: File) => Promise<void>;
  onAcademicResult?: (result: AcademicAnalyzeResponse) => void;
};

type ChatMessage = {
  role: "assistant" | "user";
  content: string;
};

// Chỉ chấp nhận Excel + CSV (Excel là định dạng chính)
const DATA_FILE_EXTS = new Set(["csv", "xlsx", "xlsm"]);
const ACCEPT_ATTR = ".csv,.xlsx,.xlsm";

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

export function UploadZone({ disabled, analysis, onAnalyzePrompt, onAskAssistant, onUploadDataFile, onAcademicResult }: Props) {
  const { t } = useI18n();
  const [websiteValue, setWebsiteValue] = useState("");
  const [chatValue, setChatValue] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  // Academic panel state
  const [academicText, setAcademicText] = useState("");
  const [academicLang, setAcademicLang] = useState<"vi" | "en">("vi");
  const [academicBusy, setAcademicBusy] = useState(false);
  const [academicStep, setAcademicStep] = useState(0); // 0=idle 1=keywords 2=papers 3=factcheck
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const chatBottomRef = useRef<HTMLDivElement | null>(null);
  const academicAbortRef = useRef<AbortController | null>(null);

  // Auto-scroll to bottom on new message (UX-5)
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!analysis) {
      setMessages([
        {
          role: "assistant",
          content: t("upload.hintMessage"),
        },
      ]);
      return;
    }

    setMessages([
      {
        role: "assistant",
        content: `${t("upload.analysisReady")} "${analysis.source_label}". ${t("upload.analysisReadyHint")}`,
      },
    ]);
  }, [analysis, t]);

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
    await runAnalyzeFromInput(payload, t("upload.labelWebsite"));
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
    if (disabled || busy || uploading) return;
    fileInputRef.current?.click();
  };

  const processDataFile = async (file: File) => {
    const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (!DATA_FILE_EXTS.has(ext)) {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: t("upload.fileTypeError"),
        },
      ]);
      return;
    }

    setMessages((current) => [
      ...current,
      { role: "user", content: `${t("upload.fileSelected")}: ${file.name}` },
    ]);

    setUploading(true);
    setBusy(true);
    try {
      await onUploadDataFile(file);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: `${t("upload.fileUploaded")} ${file.name}. ${t("upload.fileUploadedHint")}`,
        },
      ]);
    } catch {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: t("upload.fileUploadError"),
        },
      ]);
    } finally {
      setUploading(false);
      setBusy(false);
    }
  };

  const onFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || disabled) return;
    await processDataFile(file);
  };

  // Drag & Drop handlers (UX-4)
  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled && !busy) setDragOver(true);
  };

  const onDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  };

  const onDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (disabled || busy || uploading) return;
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    await processDataFile(file);
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
            {/* Panel 1: Website Analysis */}
            <div className="rounded-3xl border border-(--border) bg-(--surface-muted) p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-(--muted)">1. {t("upload.panelWebTitle")}</p>
              <p className="mt-1 text-xs leading-relaxed text-(--muted)">{t("upload.panelWebHint")}</p>
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
                {busy ? t("upload.analyzing") : t("upload.panelWebCta")}
              </button>
            </div>

            {/* Panel 2: Excel/CSV Upload with Drag & Drop (UX-4) */}
            <div className="rounded-3xl border border-(--border) bg-(--surface-muted) p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-(--muted)">2. {t("upload.panelFileTitle")}</p>
              <p className="mt-1 text-xs leading-relaxed text-(--muted)">{t("upload.panelFileHint")}</p>

              {/* Drop zone */}
              <div
                className={[
                  "mt-3 rounded-xl border-2 border-dashed p-4 text-center text-xs transition-colors",
                  dragOver
                    ? "border-(--accent) bg-[rgba(15,118,110,0.06)]"
                    : "border-(--border) bg-(--surface)",
                  disabled || busy ? "cursor-not-allowed" : "cursor-pointer",
                ].join(" ")}
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                onDrop={(e) => void onDrop(e)}
                onClick={onPickFile}
                role="button"
                tabIndex={0}
                aria-label={t("upload.dropZoneLabel")}
                onKeyDown={(e) => e.key === "Enter" && onPickFile()}
              >
                {uploading ? (
                  <div className="flex items-center justify-center gap-2">
                    <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-(--border) border-t-(--accent)" />
                    <span className="text-(--muted)">{t("upload.uploading")}</span>
                  </div>
                ) : (
                  <>
                    <p className="text-(--muted)">
                      {dragOver ? t("upload.dropNow") : t("upload.dropZoneText")}
                    </p>
                    <p className="mt-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-(--muted)">
                      {t("upload.acceptedFormats")}
                    </p>
                  </>
                )}
              </div>

              <button
                type="button"
                disabled={disabled || busy || uploading}
                onClick={onPickFile}
                className="mt-3 rounded-full border border-(--border) bg-(--surface) px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-(--fg) disabled:opacity-50"
              >
                {uploading ? t("upload.uploading") : t("upload.panelFileCta")}
              </button>
            </div>

            {/* Panel 3: Academic Content Analysis */}
            <div className="rounded-3xl border border-(--border) bg-(--surface-muted) p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-(--muted)">
                {t("academic.panelTitle")}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-(--muted)">{t("academic.panelDesc")}</p>

              {/* Language selector */}
              <div className="mt-3 flex gap-1.5">
                {(["vi", "en"] as const).map((lang) => (
                  <button
                    key={lang}
                    type="button"
                    onClick={() => setAcademicLang(lang)}
                    className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                      academicLang === lang
                        ? "bg-(--fg) text-(--surface)"
                        : "border border-(--border) bg-(--surface) text-(--muted)"
                    }`}
                  >
                    {lang === "vi" ? t("academic.langVi") : t("academic.langEn")}
                  </button>
                ))}
              </div>

              <textarea
                value={academicText}
                disabled={disabled || academicBusy}
                onChange={(e) => setAcademicText(e.target.value)}
                placeholder={t("academic.placeholder")}
                rows={4}
                className="mt-3 w-full resize-none rounded-xl border border-(--border) bg-(--surface) px-3 py-2 text-sm text-(--fg) outline-none placeholder:text-(--muted) disabled:opacity-60"
              />

              {/* Progress steps */}
              {academicBusy && (
                <div className="mt-2 flex items-center gap-2">
                  <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-(--border) border-t-(--accent)" />
                  <span className="text-xs text-(--muted)">
                    {academicStep === 1 && t("academic.step1")}
                    {academicStep === 2 && t("academic.step2")}
                    {academicStep === 3 && t("academic.step3")}
                  </span>
                </div>
              )}

              <button
                type="button"
                disabled={disabled || academicBusy || academicText.trim().length < 50}
                onClick={async () => {
                  academicAbortRef.current?.abort();
                  const ac = new AbortController();
                  academicAbortRef.current = ac;
                  setAcademicBusy(true);
                  setAcademicStep(1);
                  try {
                    setAcademicStep(2);
                    const result = await analyzeAcademicContent(
                      { text: academicText.trim(), language: academicLang },
                      ac.signal,
                    );
                    setAcademicStep(3);
                    onAcademicResult?.(result);
                  } catch {
                    // error handled upstream
                  } finally {
                    setAcademicBusy(false);
                    setAcademicStep(0);
                  }
                }}
                className="mt-3 rounded-full border border-(--fg) bg-(--fg) px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-(--surface) disabled:opacity-50"
              >
                {academicBusy ? t("academic.analyzing") : t("academic.analyzeBtn")}
              </button>

              {academicText.trim().length > 0 && academicText.trim().length < 50 && (
                <p className="mt-1.5 text-[11px] text-amber-600">{t("academic.errorTooShort")}</p>
              )}
            </div>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept={ACCEPT_ATTR}
          onChange={(event) => {
            void onFileChange(event);
          }}
        />

        {/* Chat window with auto-scroll (UX-5) */}
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
          {/* Sentinel div for auto-scroll */}
          <div ref={chatBottomRef} />
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
