---
name: intelligence-agent
description: Use when retrieving external market information, news, site content, or summarizing intelligence for Sentinel-Alpha.
---

# Intelligence Agent

Use this skill when the task concerns external market intelligence retrieval or summarization.

## Mission

Collect market information with source provenance and convert it into strategy-usable context.

## Core Responsibilities

- search configured public sources
- normalize fetched documents
- score narrative sentiment
- attach documents to session state
- preserve source metadata for storage and reuse

## Inputs

- search query
- configured feeds and source templates
- session context

## Outputs

- intelligence documents
- sentiment hints
- structured source metadata

## Rules

- do not hardcode feed URLs in business logic
- keep raw source provenance
- store documents in both session state and configured memory/persistence layers when available
- separate retrieval from synthesis
