/** Spec mặc định mới: phân tích toàn bộ dữ liệu, ưu tiên R nếu có. */
export function fullAutoAnalysisSpec(): {
  kind: "full_auto_analysis";
  prefer_r: boolean;
  max_categorical_pairs: number;
  max_group_comparisons: number;
} {
  return {
    kind: "full_auto_analysis",
    prefer_r: true,
    max_categorical_pairs: 8,
    max_group_comparisons: 12,
  };
}
