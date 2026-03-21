# Sentinel-Alpha API Spec

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
