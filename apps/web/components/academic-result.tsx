"use client";

import { useI18n } from "@/lib/i18n";
import type {
  AcademicAnalyzeResponse,
  AcademicPaper,
  AcademicQuartile,
  FactCheckVerdict,
  FactCheckVerdictType,
} from "@/lib/types";

// ── Quartile badge ────────────────────────────────────────────────────────────

const QUARTILE_STYLES: Record<AcademicQuartile, string> = {
  Q1: "bg-emerald-100 text-emerald-800 border-emerald-300",
  Q2: "bg-blue-100 text-blue-800 border-blue-300",
  Q3: "bg-amber-100 text-amber-800 border-amber-300",
  Q4: "bg-gray-100 text-gray-600 border-gray-300",
  Unknown: "bg-gray-100 text-gray-500 border-gray-200",
};

function QuartileBadge({ q }: { q: AcademicQuartile }) {
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-bold leading-none ${QUARTILE_STYLES[q]}`}
    >
      {q}
    </span>
  );
}

// ── Verdict badge ─────────────────────────────────────────────────────────────

const VERDICT_STYLES: Record<FactCheckVerdictType, { cls: string; icon: string }> = {
  Supported: { cls: "bg-emerald-50 text-emerald-700 border-emerald-300", icon: "✓" },
  Contradicted: { cls: "bg-red-50 text-red-700 border-red-300", icon: "✗" },
  Partially_supported: { cls: "bg-amber-50 text-amber-700 border-amber-300", icon: "~" },
  Unverified: { cls: "bg-gray-50 text-gray-600 border-gray-200", icon: "?" },
};

function VerdictBadge({ verdict, label }: { verdict: FactCheckVerdictType; label: string }) {
  const { cls, icon } = VERDICT_STYLES[verdict];
  return (
    <span className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-semibold ${cls}`}>
      <span>{icon}</span>
      {label}
    </span>
  );
}

// ── Paper card ────────────────────────────────────────────────────────────────

function PaperCard({ paper, t }: { paper: AcademicPaper; t: (k: string) => string }) {
  const authorsStr =
    paper.authors.length > 0
      ? paper.authors.slice(0, 3).join(", ") + (paper.authors.length > 3 ? " et al." : "")
      : "";

  return (
    <div className="rounded-xl border border-(--border) bg-(--surface) p-4 transition-shadow hover:shadow-md">
      <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <QuartileBadge q={paper.quartile} />
          {paper.open_access && (
            <span className="rounded border border-teal-300 bg-teal-50 px-1.5 py-0.5 text-[10px] font-bold text-teal-700">
              {t("academic.openAccess")}
            </span>
          )}
          {paper.year && (
            <span className="text-[11px] text-(--muted)">{paper.year}</span>
          )}
        </div>
        <span className="text-[11px] text-(--muted)">
          {paper.cited_by_count.toLocaleString()} citations
        </span>
      </div>

      <h4 className="mb-1 text-sm font-semibold leading-snug text-(--fg) line-clamp-2">
        {paper.title}
      </h4>

      {authorsStr && (
        <p className="mb-1 text-xs text-(--muted)">{authorsStr}</p>
      )}
      {paper.source_name && (
        <p className="mb-2 text-[11px] italic text-(--muted)">{paper.source_name}</p>
      )}

      {paper.abstract && (
        <p className="mb-3 text-xs leading-relaxed text-(--fg-secondary) line-clamp-3">
          {paper.abstract}
        </p>
      )}

      {paper.url && (
        <a
          href={paper.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-600 hover:underline"
        >
          {t("academic.viewPaper")} →
        </a>
      )}
    </div>
  );
}

// ── Fact-check row ────────────────────────────────────────────────────────────

function FactCheckRow({ fc, t }: { fc: FactCheckVerdict; t: (k: string) => string }) {
  const verdictLabels: Record<FactCheckVerdictType, string> = {
    Supported: t("academic.verdicts.Supported"),
    Contradicted: t("academic.verdicts.Contradicted"),
    Partially_supported: t("academic.verdicts.Partially_supported"),
    Unverified: t("academic.verdicts.Unverified"),
  };

  return (
    <div className="rounded-xl border border-(--border) bg-(--surface) p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <VerdictBadge verdict={fc.verdict} label={verdictLabels[fc.verdict]} />
        <span className="text-xs text-(--muted)">
          {t("academic.confidence")}: {Math.round(fc.confidence * 100)}%
        </span>
      </div>

      <p className="mb-2 text-sm font-medium text-(--fg)">{fc.claim}</p>

      {fc.reasoning && (
        <p className="mb-2 text-xs leading-relaxed text-(--fg-secondary)">
          {fc.reasoning}
        </p>
      )}

      {fc.supporting_papers.length > 0 && (
        <div className="mt-1">
          <span className="text-[11px] font-semibold text-emerald-700">
            {t("academic.supportingPapers")}:{" "}
          </span>
          <span className="text-[11px] text-(--muted)">
            {fc.supporting_papers.join("; ")}
          </span>
        </div>
      )}
      {fc.contradicting_papers.length > 0 && (
        <div className="mt-1">
          <span className="text-[11px] font-semibold text-red-700">
            {t("academic.contradictingPapers")}:{" "}
          </span>
          <span className="text-[11px] text-(--muted)">
            {fc.contradicting_papers.join("; ")}
          </span>
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface AcademicResultProps {
  result: AcademicAnalyzeResponse;
}

export function AcademicResult({ result }: AcademicResultProps) {
  const { t } = useI18n();
  const supportPct = Math.round(result.overall_support_score * 100);

  return (
    <div className="space-y-8">
      {/* Summary + stats */}
      <div className="rounded-2xl border border-(--border) bg-(--surface) p-5">
        <p className="mb-4 text-sm leading-relaxed text-(--fg)">{result.summary}</p>

        <div className="flex flex-wrap gap-6">
          {/* Support score */}
          <div className="min-w-[120px]">
            <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-(--muted)">
              {t("academic.supportScore")}
            </p>
            <p className="text-3xl font-bold text-(--fg)">{supportPct}%</p>
          </div>

          {/* Quartile distribution */}
          {Object.keys(result.quartile_distribution).length > 0 && (
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-(--muted)">
                {t("academic.quartileTitle")}
              </p>
              <div className="flex flex-wrap gap-2">
                {(["Q1", "Q2", "Q3", "Q4", "Unknown"] as AcademicQuartile[]).map((q) => {
                  const count = result.quartile_distribution[q] ?? 0;
                  if (!count) return null;
                  return (
                    <div key={q} className="flex items-center gap-1">
                      <QuartileBadge q={q} />
                      <span className="text-xs font-medium text-(--fg)">{count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Keywords */}
        {result.keywords.length > 0 && (
          <div className="mt-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-(--muted)">
              {t("academic.keywordsLabel")}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {result.keywords.map((kw) => (
                <span
                  key={kw}
                  className="rounded-full border border-(--border) bg-(--bg) px-2.5 py-0.5 text-xs text-(--fg-secondary)"
                >
                  {kw}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Papers */}
      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-(--muted)">
          {result.papers.length} {t("academic.papersFound")}
        </p>
        {result.papers.length === 0 ? (
          <p className="text-sm text-(--muted)">{t("academic.noPapers")}</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {result.papers.map((p, i) => (
              <PaperCard key={`${p.doi ?? p.title}-${i}`} paper={p} t={t} />
            ))}
          </div>
        )}
      </div>

      {/* Fact-checks */}
      {result.fact_checks.length > 0 && (
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-(--muted)">
            {t("academic.factCheckTitle")}
          </p>
          <div className="space-y-3">
            {result.fact_checks.map((fc, i) => (
              <FactCheckRow key={i} fc={fc} t={t} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
