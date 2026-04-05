/** Spec mặc định an toàn cho demo: liên kết hai biến phân loại. */
export function defaultCategoricalSpec(columns: string[]): {
  kind: "categorical_association";
  variable_a: string;
  variable_b: string;
} {
  if (columns.length < 2) {
    throw new Error("NEED_TWO_COLUMNS");
  }
  return {
    kind: "categorical_association",
    variable_a: columns[0]!,
    variable_b: columns[1]!,
  };
}
