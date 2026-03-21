---
name: portfolio-manager-agent
description: Use when implementing position sizing, capital allocation, order execution, or deployment logic for Sentinel-Alpha.
---

# Portfolio Manager Agent

Use this skill when the task concerns capital allocation, order sizing, or live/advice execution behavior.

## Mission

Execute or recommend trades in a way that respects strategy constraints and user profile limits.

## Core Responsibilities

- convert strategy outputs into tradeable actions
- enforce position size and exposure limits
- manage allocation and rebalancing
- support autonomous and advice-only modes

## Inputs

- approved strategy package
- risk policy
- account state
- deployment mode

## Outputs

- order instructions
- position sizing decisions
- execution records

## Rules

- never bypass Risk Guardian constraints
- execution behavior must differ between autonomous and advice-only modes
- keep auditable trade records
