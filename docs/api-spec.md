# Sentinel-Alpha API Spec

## Default Local Access

- NiceGUI: `http://127.0.0.1:8010`
- API: `http://127.0.0.1:8001`
- API health: `http://127.0.0.1:8001/api/health`

## Product Flow APIs

### `POST /api/sessions`

Create a new first-run workflow session.

Request:

```json
{
  "user_name": "Harry",
  "starting_capital": 500000
}
```

### `POST /api/sessions/{session_id}/generate-scenarios`

Generate the behavioral mapping scenarios for the current session.

### `POST /api/sessions/{session_id}/simulation/events`

Append one simulated trading event.

### `POST /api/sessions/{session_id}/simulation/complete`

Complete the simulation stage and return the Behavioral Profiler report.

### `POST /api/sessions/{session_id}/trade-universe`

Submit stocks, ETFs, or sectors. The backend expands to at least five tradeable objects by default.

### `POST /api/sessions/{session_id}/strategy/iterate`

Generate the next strategy candidate using:

- behavioral profile
- chosen universe
- optional user feedback
- automatic strategy integrity checks
- automatic stress and overfit checks

The resulting session state now includes:

- `strategy_training_log`
- `report_history`
- `strategy_package`
- `candidate_variants`
- `recommended_variant`
- generated code artifacts

### `POST /api/sessions/{session_id}/intelligence/search`

Search configured public websites and news feeds for market intelligence related to a query.

Request:

```json
{
  "query": "NVDA earnings AI demand",
  "max_documents": 5
}
```

The response includes structured intelligence documents attached to the session.

It also archives:

- summarized intelligence report
- translated and localized intelligence documents preserved in current snapshot, run history, event history, and report history
- source URLs
- intelligence run history
- historical intelligence behavior analysis, including whether searches are frequent, repeated, bursty, repeatedly centered on the same topic, or repeatedly re-checked within a short time window
- simulation-training guidance derived from intelligence history, used to recommend initial simulation or retraining when behavior drifts or topic-level confirmation bias increases

### `POST /api/sessions/{session_id}/programmer/execute`

Run the controlled `Programmer Agent` against local files.

Request:

```json
{
  "instruction": "Adjust the strategy parameters and keep the risk guard intact.",
  "target_files": ["src/sentinel_alpha/strategies/rule_based.py"],
  "context": "Use the latest failed iteration summary.",
  "commit_changes": true
}
```

Response session state includes:

- `programmer_runs`
- `history_events`
- `report_history`

### `POST /api/sessions/{session_id}/strategy/approve`

Approve the current strategy candidate only if both strategy-check agents return acceptable results.

If any check fails, the session must move into a rework-required state and the client should call `strategy/iterate` again.

### `POST /api/sessions/{session_id}/deployment`

Choose:

- `autonomous`
- `advice_only`

### `GET /api/sessions/{session_id}/monitors`

Return live monitor outputs:

- user monitor
- strategy monitor
- market and asset monitor

### `GET /api/sessions/{session_id}`

Return the full workflow state for the frontend.

### `GET /api/sessions/{session_id}/history`

Return workflow history events.

### `GET /api/sessions/{session_id}/reports`

Return archived reports, including behavioral reports, intelligence summaries, strategy iteration snapshots, and programmer runs.
