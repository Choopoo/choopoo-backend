#!/usr/bin/env bash
# Step 2 verification: catalog browse, tenant enable / override / private addition
# all isolated correctly by org.

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

JAR_A=/tmp/jar_step2_a.txt; JAR_B=/tmp/jar_step2_b.txt
rm -f "$JAR_A" "$JAR_B"

say "1) signup alice@step2a.com + bob@step2b.com"
signup "alice@step2a.com" "$JAR_A"
signup "bob@step2b.com"   "$JAR_B"

say "2) catalog browse — both orgs see the same library"
A_CAT_MAT=$(curl -s -b "$JAR_A" "$GW/api/v2/catalog/materials" | jq length)
B_CAT_MAT=$(curl -s -b "$JAR_B" "$GW/api/v2/catalog/materials" | jq length)
echo "alice sees catalog materials: $A_CAT_MAT, bob sees: $B_CAT_MAT"
[[ "$A_CAT_MAT" == "20" && "$B_CAT_MAT" == "20" ]] || fail "catalog material count mismatch"
A_CAT_IND=$(curl -s -b "$JAR_A" "$GW/api/v2/catalog/indicators" | jq length)
[[ "$A_CAT_IND" == "30" ]] || fail "catalog indicators count != 30 (got $A_CAT_IND)"
green "both tenants see all 20 materials + 30 indicators"

say "3) /me/materials starts empty for both tenants"
A_ME=$(curl -s -b "$JAR_A" "$GW/api/v2/me/materials" | jq length)
B_ME=$(curl -s -b "$JAR_B" "$GW/api/v2/me/materials" | jq length)
[[ "$A_ME" == "0" && "$B_ME" == "0" ]] || fail "/me/materials should be empty initially (A=$A_ME B=$B_ME)"
green "no materials enabled yet"

say "4) alice enables TDI catalog material with nickname '主原料 TDI'"
TDI_ID=$(curl -s -b "$JAR_A" "$GW/api/v2/catalog/materials" | jq '.[] | select(.code=="TDI") | .id')
echo "TDI catalog id = $TDI_ID"
curl -s -b "$JAR_A" -X POST "$GW/api/v2/tenant/materials/enable" \
     -H 'content-type: application/json' \
     -d "{\"catalog_raw_material_id\":$TDI_ID,\"nickname\":\"主原料 TDI\"}" >/dev/null

say "5) alice creates private material 'caprolactam'"
curl -s -b "$JAR_A" -X POST "$GW/api/v2/tenant/materials" \
     -H 'content-type: application/json' \
     -d '{"code":"CAPROLACTAM","name":"Caprolactam","name_cn":"己内酰胺","unit":"CNY/ton","category":"macro"}' >/dev/null

say "6) /me/materials reflects: alice sees TDI(catalog)+caprolactam(private); bob sees nothing"
A_LIST=$(curl -s -b "$JAR_A" "$GW/api/v2/me/materials")
B_LIST=$(curl -s -b "$JAR_B" "$GW/api/v2/me/materials")
echo "--- alice ---"; echo "$A_LIST" | jq '[.[] | {source, code, nickname}]'
echo "--- bob ---";   echo "$B_LIST" | jq '[.[] | {source, code, nickname}]'
A_COUNT=$(echo "$A_LIST" | jq length)
B_COUNT=$(echo "$B_LIST" | jq length)
[[ "$A_COUNT" == "2" ]] || fail "alice should have 2 materials, got $A_COUNT"
[[ "$B_COUNT" == "0" ]] || fail "bob leaked $B_COUNT rows from alice's tenancy"
A_NICK=$(echo "$A_LIST" | jq -r '.[] | select(.code=="TDI") | .nickname')
[[ "$A_NICK" == "主原料 TDI" ]] || fail "nickname not preserved (got: $A_NICK)"
green "tenant overlay isolated; nickname preserved"

say "7) alice OVERRIDES catalog indicator TDI_SPOT_EC formula; bob does not"
TDI_SPOT_ID=$(curl -s -b "$JAR_A" "$GW/api/v2/catalog/indicators" | jq '.[] | select(.code=="TDI_SPOT_EC") | .id')
echo "TDI_SPOT_EC catalog id = $TDI_SPOT_ID"
# Both enable the indicator first
curl -s -b "$JAR_A" -X POST "$GW/api/v2/tenant/indicators/enable" \
     -H 'content-type: application/json' -d "{\"catalog_indicator_template_id\":$TDI_SPOT_ID}" >/dev/null
curl -s -b "$JAR_B" -X POST "$GW/api/v2/tenant/indicators/enable" \
     -H 'content-type: application/json' -d "{\"catalog_indicator_template_id\":$TDI_SPOT_ID}" >/dev/null
# Alice overrides the formula to a custom shape (toy override; what matters is precedence)
curl -s -b "$JAR_A" -X POST "$GW/api/v2/tenant/indicators/override" \
     -H 'content-type: application/json' \
     -d "{\"catalog_indicator_template_id\":$TDI_SPOT_ID,\"formula_json_override\":{\"op\":\"alice_custom\",\"weighted_sources\":[\"100ppi\",\"sci99\"]}}" >/dev/null

say "8) /me/indicators precedence: alice sees override; bob sees catalog default"
A_IND=$(curl -s -b "$JAR_A" "$GW/api/v2/me/indicators" | jq '.[] | select(.code=="TDI_SPOT_EC")')
B_IND=$(curl -s -b "$JAR_B" "$GW/api/v2/me/indicators" | jq '.[] | select(.code=="TDI_SPOT_EC")')
A_SOURCE=$(echo "$A_IND" | jq -r .source)
B_SOURCE=$(echo "$B_IND" | jq -r .source)
A_FORMULA=$(echo "$A_IND" | jq -c .formula_json)
B_FORMULA=$(echo "$B_IND" | jq -c .formula_json)
echo "alice TDI_SPOT_EC: source=$A_SOURCE formula=$A_FORMULA"
echo "bob   TDI_SPOT_EC: source=$B_SOURCE formula=$B_FORMULA"
[[ "$A_SOURCE" == "catalog+override" ]] || fail "alice should see source=catalog+override, got $A_SOURCE"
[[ "$B_SOURCE" == "catalog" ]]          || fail "bob should see source=catalog, got $B_SOURCE"
[[ "$A_FORMULA" == *"alice_custom"* ]]  || fail "alice should see overridden formula"
[[ "$B_FORMULA" != *"alice_custom"* ]]  || fail "BOB SAW ALICE'S OVERRIDE (formula leak)"
green "override precedence works; no cross-tenant override leakage"

say "9) alice creates a fully PRIVATE composite indicator"
curl -s -b "$JAR_A" -X POST "$GW/api/v2/tenant/indicators" \
     -H 'content-type: application/json' \
     -d '{"code":"ALICE_TDI_HDI_RATIO","kind":"derived","subject_kind":"raw_material","unit":"ratio","formula_json":{"op":"divide","left":{"indicator_code":"TDI_SPOT_EC"},"right":{"indicator_code":"HDI_SPOT_CN"}},"description":"alice private metric"}' >/dev/null

A_PRIV=$(curl -s -b "$JAR_A" "$GW/api/v2/me/indicators" | jq '[.[] | select(.code=="ALICE_TDI_HDI_RATIO")] | length')
B_PRIV=$(curl -s -b "$JAR_B" "$GW/api/v2/me/indicators" | jq '[.[] | select(.code=="ALICE_TDI_HDI_RATIO")] | length')
[[ "$A_PRIV" == "1" ]] || fail "alice should see her private indicator (got $A_PRIV)"
[[ "$B_PRIV" == "0" ]] || fail "BOB SAW ALICE'S PRIVATE INDICATOR (private leak)"
green "private indicator visible only to creator"

green "===== STEP 2 ALL ASSERTIONS PASS ====="
