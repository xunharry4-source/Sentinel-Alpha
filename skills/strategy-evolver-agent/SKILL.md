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

1. analyze market data, target universe, current profile, and objective metric
2. analyze the current strategy candidate's weaknesses
3. if prior failed rounds exist, analyze the last failure reasons before proposing changes
4. produce two independent upgrade plans:
   - structural upgrade plan
   - strategy improvement plan
5. generate two independent code variants from the two plans
6. evaluate:
   - baseline
   - variant A
   - variant B
7. run:
   - integrity checker
   - stress and overfit checker
8. if any mandatory check fails, mark the version as rework required and continue iteration
9. archive the iteration package, generated code, checks, errors, and recommendation into history

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
- every candidate must run through integrity and stress checks
- version naming must follow `V<major>.<minor>-<test_version>-<strategy_name>`
- every iteration must leave an auditable trace
- no strategy report may overwrite the previous one without archival
- recommendation output must always retain:
  - chosen objective
  - previous failure summary
  - baseline comparison
  - candidate comparison
  - generated code
  - final recommendation reason
