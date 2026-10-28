"""
Passive Flow Lab — Pipeline Test

Tests the flow model on S&P 500 index events:
    1. Load historical event list.
    2. Pull shares outstanding from SEC EDGAR.
    3. Pull daily OHLCV from yfinance.
    4. Compute excess volume on the trade date vs a 60-day median ADV.

Convention: S&P changes are effective before the open on the effective
date, so the passive rebalancing trade executes at the close of the
prior trading day. All measurements are taken on that trade date, not
the effective date. See docs/decision_log.md.

Shares outstanding ("shares") — known limitation, fixed here:
    get_shares_at_date() reads the XBRL tag dei:EntityCommonStockSharesOutstanding
    from the latest 10-Q/10-K filed before the event. Mandatory XBRL tagging
    only phased in for most filers around 2009-2011, so this lookup can fail
    by design for older events, not just occasionally.
    The old fallback (yf.Ticker(ticker).info.get("sharesOutstanding")) always
    returns TODAY's share count, never a historical one. For any company that
    has split its stock since the event (confirmed: NVDA 2001, AMZN 2005;
    likely others, e.g. GOOG/GOOGL), that silently substituted a present-day
    number that looks plausible but is wrong by orders of magnitude.
    Fix: the fallback is now only used when the event itself is recent
    (within RECENT_EVENT_DAYS), where "today's count" is still a reasonable
    stand-in for "the count at the time". For older events with no EDGAR
    match, shares is left missing (None) rather than silently wrong — the
    existing `missing_shares` flag in flags.py / clean_events.py already
    handles that case correctly.

Run: python pipeline_test.py
"""

from edgar import Company, set_identity
import pandas as pd
import numpy as np
import yfinance as yf


# ─── CONFIGURATION ────────────────────────────────────────────────────────────

EDGAR_IDENTITY = "Mohammed Tameem Uddin tameem.uddin21@gmail.com"

MIN_DAYS_OLD = 60                # exclude events younger than this
ADV_BASELINE_WINDOW = 60         # trading days for baseline ADV
PRICE_LOOKBACK_DAYS = 120        # calendar days of price history
PRICE_LOOKAHEAD_DAYS = 30        # calendar days after the event

# The yfinance "current shares" fallback is only trustworthy for events
# this recent; for anything older, "shares" is left missing rather than
# silently wrong if EDGAR has no point-in-time figure.
RECENT_EVENT_DAYS = 90

# Events to test individually. Set event_date to the S&P effective date
# (YYYY-MM-DD) or None to use the most recent matching event in the dataset.
TEST_EVENTS = [
    {"ticker": "ABNB", "action": "add", "event_date": "2023-09-18"},
    {"ticker": "CRWD", "action": "add", "event_date": "2024-06-24"},
    {"ticker": "PLTR", "action": "add", "event_date": "2024-09-23"},
    {"ticker": "DASH", "action": "add", "event_date": "2025-03-24"},
    {"ticker": "COIN", "action": "add", "event_date": "2025-05-19"},
]

DIAGNOSTIC_TICKER = "ABNB"
DIAGNOSTIC_EVENT_DATE = "2023-09-18"
DIAGNOSTIC_WINDOW_DAYS = 10


set_identity(EDGAR_IDENTITY)


# ─── EVENT LIST ───────────────────────────────────────────────────────────────

EVENTS_URL = (
    "https://raw.githubusercontent.com/fja05680/sp500/master/"
    "S%26P%20500%20Historical%20Components%20%26%20Changes%20%28Updated%29.csv"
)


def load_events(min_days_old: int = MIN_DAYS_OLD) -> pd.DataFrame:
    """Load S&P 500 changes as one row per affected security.

    Returns a DataFrame with columns: date, ticker, action.
    """
    df = pd.read_csv(EVENTS_URL)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    events = []
    for i in range(1, len(df)):
        prev = {t.strip() for t in df.loc[i - 1, "tickers"].split(",")}
        curr = {t.strip() for t in df.loc[i, "tickers"].split(",")}

        for ticker in curr - prev:
            events.append({"date": df.loc[i, "date"], "ticker": ticker, "action": "add"})
        for ticker in prev - curr:
            events.append({"date": df.loc[i, "date"], "ticker": ticker, "action": "delete"})

    events_df = pd.DataFrame(events).sort_values("date").reset_index(drop=True)

    cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=min_days_old)
    return events_df[events_df["date"] < cutoff].reset_index(drop=True)


# ─── SHARES OUTSTANDING ───────────────────────────────────────────────────────

def get_shares_at_date(ticker: str, event_date: pd.Timestamp) -> float | None:
    """Shares outstanding from the latest 10-Q/10-K filed before event_date.

    Returns None if no filing with the XBRL tag exists before the event —
    expected for pre-~2009 events, since mandatory XBRL tagging wasn't in
    force yet. That's a data-coverage gap, not necessarily a bug.
    """
    try:
        company = Company(ticker)
        filings = company.get_filings(form=["10-Q", "10-K"])
        prior = [f for f in filings if f.filing_date < event_date.date()]
        if not prior:
            return None

        prior.sort(key=lambda f: f.filing_date, reverse=True)
        xbrl = prior[0].xbrl()
        facts = (
            xbrl.facts.query()
            .by_concept("dei:EntityCommonStockSharesOutstanding")
            .to_dataframe()
        )
        return float(facts["value"].iloc[0]) if not facts.empty else None
    except Exception as e:
        log_error(ticker, event_date, e)
        return None


def get_shares(ticker: str, event_date: pd.Timestamp) -> tuple[float | None, str]:
    """EDGAR first; yfinance "current" fallback only for recent events.

    Returns (shares, source) so the caller can record where the figure came
    from. `source` is one of: "edgar", "yfinance_current", "missing".

    yf.Ticker(...).info always reports TODAY's share count — there is no
    historical version of this field. For an event in the last
    RECENT_EVENT_DAYS, today's count is a reasonable stand-in for the count
    at the time. For anything older, using it would silently substitute a
    wrong, possibly much larger, post-split figure (confirmed for NVDA 2001
    and AMZN 2005) — so for old events with no EDGAR match, shares is left
    as None instead.
    """
    shares = get_shares_at_date(ticker, event_date)
    if shares is not None:
        return shares, "edgar"

    days_old = (pd.Timestamp.now() - event_date).days
    if days_old < RECENT_EVENT_DAYS:
        try:
            shares = yf.Ticker(ticker).info.get("sharesOutstanding")
        except Exception:
            shares = None
        if shares is not None:
            return shares, "yfinance_current"

    return None, "missing"


def log_error(ticker: str, event_date: pd.Timestamp, err: Exception) -> None:
    """Append an error line to data/errors.log."""
    import os
    os.makedirs("data", exist_ok=True)
    with open("data/errors.log", "a") as f:
        f.write(f"{ticker} {event_date.date()}: {err}\n")


# ─── PRICES ───────────────────────────────────────────────────────────────────

def get_price_data(
    ticker: str,
    event_date: pd.Timestamp,
    lookback: int = PRICE_LOOKBACK_DAYS,
    lookahead: int = PRICE_LOOKAHEAD_DAYS,
) -> pd.DataFrame | None:
    """Daily OHLCV around the event, indexed by date. None on failure."""
    start = event_date - pd.Timedelta(days=lookback)
    end = event_date + pd.Timedelta(days=lookahead)
    try:
        data = yf.download(ticker, start=start, end=end, progress=False)
        if data is None or data.empty:
            return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except Exception:
        return None


# ─── TRADE DATE ───────────────────────────────────────────────────────────────

def trade_date_for(prices: pd.DataFrame, effective_date: pd.Timestamp) -> pd.Timestamp | None:
    """Last trading day strictly before the effective date.

    This is the day the passive rebalancing flow actually executes.
    """
    pre = prices.loc[: effective_date - pd.Timedelta(days=1)]
    return pre.index[-1] if not pre.empty else None


# ─── EXCESS VOLUME ────────────────────────────────────────────────────────────

def compute_excess_volume(
    ticker: str,
    event_date: pd.Timestamp,
    baseline_window: int = ADV_BASELINE_WINDOW,
) -> dict | None:
    """Excess volume on the trade date vs a baseline median ADV.

    `event_date` is the effective date. Measurement is taken on the
    trade date (last trading day before the effective date).
    """
    prices = get_price_data(ticker, event_date)
    if prices is None or prices.empty or "Volume" not in prices.columns:
        return None

    pre_event = prices.loc[: event_date - pd.Timedelta(days=1)].tail(baseline_window)
    if len(pre_event) < 20:
        return None

    adv = pre_event["Volume"].median()
    if adv <= 0 or np.isnan(adv):
        return None

    trade_date = trade_date_for(prices, event_date)
    if trade_date is None:
        return None

    trade_volume = prices.loc[trade_date, "Volume"]
    excess = trade_volume - adv

    return {
        "ticker": ticker,
        "effective_date": event_date,
        "trade_date": trade_date,
        "adv": adv,
        "trade_volume": trade_volume,
        "excess_volume": excess,
        "excess_adv_multiple": excess / adv,
    }


# ─── SINGLE EVENT ─────────────────────────────────────────────────────────────

def run_event(
    ticker: str,
    action: str,
    event_date: pd.Timestamp,
) -> dict | None:
    """Run the pipeline on one event and print the result."""
    print("=" * 70)
    print(f"EVENT: {ticker} | {action} | effective {event_date.date()}")
    print("=" * 70)

    shares, shares_source = get_shares(ticker, event_date)
    if shares:
        print(f"  Shares outstanding: {shares:,.0f}  (source: {shares_source})")
    else:
        print("  Shares: NOT FOUND")

    result = compute_excess_volume(ticker, event_date)
    if result is None:
        print("  Could not compute excess volume (missing price data).\n")
        return None

    print(f"  Trade date:        {result['trade_date'].date()}  (measurement day)")
    print(f"  ADV (60d median):  {result['adv']:,.0f} shares")
    print(f"  Trade-day volume:  {result['trade_volume']:,.0f} shares")
    print(f"  Excess volume:     {result['excess_volume']:,.0f} shares")
    print(f"  Excess / ADV:      {result['excess_adv_multiple']:.2f}x")

    m = result["excess_adv_multiple"]
    if m < 0:
        flag = "WARNING: negative excess"
    elif m < 0.5:
        flag = "WARNING: very low excess"
    elif m > 20:
        flag = "WARNING: very high excess, check for splits"
    else:
        flag = "OK"
    print(f"  Sanity:            {flag}\n")

    return {"action": action, "shares": shares, "shares_source": shares_source, **result}


def print_volume_window(
    ticker: str,
    event_date: pd.Timestamp,
    window_days: int = DIAGNOSTIC_WINDOW_DAYS,
) -> None:
    """Print daily volume and excess-ADV around an event, marking the trade date."""
    prices = get_price_data(ticker, event_date, lookback=150, lookahead=window_days)
    if prices is None or prices.empty:
        print(f"No price data for {ticker}.")
        return

    adv = prices.loc[: event_date - pd.Timedelta(days=1)].tail(60)["Volume"].median()
    trade_date = trade_date_for(prices, event_date)

    window = prices.loc[
        event_date - pd.Timedelta(days=window_days) : event_date + pd.Timedelta(days=5)
    ].copy()
    window["excess_adv"] = window["Volume"] / adv

    print(f"\nVolume window: {ticker}")
    print(f"  Effective date: {event_date.date()}")
    print(f"  Trade date:     {trade_date.date() if trade_date is not None else 'N/A'}")
    print(f"  Baseline ADV:   {adv:,.0f}\n")
    for date, row in window.iterrows():
        marker = "  <- TRADE DATE" if date == trade_date else ""
        print(f"  {date.date()}  {row['Volume']:>15,.0f}  {row['excess_adv']:>7.2f}x{marker}")


# ─── BULK RUN ─────────────────────────────────────────────────────────────────

def run_all_events(events: pd.DataFrame) -> pd.DataFrame:
    """Run the pipeline over every event and return a results DataFrame."""
    results = []
    total = len(events)

    for i, row in events.iterrows():
        ticker, action, event_date = row["ticker"], row["action"], row["date"]

        if (i + 1) % 50 == 0:
            print(f"  Progress: {i + 1}/{total}")

        base = {
            "ticker": ticker,
            "action": action,
            "effective_date": event_date,
        }

        try:
            shares, shares_source = get_shares(ticker, event_date)
            result = compute_excess_volume(ticker, event_date)
        except Exception as e:
            log_error(ticker, event_date, e)
            results.append({**base, "status": "error", "error": str(e)})
            continue

        base["shares"] = shares
        base["shares_source"] = shares_source

        if result is None:
            results.append({**base, "status": "no_price_data"})
        else:
            results.append({
                **base,
                "trade_date": result["trade_date"],
                "adv": result["adv"],
                "trade_volume": result["trade_volume"],
                "excess_volume": result["excess_volume"],
                "excess_adv_multiple": result["excess_adv_multiple"],
                "status": "ok",
            })

        # Incremental save every 100 events
        if (i + 1) % 100 == 0:
            pd.DataFrame(results).to_csv("data/event_results_partial.csv", index=False)

    return pd.DataFrame(results)


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main() -> None:
    import os
    os.makedirs("data", exist_ok=True)

    print("Loading event list...")
    events = load_events()
    print(f"  Events: {len(events)}\n")

    print("Running pipeline on all events...")
    results = run_all_events(events)

    results.to_csv("data/event_results.csv", index=False)
    print(f"\nSaved {len(results)} rows to data/event_results.csv")

    ok = results[results["status"] == "ok"]
    print(f"\nSuccessful: {len(ok)}/{len(results)}")

    if ok.empty:
        print("No successful events. Check data/errors.log.")
        return

    print("\nShares source breakdown (successful rows):")
    print(ok["shares_source"].value_counts())

    print("\nExcess ADV multiple distribution:")
    print(ok["excess_adv_multiple"].describe())

    print("\nBy action:")
    print(ok.groupby("action")["excess_adv_multiple"].describe())

    print("\nTop 10 by excess:")
    print(ok.nlargest(10, "excess_adv_multiple")[
        ["ticker", "action", "trade_date", "excess_adv_multiple"]
    ].to_string(index=False))

    print("\nBottom 10 by excess:")
    print(ok.nsmallest(10, "excess_adv_multiple")[
        ["ticker", "action", "trade_date", "excess_adv_multiple"]
    ].to_string(index=False))


if __name__ == "__main__":
    main()