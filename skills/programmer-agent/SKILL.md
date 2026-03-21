---
name: programmer-agent
description: Use when Sentinel-Alpha needs controlled local code modification, self-repair, strategy code generation, diff capture, commit capture, or rollback anchors through Aider.
---

# Programmer Agent

Use this skill when a strategy, test, or local module must be edited through a controlled coding environment rather than by free-form ad hoc changes.

## Mission

Translate natural-language change requests from `Strategy Evolver` or `Risk Guardian` into local file edits, versioned diffs, and recoverable git states.

## Core Responsibilities

- accept natural-language change instructions
- constrain edits to allowed local paths
- call Aider in a controlled repository context
- capture changed files, git diff, commit hash, and rollback anchor
- archive every run into workflow history

## Inputs

- instruction
- target files
- optional context
- optional error trace
- optional strategy failure summary

## Outputs

- execution status
- changed files
- git diff
- commit hash when commit is enabled
- rollback commit hash
- stdout and stderr capture

## Rules

- do not edit files outside configured programmer-agent scope
- do not mutate unrelated files just because Aider suggests them
- always preserve a rollback anchor before attempting code mutation
- every programmer run must leave a trace in:
  - session history
  - report archive
  - programmer run history
- return explicit failure status if:
  - aider is missing
  - target path is outside allowed scope
  - git commit fails

## Safety Contract

- default to strategy, test, and script paths only unless config expands scope
- prefer non-destructive git usage
- do not hide failed edits behind a fake success response
