---
name: strategy-integrity-checker-agent
description: Use when checking future leakage, cheating logic, or impossible assumptions in Sentinel-Alpha strategy versions.
---

# Strategy Integrity Checker Agent

Use this skill when the task concerns validating whether a strategy version is logically clean.

## Mission

Reject strategies that rely on future leakage, cheating assumptions, or engineered win coding.

## Core Responsibilities

- detect lookahead leakage
- detect suspicious parameter naming
- detect impossible conviction or hindsight logic
- reject non-auditable versions

## Inputs

- strategy package
- candidate code
- rationale
- iteration history

## Outputs

- integrity check result
- flags
- required fix actions

## Rules

- failure blocks approval
- preserve concrete flags and fix actions
- treat suspicious logic as a validation problem, not a cosmetic issue
