#!/usr/bin/env bash
# Step 5 verification: copilot tool-loop dispatches through service-secret auth path,
# RLS still enforced end-to-end across browser → gateway → copilot → gateway → DB.

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

converse() {
  local jar=$1 msg=$2
  curl -s -b "$jar" -X POST "$GW/api/v2/copilot/converse" \
       -H 'content-type: application/json' \
       -d "$(jq -nc --arg m "$msg" '{message:$m}')"
}

JAR_A=/tmp/jar_step5_a.txt; JAR_B=/tmp/jar_step5_b.txt
rm -f "$JAR_A" "$JAR_B"

say "1) signup alice@step5a.com + bob@step5b.com"
signup "alice@step5a.com" "$JAR_A"
signup "bob@step5b.com"   "$JAR_B"

say "2) verify copilot is in stub mode (no ANTHROPIC_API_KEY)"
HEALTH=$(curl -s -b "$JAR_A" "$GW/api/v2/copilot/converse" -X POST -H 'content-type: application/json' -d '{"message":"health"}')
echo "$HEALTH" | head -c 300; echo
# stub-mode replies start with ✓ or ✗ since stub_loop pattern-matches

say "3) alice asks copilot to create a goal"
RESP=$(converse "$JAR_A" "goal:Track TDI cost lens=buy horizon=90")
echo "$RESP" | jq '{text, tool_calls}'
GID=$(echo "$RESP" | jq -r '.tool_calls[0].result.id')
[[ "$GID" =~ ^[0-9]+$ ]] || fail "create_goal didn't return id (got $GID)"

say "4) alice asks copilot to search catalog for TDI"
RESP=$(converse "$JAR_A" "search:material:TDI")
HITS=$(echo "$RESP" | jq '.tool_calls[0].result.matches | length')
[[ "$HITS" -ge 1 ]] || fail "search_catalog returned no TDI matches"
TDI_ID=$(echo "$RESP" | jq '.tool_calls[0].result.matches[] | select(.code=="TDI") | .id')
green "found TDI in catalog at id=$TDI_ID"

say "5) alice enables TDI via copilot with nickname"
RESP=$(converse "$JAR_A" "enable:material:$TDI_ID nickname=主原料 TDI")
echo "$RESP" | jq '{text, tool_calls}'
[[ $(echo "$RESP" | jq '.tool_calls[0].result.ok') == "true" ]] || fail "enable_catalog_material failed"

say "6) verify enablement is visible only to alice (RLS via service-secret path)"
A_MAT=$(curl -s -b "$JAR_A" "$GW/api/v2/me/materials" | jq '[.[] | select(.code=="TDI")] | length')
B_MAT=$(curl -s -b "$JAR_B" "$GW/api/v2/me/materials" | jq '[.[] | select(.code=="TDI")] | length')
[[ "$A_MAT" == "1" ]] || fail "alice should see TDI enabled (got $A_MAT)"
[[ "$B_MAT" == "0" ]] || fail "bob LEAKED alice's TDI enablement ($B_MAT rows)"
green "RLS enforced through copilot tool-call path"

say "7) alice composes a private spread indicator via copilot"
FORMULA='{"op":"subtract","left":{"indicator_code":"TDI_SPOT_EC"},"right":{"indicator_code":"TOLUENE_SPOT"}}'
RESP=$(converse "$JAR_A" "compose:ALICE_TDI_TOLUENE:CNY/ton:$FORMULA")
echo "$RESP" | jq '{text, tool_calls}'
PRIV_ID=$(echo "$RESP" | jq '.tool_calls[0].result.id')
[[ "$PRIV_ID" =~ ^[0-9]+$ ]] || fail "compose_indicator_formula failed"
green "private composite indicator created via copilot id=$PRIV_ID"

say "8) alice links the new indicator to her goal via copilot"
RESP=$(converse "$JAR_A" "link:$GID:tenant:$PRIV_ID role=primary")
echo "$RESP" | jq '{text, tool_calls}'
LINK_ID=$(echo "$RESP" | jq '.tool_calls[0].result.id')
[[ "$LINK_ID" =~ ^[0-9]+$ ]] || fail "add_indicator_to_goal failed"

say "9) verify the goal's drill page shows the linked private indicator"
DETAIL=$(curl -s -b "$JAR_A" "$GW/api/v2/goals/$GID")
echo "$DETAIL" | jq '{title, indicators}'
HAS_PRIV=$(echo "$DETAIL" | jq "[.indicators[] | select(.indicator_code==\"ALICE_TDI_TOLUENE\")] | length")
[[ "$HAS_PRIV" == "1" ]] || fail "linked indicator not on goal detail page"
green "linked indicator surfaces on goal drill"

say "10) bob cannot impersonate alice's session-secret path (no cookie)"
ANON_STATUS=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$GW/api/v2/copilot/converse" -H 'content-type: application/json' -d '{"message":"goal:hack"}')
[[ "$ANON_STATUS" == "401" ]] || fail "anonymous copilot call should 401 (got $ANON_STATUS)"

say "11) attempt to forge X-Service-Secret directly from browser → blocked because browsers can't set X-Service-Secret over CORS, but verify gateway accepts headers only when secret matches"
BAD_STATUS=$(curl -s -o /dev/null -w '%{http_code}' "$GW/api/v2/me/materials" \
   -H 'X-Service-Secret: wrong-secret' \
   -H 'X-Org-Id: 999' -H 'X-User-Id: 999' -H 'X-User-Role: owner')
[[ "$BAD_STATUS" == "401" ]] || fail "wrong service secret should 401 (got $BAD_STATUS)"
green "wrong service secret rejected"

green "===== STEP 5 ALL ASSERTIONS PASS ====="
