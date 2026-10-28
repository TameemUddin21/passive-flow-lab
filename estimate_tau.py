"""
Estimate the tracking factor (tau) from cleaned S&P 500 event data.

Model: excess_volume(i) ~= tau * shares(i), fit separately for additions and
deletions by weighted least squares through the origin, scaling both sides
by ADV so that small, illiquid names don't dominate the fit:

    y = excess_volume / adv
    x = shares / adv
    tau_hat = sum(x*y) / sum(x*x)

`shares` stands in for the float-share change an event causes. This is a
simplification: it's total shares outstanding, not the free float, and not
the portion specifically held by passive trackers. tau here should be read
as "fraction of total shares outstanding that changes hands on the event
day", not as a literal passive-ownership percentage. [VERIFY / improve once
real free-float data is available.]

Before fitting, rows with an implausible share count are dropped and logged
(not silently) — a handful of EDGAR extractions returned shares in the
hundreds or thousands, which would badly distort the regression if left in.

Run from the repo root (where data/event_results_clean.csv lives):
    python estimate_tau.py

Writes:
    data/tau_estimates.csv          - tau per action, with fit diagnostics
    data/tau_shares_excluded.csv    - rows dropped for implausible shares
"""

from __future__ import annotations

import pandas as pd

PATH_IN = "data/event_results_clean.csv"
TAU_OUT = "data/tau_estimates.csv"
SHARES_LOG_OUT = "data/tau_shares_excluded.csv"

# No S&P 500 constituent has fewer than this many shares outstanding. Rows
# below this are almost certainly a bad data extraction, not a real company.
MIN_PLAUSIBLE_SHARES = 1_000_000

# Walk-forward split: fit tau on events before this year, test on events
# from this year on. A crude first check of out-of-sample stability.
HOLDOUT_FROM_YEAR = 2020


def fit_tau(df: pd.DataFrame) -> dict:
    """Weighted least squares through the origin: excess/adv ~= tau * shares/adv."""
    x = df["shares"] / df["adv"]
    y = df["excess_volume"] / df["adv"]
    tau_hat = (x * y).sum() / (x * x).sum()
    resid = y - tau_hat * x
    return {
        "tau_hat": tau_hat,
        "n": len(df),
        "resid_std": resid.std(),
        "resid_mean": resid.mean(),
    }


def predict_and_score(df: pd.DataFrame, tau_hat: float) -> dict:
    """Compare predicted excess volume (tau_hat * shares) to what happened."""
    x = df["shares"] / df["adv"]
    y = df["excess_volume"] / df["adv"]
    pred = tau_hat * x
    error = y - pred
    return {
        "n": len(df),
        "mae_adv_multiples": error.abs().mean(),
        "bias_adv_multiples": error.mean(),
    }


def main(path_in: str = PATH_IN) -> None:
    df = pd.read_csv(path_in, parse_dates=["effective_date", "trade_date"])
    print(f"Loaded {len(df)} rows from {path_in}")

    implausible = df[df["shares"] < MIN_PLAUSIBLE_SHARES]
    if not implausible.empty:
        print(
            f"\nDropping {len(implausible)} rows with shares < "
            f"{MIN_PLAUSIBLE_SHARES:,} (likely bad EDGAR extraction):"
        )
        print(implausible[["ticker", "action", "effective_date", "shares"]].to_string(index=False))
        implausible[["ticker", "action", "effective_date", "shares"]].to_csv(
            SHARES_LOG_OUT, index=False
        )

    df = df[df["shares"] >= MIN_PLAUSIBLE_SHARES].copy()
    print(f"\n{len(df)} rows remain for fitting.")

    # ── Fit on the full cleaned sample, per action ──────────────────────
    results = []
    for action in ["add", "delete"]:
        sub = df[df["action"] == action]
        fit = fit_tau(sub)
        fit["action"] = action
        fit["sample"] = "full"
        results.append(fit)

    print("\n=== Tau estimates (full sample) ===")
    for r in results:
        print(
            f"  {r['action']:7s} n={r['n']:4d}  tau_hat={r['tau_hat']:.4f}  "
            f"resid_std={r['resid_std']:.2f}"
        )

    # ── Crude walk-forward check: fit pre-HOLDOUT_FROM_YEAR, test after ──
    print(f"\n=== Walk-forward check (fit before {HOLDOUT_FROM_YEAR}, test from {HOLDOUT_FROM_YEAR}) ===")
    for action in ["add", "delete"]:
        sub = df[df["action"] == action]
        train = sub[sub["effective_date"].dt.year < HOLDOUT_FROM_YEAR]
        test = sub[sub["effective_date"].dt.year >= HOLDOUT_FROM_YEAR]
        if len(train) < 10 or len(test) < 5:
            print(f"  {action}: not enough rows to test (train={len(train)}, test={len(test)})")
            continue
        fit = fit_tau(train)
        score = predict_and_score(test, fit["tau_hat"])
        baseline_score = predict_and_score(test, tau_hat=0.0)  # benchmark: predict no excess
        print(
            f"  {action:7s} tau_hat(train)={fit['tau_hat']:.4f}  "
            f"test MAE={score['mae_adv_multiples']:.2f}  "
            f"vs zero-prediction MAE={baseline_score['mae_adv_multiples']:.2f}"
        )
        results.append(
            {**fit, "action": action, "sample": "walk_forward_train",
             "test_mae": score["mae_adv_multiples"], "test_bias": score["bias_adv_multiples"]}
        )

    pd.DataFrame(results).to_csv(TAU_OUT, index=False)
    print(f"\nSaved estimates to {TAU_OUT}")


if __name__ == "__main__":
    main()