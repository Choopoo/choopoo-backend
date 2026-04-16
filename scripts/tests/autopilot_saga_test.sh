#!/usr/bin/env bash
# Step 9 verification: Goal-to-Data autopilot saga end-to-end.
# Browser creates a goal -> outbox -> Kafka -> workflow service plans saga ->
# materials enabled, indicators linked, briefing insight created -> all tenant-isolated.

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

wait_for_saga() {
  local jar=$1 goal_id=$2 tries=0
  while (( tries < 25 )); do
    local state
    state=$(curl -s -b "$jar" "$GW/api/v2/workflows?goal_id=$goal_id" | jq -r '.[0].state // empty')
    if [[ "$state" == "succeeded" || "$state" == "failed" ]]; then
      echo "$state"
      return 0
    fi
    sleep 0.5
    tries=$((tries+1))
  done
  echo "timeout"
  return 1
}

JAR_A=/tmp/jar_step9_a.txt; JAR_B=/tmp/jar_step9_b.txt
rm -f "$JAR_A" "$JAR_B"

say "1) signup alice + bob"
signup "alice@step9a.com" "$JAR_A"
signup "bob@step9b.com"   "$JAR_B"

say "2) alice creates goal 'Cut TDI procurement cost 5%' -> outbox should publish goal.created.v1"
GID_A=$(curl -s -b "$JAR_A" -X POST "$GW/api/v2/goals" \
     -H 'content-type: application/json' \
     -d '{"title":"Cut TDI procurement cost 5%","lens":"buy","horizon_days":90}' | jq .id)
[[ "$GID_A" =~ ^[0-9]+$ ]] || fail "create goal failed: $GID_A"
echo "alice goal_id=$GID_A"

say "3) wait for saga to reach terminal state"
STATE=$(wait_for_saga "$JAR_A" "$GID_A")
echo "saga state=$STATE"
[[ "$STATE" == "succeeded" ]] || fail "saga did not succeed: $STATE"

say "4) /api/v2/workflows?goal_id=$GID_A shows the run"
RUN=$(curl -s -b "$JAR_A" "$GW/api/v2/workflows?goal_id=$GID_A" | jq '.[0]')
echo "$RUN" | jq '{id, kind, state, current_step, subject_ref, steps_log}'
STEPS=$(echo "$RUN" | jq '.steps_log | length')
[[ "$STEPS" -ge 1 ]] || fail "steps_log is empty"

say "5) goal now has indicators linked by the saga"
DETAIL=$(curl -s -b "$JAR_A" "$GW/api/v2/goals/$GID_A")
echo "$DETAIL" | jq '{title, indicators: [.indicators[] | {indicator_code, role}]}'
IND_COUNT=$(echo "$DETAIL" | jq '.indicators | length')
[[ "$IND_COUNT" -ge 1 ]] || fail "saga didn't link any indicators (expected >=1, got $IND_COUNT)"

say "6) briefing insight exists, cites catalog indicator readings"
BRIEF=$(curl -s -b "$JAR_A" "$GW/api/v2/insights?goal_id=$GID_A")
echo "$BRIEF" | jq '[.[] | {id, kind, title}]'
[[ $(echo "$BRIEF" | jq length) -ge 1 ]] || fail "no briefing created"
INS_ID=$(echo "$BRIEF" | jq '.[0].id')
DETAIL=$(curl -s -b "$JAR_A" "$GW/api/v2/insights/$INS_ID")
EV_COUNT=$(echo "$DETAIL" | jq '.evidence | length')
[[ "$EV_COUNT" -ge 1 ]] || fail "briefing has no evidence attached"
green "briefing cites $EV_COUNT evidence item(s)"

say "7) alice's TDI material is now enabled (saga-enabled)"
MATS=$(curl -s -b "$JAR_A" "$GW/api/v2/me/materials" | jq '[.[] | {code, source}]')
echo "$MATS"
HAS_TDI=$(curl -s -b "$JAR_A" "$GW/api/v2/me/materials" | jq '[.[] | select(.code=="TDI")] | length')
[[ "$HAS_TDI" == "1" ]] || fail "saga didn't enable TDI material"

say "8) bob's tenant sees zero autopilot side-effects"
B_MATS=$(curl -s -b "$JAR_B" "$GW/api/v2/me/materials" | jq length)
B_INS=$(curl -s -b "$JAR_B" "$GW/api/v2/insights" | jq length)
B_WF=$(curl -s -b "$JAR_B" "$GW/api/v2/workflows" | jq length)
[[ "$B_MATS" == "0" ]] || fail "bob leaked $B_MATS materials"
[[ "$B_INS" == "0" ]]  || fail "bob leaked $B_INS insights"
[[ "$B_WF" == "0" ]]   || fail "bob leaked $B_WF workflow runs"
green "saga is RLS-isolated (zero leak to bob)"

say "9) private-material path: create a goal for something NOT in catalog"
GID_C=$(curl -s -b "$JAR_A" -X POST "$GW/api/v2/goals" \
     -H 'content-type: application/json' \
     -d '{"title":"Track Caprolactam supply risk","lens":"buy"}' | jq .id)
STATE_C=$(wait_for_saga "$JAR_A" "$GID_C")
[[ "$STATE_C" == "succeeded" ]] || fail "caprolactam saga did not succeed: $STATE_C"
HAS_CAPRO=$(curl -s -b "$JAR_A" "$GW/api/v2/me/materials" | jq '[.[] | select(.code=="CAPROLACTAM")] | length')
[[ "$HAS_CAPRO" == "1" ]] || fail "saga didn't create private Caprolactam material"
green "private-material path works (autopilot created Caprolactam as tenant private)"

green "===== STEP 9 AUTOPILOT SAGA — ALL ASSERTIONS PASS ====="
