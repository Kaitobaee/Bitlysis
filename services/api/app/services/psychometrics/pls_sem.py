"""PLS-SEM thuần Python (NIPALS, reflective).

Tham chiếu thuật toán:
- Wold (1985), Lohmöller (1989) NIPALS.
- Henseler et al. (2015) HTMT.
- Dijkstra & Henseler (2015) rho_A.
- Hair et al. (2017) công thức composite reliability / AVE / f² / Q².

Tính năng:
- Inner weighting scheme: path-weighting (mặc định, giống seminr default).
- Outer mode: reflective (Mode A) — duy nhất hỗ trợ trong phase này.
- Bootstrap percentile CI cho path & loadings.
- HTMT, Fornell-Larcker, AVE, CR, rho_A, R², adjusted R², f², Q² (blindfolding).
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


DEFAULT_MAX_ITER = 300
DEFAULT_CONVERGE_TOL = 1e-7
DEFAULT_BOOTSTRAP_N = 500
DEFAULT_BOOTSTRAP_CI = 0.95
DEFAULT_BLINDFOLD_DISTANCE = 7


def _standardize(arr: np.ndarray) -> np.ndarray:
    mean = arr.mean(axis=0)
    std = arr.std(axis=0, ddof=1)
    std = np.where(std == 0, 1.0, std)
    return (arr - mean) / std


def _ols_coefs(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """OLS không intercept (vì X & Y đã standardize), trả vector hệ số."""
    if x.ndim == 1:
        x = x.reshape(-1, 1)
    # Pseudo-inverse cho ổn định khi gần colinear
    return np.linalg.pinv(x) @ y


class _Model:
    def __init__(
        self,
        constructs: list[dict[str, Any]],
        paths: list[dict[str, Any]],
        df: pd.DataFrame,
    ) -> None:
        self.construct_names: list[str] = [str(c["name"]) for c in constructs]
        self.indicators: dict[str, list[str]] = {
            str(c["name"]): [str(i) for i in c["indicators"]] for c in constructs
        }
        self.mode: dict[str, str] = {
            str(c["name"]): str(c.get("mode") or "reflective") for c in constructs
        }
        self.paths: list[tuple[str, str]] = []
        for p in paths or []:
            froms = p.get("from")
            tos = p.get("to")
            if isinstance(froms, list):
                fs = [str(x) for x in froms]
            else:
                fs = [str(froms)] if froms is not None else []
            if isinstance(tos, list):
                ts = [str(x) for x in tos]
            else:
                ts = [str(tos)] if tos is not None else []
            for a in fs:
                for b in ts:
                    if a in self.indicators and b in self.indicators:
                        self.paths.append((a, b))
        self.predecessors: dict[str, list[str]] = {n: [] for n in self.construct_names}
        self.successors: dict[str, list[str]] = {n: [] for n in self.construct_names}
        for src, dst in self.paths:
            self.predecessors[dst].append(src)
            self.successors[src].append(dst)
        self.endogenous: list[str] = [
            n for n in self.construct_names if self.predecessors[n]
        ]
        self.exogenous: list[str] = [
            n for n in self.construct_names if not self.predecessors[n]
        ]
        # Chuẩn hóa indicators ma trận theo construct.
        self.X: dict[str, np.ndarray] = {}
        for name, items in self.indicators.items():
            self.X[name] = _standardize(df[items].to_numpy(dtype=float))


def _nipals(
    model: _Model,
    *,
    max_iter: int = DEFAULT_MAX_ITER,
    tol: float = DEFAULT_CONVERGE_TOL,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], int, bool]:
    """Trả (weights, scores, n_iter, converged)."""
    weights: dict[str, np.ndarray] = {}
    scores: dict[str, np.ndarray] = {}
    for name, X in model.X.items():
        # Init: trung bình các indicator (chuẩn hóa).
        w = np.ones(X.shape[1]) / X.shape[1]
        score = X @ w
        score = (score - score.mean()) / (score.std(ddof=1) or 1.0)
        weights[name] = w
        scores[name] = score

    converged = False
    n_iter = 0
    for it in range(1, max_iter + 1):
        n_iter = it
        # Inner approximation theo path-weighting scheme.
        inner_scores: dict[str, np.ndarray] = {}
        for name in model.construct_names:
            preds = model.predecessors[name]
            succs = model.successors[name]
            acc = np.zeros_like(scores[name])
            if preds:
                P = np.column_stack([scores[p] for p in preds])
                beta = _ols_coefs(P, scores[name])
                for j, p in enumerate(preds):
                    acc = acc + float(beta[j]) * scores[p]
            for s in succs:
                r = float(np.corrcoef(scores[name], scores[s])[0, 1])
                if not np.isfinite(r):
                    r = 0.0
                acc = acc + r * scores[s]
            if preds or succs:
                inner_scores[name] = acc
            else:
                inner_scores[name] = scores[name]
        # Outer update (Mode A reflective): weight = cov(X_i, inner_score) / var(inner_score).
        new_weights: dict[str, np.ndarray] = {}
        new_scores: dict[str, np.ndarray] = {}
        max_diff = 0.0
        for name, X in model.X.items():
            inner = inner_scores[name]
            inner_var = float(np.var(inner, ddof=1)) or 1.0
            # Mode A: cov / var
            w_new = (X.T @ (inner - inner.mean())) / ((X.shape[0] - 1) * inner_var)
            # Chuẩn hóa để LV score có phương sai 1.
            score_new = X @ w_new
            sd = float(score_new.std(ddof=1)) or 1.0
            w_new = w_new / sd
            score_new = (X @ w_new)
            score_new = score_new - score_new.mean()
            score_new = score_new / (float(score_new.std(ddof=1)) or 1.0)
            diff = float(np.max(np.abs(w_new - weights[name])))
            if diff > max_diff:
                max_diff = diff
            new_weights[name] = w_new
            new_scores[name] = score_new
        weights = new_weights
        scores = new_scores
        if max_diff < tol:
            converged = True
            break
    return weights, scores, n_iter, converged


def _outer_loadings(
    model: _Model,
    scores: dict[str, np.ndarray],
) -> dict[str, list[dict[str, float]]]:
    """LV-indicator correlation (loadings) mỗi construct."""
    out: dict[str, list[dict[str, float]]] = {}
    for name, items in model.indicators.items():
        X = model.X[name]
        s = scores[name]
        rows: list[dict[str, float]] = []
        for j, item in enumerate(items):
            r = float(np.corrcoef(X[:, j], s)[0, 1])
            if not np.isfinite(r):
                r = 0.0
            rows.append({"construct": name, "item": item, "loading": r})
        out[name] = rows
    return out


def _ave(loadings_by_c: dict[str, list[dict[str, float]]]) -> dict[str, float]:
    ave: dict[str, float] = {}
    for name, rows in loadings_by_c.items():
        ls = np.array([r["loading"] for r in rows], dtype=float)
        if ls.size == 0:
            ave[name] = float("nan")
        else:
            ave[name] = float((ls**2).mean())
    return ave


def _composite_reliability(
    loadings_by_c: dict[str, list[dict[str, float]]],
) -> dict[str, float]:
    out: dict[str, float] = {}
    for name, rows in loadings_by_c.items():
        ls = np.array([r["loading"] for r in rows], dtype=float)
        sum_l = float(ls.sum())
        sum_err = float((1 - ls**2).sum())
        denom = sum_l**2 + sum_err
        out[name] = float((sum_l**2) / denom) if denom > 0 else float("nan")
    return out


def _rho_a(
    model: _Model,
    weights: dict[str, np.ndarray],
) -> dict[str, float]:
    """Dijkstra & Henseler (2015) rho_A: ước lượng độ tin cậy nhất quán PLS."""
    out: dict[str, float] = {}
    for name, items in model.indicators.items():
        X = model.X[name]
        w = weights[name]
        K = X.shape[1]
        if K < 2 or X.shape[0] < 2:
            out[name] = float("nan")
            continue
        S = np.cov(X, rowvar=False, ddof=1)
        # off-diagonal sums
        S_off = S - np.diag(np.diag(S))
        ww_off = np.outer(w, w) - np.diag(np.diag(np.outer(w, w)))
        num = float(w @ S_off @ w)
        den = float(w @ ww_off @ w)
        if den == 0:
            out[name] = float("nan")
            continue
        ratio = num / den
        # rho_A = (w'w)^2 * (w'(S - diag(S))w / w'(ww' - diag(ww'))w)
        wtw = float(w @ w)
        out[name] = float((wtw**2) * ratio)
    return out


def _structural(
    model: _Model,
    scores: dict[str, np.ndarray],
) -> tuple[list[dict[str, Any]], dict[str, float], dict[str, float]]:
    """OLS scores chuẩn hóa cho mỗi endogenous LV → path_coef, R², adj R²."""
    paths_out: list[dict[str, Any]] = []
    r2: dict[str, float] = {}
    adj_r2: dict[str, float] = {}
    for endo in model.endogenous:
        preds = model.predecessors[endo]
        if not preds:
            continue
        y = scores[endo]
        X = np.column_stack([scores[p] for p in preds])
        beta = _ols_coefs(X, y)
        y_hat = X @ beta
        ss_res = float(np.sum((y - y_hat) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r2_val = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        n = X.shape[0]
        p = X.shape[1]
        if n - p - 1 > 0 and np.isfinite(r2_val):
            adj_val = 1.0 - (1.0 - r2_val) * (n - 1) / (n - p - 1)
        else:
            adj_val = float("nan")
        r2[endo] = float(r2_val) if np.isfinite(r2_val) else float("nan")
        adj_r2[endo] = float(adj_val) if np.isfinite(adj_val) else float("nan")
        for j, src in enumerate(preds):
            paths_out.append({
                "from": src,
                "to": endo,
                "path_coef": float(beta[j]),
            })
    return paths_out, r2, adj_r2


def _f_squared(
    model: _Model,
    scores: dict[str, np.ndarray],
    r2_full: dict[str, float],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for endo in model.endogenous:
        preds = model.predecessors[endo]
        if not preds:
            continue
        r2_inc = r2_full.get(endo, float("nan"))
        for excl in preds:
            others = [p for p in preds if p != excl]
            if not others:
                # f^2 vs null model: R^2_excluded = 0
                r2_excl = 0.0
            else:
                X = np.column_stack([scores[p] for p in others])
                y = scores[endo]
                beta = _ols_coefs(X, y)
                y_hat = X @ beta
                ss_res = float(np.sum((y - y_hat) ** 2))
                ss_tot = float(np.sum((y - y.mean()) ** 2))
                r2_excl = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
            if not np.isfinite(r2_inc) or not np.isfinite(r2_excl):
                f2 = float("nan")
            elif (1.0 - r2_inc) <= 0:
                f2 = float("nan")
            else:
                f2 = float((r2_inc - r2_excl) / (1.0 - r2_inc))
            rows.append({
                "from": excl,
                "to": endo,
                "f_squared": f2,
            })
    return rows


def _htmt(
    model: _Model,
    df: pd.DataFrame,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    names = model.construct_names
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            items_a = model.indicators[a]
            items_b = model.indicators[b]
            if not items_a or not items_b:
                continue
            # Heterotrait (cross): abs cor giữa indicator a với indicator b
            cor_ab: list[float] = []
            for ia in items_a:
                for ib in items_b:
                    r = float(df[ia].corr(df[ib]))
                    if np.isfinite(r):
                        cor_ab.append(abs(r))
            # Monotrait: abs cor giữa indicator cùng construct (off-diagonal).
            def _mono(items: list[str]) -> list[float]:
                vals: list[float] = []
                for x in range(len(items)):
                    for y in range(x + 1, len(items)):
                        r = float(df[items[x]].corr(df[items[y]]))
                        if np.isfinite(r):
                            vals.append(abs(r))
                return vals

            mono_a = _mono(items_a)
            mono_b = _mono(items_b)
            if not cor_ab or (not mono_a and not mono_b):
                out.append({"from": a, "to": b, "htmt": None})
                continue
            num = float(np.mean(cor_ab))
            if mono_a and mono_b:
                den = float(np.sqrt(np.mean(mono_a) * np.mean(mono_b)))
            elif mono_a:
                den = float(np.mean(mono_a))
            else:
                den = float(np.mean(mono_b))
            ratio = num / den if den > 0 else float("nan")
            out.append({
                "from": a,
                "to": b,
                "htmt": float(ratio) if np.isfinite(ratio) else None,
            })
    return out


def _fornell_larcker(
    ave: dict[str, float],
    scores: dict[str, np.ndarray],
) -> list[dict[str, Any]]:
    names = list(ave.keys())
    rows: list[dict[str, Any]] = []
    for i, ni in enumerate(names):
        row: dict[str, Any] = {"construct": ni}
        for j, nj in enumerate(names):
            if i == j:
                v = float(np.sqrt(ave[ni])) if np.isfinite(ave[ni]) and ave[ni] >= 0 else None
            else:
                r = float(np.corrcoef(scores[ni], scores[nj])[0, 1])
                v = float(r) if np.isfinite(r) else None
            row[nj] = v
        rows.append(row)
    return rows


def _blindfold_q2(
    model: _Model,
    weights: dict[str, np.ndarray],
    scores_full: dict[str, np.ndarray],
    *,
    distance: int = DEFAULT_BLINDFOLD_DISTANCE,
) -> dict[str, float]:
    """Cross-validated communality blindfolding (sơ giản — không tái fit toàn bộ).

    Mỗi vòng d, omit các ô (i, j) thoả ((i*K + j) mod d == round). Dự đoán giá trị
    bị omit từ outer mean (score * loading + mean), tính SSE/SSO → Q² = 1 - SSE/SSO.
    """
    out: dict[str, float] = {}
    for endo in model.endogenous:
        X = model.X[endo]
        s = scores_full[endo]
        if X.size == 0:
            out[endo] = float("nan")
            continue
        # Loading mỗi item (chuẩn hóa Pearson với LV score).
        loadings = np.array([
            float(np.corrcoef(X[:, j], s)[0, 1]) for j in range(X.shape[1])
        ])
        loadings = np.where(np.isfinite(loadings), loadings, 0.0)
        n_rows, K = X.shape
        sso = 0.0
        sse = 0.0
        for d in range(distance):
            mask = np.zeros((n_rows, K), dtype=bool)
            for r in range(n_rows):
                for c in range(K):
                    if ((r * K + c) % distance) == d:
                        mask[r, c] = True
            if not mask.any():
                continue
            # Predicted = LV score * loading; thực ra X đã standardized, mean=0.
            pred = np.outer(s, loadings)
            err = (X - pred) ** 2
            sso += float(np.sum(X[mask] ** 2))
            sse += float(np.sum(err[mask]))
        out[endo] = float(1.0 - sse / sso) if sso > 0 else float("nan")
    # Exogenous: blindfolding không định nghĩa Q² (giữ NaN ngầm).
    return out


def _bootstrap_paths_loadings(
    df_orig: pd.DataFrame,
    constructs: list[dict[str, Any]],
    paths: list[dict[str, Any]],
    indicators_used: list[str],
    *,
    n_boot: int,
    ci: float,
    rng: np.random.Generator,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Trả (path_bootstrap_rows, loading_bootstrap_rows)."""
    alpha = 1.0 - ci
    lo_q = alpha / 2.0
    hi_q = 1.0 - alpha / 2.0

    path_samples: dict[tuple[str, str], list[float]] = {}
    loading_samples: dict[tuple[str, str], list[float]] = {}

    n_rows = len(df_orig)
    df_sub = df_orig[indicators_used].astype(float).reset_index(drop=True)

    boot_done = 0
    failures = 0
    for _ in range(n_boot):
        idx = rng.integers(0, n_rows, size=n_rows)
        df_b = df_sub.iloc[idx].reset_index(drop=True)
        try:
            model_b = _Model(constructs, paths, df_b)
            w_b, s_b, _, _ = _nipals(model_b)
            paths_rows, _r2, _adj = _structural(model_b, s_b)
            load_b = _outer_loadings(model_b, s_b)
        except Exception:  # noqa: BLE001
            failures += 1
            continue
        for p in paths_rows:
            key = (p["from"], p["to"])
            path_samples.setdefault(key, []).append(float(p["path_coef"]))
        for name, rows in load_b.items():
            for r in rows:
                key2 = (name, r["item"])
                loading_samples.setdefault(key2, []).append(float(r["loading"]))
        boot_done += 1

    path_rows: list[dict[str, Any]] = []
    for (src, dst), samples in path_samples.items():
        arr = np.array(samples)
        path_rows.append({
            "from": src,
            "to": dst,
            "mean": float(arr.mean()),
            "std_error": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
            "ci_low": float(np.quantile(arr, lo_q)),
            "ci_high": float(np.quantile(arr, hi_q)),
            "t_value": float(arr.mean() / (arr.std(ddof=1) or float("nan"))),
            "n_samples": int(arr.size),
        })

    load_rows: list[dict[str, Any]] = []
    for (cname, item), samples in loading_samples.items():
        arr = np.array(samples)
        load_rows.append({
            "construct": cname,
            "item": item,
            "mean": float(arr.mean()),
            "std_error": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
            "ci_low": float(np.quantile(arr, lo_q)),
            "ci_high": float(np.quantile(arr, hi_q)),
            "n_samples": int(arr.size),
        })

    return path_rows, load_rows


def run_pls_sem(
    df: pd.DataFrame,
    block: dict[str, Any],
    *,
    random_seed: int | None = None,
) -> dict[str, Any]:
    min_n = int(block.get("min_n") or 100)
    min_items = int(block.get("min_items_per_construct") or 2)
    min_constructs = int(block.get("min_constructs") or 2)
    constructs = list(block.get("constructs") or [])
    paths = list(block.get("paths") or [])

    n_boot = int(block.get("bootstrap_samples") or DEFAULT_BOOTSTRAP_N)
    if n_boot < 0:
        n_boot = 0
    ci = float(block.get("bootstrap_ci") or DEFAULT_BOOTSTRAP_CI)
    if not (0.5 < ci < 0.9999):
        ci = DEFAULT_BOOTSTRAP_CI

    warnings: list[str] = []

    if not constructs:
        return {
            "type": "pls_sem",
            "ok": True,
            "ran": False,
            "skipped": True,
            "warnings": ["PLS-SEM skipped: không có constructs."],
            "gates": {},
        }

    # Validate construct items + mode.
    indicators_used: list[str] = []
    for co in constructs:
        name = str(co.get("name") or "unnamed")
        items = list(co.get("indicators") or [])
        mode = str(co.get("mode") or "reflective")
        if mode != "reflective":
            warnings.append(
                f"Construct '{name}': chỉ hỗ trợ mode=reflective; phát hiện '{mode}'.",
            )
        if len(items) < min_items:
            warnings.append(
                f"Construct '{name}': {len(items)} chỉ số < min_items_per_construct={min_items}.",
            )
        indicators_used.extend(items)

    if len(constructs) < min_constructs:
        warnings.append(
            f"Số construct={len(constructs)} < min_constructs={min_constructs}.",
        )

    missing = [c for c in indicators_used if c not in df.columns]
    if missing:
        warnings.append(f"Thiếu cột: {', '.join(missing)}")

    if not paths:
        warnings.append("Không có structural paths — bỏ qua ước lượng PLS.")

    if warnings:
        return {
            "type": "pls_sem",
            "ok": True,
            "ran": False,
            "skipped": True,
            "warnings": warnings,
            "gates": {
                "min_n": min_n,
                "min_items_per_construct": min_items,
                "min_constructs": min_constructs,
            },
        }

    sub = df[indicators_used].apply(pd.to_numeric, errors="coerce").dropna(how="any")
    n_ok = int(len(sub))
    if n_ok < min_n:
        return {
            "type": "pls_sem",
            "ok": True,
            "ran": False,
            "skipped": True,
            "warnings": [f"Sau listwise: n={n_ok} < min_n={min_n}."],
            "gates": {"n": n_ok, "min_n": min_n},
        }

    model = _Model(constructs, paths, sub.reset_index(drop=True))
    weights, scores, n_iter, converged = _nipals(model)
    if not converged:
        warnings.append(f"NIPALS không hội tụ sau {n_iter} vòng (kết quả vẫn trả về).")

    loadings_by_c = _outer_loadings(model, scores)
    measurement_rows: list[dict[str, Any]] = []
    for rows in loadings_by_c.values():
        measurement_rows.extend(rows)

    ave = _ave(loadings_by_c)
    cr = _composite_reliability(loadings_by_c)
    rho_a = _rho_a(model, weights)
    path_coef_rows, r2, adj_r2 = _structural(model, scores)
    f2_rows = _f_squared(model, scores, r2)
    htmt_rows = _htmt(model, sub.reset_index(drop=True))
    fl_matrix = _fornell_larcker(ave, scores)
    q2 = _blindfold_q2(model, weights, scores)

    rng = np.random.default_rng(random_seed)
    if n_boot > 0:
        boot_paths, boot_loadings = _bootstrap_paths_loadings(
            sub.reset_index(drop=True),
            constructs,
            paths,
            indicators_used,
            n_boot=n_boot,
            ci=ci,
            rng=rng,
        )
    else:
        boot_paths, boot_loadings = [], []

    weights_rows: list[dict[str, Any]] = []
    for name, items in model.indicators.items():
        w = weights[name]
        for it, val in zip(items, w.tolist(), strict=True):
            weights_rows.append({
                "construct": name,
                "item": it,
                "weight": float(val),
            })

    reliability_rows = [
        {
            "construct": name,
            "ave": float(ave[name]) if np.isfinite(ave[name]) else None,
            "composite_reliability": float(cr[name]) if np.isfinite(cr[name]) else None,
            "rho_a": float(rho_a[name]) if np.isfinite(rho_a[name]) else None,
        }
        for name in model.construct_names
    ]

    r2_rows = [
        {
            "construct": k,
            "r_squared": float(v) if np.isfinite(v) else None,
            "adj_r_squared": float(adj_r2.get(k, float("nan")))
            if np.isfinite(adj_r2.get(k, float("nan")))
            else None,
        }
        for k, v in r2.items()
    ]

    q2_rows = [
        {"construct": k, "q_squared": float(v) if np.isfinite(v) else None}
        for k, v in q2.items()
    ]

    return {
        "type": "pls_sem",
        "ok": True,
        "ran": True,
        "skipped": False,
        "n": n_ok,
        "converged": converged,
        "n_iterations": n_iter,
        "construct_names": model.construct_names,
        "endogenous": model.endogenous,
        "exogenous": model.exogenous,
        "measurement_model": {
            "outer_loadings": measurement_rows,
            "outer_weights": weights_rows,
            "reliability": reliability_rows,
        },
        "structural_model": {
            "path_coefficients": path_coef_rows,
            "r_squared": r2_rows,
            "f_squared": f2_rows,
            "q_squared": q2_rows,
        },
        "htmt": htmt_rows,
        "fornell_larcker": fl_matrix,
        "bootstrapping": {
            "n_samples": n_boot,
            "ci": ci,
            "paths": boot_paths,
            "loadings": boot_loadings,
        },
        # Aliases tương thích shape R cũ.
        "path_coef": path_coef_rows,
        "warnings": warnings,
        "gates": {"min_n": min_n, "min_items_per_construct": min_items},
    }
