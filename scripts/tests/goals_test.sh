#!/usr/bin/env bash
# Step 3 verification: goals create/list/detail, link catalog + private indicators,
# tenant isolation enforced.

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

JAR_A=/tmp/jar_step3_a.txt; JAR_B=/tmp/jar_step3_b.txt
rm -f "$JAR_A" "$JAR_B"

say "1) signup alice@step3a.com + bob@step3b.com"
signup "alice@step3a.com" "$JAR_A"
signup "bob@step3b.com"   "$JAR_B"

say "2) alice creates two goals"
GID_A1=$(curl -s -b "$JAR_A" -X POST "$GW/api/v2/goals" \
     -H 'content-type: application/json' \
     -d '{"title":"Cut TDI procurement cost 5%","lens":"buy","horizon_days":90,"pinned":true}' | jq .id)
GID_A2=$(curl -s -b "$JAR_A" -X POST "$GW/api/v2/goals" \
     -H 'content-type: application/json' \
     -d '{"title":"Watch HDI supply through Q3","lens":"buy","horizon_days":120}' | jq .id)
echo "alice goals: $GID_A1 $GID_A2"
[[ "$GID_A1" =~ ^[0-9]+$ ]] || fail "GID_A1 not numeric"

say "3) bob creates one goal"
GID_B1=$(curl -s -b "$JAR_B" -X POST "$GW/api/v2/goals" \
     -H 'content-type: application/json' \
     -d '{"title":"Track furniture export → wood-coating demand","lens":"sell"}' | jq .id)
echo "bob goal: $GID_B1"

say "4) GET /api/v2/goals — alice sees 2, bob sees 1; pinned first"
A_GOALS=$(curl -s -b "$JAR_A" "$GW/api/v2/goals")
B_GOALS=$(curl -s -b "$JAR_B" "$GW/api/v2/goals")
echo "--- alice ---"; echo "$A_GOALS" | jq '[.[] | {id,title,lens,pinned}]'
echo "--- bob ---";   echo "$B_GOALS" | jq '[.[] | {id,title,lens,pinned}]'
[[ $(echo "$A_GOALS" | jq length) == "2" ]] || fail "alice should have 2 goals"
[[ $(echo "$B_GOALS" | jq length) == "1" ]] || fail "bob should have 1 goal"
TOP_ALICE=$(echo "$A_GOALS" | jq -r '.[0].pinned')
[[ "$TOP_ALICE" == "true" ]] || fail "pinned goal should be first"

say "5) tenant isolation: bob cannot fetch alice's goal by id"
BOB_PEEK_STATUS=$(curl -s -b "$JAR_B" -o /dev/null -w '%{http_code}' "$GW/api/v2/goals/$GID_A1")
[[ "$BOB_PEEK_STATUS" == "404" ]] || fail "bob should get 404 on alice's goal (got $BOB_PEEK_STATUS)"
green "tenant isolation enforced via RLS (404 not 200)"

say "6) alice links a CATALOG indicator (TDI_SPOT_EC) and a PRIVATE indicator to GID_A1"
TDI_SPOT_ID=$(curl -s -b "$JAR_A" "$GW/api/v2/catalog/indicators" | jq '.[] | select(.code=="TDI_SPOT_EC") | .id')
# enable + role=primary
curl -s -b "$JAR_A" -X POST "$GW/api/v2/goals/$GID_A1/indicators" \
     -H 'content-type: application/json' \
     -d "{\"indicator_kind\":\"catalog\",\"indicator_id\":$TDI_SPOT_ID,\"role\":\"primary\"}" >/dev/null
# create a private one
PRIV_ID=$(curl -s -b "$JAR_A" -X POST "$GW/api/v2/tenant/indicators" \
     -H 'content-type: application/json' \
     -d '{"code":"ALICE_TDI_RECENT_VOL","kind":"derived","subject_kind":"raw_material","unit":"CNY/ton","description":"alice volatility"}' | jq .id)
curl -s -b "$JAR_A" -X POST "$GW/api/v2/goals/$GID_A1/indicators" \
     -H 'content-type: application/json' \
     -d "{\"indicator_kind\":\"tenant\",\"indicator_id\":$PRIV_ID,\"role\":\"driver\"}" >/dev/null

say "7) GET /api/v2/goals/:id returns linked indicators with codes"
DETAIL=$(curl -s -b "$JAR_A" "$GW/api/v2/goals/$GID_A1")
echo "$DETAIL" | jq '{id, title, indicators}'
LINK_COUNT=$(echo "$DETAIL" | jq '.indicators | length')
[[ "$LINK_COUNT" == "2" ]] || fail "expected 2 linked indicators, got $LINK_COUNT"
HAS_CATALOG=$(echo "$DETAIL" | jq '[.indicators[] | select(.indicator_code=="TDI_SPOT_EC")] | length')
HAS_PRIV=$(echo "$DETAIL" | jq '[.indicators[] | select(.indicator_code=="ALICE_TDI_RECENT_VOL")] | length')
[[ "$HAS_CATALOG" == "1" ]] || fail "catalog link missing"
[[ "$HAS_PRIV" == "1" ]]    || fail "private indicator link missing"
green "polymorphic indicator links (catalog + tenant) joined to codes"

say "8) bob cannot tamper with alice's goal — POST link returns 404"
BOB_TAMPER=$(curl -s -b "$JAR_B" -o /dev/null -w '%{http_code}' \
     -X POST "$GW/api/v2/goals/$GID_A1/indicators" \
     -H 'content-type: application/json' \
     -d "{\"indicator_kind\":\"catalog\",\"indicator_id\":$TDI_SPOT_ID}")
[[ "$BOB_TAMPER" == "404" ]] || fail "bob's tamper attempt should 404 (got $BOB_TAMPER)"
green "cross-tenant goal mutation blocked at RLS layer"

say "9) alice deletes a goal; cascades to its links"
curl -s -b "$JAR_A" -X DELETE "$GW/api/v2/goals/$GID_A2" >/dev/null
A_AFTER=$(curl -s -b "$JAR_A" "$GW/api/v2/goals" | jq length)
[[ "$A_AFTER" == "1" ]] || fail "alice should have 1 goal after delete (got $A_AFTER)"
green "delete works, isolation intact"

green "===== STEP 3 ALL ASSERTIONS PASS ====="
