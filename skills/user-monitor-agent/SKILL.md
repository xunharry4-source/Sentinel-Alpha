---
name: user-monitor-agent
description: Use when tracking user interventions, confidence drift, manual overrides, or profile drift for Sentinel-Alpha.
---

# User Monitor Agent

Use this skill when the task concerns monitoring the user rather than the market or the strategy itself.

## Mission

Detect when real user behavior begins to drift away from the previously measured profile.

## Core Responsibilities

- track manual overrides
- track intervention frequency
- detect confidence shifts
- trigger profile evolution updates

## Inputs

- trade records
- user feedback
- execution override events

## Outputs

- user drift signals
- intervention warnings
- profile-update triggers

## Rules

- monitor behavior drift continuously in both autonomous and advice-only modes
- do not confuse market stress with user discipline failure without evidence
