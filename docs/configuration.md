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
