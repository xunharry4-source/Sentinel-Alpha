# Docker Deployment

Sentinel-Alpha now ships with a Docker deployment path for both local demo mode and persistent infrastructure mode.

The Docker images use `python:3.13-slim` so the container runtime stays close to the newest stable Python line supported by the current dependency set.

## Files

- compose file: [docker-compose.yml](/Users/harry/Documents/git/Sentinel-Alpha/docker-compose.yml)
- API image: [Dockerfile.api](/Users/harry/Documents/git/Sentinel-Alpha/Dockerfile.api)
- web image: [Dockerfile.web](/Users/harry/Documents/git/Sentinel-Alpha/Dockerfile.web)
- Timescale init SQL: [001_extensions.sql](/Users/harry/Documents/git/Sentinel-Alpha/docker/timescaledb/init/001_extensions.sql)
- schema SQL: [product_schema.sql](/Users/harry/Documents/git/Sentinel-Alpha/sql/product_schema.sql)

## Deployment Modes

### Memory mode

Use this when you want the frontend plus the in-memory FastAPI workflow service.

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
docker compose --profile memory up --build
```

Exposed services:

- web: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- API: [http://127.0.0.1:8001](http://127.0.0.1:8001)

### Persistent mode

Use this when you want the persistent workflow service plus TimescaleDB, Redis, and Qdrant.

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
docker compose --profile persistent up --build
```

This profile starts:

- `web`
- `persistent-api`
- `timescaledb`
- `redis`
- `qdrant`

Exposed services:

- web: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- persistent API: [http://127.0.0.1:8001](http://127.0.0.1:8001)
- TimescaleDB/PostgreSQL: `127.0.0.1:5432`
- Redis: `127.0.0.1:6379`
- Qdrant: [http://127.0.0.1:6333](http://127.0.0.1:6333)

### Observability mode

Use this when you want Prometheus, Grafana, and LangFuse alongside the application stack.

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
docker compose --profile observability up --build
```

This profile adds:

- `prometheus`
- `grafana`
- `langfuse-web`
- `langfuse-postgres`
- `langfuse-redis`
- `langfuse-clickhouse`

Exposed services:

- Prometheus: [http://127.0.0.1:9090](http://127.0.0.1:9090)
- Grafana: [http://127.0.0.1:3001](http://127.0.0.1:3001)
- LangFuse: [http://127.0.0.1:3000](http://127.0.0.1:3000)

## What Gets Initialized

The persistent profile mounts schema SQL into `docker-entrypoint-initdb.d` and initializes:

- TimescaleDB extension
- product workflow tables
- behavioral log table

Mounted init files:

- [001_extensions.sql](/Users/harry/Documents/git/Sentinel-Alpha/docker/timescaledb/init/001_extensions.sql)
- [product_schema.sql](/Users/harry/Documents/git/Sentinel-Alpha/sql/product_schema.sql)
- [behavioral_log.sql](/Users/harry/Documents/git/Sentinel-Alpha/sql/behavioral_log.sql)

## Runtime Configuration

Container runtime still follows the same config rules:

- base config file: [settings.toml](/Users/harry/Documents/git/Sentinel-Alpha/config/settings.toml)
- frontend config file: [config.json](/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/webapp/static/config.json)

Docker overrides only the deployment-sensitive values through environment variables:

- `SENTINEL_API_HOST`
- `SENTINEL_API_PORT`
- `SENTINEL_FRONTEND_HOST`
- `SENTINEL_FRONTEND_PORT`
- `SENTINEL_POSTGRES_DSN`
- `SENTINEL_TIMESCALE_DSN`
- `SENTINEL_REDIS_URL`
- `SENTINEL_QDRANT_URL`
- `SENTINEL_PROMETHEUS_ENABLED`
- `SENTINEL_PROMETHEUS_METRICS_PATH`
- `SENTINEL_SENTRY_ENABLED`
- `SENTINEL_SENTRY_DSN`
- `SENTINEL_LANGFUSE_ENABLED`
- `SENTINEL_LANGFUSE_HOST`
- `SENTINEL_LANGFUSE_PUBLIC_KEY`
- `SENTINEL_LANGFUSE_SECRET_KEY`
- `SENTINEL_GRAFANA_URL`

## Dependency Baseline

The project dependency floor has been updated to the latest stable versions verified from PyPI on March 21, 2026:

- `fastapi>=0.135.1`
- `uvicorn>=0.41.0`
- `psycopg[binary]>=3.3.3`
- `qdrant-client>=1.17.0`
- `redis>=7.2.1`
- `langchain>=1.2.13`
- `langchain-core>=1.2.18`
- `langchain-qdrant>=1.1.0`
- `prometheus-fastapi-instrumentator>=7.1.0`
- `sentry-sdk[fastapi]>=2.39.1`
- `langfuse>=3.4.2`

These package constraints live in [pyproject.toml](/Users/harry/Documents/git/Sentinel-Alpha/pyproject.toml).

## Notes

- `web` is always available in both profiles.
- `api` and `persistent-api` publish the same host port `8001`, so only one profile should be active at a time.
- the persistent profile uses a single TimescaleDB instance for both relational workflow tables and time-series tables.
- `config.json` currently points the browser to `http://127.0.0.1:8001`, which matches the published Docker API port.

## Stop

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
docker compose down
```

To remove persistent volumes as well:

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
docker compose down -v
```
