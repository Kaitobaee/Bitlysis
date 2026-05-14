"use client";

import { useEffect, useRef, useState } from "react";

import { analyzeAcademicContent } from "@/lib/academic-api";
import { extractContentFile } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { AcademicAnalyzeResponse, WebAnalysisMode, WebAnalysisResponse } from "@/lib/types";

type Props = {
  disabled?: boolean;
  analysis: WebAnalysisResponse | null;
  analysisMode: WebAnalysisMode;
  onAnalysisModeChange: (mode: WebAnalysisMode) => void;
  onAnalyzePrompt: (value: string) => Promise<void>;
  onAskAssistant: (value: string) => Promise<string>;
  onUploadDataFile: (file: File) => Promise<void>;
  onAcademicResult?: (result: AcademicAnalyzeResponse) => void;
  onAnalyzeContent?: (text: string, language: string) => Promise<void>;
};

type ChatMessage = {
  role: "assistant" | "user";
  content: string;
};

type SourceKind = "data" | "website" | "content";

const DATA_FILE_EXTS = new Set(["csv", "xlsx", "xlsm", "xls"]);
const TEXT_FILE_EXTS = new Set(["txt", "md", "markdown"]);
const WORD_FILE_EXTS = new Set(["docx", "doc", "docm"]);
const DATA_ACCEPT_ATTR = ".csv,.xlsx,.xlsm,.xls";
const CONTENT_ACCEPT_ATTR = ".docx,.doc,.docm,.txt,.md,.markdown";

const sourceOptions = {
  en: {
    data: "Data analysis",
    website: "Website analysis",
    content: "Content analysis",
  },
  vi: {
    data: "Phân tích dữ liệu",
    website: "Phân tích website",
    content: "Phân tích nội dung",
  },
} as const;

const modeOptions: Array<{ value: WebAnalysisMode; en: string; vi: string }> = [
  { value: "academic", en: "Academic report", vi: "Báo cáo học thuật" },
  { value: "marketing_seo", en: "Marketing/SEO", vi: "Marketing/SEO" },
  { value: "business", en: "Business analysis", vi: "Phân tích business" },
];

const quickPrompts = {
  en: [
    "Explain this simply",
    "Find key findings",
    "Show supporting evidence",
    "What should I do next?",
  ],
  vi: [
    "Giải thích thật dễ hiểu",
    "Tìm các phát hiện chính",
    "Cho tôi xem bằng chứng",
    "Tôi nên làm gì tiếp?",
  ],
} as const;

const composerCopy = {
  en: {
    labelAnalyze: "Ask Bitlysis",
    labelChat: "Continue this analysis",
    hint:
      "Choose a source type, then upload data, enter a website, or paste content for grounded explanation.",
    hintReady:
      "Bitlysis is grounded in the current source. Ask for explanation, evidence, interpretation, or next steps.",
    placeholders: {
      data: "Choose Data analysis, then press + to upload Excel or CSV...",
      website: "Paste a website URL, for example https://example.com",
      content: "Paste content, notes, survey text, or document excerpts...",
    },
    placeholderChat: "Ask a follow-up about this analysis...",
    search: "Search",
    modes: "Modes",
    addFile: "Add file",
    send: "Send",
    analyzing: "Understanding...",
    acceptedData: "Excel or CSV",
    acceptedContent: "DOC, TXT, Markdown",
    fileSelected: "Selected file",
    fileReady: "File ready. Press the arrow button to start analysis.",
    fileUploaded: "Uploaded",
    fileUploadedHint: "I will help interpret the results once the analysis is ready.",
    dataFileTypeError: "Please upload CSV, XLS, XLSX, or XLSM.",
    contentFileTypeError: "Please upload DOC, DOCX, DOCM, TXT, MD, or Markdown.",
    wordNeedsText:
      "File .doc (old Word format) is not supported directly. Please open it in Word and save as .docx, then upload again.",
    wordExtracting: "Reading Word file...",
    wordExtractError: "Could not read the Word file.",
    invalidUrl: "Enter a valid http or https website URL.",
    contentTooShort: "Paste at least 50 characters for content analysis.",
    assistantHello:
      "Choose a source type below. Data uses the + button, website uses the text field, and content supports pasted text or simple text files.",
    ready: "I have context for",
    readyHint: "Ask what it means, what supports it, or what to do next.",
  },
  vi: {
    labelAnalyze: "Hỏi Bitlysis",
    labelChat: "Tiếp tục phân tích này",
    hint:
      "Chọn loại nguồn, rồi tải dữ liệu, nhập website hoặc dán nội dung để nhận giải thích có căn cứ.",
    hintReady:
      "Bitlysis đang bám vào nguồn hiện tại. Hãy hỏi về giải thích, bằng chứng, diễn giải hoặc bước tiếp theo.",
    placeholders: {
      data: "Chọn Phân tích dữ liệu, rồi bấm + để tải Excel hoặc CSV...",
      website: "Dán URL website, ví dụ https://example.com",
      content: "Dán nội dung, ghi chú, khảo sát hoặc đoạn tài liệu...",
    },
    placeholderChat: "Hỏi tiếp về phân tích này...",
    search: "Search",
    modes: "Modes",
    addFile: "Thêm file",
    send: "Gửi",
    analyzing: "Đang hiểu...",
    acceptedData: "Excel hoặc CSV",
    acceptedContent: "DOC, TXT, Markdown",
    fileSelected: "Đã chọn file",
    fileReady: "File đã sẵn sàng. Bấm nút mũi tên để bắt đầu phân tích.",
    fileUploaded: "Đã tải lên",
    fileUploadedHint: "Tôi sẽ giúp diễn giải kết quả khi phân tích sẵn sàng.",
    dataFileTypeError: "Vui lòng tải CSV, XLS, XLSX hoặc XLSM.",
    contentFileTypeError: "Vui lòng tải DOC, DOCX, DOCM, TXT, MD hoặc Markdown.",
    wordNeedsText:
      "File .doc (định dạng Word cũ) chưa được hỗ trợ trực tiếp. Vui lòng mở trong Word, lưu lại dưới dạng .docx rồi tải lên lại.",
    wordExtracting: "Đang đọc file Word...",
    wordExtractError: "Không thể đọc nội dung file Word.",
    invalidUrl: "Hãy nhập URL website hợp lệ bắt đầu bằng http hoặc https.",
    contentTooShort: "Dán ít nhất 50 ký tự để phân tích nội dung.",
    assistantHello:
      "Chọn loại nguồn ở dưới. Dữ liệu dùng nút +, website dùng ô nhập, còn nội dung hỗ trợ dán text hoặc file text đơn giản.",
    ready: "Tôi đã có ngữ cảnh về",
    readyHint: "Hãy hỏi ý nghĩa, bằng chứng hỗ trợ hoặc bước tiếp theo.",
  },
} as const;

function formatAssistantMessage(value: string): string {
  return value
    .replace(/\r\n/g, "\n")
    .replace(/```(?:json|text)?\s*/gi, "")
    .replace(/```/g, "")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\*(.*?)\*/g, "$1")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function fileExtension(file: File): string {
  return file.name.split(".").pop()?.toLowerCase() ?? "";
}

function normalizeWebsiteUrl(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
    if (!parsed.hostname || !parsed.hostname.includes(".")) return null;
    return parsed.toString();
  } catch {
    return null;
  }
}

export function UploadZone({
  disabled,
  analysis,
  analysisMode,
  onAnalysisModeChange,
  onAnalyzePrompt,
  onAskAssistant,
  onUploadDataFile,
  onAcademicResult,
  onAnalyzeContent,
}: Props) {
  const { locale } = useI18n();
  const c = composerCopy[locale];
  const [sourceKind, setSourceKind] = useState<SourceKind>("website");
  const [sourceValue, setSourceValue] = useState("");
  const [chatValue, setChatValue] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [validationMessage, setValidationMessage] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const chatBottomRef = useRef<HTMLDivElement | null>(null);
  const textDisabled = !analysis && sourceKind === "data";
  const addDisabled = disabled || busy || uploading || (!analysis && sourceKind === "website");
  const acceptAttr = sourceKind === "content" ? CONTENT_ACCEPT_ATTR : DATA_ACCEPT_ATTR;

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!analysis) {
      setMessages([{ role: "assistant", content: c.assistantHello }]);
      return;
    }

    setMessages([
      {
        role: "assistant",
        content: `${c.ready} "${analysis.source_label}". ${c.readyHint}`,
      },
    ]);
  }, [analysis, c.assistantHello, c.ready, c.readyHint]);

  const addMessage = (message: ChatMessage) => {
    setMessages((current) => [...current, message]);
  };

  const runWebsiteAnalysis = async (rawValue: string) => {
    const url = normalizeWebsiteUrl(rawValue);
    if (!url) {
      setValidationMessage(c.invalidUrl);
      return;
    }

    setValidationMessage("");
    setSourceValue("");
    addMessage({ role: "user", content: url });
    setBusy(true);
    try {
      await onAnalyzePrompt(url);
    } finally {
      setBusy(false);
    }
  };

  const runContentAnalysis = async (rawValue: string) => {
    const cleaned = rawValue.trim();
    if (cleaned.length < 50) {
      setValidationMessage(c.contentTooShort);
      return;
    }

    setValidationMessage("");
    setSourceValue("");
    addMessage({ role: "user", content: cleaned.slice(0, 260) });
    setBusy(true);
    try {
      if (onAnalyzeContent) {
        await onAnalyzeContent(cleaned, locale);
      } else {
        const result = await analyzeAcademicContent({ text: cleaned, language: locale });
        onAcademicResult?.(result);
      }
      addMessage({ role: "assistant", content: c.fileUploadedHint });
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      addMessage({ role: "assistant", content: msg || c.fileUploadedHint });
    } finally {
      setBusy(false);
    }
  };

  const submitChat = async (value = chatValue) => {
    const cleaned = value.trim();
    if (!cleaned || disabled || busy || !analysis) return;
    setChatValue("");
    addMessage({ role: "user", content: cleaned });
    setBusy(true);
    try {
      const answer = await onAskAssistant(cleaned);
      addMessage({ role: "assistant", content: answer });
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = async () => {
    if (analysis) {
      await submitChat();
      return;
    }

    if (sourceKind === "website") {
      await runWebsiteAnalysis(sourceValue);
      return;
    }

    if (sourceKind === "data") {
      if (!selectedFile) {
        setValidationMessage(c.dataFileTypeError);
        return;
      }
      setValidationMessage("");
      setUploading(true);
      setBusy(true);
      try {
        await onUploadDataFile(selectedFile);
        addMessage({
          role: "assistant",
          content: `${c.fileUploaded}: ${selectedFile.name}. ${c.fileUploadedHint}`,
        });
        setSelectedFile(null);
      } finally {
        setUploading(false);
        setBusy(false);
      }
      return;
    }

    if (sourceKind === "content") {
      if (!sourceValue.trim() && selectedFile && WORD_FILE_EXTS.has(fileExtension(selectedFile))) {
        setValidationMessage(c.wordNeedsText);
        return;
      }
      await runContentAnalysis(sourceValue);
    }
  };

  const handlePrompt = async (prompt: string) => {
    if (analysis) {
      await submitChat(prompt);
      return;
    }
    if (sourceKind !== "data") setSourceValue(prompt);
  };

  const onPickFile = () => {
    if (addDisabled) return;
    fileInputRef.current?.click();
  };

  const processDataFile = async (file: File) => {
    const ext = fileExtension(file);
    if (!DATA_FILE_EXTS.has(ext)) {
      addMessage({ role: "assistant", content: c.dataFileTypeError });
      return;
    }

    setSelectedFile(file);
    setSourceValue("");
    setValidationMessage("");
    addMessage({ role: "user", content: `${c.fileSelected}: ${file.name}` });
    addMessage({ role: "assistant", content: c.fileReady });
  };

  const processContentFile = async (file: File) => {
    const ext = fileExtension(file);
    if (!TEXT_FILE_EXTS.has(ext) && !WORD_FILE_EXTS.has(ext)) {
      addMessage({ role: "assistant", content: c.contentFileTypeError });
      return;
    }

    addMessage({ role: "user", content: `${c.fileSelected}: ${file.name}` });
    setSelectedFile(file);

    if (TEXT_FILE_EXTS.has(ext)) {
      const text = await file.text();
      setSourceValue(text);
      addMessage({ role: "assistant", content: c.fileReady });
      return;
    }

    // Word file (.docx / .docm / .doc) — extract via backend
    addMessage({ role: "assistant", content: c.wordExtracting });
    setBusy(true);
    try {
      const result = await extractContentFile(file);
      setSourceValue(result.text);
      // Replace the "reading…" message with the ready confirmation
      setMessages((current) => {
        const updated = [...current];
        const lastIdx = updated.length - 1;
        if (updated[lastIdx]?.content === c.wordExtracting) {
          updated[lastIdx] = { role: "assistant", content: c.fileReady };
        } else {
          updated.push({ role: "assistant", content: c.fileReady });
        }
        return updated;
      });
    } catch (error) {
      const detail =
        error instanceof Error ? error.message : c.wordExtractError;
      setMessages((current) => {
        const updated = [...current];
        const lastIdx = updated.length - 1;
        if (updated[lastIdx]?.content === c.wordExtracting) {
          updated[lastIdx] = { role: "assistant", content: detail };
        } else {
          updated.push({ role: "assistant", content: detail });
        }
        return updated;
      });
      setSelectedFile(null);
    } finally {
      setBusy(false);
    }
  };

  const processSelectedFile = async (file: File) => {
    setValidationMessage("");
    if (sourceKind === "content") {
      await processContentFile(file);
      return;
    }
    await processDataFile(file);
  };

  const onFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || disabled) return;
    await processSelectedFile(file);
  };

  const composerValue = analysis ? chatValue : sourceValue;
  const setComposerValue = analysis ? setChatValue : setSourceValue;
  const canSubmit =
    !disabled &&
    !busy &&
    (analysis
      ? chatValue.trim().length > 0
      : sourceKind === "data"
        ? selectedFile !== null
        : sourceKind === "website" || sourceKind === "content"
          ? sourceValue.trim().length > 0 || selectedFile !== null
          : false);

  return (
    <section
      className={[
        "relative rounded-[30px] border border-(--border) bg-(--surface) p-4 shadow-[0_18px_48px_rgba(15,23,42,0.06)] sm:p-5",
        disabled ? "opacity-60" : "",
      ].join(" ")}
      aria-label={analysis ? c.labelChat : c.labelAnalyze}
    >
      <div className="space-y-4">
        <div>
          <p className="text-label text-(--accent)">{analysis ? c.labelChat : c.labelAnalyze}</p>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-(--muted)">
            {analysis ? c.hintReady : c.hint}
          </p>
        </div>

        <div
          className={[
            "rounded-[24px] border-2 bg-[#f3f2ee] p-4 text-[#161615] shadow-[0_18px_40px_rgba(15,23,42,0.06)] transition",
            dragOver ? "border-[#161615] ring-4 ring-[rgba(22,22,21,0.08)]" : "border-[#e4e2dc]",
          ].join(" ")}
          onDragOver={(event) => {
            event.preventDefault();
            if (!addDisabled) setDragOver(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            setDragOver(false);
          }}
          onDrop={(event) => {
            event.preventDefault();
            setDragOver(false);
            const file = event.dataTransfer.files?.[0];
            if (file && !addDisabled) void processSelectedFile(file);
          }}
        >
          <textarea
            value={composerValue}
            disabled={disabled || busy || textDisabled}
            onChange={(event) => {
              setValidationMessage("");
              setComposerValue(event.target.value);
            }}
            placeholder={analysis ? c.placeholderChat : c.placeholders[sourceKind]}
            rows={3}
            className="min-h-24 w-full resize-none bg-transparent text-[15px] leading-relaxed text-[#161615] outline-none placeholder:text-[#5a5a58] disabled:cursor-not-allowed disabled:opacity-45"
          />

          {validationMessage ? (
            <p className="mb-3 text-xs font-medium text-[#92400e]">{validationMessage}</p>
          ) : null}

          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={onPickFile}
                disabled={addDisabled}
                aria-label={c.addFile}
                className="flex h-9 w-9 items-center justify-center rounded-full border border-[#161615] bg-[#f6f0e6] text-2xl leading-none text-[#161615] transition hover:bg-[#dff2e8] disabled:cursor-not-allowed disabled:opacity-25"
              >
                +
              </button>

              <select
                value={sourceKind}
                disabled={disabled || busy || !!analysis}
                onChange={(event) => {
                  setSourceKind(event.target.value as SourceKind);
                  setSourceValue("");
                  setSelectedFile(null);
                  setValidationMessage("");
                }}
                className="h-9 rounded-full border border-[#161615] bg-white px-3 text-sm text-[#161615] outline-none disabled:opacity-50"
                aria-label={c.search}
              >
                {(Object.keys(sourceOptions[locale]) as SourceKind[]).map((kind) => (
                  <option key={kind} value={kind}>
                    {kind === sourceKind ? `${c.search} · ` : ""}
                    {sourceOptions[locale][kind]}
                  </option>
                ))}
              </select>

              <span className="hidden max-w-48 truncate text-xs text-[#5a5a58] sm:inline">
                {selectedFile?.name ?? (sourceKind === "content" ? c.acceptedContent : sourceKind === "data" ? c.acceptedData : "URL")}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <select
                value={analysisMode}
                disabled={disabled || busy}
                onChange={(event) => onAnalysisModeChange(event.target.value as WebAnalysisMode)}
                className="h-9 rounded-full border border-[#161615] bg-white px-3 text-sm text-[#161615] outline-none disabled:opacity-50"
                aria-label={c.modes}
              >
                {modeOptions.map((mode) => (
                  <option key={mode.value} value={mode.value}>
                    {`${c.modes} · ${mode[locale]}`}
                  </option>
                ))}
              </select>

              <button
                type="button"
                disabled={!canSubmit}
                onClick={() => void handleSubmit()}
                aria-label={c.send}
                className="flex h-10 w-10 items-center justify-center rounded-full border border-[#161615] bg-[#0f766e] text-white transition hover:bg-[#0f766e]/90 disabled:cursor-not-allowed disabled:opacity-35"
              >
                <span className="text-lg font-black leading-none">↑</span>
              </button>
            </div>
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept={acceptAttr}
          onChange={(event) => {
            void onFileChange(event);
          }}
        />

        <div className="flex flex-wrap gap-2">
          {quickPrompts[locale].map((prompt) => (
            <button
              key={prompt}
              type="button"
              disabled={disabled || busy || (!analysis && sourceKind === "data")}
              onClick={() => void handlePrompt(prompt)}
              className="rounded-full border border-[#161615] bg-[#f6f0e6] px-3 py-1.5 text-xs font-black uppercase text-[#161615] transition hover:bg-[#dff2e8] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {prompt}
            </button>
          ))}
        </div>

        <div className="max-h-80 min-h-48 space-y-2 overflow-auto rounded-[24px] border border-(--border) bg-(--surface-muted) p-3">
          {messages.map((message, idx) => (
            <div
              key={`${message.role}-${idx}`}
              className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[88%] rounded-2xl px-3 py-2 text-sm leading-relaxed ${
                  message.role === "user"
                    ? "bg-(--fg) text-(--surface)"
                    : "border border-(--border) bg-(--surface) text-(--fg)"
                }`}
              >
                <span className="whitespace-pre-wrap break-words">
                  {message.role === "assistant"
                    ? formatAssistantMessage(message.content)
                    : message.content}
                </span>
              </div>
            </div>
          ))}
          <div ref={chatBottomRef} />
        </div>
      </div>
    </section>
  );
}
