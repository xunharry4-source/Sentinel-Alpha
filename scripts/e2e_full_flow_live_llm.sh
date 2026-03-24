#!/usr/bin/env bash
set -euo pipefail

API_BASE="${SENTINEL_API_BASE:-http://127.0.0.1:8001}"
API_BASE="${API_BASE%/}"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

step() {
  local name="$1"
  shift
  echo "== $name"
  "$@"
}

curl_json() {
  local method="$1"
  local path="$2"
  local body_file="${3:-}"
  local out="$tmp_dir/out.json"
  local code="$tmp_dir/code.txt"

  if [[ -n "$body_file" ]]; then
    curl -sS -o "$out" -w "%{http_code}" -X "$method" \
      -H "Content-Type: application/json" \
      --data-binary "@$body_file" \
      "$API_BASE$path" >"$code"
  else
    curl -sS -o "$out" -w "%{http_code}" -X "$method" \
      -H "Content-Type: application/json" \
      "$API_BASE$path" >"$code"
  fi
  local http_code
  http_code="$(cat "$code")"
  printf "%s" "$http_code"
}

py_get() {
  local expr="$1"
  python -c "import sys,json; d=json.load(sys.stdin); print($expr)"
}

require_live_llm() {
  local code payload
  code="$(curl_json GET /api/llm-config)"
  payload="$(cat "$tmp_dir/out.json")"
  if [[ "$code" != "200" ]]; then
    echo "FAIL llm-config http=$code"
    echo "$payload" | head -c 400
    echo
    return 2
  fi
  local mode creds
  mode="$(echo "$payload" | py_get '((d.get("agents") or {}).get("behavioral_profiler") or {}).get("generation_mode")')"
  creds="$(echo "$payload" | py_get '((d.get("agents") or {}).get("behavioral_profiler") or {}).get("credential_count")')"
  if [[ "$mode" != "live_llm" || "$creds" == "0" || -z "$creds" ]]; then
    echo "FAIL live_llm_required mode=$mode credential_count=$creds"
    return 2
  fi
  echo "PASS live_llm_required mode=$mode credential_count=$creds"
}

write_json() {
  local path="$1"
  local json="$2"
  printf "%s" "$json" >"$path"
}

step "health" bash -c '
  out="'"$tmp_dir"'/health.json"
  code="000"
  for i in $(seq 1 30); do
    code="$(curl -sS -o "$out" -w "%{http_code}" -H "Content-Type: application/json" "'"$API_BASE"'/api/health" || true)"
    if [[ "$code" == "200" ]]; then
      break
    fi
    sleep 1
  done
  echo "http=$code"
  if [[ -f "$out" ]]; then
    head -c 240 "$out"; echo
  fi
  [[ "$code" == "200" ]]
'

step "require_live_llm" require_live_llm

session_body="$tmp_dir/create_session.json"
write_json "$session_body" '{"user_name":"E2E_LIVE","starting_capital":500000}'
code="$(curl_json POST /api/sessions "$session_body")"
body="$(cat "$tmp_dir/out.json")"
echo "create_session http=$code"
session_id="$(echo "$body" | py_get 'd.get("session_id")')"
echo "session_id=$session_id"
if [[ "$code" != "200" || "$session_id" == "None" || -z "$session_id" ]]; then
  echo "FAIL create_session"
  exit 2
fi

code="$(curl_json POST "/api/sessions/$session_id/generate-scenarios")"
body="$(cat "$tmp_dir/out.json")"
echo "generate-scenarios http=$code scenarios=$(echo "$body" | py_get 'len(d.get("scenarios") or [])')"
[[ "$code" == "200" ]] || exit 2

pref_body="$tmp_dir/prefs.json"
write_json "$pref_body" '{"trading_frequency":"high","preferred_timeframe":"minute","rationale":"e2e"}'
code="$(curl_json POST "/api/sessions/$session_id/trading-preferences" "$pref_body")"
body="$(cat "$tmp_dir/out.json")"
echo "trading-preferences http=$code phase=$(echo "$body" | py_get 'd.get("phase")')"
[[ "$code" == "200" ]] || exit 2

ev1="$tmp_dir/ev1.json"
write_json "$ev1" '{"scenario_id":"scenario-fake-reversal","price_drawdown_pct":-10,"action":"buy","noise_level":0.9,"sentiment_pressure":0.8,"latency_seconds":40}'
code="$(curl_json POST "/api/sessions/$session_id/simulation/events" "$ev1")"
echo "simulation-event-1 http=$code"
[[ "$code" == "200" ]] || exit 2

ev2="$tmp_dir/ev2.json"
write_json "$ev2" '{"scenario_id":"scenario-fake-reversal","price_drawdown_pct":-15,"action":"sell","noise_level":0.8,"sentiment_pressure":-0.7,"latency_seconds":35}'
code="$(curl_json POST "/api/sessions/$session_id/simulation/events" "$ev2")"
echo "simulation-event-2 http=$code"
[[ "$code" == "200" ]] || exit 2

complete="$tmp_dir/complete.json"
write_json "$complete" '{"symbol":"QQQ"}'
code="$(curl_json POST "/api/sessions/$session_id/simulation/complete" "$complete")"
body="$(cat "$tmp_dir/out.json")"
mode="$(echo "$body" | py_get '((d.get("behavioral_user_report") or {}).get("report_generation_mode"))')"
warning="$(echo "$body" | py_get '((d.get("behavioral_system_report") or {}).get("analysis_warning"))')"
echo "simulation-complete http=$code report_generation_mode=$mode analysis_warning=$warning"
[[ "$code" == "200" ]] || exit 2
[[ "$mode" == "live_llm" ]] || exit 2
[[ "$warning" == "None" ]] || exit 2

universe="$tmp_dir/universe.json"
write_json "$universe" '{"input_type":"stocks","symbols":["TSLA","NVDA"],"allow_overfit_override":false}'
code="$(curl_json POST "/api/sessions/$session_id/trade-universe" "$universe")"
body="$(cat "$tmp_dir/out.json")"
expanded="$(echo "$body" | py_get 'len(((d.get("trade_universe") or {}).get("expanded") or []))')"
echo "trade-universe http=$code expanded=$expanded"
[[ "$code" == "200" && "$expanded" -ge 5 ]] || exit 2

iterate="$tmp_dir/iterate.json"
write_json "$iterate" '{"feedback":"Reduce concentration","strategy_type":"trend_following_aligned","iteration_mode":"guided","auto_iterations":1,"objective_metric":"return","target_return_pct":20,"target_win_rate_pct":58,"target_drawdown_pct":12,"target_max_loss_pct":6}'
code="$(curl_json POST "/api/sessions/$session_id/strategy/iterate" "$iterate")"
body="$(cat "$tmp_dir/out.json")"
version="$(echo "$body" | py_get '((d.get("strategy_package") or {}).get("version_label"))')"
echo "strategy-iterate http=$code version=$version"
[[ "$code" == "200" && "$version" != "None" ]] || exit 2

# Data source expansion agent
ds="$tmp_dir/ds.json"
write_json "$ds" '{"provider_name":"ExampleSource","category":"market_data","base_url":"https://api.example.com","api_key_envs":["EXAMPLE_API_KEY"],"docs_summary":"REST JSON API.","docs_url":"https://docs.example.com/source","sample_endpoint":"quote","auth_style":"query","response_format":"json"}'
code="$(curl_json POST "/api/sessions/$session_id/data-source/expand" "$ds")"
body="$(cat "$tmp_dir/out.json")"
ds_runs="$(echo "$body" | py_get 'len(d.get("data_source_runs") or [])')"
echo "data-source-expand http=$code runs=$ds_runs"
[[ "$code" == "200" && "$ds_runs" -ge 1 ]] || exit 2

# Trading terminal integration agent
term="$tmp_dir/term.json"
write_json "$term" '{"terminal_name":"Smoke Broker","terminal_type":"broker_api","official_docs_url":"https://example.com/docs","docs_search_url":"https://example.com/search?q=order","api_base_url":"https://api.example.com","api_key_envs":["SMOKE_BROKER_KEY"],"auth_style":"header","order_endpoint":"orders/place","cancel_endpoint":"orders/cancel","order_status_endpoint":"orders/status","positions_endpoint":"portfolio/positions","balances_endpoint":"account/balances","docs_summary":"REST trading API.","user_notes":"Need smoke test coverage."}'
code="$(curl_json POST "/api/sessions/$session_id/terminal/expand" "$term")"
body="$(cat "$tmp_dir/out.json")"
run_id="$(echo "$body" | py_get '((d.get("terminal_integration_runs") or [])[-1].get("run_id") if (d.get("terminal_integration_runs") or []) else None)')"
echo "terminal-expand http=$code run_id=$run_id"
[[ "$code" == "200" && "$run_id" != "None" ]] || exit 2

term_test="$tmp_dir/term_test.json"
write_json "$term_test" "{\"run_id\":\"$run_id\"}"
code="$(curl_json POST "/api/sessions/$session_id/terminal/test" "$term_test")"
body="$(cat "$tmp_dir/out.json")"
status="$(echo "$body" | py_get '((d.get("terminal_integration_runs") or [])[-1].get("terminal_test") or {}).get("status")')"
echo "terminal-test http=$code status=$status"
[[ "$code" == "200" ]] || exit 2

code="$(curl_json GET /api/system-health)"
body="$(cat "$tmp_dir/out.json")"
api_requests="$(echo "$body" | py_get '(((d.get("token_usage") or {}).get("aggregate") or {}).get("api_request_count"))')"
total_tokens="$(echo "$body" | py_get '(((d.get("token_usage") or {}).get("aggregate") or {}).get("total_tokens"))')"
live_calls="$(echo "$body" | py_get '(((d.get("token_usage") or {}).get("aggregate") or {}).get("live_request_count"))')"
fallback_calls="$(echo "$body" | py_get '(((d.get("token_usage") or {}).get("aggregate") or {}).get("fallback_request_count"))')"
echo "token-usage http=$code api_request_count=$api_requests total_tokens=$total_tokens live=$live_calls fallback=$fallback_calls"
[[ "$code" == "200" ]] || exit 2

echo "ALL PASS"
