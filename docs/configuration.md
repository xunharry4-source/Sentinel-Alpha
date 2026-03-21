# Configuration

Sentinel-Alpha must not rely on hardcoded runtime endpoints or storage addresses inside business logic.

## Canonical Config Sources

- Backend runtime config: [config/settings.toml](/Users/harry/Documents/git/Sentinel-Alpha/config/settings.toml)
- Frontend runtime config: [config.json](/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/webapp/static/config.json)

## Backend Config

`config/settings.toml` controls:

- app name and mode
- API host and port
- CORS allowed origins
- frontend host and port
- PostgreSQL DSN
- TimescaleDB DSN
- Redis URL
- Qdrant URL and collection
- minimum trade universe size
- frontend health retry interval
- intelligence search enablement
- intelligence RSS search templates
- intelligence fetch timeout and max document count
- LLM global enablement
- default LLM provider/model/temperature/max tokens
- provider credential env names
- per-agent LLM mappings
- per-task LLM mappings such as behavior analysis, strategy analysis, strategy code generation, and strategy critic
- programmer-agent enablement
- programmer-agent command and arguments
- programmer-agent repository path
- programmer-agent allowlisted editable paths
- programmer-agent auto-commit policy and timeout
- Prometheus enablement and metrics path
- Sentry DSN, environment, and sampling
- LangFuse host and credentials
- Grafana dashboard URL

Environment variables may override storage secrets when needed:

- `SENTINEL_CONFIG_FILE`
- `SENTINEL_API_HOST`
- `SENTINEL_API_PORT`
- `SENTINEL_FRONTEND_HOST`
- `SENTINEL_FRONTEND_PORT`
- `SENTINEL_POSTGRES_DSN`
- `SENTINEL_TIMESCALE_DSN`
- `SENTINEL_REDIS_URL`
- `SENTINEL_QDRANT_URL`
- `SENTINEL_QDRANT_COLLECTION`
- `SENTINEL_LLM_ENABLED`
- `SENTINEL_LLM_DEFAULT_PROVIDER`
- `SENTINEL_LLM_DEFAULT_MODEL`
- `SENTINEL_LLM_DEFAULT_TEMPERATURE`
- `SENTINEL_LLM_DEFAULT_MAX_TOKENS`
- `SENTINEL_PROGRAMMER_AGENT_ENABLED`
- `SENTINEL_PROGRAMMER_AGENT_COMMAND`
- `SENTINEL_PROGRAMMER_AGENT_REPO_PATH`
- `SENTINEL_PROGRAMMER_AGENT_AUTO_COMMIT`
- `SENTINEL_PROGRAMMER_AGENT_TIMEOUT_SECONDS`
- `SENTINEL_PROMETHEUS_ENABLED`
- `SENTINEL_PROMETHEUS_METRICS_PATH`
- `SENTINEL_SENTRY_ENABLED`
- `SENTINEL_SENTRY_DSN`
- `SENTINEL_SENTRY_ENVIRONMENT`
- `SENTINEL_SENTRY_TRACES_SAMPLE_RATE`
- `SENTINEL_SENTRY_PROFILES_SAMPLE_RATE`
- `SENTINEL_LANGFUSE_ENABLED`
- `SENTINEL_LANGFUSE_HOST`
- `SENTINEL_LANGFUSE_PUBLIC_KEY`
- `SENTINEL_LANGFUSE_SECRET_KEY`
- `SENTINEL_GRAFANA_URL`

These overrides are the expected deployment path for Docker and other container runtimes.

## Frontend Config

`src/sentinel_alpha/webapp/static/config.json` controls:

- `apiBase`
- `healthRetryMs`
- `frontendLabel`
- `expectedApiService`

The web client must load this file at startup before attempting API calls.

## Architecture Rules

- API base URLs must not be hardcoded in frontend application logic.
- Database DSNs and cache/vector endpoints must not be hardcoded in infrastructure adapters.
- CORS origins must come from configuration.
- behavioral thresholds that affect workflow behavior, such as minimum trade universe size, must come from configuration.
- if a new agent depends on an external provider or service, its endpoint and credentials must be added to config before implementation is considered complete.
- behavior analysis, strategy analysis, strategy code generation, and strategy critique must support different model mappings when the workflow requires it; do not force every task through a single model.
- programmer-agent file mutation scope must come from config, not from hardcoded path checks spread across business logic.

## Persistence Rules

The following categories are configuration-bound infrastructure responsibilities and must use configured storage backends:

- workflow session state
- behavioral reports
- strategy iteration history
- strategy feedback history
- market snapshots and historical market replay points
- trade execution records
- monitoring snapshots
- profile evolution events
- vector memory records
- website intelligence documents

## Operational Modes

- `src/sentinel_alpha/api/app.py` uses the shared config and runs the in-memory workflow service.
- `src/sentinel_alpha/api/persistent_app.py` uses the same config and swaps in the persistent workflow service.
- `src/sentinel_alpha/webapp/server.py` serves the canonical frontend module from `src/sentinel_alpha/webapp/static`.
- both backend modes must expose the same API surface to the frontend module.

## Docker Rule

Container deployment must preserve the same configuration contract rather than introducing a second hardcoded runtime path.

- Docker images may override host, port, and external service DSNs through environment variables.
- Docker Compose must not duplicate business thresholds outside the canonical config contract.
- schema initialization for TimescaleDB/PostgreSQL must come from tracked SQL files in `sql/` or `docker/`.
- the canonical Docker deployment spec lives in [docker-deployment.md](/Users/harry/Documents/git/Sentinel-Alpha/docs/docker-deployment.md).
