# Passive Flow Lab — Project Plan

*Draft v0.2 · Scope: S&P 500 additions and deletions · Items marked **[VERIFY]** must be checked against primary sources before use.*

## 1. Goal

Deliver one narrow project, finished, over six months: estimate the passive trading caused by S&P 500 index changes using past events, then test whether its size predicts price impact. The output is tested code, a written methodology, honest evaluation against simple baselines, and the ability to explain every decision.

## 2. Research questions

- **RQ1 (flow):** can a tracking factor τ estimated from past events predict excess volume at future events better than simple benchmarks?
- **RQ2 (impact):** does the predicted flow, measured in ADV multiples, explain the price impact around an event, and how fast does that impact fade?

## 3. Scope

**In:** S&P 500 additions and deletions from public change lists; public price, volume and share data; public methodology documents.
**Out unless the core is finished:** other indices, quarterly and off-cycle event types, LLM filing extraction.
**Never in the repo:** any material supplied to you as part of Intropic's application process.

## 4. Feasibility gate (weeks 1-2, decide go or no-go)

| Check | Go if |
|---|---|
| Event list | You have announcement and effective dates for at least ~100 past changes, cross-checked against S&P announcements for a sample |
| Volume data | Daily volume is available for all of them. Closing-auction volume is a bonus, not a requirement; if absent, use volume above a moving-average baseline and say so |
| Float and shares | You can approximate float shares at each event date from public sources **[VERIFY: S&P float methodology, trade-date convention]** |
| Pilot | You have computed excess volume for 10 events by hand-checked code and it looks sensible |

If a check fails, use the fallback in Section 8 before continuing. Commit to the first month only; decide on the rest at the gate.

## 5. Method in brief

**Phase 1, flow estimator.** For each past event, excess volume E = event-day volume minus a baseline average (baseline window is a tested choice). Implied float-share change ΔFS follows from the rules (the whole float for an add or delete). Estimate τ by weighted least squares through the origin on ADV-scaled variables, E/ADV = τ · ΔFS/ADV + ε, separately for adds and deletes, with a rolling window. Predict Ê = τ̂ · ΔFS for later events. Evaluate walk-forward against (a) a fixed assumed tracking factor and (b) zero excess volume, reporting bias, MAE in ADV multiples, rank correlation and interval coverage.

**Phase 2, price impact.** Market-model abnormal returns, cumulative over windows around announcement and effective dates. Regress on log ADV multiple with controls for size and prior momentum. Robustness: placebo dates, alternative benchmarks, winsorising, standard errors clustered by date, and a check for change over time.

## 6. Skills targeted (from the interview feedback)

| Skill | How the project covers it |
|---|---|
| Structured Python | Package with classes where they fit, pytest tests, README |
| Quant modelling start to finish | Written methodology, model, evaluation against baselines |
| Rigour | Every rule and assumption documented and tested; review checklist before each release |
| Explaining your work | Decision log; one summary per phase |
| Markets knowledge | Weekly note on a real index event and its likely flows |

## 7. Roadmap

| Month | Focus | Deliverable |
|---|---|---|
| 1 | Feasibility gate, then data pipeline and tests | Go/no-go note; clean event dataset |
| 2 | Excess volume and τ estimation | First walk-forward flow backtest |
| 3 | Sensitivity: baseline windows, adds vs deletes, drift over time | Flow report with limitations |
| 4 | Event study core | First CAR results and regressions |
| 5 | Robustness checks | Placebo and alternative-specification results |
| 6 | Write-up, code cleanup, demo | Final report; a demo you can walk through |

**Habits throughout:** commit regularly, keep a decision log, write a weekly market note, run the review checklist before calling anything done.

## 8. Risks and fallbacks

- **No closing-auction data:** use daily volume above a baseline and state it as a cruder proxy.
- **Messy or incomplete event history:** narrow the sample to events you can verify, or switch to a better-documented period.
- **Simultaneous rebalances at the same close:** prefer isolated dates and state the limitation.
- **Null results:** report them. A clear negative finding, properly tested, is still a valid result.
- **Scope creep:** no extensions until Phases 1 and 2 are written up.

## 9. Assumptions I could not confirm

- What counts as "six months of experience" to the hiring team.
- Whether a project in their domain is welcome, and whether they expect a copy of their product.
- Trade-date and float conventions for S&P 500 events (marked **[VERIFY]** above).

## 10. Explaining the project (fill in as you go)

Objective; what you personally built; method and why over alternatives; two or three technical decisions with reasons; what went wrong and how you handled it; results and what you would change.

## 11. Week-one checklist

- [ ] Find and record event sources, then cross-check a sample against S&P announcements
- [ ] Check volume and share-count data for those events
- [ ] Read the S&P methodology; resolve every **[VERIFY]**
- [ ] Create the repo with a first passing test
- [ ] Write the first weekly market note
