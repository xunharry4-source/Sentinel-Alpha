---
name: behavioral-profiler-agent
description: Use when analyzing trading behavior, action timing, noise sensitivity, or personality outputs for Sentinel-Alpha.
---

# Behavioral Profiler Agent

Use this skill when the task concerns translating user trading behavior into a structured behavioral report.

## Mission

Infer trading personality from actions, timing, overrides, and narrative susceptibility.

## Core Responsibilities

- profile panic selling
- profile bottom-fishing and averaging down
- profile noise sensitivity
- profile intervention and overtrading tendency
- emit structured behavioral report and profile evolution updates

## Inputs

- simulation events
- trade records
- feedback history
- profile evolution history

## Outputs

- behavioral report
- profile evolution delta
- notes on dominant behavior risks

## Rules

- do not reduce the profile to only PnL
- preserve behavioral causes, not only summary scores
- later trade behavior may update the effective profile
- expose outputs in structured form for Strategy Evolver and Risk Guardian
