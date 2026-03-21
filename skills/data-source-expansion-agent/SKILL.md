# Data Source Expansion Agent Skill

## Purpose

The `Data Source Expansion Agent` is responsible for turning a user-supplied market-data or research-data source into an integration package that can be reviewed and then applied by the code-mutation layer.

## Inputs

- provider name
- category
  - `market_data`
  - `fundamentals`
  - `dark_pool`
  - `options`
- base URL
- API key environment variable name
- short documentation summary
- optional sample endpoint
- auth style
- response format

## Outputs

Each run must produce:

- a provider slug
- a target adapter module path
- a target test path
- a generated adapter code artifact
- a generated test code artifact
- a config fragment
- syntax validation results

## Rules

- Always preserve the original source address and user-provided auth/key hints in the archived run.
- Prefer a narrow adapter skeleton that is easy to audit and refine.
- Generate tests that validate request path construction and parameter passing before any real network integration.
- The output of this agent is a handoff package for `Programmer Agent`, not a silent direct mutation of the codebase.
- Every run must be archived in session history and report history.
