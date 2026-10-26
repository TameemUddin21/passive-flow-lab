# Decision Log

# Passive Flow Lab — Running Decision & Methodology Log

## Log Entry 001: Trade Date Measurement Convention
- **Date**: Pre-modeling setup
- **Context**: S&P 500 constituent changes become effective before the market open on the effective date ($T$).
- **Methodological Decision**: Take all flow, ADV, and excess volume measurements on the **Trade Date** ($T-1$, the last trading session strictly prior to the effective date).
- **Rationale**: Passive index-tracking funds (SPY, IVV, VOO) seek to minimize tracking error by holding the exact index composition at the open of $T$. To achieve this, their rebalancing trades must execute in the **Closing Auction on $T-1$** (Market-on-Close orders). Measuring volume on date $T$ would capture post-event trading rather than passive rebalance flow.
- **Implementation**: `trade_date_for()` locates the last trading day strictly before the effective date.

---

## Log Entry 002: Point-in-Time Share Count Integrity & Stock Split Contamination
- **Date**: Data pipeline review
- **Defect Identified**: When an SEC EDGAR point-in-time filing was missing, the pipeline fell back to `yfinance.Ticker.info['sharesOutstanding']`. Because `info` always returns **today's** share count, companies with post-event stock splits (confirmed: NVIDIA 2001 addition, Amazon 2005 addition) were assigned share counts 1 to 2 orders of magnitude too large.
- **Methodological Decision**: 
  - Restrict the `yfinance` current-share fallback strictly to events occurring within the last 90 calendar days (`RECENT_EVENT_DAYS = 90`).
  - For older events with no point-in-time XBRL match, record `shares = None` and `shares_source = "missing"`.
- **Impact**: 204 historical events were properly left as missing rather than silently corrupting the regression slope.

---

## Log Entry 003: Auditable Exclusion Matrix vs. Blind Truncation
- **Date**: Data cleaning stage
- **Methodological Decision**: Replaced blind statistical winsorization/percentile trimming with a discrete, auditable exclusion logging system (`data/cleaning_log.csv`).
- **Exclusion Categories**:
  - `missing_shares`: Unmatched historical filings (primarily pre-2010 prior to mandatory XBRL).
  - `status_no_price_data`: Delisted/acquired securities (survivorship constraint in public price feeds).
  - `share_class_event`: Structural corporate actions (e.g., GOOG/GOOGL dual-listing split).
  - `zero_volume` / `missing_volume`: Market holidays or halted trading sessions.
- **Review Categories Kept in Sample**:
  - `holiday_trade_date`: Low-liquidity sessions between Dec 24 and Jan 3. Kept but tagged for sensitivity testing.
  - `negative_excess`: Cases where trade-date volume was below 60-day median ADV.

---

## Log Entry 004: Micro-Share Filing Extractions (< 1,000,000 Shares)
- **Date**: Model estimation stage
- **Anomaly**: Four SEC EDGAR extractions returned implausible share counts: `UHS` (664k), `DXC` (100), `LIN` (25k), and `VTRS` (100).
- **Root Cause Analysis**:
  - **UHS (Universal Health Services)**: Multi-class equity structure. The XBRL tag extracted non-trading Class A shares rather than total common shares.
  - **DXC & VTRS**: Pre-distribution Form 10 registration shells prior to spin-off mergers.
  - **LIN (Linde plc)**: Pre-merger holding company initial formation capital prior to the Praxair share exchange.
- **Action**: Enforced `MIN_PLAUSIBLE_SHARES = 1_000_000` filter and logged excluded records to `data/tau_shares_excluded.csv`.

---

## Log Entry 005: WLS Formulation & Homoskedastic Scaling
- **Date**: Model specification
- **Model**: $\text{Excess Volume}_i \approx \tau \cdot \text{Shares}_i$
- **Methodological Decision**: Fit through the origin using Weighted Least Squares, scaling both sides by 60-day median ADV:
  $$y_i = \frac{\text{Excess Volume}_i}{\text{ADV}_i}, \quad x_i = \frac{\text{Shares}_i}{\text{ADV}_i}, \quad \hat{\tau} = \frac{\sum x_i y_i}{\sum x_i^2}$$
- **Rationale**: Rebalancing volume volatility scales with baseline market activity ($\text{Var}(\epsilon_i) \propto \text{ADV}_i^2$). Unscaled OLS would be dominated by a few mega-cap names or highly liquid volatile stocks. Normalizing by ADV ensures homoskedastic errors across large-cap and mid-cap constituents.

---

## Log Entry 006: Empirical Findings & The Deletion Asymmetry
- **Date**: Model evaluation
- **Results**:
  - **Additions**: $\hat{\tau}_{\text{train}} = 12.50\%$ (full sample: $13.59\%$). Out-of-sample MAE ($10.67$x ADV) substantially outperforms the zero-flow baseline. Out-of-sample bias is $+5.08$x ADV, reflecting the secular growth in passive index-tracking AUM between 2010 and 2026.
  - **Deletions**: $\hat{\tau}_{\text{train}} = 1.82\%$ (full sample: $1.63\%$). Model exhibits high prediction error (test MAE: $12.34$x ADV, bias: $+11.08$x ADV).
- **Microstructure Hypothesis for Asymmetry**:
  - A substantial proportion of S&P 500 discretionary deletions (e.g., `VFC`, `XRAY`, `VNO`, `DXC`) are **simultaneously added to the S&P MidCap 400**.
  - Passive asset managers running both funds (Vanguard, BlackRock, State Street) **internally cross** the S&P 500 sell orders against MidCap 400 buy orders at the official 4:00 PM closing price (SEC Rule 17a-7), bypassing the public exchange tape.
  - Public exchange volume reflects only the net imbalance, collapsing observed excess volume to $\approx 0$.
- **Next Action**: Implement deletion sub-classification (MidCap 400 transfers vs. clean exits).
