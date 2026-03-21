---
name: strategy-optimization-rules
description: Use when implementing or revising Sentinel-Alpha strategy generation rules, generic strategy interfaces, versioned strategy candidates, or iteration rules for strategy optimization, integrity checks, and overfit control.
---

# Strategy Optimization Rules

Use this skill when the task touches the shared strategy interface or the rules for iterating strategy versions.

## Core Rule

All strategy implementations must go through one generic strategy interface.

Do not let each strategy invent its own incompatible contract.

## Required Architecture

Every strategy implementation must support:

- shared input context
- versioned strategy candidate output
- typed strategy identifier
- compatibility with:
  - Strategy Integrity Checker
  - Strategy Stress and Overfit Checker
  - Behavioral Profiler output
  - user feedback during iteration

## Generic Strategy Interface

Every strategy must consume:

- user profile
- behavioral report
- market snapshot
- risk policy
- selected universe
- optional user feedback

Every strategy must produce:

- `strategy_id`
- `version`
- `strategy_type`
- `signals`
- `parameters`
- `metadata`

## Optimization Iteration Rules

For each new strategy version:

1. Start from the previous version or baseline implementation.
2. Apply user feedback and behavioral constraints first.
3. Recompute candidate parameters.
4. Emit a new versioned strategy candidate.
5. Run:
   - Strategy Integrity Checker
   - Strategy Stress and Overfit Checker
6. If either returns `fail`, mark the version as rework-required.
7. Do not allow approval of failed versions.
8. Preserve the rationale for what changed between versions.

## Anti-Overfit Rules

- Do not optimize on fewer than 5 tradeable objects by default.
- Do not accept a version only because in-sample metrics improved.
- Prefer robust parameter ranges over fragile point estimates.
- Treat repeated manual tuning as a warning sign for hidden curve fitting.

## Implementation Checklist

- a shared strategy base or protocol exists
- a strategy registry or dispatch layer exists
- every strategy emits versioned candidates
- iteration rules are explicit
- failed check results force re-iteration
