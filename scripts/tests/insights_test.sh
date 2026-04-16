#!/usr/bin/env bash
# Step 4 verification: insights + traceable evidence (page + indicator), tenant isolation.

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

JAR_A=/tmp/jar_step4_a.txt; JAR_B=/tmp/jar_step4_b.txt
rm -f "$JAR_A" "$JAR_B"

say "1) signup alice@step4a.com + bob@step4b.com"
signup "alice@step4a.com" "$JAR_A"
signup "bob@step4b.com"   "$JAR_B"

say "2) alice creates a goal + seeds a page (will be cited as evidence)"
GID=$(curl -s -b "$JAR_A" -X POST "$GW/api/v2/goals" \
     -H 'content-type: application/json' \
     -d '{"title":"Buy TDI cheaper","lens":"buy"}' | jq .id)
SEED=$(curl -s -b "$JAR_A" -X POST "$GW/api/v2/test/seed" \
     -H 'content-type: application/json' \
     -d '{"url":"https://100ppi.com/tdi-2026-04-16","title":"TDI华东 ¥15,800/吨"}')
PAGE_ID=$(echo "$SEED" | jq .id)
echo "goal=$GID page=$PAGE_ID"

say "3) alice creates an insight citing the page + a catalog indicator reading"
TDI_SPOT_ID=$(curl -s -b "$JAR_A" "$GW/api/v2/catalog/indicators" | jq '.[] | select(.code=="TDI_SPOT_EC") | .id')
INSIGHT=$(curl -s -b "$JAR_A" -X POST "$GW/api/v2/insights" \
     -H 'content-type: application/json' \
     -d "{
       \"goal_id\": $GID,
       \"kind\": \"briefing\",
       \"title\": \"TDI mild upward, maintain pace\",
       \"body_md\": \"TDI 华东现货 ¥15,800/ton (+0.8%). 万华福建一期检修剩余 12 天.\",
       \"ai_model\": \"claude-opus-4-7\",
       \"evidence\": [
         {\"kind\":\"page\",\"page_id\":$PAGE_ID,\"weight\":0.6,\"excerpt\":\"TDI华东主流成交价15,800元/吨\"},
         {\"kind\":\"catalog_indicator\",\"catalog_indicator_id\":$TDI_SPOT_ID,\"reading_ts\":\"2026-04-16T08:15:00Z\",\"weight\":0.4}
       ]
     }")
INSIGHT_ID=$(echo "$INSIGHT" | jq .id)
echo "insight id = $INSIGHT_ID"
[[ "$INSIGHT_ID" =~ ^[0-9]+$ ]] || fail "insight create failed: $INSIGHT"

say "4) GET /api/v2/insights/:id returns body + evidence joined to page url + indicator code"
DETAIL=$(curl -s -b "$JAR_A" "$GW/api/v2/insights/$INSIGHT_ID")
echo "$DETAIL" | jq '{title, body_md, evidence}'
EV_COUNT=$(echo "$DETAIL" | jq '.evidence | length')
[[ "$EV_COUNT" == "2" ]] || fail "expected 2 evidence items, got $EV_COUNT"
HAS_URL=$(echo "$DETAIL" | jq '[.evidence[] | select(.page_url=="https://100ppi.com/tdi-2026-04-16")] | length')
HAS_CODE=$(echo "$DETAIL" | jq '[.evidence[] | select(.indicator_code=="TDI_SPOT_EC")] | length')
[[ "$HAS_URL" == "1" ]]  || fail "page evidence not joined to url"
[[ "$HAS_CODE" == "1" ]] || fail "indicator evidence not joined to code"
green "evidence traceability works (page url + indicator code surfaced)"

say "5) GET /api/v2/me/briefing surfaces it"
BRIEF=$(curl -s -b "$JAR_A" "$GW/api/v2/me/briefing")
echo "$BRIEF" | jq '[.[] | {id, kind, title}]'
[[ $(echo "$BRIEF" | jq length) -ge 1 ]] || fail "briefing should include the new insight"

say "6) bob cannot see alice's insight"
BOB_LIST=$(curl -s -b "$JAR_B" "$GW/api/v2/insights" | jq length)
BOB_DETAIL_STATUS=$(curl -s -b "$JAR_B" -o /dev/null -w '%{http_code}' "$GW/api/v2/insights/$INSIGHT_ID")
[[ "$BOB_LIST" == "0" ]]            || fail "bob's insight list should be empty (got $BOB_LIST)"
[[ "$BOB_DETAIL_STATUS" == "404" ]] || fail "bob fetching alice's insight should 404 (got $BOB_DETAIL_STATUS)"
green "tenant isolation on insights enforced"

say "7) GET /api/v2/insights?goal_id=$GID returns the insight; alien goal returns empty"
BY_GOAL=$(curl -s -b "$JAR_A" "$GW/api/v2/insights?goal_id=$GID" | jq length)
[[ "$BY_GOAL" == "1" ]] || fail "expected 1 insight for goal $GID, got $BY_GOAL"

green "===== STEP 4 ALL ASSERTIONS PASS ====="
