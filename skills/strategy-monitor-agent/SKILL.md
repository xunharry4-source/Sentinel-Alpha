---
name: strategy-monitor-agent
description: Use when monitoring strategy degradation, mismatch, or live robustness drift for Sentinel-Alpha.
---

# Strategy Monitor Agent

Use this skill when the task concerns post-training monitoring of strategy quality.

## Mission

Detect when the currently deployed or recommended strategy no longer behaves as expected.

## Core Responsibilities

- detect strategy degradation
- detect mismatch against profile or objective
- recommend re-training or rollback

## Inputs

- deployed strategy
- evaluation history
- monitoring results

## Outputs

- strategy health signals
- rollback or retrain recommendations

## Rules

- do not approve continued deployment when strategy health materially degrades
- preserve links to the exact strategy version under review
