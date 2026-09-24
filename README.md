# Passive Flow Lab

An independent research project on how much passive trading S&P 500 index changes cause, and whether that trading moves prices.

**Status:** early stage. The project is in its feasibility phase (data checks and methodology). No results yet; results will be added here as they are produced and checked.

## Research questions

1. **Flow:** can a tracking factor estimated from past S&P 500 additions and deletions predict excess trading volume at later events better than simple benchmarks?
2. **Impact:** does the predicted flow, measured in multiples of average daily volume (ADV), explain the price impact around an event, and how quickly does that impact fade?

## Approach

- **Excess volume:** event-day volume minus a baseline average, with the baseline window tested as a choice rather than assumed.
- **Tracking factor:** for each past event, relate excess volume to the float-share change the index rules imply, estimated with weighted least squares on ADV-scaled variables, separately for additions and deletions.
- **Evaluation:** walk-forward, using only events before the one being predicted. Compared against a fixed assumed tracking factor and against predicting zero excess volume. Reported as bias, error in ADV multiples, rank correlation and interval coverage.
- **Price impact:** a standard event study with market-model abnormal returns, cross-sectional regressions on log ADV multiple, and robustness checks (placebo dates, alternative benchmarks, winsorising, date-clustered standard errors).

The full plan is in [`docs/project_plan.md`](docs/project_plan.md). Decisions and assumptions are recorded in [`docs/decision_log.md`](docs/decision_log.md).

## Scope

- **In:** S&P 500 additions and deletions, using public event lists and public price, volume and share data.
- **Later, only if the core is finished:** other indices and other event types.

## Repository layout

```
passive-flow-lab/
├── README.md
├── docs/            # plan, methodology, decision log, weekly notes
├── src/pfl/         # package code (data loading, rules, flows, scoring)
├── tests/           # pytest tests
└── data/            # local data; raw files are not committed
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install pandas numpy scipy statsmodels matplotlib pytest yfinance
pytest
```

## Data and limitations

- All data comes from public sources; raw data is not redistributed in this repository.
- Free price and volume data is unofficial and can contain errors, so a sample of values is cross-checked against a second source.
- Closing-auction volume may not be available from free sources; where it is not, daily volume is used and this is stated in the results as a cruder proxy.
- When several indices rebalance at the same close, excess volume cannot be attributed to one index. Affected events are flagged and treated as a limitation.
- Null and negative results will be reported.

## Mohammed Tameem Uddin
