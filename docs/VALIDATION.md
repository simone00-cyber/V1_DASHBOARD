# Validation Register

- Public formula registry is visible in the Strategy Lab methodology tab.
- Signal-to-position processing is centralized in one deterministic state machine.
- Every event produces an audit transition with state before, action, state after and reason.
- TAKE PROFIT events are counted separately as total and effective. A TAKE PROFIT while FLAT is not an exit and is explicitly labelled.
- Event-driven trade closes are reconciled with state-machine close transitions.
- Automated tests cover repeated entries, TAKE PROFIT exits, reversals, long-only ignored shorts and trace consistency.

## Execution-policy validation

- Signal-only TAKE PROFIT retains the existing exposure.
- Full-exit TAKE PROFIT closes the full exposure.
- Partial-exit TAKE PROFIT reduces exposure by the configured fraction.
- Consecutive repeated TAKE PROFIT instructions do not repeatedly liquidate the
  same position unless explicitly enabled by a future policy.
- A new directional signal can restore full exposure after a partial reduction.
- Exposure is constrained to `[-1, +1]` and remains lagged by one completed bar.

## Matrix Engine validation

- Week-by-week timeline includes documented and explicitly undefined cases.
- Persistent instructions are separated from new instruction changes.
- No action is inferred for combinations absent from the public 12-case table.
- Matrix output is independent from execution and money-management policies.

## Drawdown-analysis validation

- Drawdown episodes are derived only from the strategy equity curve.
- Each episode records peak, trough, recovery status and duration.
- Trade drill-down links trades whose active interval overlaps the peak-to-trough decline.
- Loss attribution uses weighted realised trade contribution (`net return x size`).
- Attribution shares sum to 100% when losing trades exist.
- The analysis is descriptive and does not modify signals or execution.
