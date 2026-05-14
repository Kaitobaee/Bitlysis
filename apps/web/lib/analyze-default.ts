/**
 * Spec mặc định: comprehensive_analysis (orchestrator một-lần-chạy).
 * Backend xử lý: profile → cleaning → hypothesis suggestion → engine dispatch
 * (stats / psychometrics Python / timeseries) → schema thống nhất.
 */
export function comprehensiveAnalysisSpec(language: "vi" | "en" = "vi"): {
  kind: "comprehensive_analysis";
  enable_psychometrics: boolean;
  enable_pls: boolean;
  enable_timeseries: boolean;
  enable_llm_hypotheses: boolean;
  max_categorical_pairs: number;
  max_group_comparisons: number;
  random_seed: number | null;
  language: "vi" | "en";
} {
  return {
    kind: "comprehensive_analysis",
    enable_psychometrics: true,
    enable_pls: true,
    enable_timeseries: true,
    enable_llm_hypotheses: false,
    max_categorical_pairs: 8,
    max_group_comparisons: 12,
    random_seed: 42,
    language,
  };
}

/** Alias deprecated giữ tương thích cho import cũ. */
export const fullAutoAnalysisSpec = comprehensiveAnalysisSpec;
