# Configuration

## License

The project and its configuration artifacts are distributed under the Apache License 2.0.

- [LICENSE](/Users/harry/Documents/git/Sentinel-Alpha/LICENSE)

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
- market-data default provider
- market-data enabled free providers
- market-data request timeout
- provider-specific API key env names and base URLs
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

Market-data providers currently supported by config are:

- `yahoo`
- `alphavantage`
- `finnhub`
- `akshare`
- `local_file`

Fundamentals providers:

- `sec`
- `alphavantage`
- `finnhub`
- `local_file`

Dark-pool providers:

- `finra`
- `local_file`

Options providers:

- `yahoo_options`
- `finnhub`
- `local_file`

`local_file` provider defaults:

- market data:
  - `base_path = "data/local_market_data/market_data"`
- `quote_filename = "{symbol}_quote.json"`
- `history_filename = "{symbol}_{interval}.csv"`
- fundamentals:
  - `base_path = "data/local_market_data/fundamentals"`
  - `financials_filename = "{symbol}_financials.json"`
- dark pool:
  - `base_path = "data/local_market_data/dark_pool"`
  - `dark_pool_filename = "{symbol}_dark_pool.json"`
- options:
  - `base_path = "data/local_market_data/options"`
  - `options_filename = "{symbol}_options.json"`

Default resolved local roots in this repository:

- `/Users/harry/Documents/git/Sentinel-Alpha/data/local_market_data/market_data`
- `/Users/harry/Documents/git/Sentinel-Alpha/data/local_market_data/fundamentals`
- `/Users/harry/Documents/git/Sentinel-Alpha/data/local_market_data/dark_pool`
- `/Users/harry/Documents/git/Sentinel-Alpha/data/local_market_data/options`

Data-source expansion local registry:

- generated and supplemented data-source definitions are also persisted under:
  - `/Users/harry/Documents/git/Sentinel-Alpha/config/data_source_registry/{provider_slug}/`
- each provider directory stores:
  - `{run_id}.expand.json`
  - `{run_id}.apply.json`
  - `latest.expand.json`
  - `latest.apply.json`
- these local registry files must not store raw API keys; only metadata, generated artifacts, config candidates, validation output, and whether an API key was supplied

Expected local history CSV columns:

- `timestamp`
- `open`
- `high`
- `low`
- `close`
- `volume`

Supported local file formats:

- history:
  - `market_data/{SYMBOL}_{interval}.csv`
  - `market_data/{SYMBOL}_{interval}.json`
  - example: `market_data/AAPL_1d.csv`
- quote:
  - `market_data/{SYMBOL}_quote.json`
  - `market_data/{SYMBOL}_quote.csv`
  - example: `market_data/AAPL_quote.json`
- fundamentals:
  - `fundamentals/{SYMBOL}_financials.json`
  - example: `fundamentals/AAPL_financials.json`
- dark pool:
  - `dark_pool/{SYMBOL}_dark_pool.json`
- options:
  - `options/{SYMBOL}_options.json`

Example local history CSV:

```csv
timestamp,open,high,low,close,volume
2026-03-24T00:00:00Z,180.2,183.1,179.8,182.5,53200000
2026-03-25T00:00:00Z,182.5,184.4,181.7,183.9,48700000
```

Example local quote JSON:

```json
{
  "provider": "local_file",
  "symbol": "AAPL",
  "price": 183.9,
  "open": 182.5,
  "high": 184.4,
  "low": 181.7,
  "previous_close": 182.5,
  "timestamp": "2026-03-25T20:00:00Z"
}
```

Example local financials JSON:

```json
{
  "provider": "local_file",
  "symbol": "AAPL",
  "normalized": {
    "entity_name": "Apple Inc.",
    "report_period": "2025-12-31",
    "statements": [
      {
        "period_end": "2025-12-31",
        "revenue": 391000000000,
        "net_income": 97000000000
      }
    ]
  }
}
```

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
- `src/sentinel_alpha/nicegui/app.py` is the canonical frontend runtime.
- `src/sentinel_alpha/webapp/server.py` only serves legacy redirect shells from `src/sentinel_alpha/webapp/static`.
- both backend modes must expose the same API surface to the NiceGUI frontend module.
- the default development workflow should run the API and NiceGUI locally with hot reload rather than using Docker as the primary inner loop.

## Docker Rule

Container deployment must preserve the same configuration contract rather than introducing a second hardcoded runtime path.

- Docker images may override host, port, and external service DSNs through environment variables.
- Docker Compose must not duplicate business thresholds outside the canonical config contract.
- schema initialization for TimescaleDB/PostgreSQL must come from tracked SQL files in `sql/` or `docker/`.
- the canonical Docker deployment spec lives in [docker-deployment.md](/Users/harry/Documents/git/Sentinel-Alpha/docs/docker-deployment.md).
