# Sentinel-Alpha

![Sentinel-Alpha Logo](assets/logo.jpg)

Behavior-Aligned Personal Trading Framework.

`Sentinel-Alpha` is a multi-agent trading research and product framework for building personal trading experts that adapt to an individual's behavior, intervention patterns, risk limits, and information environment.

The objective is not raw return maximization. The objective is user-aligned utility:

`U = E(R) - lambda * sigma^2 - phi(user_behavior)`

## What Exists Now

- behavioral stress scenario generation
- behavioral profiling
- explicit trading-frequency and timeframe preference flow
- behavior-based recommendation of trading rhythm
- behavior-based recommendation of default strategy type
- unified strategy interface with multiple strategy families
- mandatory integrity and stress checks before strategy approval
- profile evolution from feedback and trade records
- PostgreSQL / TimescaleDB / Qdrant / Redis persistence adapters
- dedicated frontend web module

## Main Docs

- technical guide: [github-technical-guide.md](/Users/harry/Documents/git/Sentinel-Alpha/docs/github-technical-guide.md)
- architecture: [architecture.md](/Users/harry/Documents/git/Sentinel-Alpha/docs/architecture.md)
- configuration: [configuration.md](/Users/harry/Documents/git/Sentinel-Alpha/docs/configuration.md)
- Docker deployment: [docker-deployment.md](/Users/harry/Documents/git/Sentinel-Alpha/docs/docker-deployment.md)
- API spec: [api-spec.md](/Users/harry/Documents/git/Sentinel-Alpha/docs/api-spec.md)
- database spec: [database-spec.md](/Users/harry/Documents/git/Sentinel-Alpha/docs/database-spec.md)
- workflow skill: [SKILL.md](/Users/harry/Documents/git/Sentinel-Alpha/skills/sentinel-alpha-workflow/SKILL.md)

## Run

Backend, in-memory:

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
PYTHONPATH=src uvicorn sentinel_alpha.api.app:app --host 127.0.0.1 --port 8001
```

Backend, persistent:

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
PYTHONPATH=src uvicorn sentinel_alpha.api.persistent_app:app --host 127.0.0.1 --port 8001
```

Frontend web module:

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
PYTHONPATH=src python -m sentinel_alpha.webapp.server
```

Dependency baseline:

- Python: `3.11+` locally, `python:3.13-slim` in Docker
- package constraints: [pyproject.toml](/Users/harry/Documents/git/Sentinel-Alpha/pyproject.toml)

Docker, memory mode:

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
docker compose --profile memory up --build
```

Docker, persistent mode:

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
docker compose --profile persistent up --build
```

Docker deployment details:

- [docker-deployment.md](/Users/harry/Documents/git/Sentinel-Alpha/docs/docker-deployment.md)

## Frontend

Canonical frontend module:

- [webapp](/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/webapp)
- [index.html](/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/webapp/static/index.html)
- [session.html](/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/webapp/static/pages/session.html)
- [simulation.html](/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/webapp/static/pages/simulation.html)
- [report.html](/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/webapp/static/pages/report.html)
- [preferences.html](/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/webapp/static/pages/preferences.html)
- [strategy.html](/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/webapp/static/pages/strategy.html)
- [intelligence.html](/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/webapp/static/pages/intelligence.html)
- [system-health.html](/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/webapp/static/pages/system-health.html)
- [operations.html](/Users/harry/Documents/git/Sentinel-Alpha/src/sentinel_alpha/webapp/static/pages/operations.html)

Frontend page rule:

- 首页只做产品总览和页面导航
- 会话创建、模拟测试、测试报告、交易偏好、策略训练、情报中心、系统健康、部署监控必须分页面承载

## Validation

```bash
cd /Users/harry/Documents/git/Sentinel-Alpha
PYTHONPATH=src python -m pytest tests/test_api_workflow.py tests/test_strategy_interface.py tests/test_pipeline.py tests/test_scenario_generator.py
PYTHONDONTWRITEBYTECODE=1 python -m py_compile src/sentinel_alpha/**/*.py tests/*.py
node --check src/sentinel_alpha/webapp/static/script.js
node --check src/sentinel_alpha/webapp/static/session-shell.js
```
