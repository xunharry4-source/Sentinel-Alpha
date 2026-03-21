# Trading Terminal Integration Agent Skill

The `Trading Terminal Integration Agent` is responsible for turning a user-specified trading terminal or broker gateway into a controlled integration package.

## Responsibilities

- collect user-supplied terminal metadata:
  - terminal name
  - terminal type
  - official docs URL
  - docs search URL
  - API base URL
  - auth style
  - order, cancel, and positions endpoints
  - user notes
- fetch official documentation context when URLs are provided
- generate:
  - terminal adapter code
  - terminal adapter test code
  - terminal config candidate
- hand the generated files to `Programmer Agent` for controlled local write, diff, and commit flow

## Required Rule

- do not hardcode terminal-specific behavior into the global workflow
- terminal integrations must be generated as adapter modules
- generated terminal adapters must live under:
  - `/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/infra/generated_terminals`
- generated terminal tests must live under:
  - `/Users/harry/Documents/git/Sentinel-Alpha/tests/generated`

## Output Contract

Each run must preserve:

- documentation fetch status
- docs excerpts
- generated module path
- generated test path
- config candidate
- syntax validation result
- programmer-apply result when executed

## Platform Rule

Terminal-specific integration should plug into the stable platform without changing:

- strategy workflow
- dataset protocol
- monitoring contracts
- history/report archive contracts
- approval gates
