# Core Engine Specification

## Formula layer
KEY, XTL and Composite Momentum are calculated only by `caruso_analysis.py` from the published formulas. The precise registry is exposed by `analysis/cyclical/formulas.py`.

## Signal layer
The signal engine applies the public 12-case matrix to completed quarterly, monthly and weekly bars. It produces only BUY, SELL SHORT and TAKE PROFIT events.

## Execution layer
The execution state machine accepts only FLAT, LONG and SHORT. It does not generate signals, pyramid positions, size positions or invent stops.

- Long only: BUY opens long; TAKE PROFIT or SELL SHORT closes long; SELL SHORT while flat is ignored.
- Long / Short: BUY and SELL SHORT open or reverse direction; TAKE PROFIT closes the active position.

## Timing
A signal observed on completed weekly close `t` affects the return from `t` to `t+1`.

## Execution and Money-Management Policies (v0.7)

Signal generation is immutable and remains based on the public cyclical matrix.
Execution is handled by a separate `ExecutionPolicy` with two independent axes:

- direction: `LONG_ONLY` or `LONG_SHORT`;
- TAKE PROFIT treatment: `SIGNAL_ONLY`, `FULL_EXIT`, or `PARTIAL_EXIT`.

`SIGNAL_ONLY` is the default because the source documents describe TAKE PROFIT
as profit management and partial monetisation but do not publish one universal
liquidation percentage. `FULL_EXIT` and `PARTIAL_EXIT` are explicitly labelled
research scenarios. Partial liquidation percentages are user parameters and are
never presented as proprietary formulas.

The policy engine produces a continuous exposure in `[-1, +1]`. Repeated TAKE
PROFIT instructions in the same uninterrupted run are not applied repeatedly by
default. A later BUY or SELL SHORT may restore or reverse full exposure.

## Matrix Engine v1

The Matrix Engine reconstructs every completed weekly decision state from the
public 12-case matrix. It records quarterly direction, monthly direction,
weekly turn, weekly phase, Composite Momentum, instruction, rating,
provenance, decision type, state stability and whether the instruction is a
new transition or a persistent state.

It does not execute trades. Any combination absent from the public matrix is
labelled `NOT DEFINED`; the framework does not infer HOLD or another action.
