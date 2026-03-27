#!/usr/bin/env bash
set -euo pipefail

API_BASE="${SENTINEL_API_BASE:-http://127.0.0.1:8001}"

tmp_dir="$(mktemp -d)"
cleanup() { rm -rf "$tmp_dir"; }
trap cleanup EXIT

json_post() {
  local path="$1"
  local body_file="$2"
  curl -s -X POST "${API_BASE}${path}" -H "Content-Type: application/json" --data-binary "@${body_file}"
}

json_get() {
  local path="$1"
  curl -s "${API_BASE}${path}"
}

echo "== health"
json_get "/api/health" >/dev/null
echo "health ok"

cat >"$tmp_dir/create.json" <<'JSON'
{"user_name":"E2E_PROGRESS","starting_capital":500000}
JSON
create_out="$(json_post "/api/sessions" "$tmp_dir/create.json")"
session_id="$(printf "%s" "$create_out" | python -c 'import sys,json;print(json.loads(sys.stdin.read())["session_id"])')"
echo "session_id=${session_id}"

json_post "/api/sessions/${session_id}/generate-scenarios" /dev/null >/dev/null || true

cat >"$tmp_dir/prefs.json" <<'JSON'
{"trading_frequency":"high","preferred_timeframe":"minute","rationale":"progress test"}
JSON
json_post "/api/sessions/${session_id}/trading-preferences" "$tmp_dir/prefs.json" >/dev/null

cat >"$tmp_dir/event1.json" <<'JSON'
{"scenario_id":"scenario-fake-reversal","price_drawdown_pct":-10,"action":"buy","noise_level":0.9,"sentiment_pressure":0.8,"latency_seconds":40}
JSON
cat >"$tmp_dir/event2.json" <<'JSON'
{"scenario_id":"scenario-fake-reversal","price_drawdown_pct":-15,"action":"sell","noise_level":0.8,"sentiment_pressure":-0.7,"latency_seconds":35}
JSON
json_post "/api/sessions/${session_id}/simulation/events" "$tmp_dir/event1.json" >/dev/null
json_post "/api/sessions/${session_id}/simulation/events" "$tmp_dir/event2.json" >/dev/null

cat >"$tmp_dir/complete.json" <<'JSON'
{"symbol":"QQQ"}
JSON
json_post "/api/sessions/${session_id}/simulation/complete" "$tmp_dir/complete.json" >/dev/null

cat >"$tmp_dir/universe.json" <<'JSON'
{"input_type":"stocks","symbols":["TSLA","NVDA"],"allow_overfit_override":false}
JSON
json_post "/api/sessions/${session_id}/trade-universe" "$tmp_dir/universe.json" >/dev/null

cat >"$tmp_dir/iterate.json" <<'JSON'
{"feedback":"Reduce concentration","strategy_type":"trend_following_aligned","iteration_mode":"guided","auto_iterations":1,"objective_metric":"return","target_return_pct":20,"target_win_rate_pct":58,"target_drawdown_pct":12,"target_max_loss_pct":6}
JSON

echo "== start iterate (background)"
iterate_out="$tmp_dir/iterate_out.json"
curl -s -X POST "${API_BASE}/api/sessions/${session_id}/strategy/iterate" \
  -H "Content-Type: application/json" --data-binary "@${tmp_dir}/iterate.json" >"$iterate_out" &
iterate_pid=$!

since=""
poll_count=0
echo "== polling /agent-activity while iterate is running"
while kill -0 "$iterate_pid" 2>/dev/null; do
  poll_count=$((poll_count + 1))
  if [ -n "$since" ]; then
    activity="$(json_get "/api/sessions/${session_id}/agent-activity?since=$(python -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$since")&limit=200")"
  else
    activity="$(json_get "/api/sessions/${session_id}/agent-activity?limit=200")"
  fi
  new_count="$(printf "%s" "$activity" | python -c 'import sys,json; d=json.loads(sys.stdin.read() or "{}"); print(len(d.get("events") or []))')"
  if [ "$new_count" != "0" ]; then
    last="$(printf "%s" "$activity" | python -c 'import sys,json; d=json.loads(sys.stdin.read() or "{}"); e=(d.get("events") or [])[-1]; print(f"{e.get(\"timestamp\")} | {e.get(\"agent\")} | {e.get(\"operation\")} | {e.get(\"status\")}"); print(e.get(\"timestamp\") or \"\")')"
    last_line="$(printf "%s" "$last" | head -n 1)"
    since="$(printf "%s" "$last" | tail -n 1)"
    echo "poll#${poll_count} new_events=${new_count} last=${last_line}"
  else
    echo "poll#${poll_count} new_events=0"
  fi
  sleep 1
done

wait "$iterate_pid"
version_label="$(python -c 'import json;print(json.load(open("'"$iterate_out"'")).get("strategy_package",{}).get("version_label","unknown"))')"
echo "iterate done version=${version_label}"
echo "DONE"

