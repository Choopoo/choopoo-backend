#!/usr/bin/env bash
# Step 6 verification: formula_json composer evaluates spread indicators correctly.

set -euo pipefail
GW=http://localhost:8081

red()   { printf "\033[31m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
say()   { printf "\033[36m== %s\033[0m\n" "$*"; }
fail()  { red "$*"; exit 1; }

signup() {
  local link
  link=$(curl -s -X POST "$GW/auth/magic-link" \
        -H 'content-type: application/json' \
        -d "{\"email\":\"$1\"}" | jq -r .dev_link)
  [[ -n "$link" && "$link" != "null" ]] || fail "no dev link for $1"
  curl -s -c "$2" "$link" >/dev/null
}

JAR=/tmp/jar_step6.txt
rm -f "$JAR"
signup "alice@step6.com" "$JAR"

say "1) seed catalog readings: TDI=15800, TOLUENE=7200"
curl -s -b "$JAR" -X POST "$GW/api/v2/test/indicator/reading" \
     -H 'content-type: application/json' \
     -d '{"code":"TDI_SPOT_EC","value":15800,"ts":"2026-04-16T08:00:00Z"}' >/dev/null
curl -s -b "$JAR" -X POST "$GW/api/v2/test/indicator/reading" \
     -H 'content-type: application/json' \
     -d '{"code":"TOLUENE_SPOT","value":7200,"ts":"2026-04-16T08:00:00Z"}' >/dev/null

say "2) GET /api/v2/indicators/TDI_SPOT_EC/latest -> 15800"
RAW=$(curl -s -b "$JAR" "$GW/api/v2/indicators/TDI_SPOT_EC/latest")
echo "$RAW" | jq .
V=$(echo "$RAW" | jq .value)
[[ "$V" == "15800" ]] || fail "TDI latest != 15800 (got $V)"

say "3) GET /api/v2/indicators/TDI_TOLUENE_SPREAD/latest -> 8600 (15800 - 7200)"
RAW=$(curl -s -b "$JAR" "$GW/api/v2/indicators/TDI_TOLUENE_SPREAD/latest")
echo "$RAW" | jq .
V=$(echo "$RAW" | jq .value)
[[ "$V" == "8600" ]] || fail "spread != 8600 (got $V)"
green "spread composer works (15800 - 7200 = 8600)"

say "4) seed MDI=14867, then GET /api/v2/indicators/MDI_TDI_SPREAD/latest -> -933"
curl -s -b "$JAR" -X POST "$GW/api/v2/test/indicator/reading" \
     -H 'content-type: application/json' \
     -d '{"code":"MDI_SPOT_EC","value":14867,"ts":"2026-04-16T08:00:00Z"}' >/dev/null
RAW=$(curl -s -b "$JAR" "$GW/api/v2/indicators/MDI_TDI_SPREAD/latest")
echo "$RAW" | jq .
V=$(echo "$RAW" | jq .value)
[[ "$V" == "-933" ]] || fail "MDI-TDI spread != -933 (got $V)"
green "second composite indicator works"

say "5) compose a NEW private composite via copilot, then resolve via /latest"
FORMULA='{"op":"divide","left":{"indicator_code":"TDI_SPOT_EC"},"right":{"indicator_code":"TOLUENE_SPOT"}}'
RESP=$(curl -s -b "$JAR" -X POST "$GW/api/v2/copilot/converse" \
     -H 'content-type: application/json' \
     -d "$(jq -nc --arg f "$FORMULA" '{message:("compose:ALICE_TDI_PER_TOLUENE:ratio:" + $f)}')")
echo "$RESP" | jq '{text, tool_calls: .tool_calls[0].result}'
RAW=$(curl -s -b "$JAR" "$GW/api/v2/indicators/ALICE_TDI_PER_TOLUENE/latest")
echo "$RAW" | jq .
V=$(echo "$RAW" | jq .value)
EXPECTED=$(python3 -c "print(15800/7200)")
[[ "$V" == "$EXPECTED" ]] || fail "private composite ratio != $EXPECTED (got $V)"
green "private composite (created via copilot) resolves correctly"

say "6) /api/v2/me/indicators (after enabling spread) reflects formula on the resolved view"
SPREAD_ID=$(curl -s -b "$JAR" "$GW/api/v2/catalog/indicators" | jq '.[] | select(.code=="TDI_TOLUENE_SPREAD") | .id')
curl -s -b "$JAR" -X POST "$GW/api/v2/tenant/indicators/enable" \
     -H 'content-type: application/json' \
     -d "{\"catalog_indicator_template_id\":$SPREAD_ID}" >/dev/null
ME=$(curl -s -b "$JAR" "$GW/api/v2/me/indicators" | jq '.[] | select(.code=="TDI_TOLUENE_SPREAD")')
echo "$ME" | jq .
[[ $(echo "$ME" | jq -r .source) == "catalog" ]] || fail "TDI_TOLUENE_SPREAD source should be catalog"

green "===== STEP 6 ALL ASSERTIONS PASS ====="
