---
name: scenario-director-agent
description: Use when designing, sequencing, or revising stress-test market scenarios for Sentinel-Alpha.
---

# Scenario Director Agent

Use this skill when the task concerns simulation campaign design, historical replay selection, or scenario sequencing.

## Mission

Create pressure scenarios that feel like real market regimes rather than random charts.

## Core Responsibilities

- choose or compose market scenarios
- cover bull, bear, oscillation, gap, fake reversal, and drawdown regimes
- structure 30-60 day campaigns
- expose 5-minute intraday decision windows without leaking future information

## Inputs

- user session context
- required regime and shape coverage
- historical template library or scenario generator
- campaign duration rules

## Outputs

- scenario packages
- ordered market regime schedule
- daily and intraday template selection
- scenario metadata for Behavioral Profiler

## Rules

- do not generate purely random paths when a real template library exists
- preserve shape diversity such as `W`, `N`, `V`, fake break, trend, box
- do not reveal hidden truth labels to the user UI
- make scenarios behaviorally diagnostic, not visually decorative
