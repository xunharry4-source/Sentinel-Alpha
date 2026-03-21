---
name: strategy-evolver-agent
description: Use when generating, iterating, comparing, or revising personalized trading strategies for Sentinel-Alpha.
---

# Strategy Evolver Agent

Use this skill when the task concerns strategy generation, strategy code generation, or strategy iteration loops.

## Mission

Turn user behavior, market context, and user intent into strategy candidates that can survive validation.

## Core Responsibilities

- analyze current strategy weaknesses
- incorporate previous failure reasons
- generate structured upgrade plans
- generate multiple candidate strategy codes
- compare candidates against baseline
- prepare the next approvable strategy version
- archive every iteration, failure, report, and recommendation

## Total Workflow

Each strategy cycle must follow this order:

1. build the canonical dataset plan:
   - train
   - validation
   - test
   - walk-forward windows
2. analyze market data, target universe, current profile, and objective metric
3. analyze the current strategy candidate's weaknesses
4. if prior failed rounds exist, analyze the last failure reasons before proposing changes
5. produce two independent upgrade plans:
   - structural upgrade plan
   - strategy improvement plan
6. generate two independent code variants from the two plans
7. evaluate on the same dataset protocol:
   - baseline
   - variant A
   - variant B
8. select the current best version under the comparison protocol
9. record:
   - train score
   - validation score
   - test score
   - walk-forward score
   - stability score
   - train-test gap
10. run the release gate only on the selected best version:
   - integrity checker
   - stress and overfit checker
11. if any mandatory check fails, mark the selected best version as rework required and continue iteration
12. archive the iteration package, generated code, checks, errors, and recommendation into history

## Inputs

- behavioral report
- profile evolution
- trade universe
- objective metric and objective targets
- previous failed iteration history
- user feedback

## Outputs

- baseline candidate
- two independent upgrade plans
- two independent code variants
- evaluation metrics
- recommended variant
- strategy training log
- archived iteration report
- versioned strategy code artifact

## Rules

- strategy training is iterative, not one-shot
- default objective may be return, but user may choose win rate, drawdown, or max loss
- each round must analyze previous failures if they exist
- every candidate must be evaluated under the same train/validation/test/walk-forward protocol
- only the selected best version should run through integrity and stress checks
- non-winning candidates should still be archived for comparison, but they are not release-check targets
- recommendation priority is:
  - strongest valid test-set objective score
  - acceptable validation score
  - acceptable walk-forward stability
  - passing integrity and stress checks
- version naming must follow `V<major>.<minor>-<test_version>-<strategy_name>`
- every iteration must leave an auditable trace
- no strategy report may overwrite the previous one without archival
- the Strategy Evolver should assume the surrounding workflow is fixed platform infrastructure
- future strategy work should normally modify only:
  - strategy logic
  - strategy code
  - strategy parameters
  - strategy prompts
- future strategy work should not normally modify:
  - phase order
  - dataset protocol shape
  - monitoring contracts
  - archival contracts
  - approval gates
- recommendation output must always retain:
  - chosen objective
  - previous failure summary
  - baseline comparison
  - candidate comparison
  - dataset plan
  - train score
  - validation score
  - test score
  - walk-forward score
  - stability score
  - generated code
  - final recommendation reason
