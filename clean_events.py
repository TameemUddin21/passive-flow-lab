"""
Clean event_results.csv before tracking-factor estimation.

Unlike a pure statistical filter (e.g. winsorising at a percentile), every
exclusion here is tied to a named reason, and a log of what was dropped and
why is written alongside the cleaned file. A reviewer can see *why* a row
was excluded, not just that it was an outlier.

Run from the repo root (where data/event_results.csv lives):
    python clean_events.py

Writes:
    data/event_results_clean.csv   - kept rows, with a `flags` column
    data/cleaning_log.csv          - every dropped row, with its reason
"""

from __future__ import annotations

import pandas as pd

# ─── CONFIG ─────────────────────────────────────────────────────────────────

PATH_IN = "data/event_results.csv"
PATH_OUT = "data/event_results_clean.csv"
LOG_OUT = "data/cleaning_log.csv"

# Tickers with a share-class or structural event, not a genuine new
# addition/deletion. [VERIFY] grow this list as you find more cases below.
SHARE_CLASS_TICKERS = {"GOOG", "GOOGL"}

# A trade date in the last week of December / first days of January sits in
# a low-volume holiday session. The 60-day baseline isn't holiday-adjusted,
# so "excess" there is distorted in both directions.
HOLIDAY_WINDOW = {(12, d) for d in range(24, 32)} | {(1, d) for d in range(1, 4)}

# Flags that mean the row should be dropped outright (known-bad, not
# ambiguous). Everything else is kept but flagged for manual review.
EXCLUDE_FLAGS = {"zero_volume", "missing_volume", "share_class_event", "missing_shares"}

ERA_SPLIT_YEAR = 2010


# ─── FLAGGING ───────────────────────────────────────────────────────────────

def flag_row(row: pd.Series) -> str:
    """Return a comma-separated list of flags for one event_results row."""
    flags = []

    if pd.isna(row.get("trade_volume")):
        flags.append("missing_volume")
    elif row["trade_volume"] == 0:
        flags.append("zero_volume")

    trade_date = row.get("trade_date")
    if pd.notna(trade_date):
        trade_date = pd.Timestamp(trade_date)
        if (trade_date.month, trade_date.day) in HOLIDAY_WINDOW:
            flags.append("holiday_trade_date")

    if row.get("ticker") in SHARE_CLASS_TICKERS:
        flags.append("share_class_event")

    multiple = row.get("excess_adv_multiple")
    if pd.notna(multiple):
        if multiple < 0:
            flags.append("negative_excess")
        elif multiple > 100:
            flags.append("extreme_excess")  # check individually before trusting

    if pd.isna(row.get("shares")):
        flags.append("missing_shares")

    return ",".join(flags)


def add_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df with a `flags` column, one row at a time."""
    df = df.copy()
    df["flags"] = df.apply(flag_row, axis=1)
    return df


# ─── CLEANING ───────────────────────────────────────────────────────────────

def clean(path_in: str = PATH_IN, path_out: str = PATH_OUT, log_out: str = LOG_OUT) -> pd.DataFrame:
    df = pd.read_csv(path_in, parse_dates=["effective_date", "trade_date"])
    print(f"Starting: {len(df)} rows")

    not_ok = df[df["status"] != "ok"].copy()
    not_ok["flags"] = "status_" + not_ok["status"].astype(str)
    df = df[df["status"] == "ok"].copy()
    print(f"After status filter: {len(df)} (dropped {len(not_ok)} not ok)")

    df = add_flags(df)

    is_excluded = df["flags"].apply(
        lambda f: any(flag in EXCLUDE_FLAGS for flag in f.split(",")) if f else False
    )
    excluded = pd.concat([not_ok, df[is_excluded]], ignore_index=True)
    kept = df[~is_excluded].copy()
    print(f"After excluding flagged rows: {len(kept)} (dropped {is_excluded.sum()} more)")

    excluded[["ticker", "action", "effective_date", "flags"]].to_csv(log_out, index=False)
    print(f"Exclusion log written to {log_out} ({len(excluded)} rows)")

    kept["era"] = kept["effective_date"].dt.year.apply(
        lambda y: "pre_2010" if y < ERA_SPLIT_YEAR else "2010_onwards"
    )

    remaining_flags = kept[kept["flags"] != ""]
    if not remaining_flags.empty:
        print(f"\nKept but flagged ({len(remaining_flags)} rows, review these individually):")
        print(remaining_flags[["ticker", "action", "effective_date", "flags"]].to_string(index=False))

    kept.to_csv(path_out, index=False)
    print(f"\nSaved {len(kept)} rows to {path_out}")

    print("\nFinal distribution by era and action:")
    print(kept.groupby(["era", "action"])["excess_adv_multiple"].describe()[["count", "mean", "50%"]])

    return kept


if __name__ == "__main__":
    clean()