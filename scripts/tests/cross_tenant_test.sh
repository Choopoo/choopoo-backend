#!/usr/bin/env bash
# Cross-tenant isolation integration test for Choopoo gateway.
# Asserts: two orgs see only their own pages; v1 sees neither (sentinel-only).

set -euo pipefail
GW=http://localhost:8081

red()   { printf "\033[31m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
say()   { printf "\033[36m== %s\033[0m\n" "$*"; }

signup() {
  local email=$1
  local cookiejar=$2
  local link
  link=$(curl -s -X POST "$GW/auth/magic-link" \
        -H 'content-type: application/json' \
        -d "{\"email\":\"$email\"}" | jq -r .dev_link)
  if [[ -z "$link" || "$link" == "null" ]]; then
    red "no dev_link returned for $email"; exit 1
  fi
  curl -s -c "$cookiejar" "$link" >/dev/null
}

seed() {
  local cookiejar=$1
  local url=$2
  curl -s -b "$cookiejar" -X POST "$GW/api/v2/test/seed" \
       -H 'content-type: application/json' \
       -d "{\"url\":\"$url\",\"title\":\"seed\"}" | jq .
}

list() {
  curl -s -b "$1" "$GW/api/v2/results?limit=20" | jq '[.[] | {id, url, org_id}]'
}

JAR_A=/tmp/jar_a.txt; JAR_B=/tmp/jar_b.txt
rm -f "$JAR_A" "$JAR_B"

say "1) signing up alice@a.com and bob@b.com via magic-link"
signup "alice@a.com" "$JAR_A"
signup "bob@b.com"   "$JAR_B"

say "2) /api/v2/me identities"
ME_A=$(curl -s -b "$JAR_A" "$GW/api/v2/me")
ME_B=$(curl -s -b "$JAR_B" "$GW/api/v2/me")
echo "alice -> $ME_A"
echo "bob   -> $ME_B"
ORG_A=$(echo "$ME_A" | jq -r .org_id)
ORG_B=$(echo "$ME_B" | jq -r .org_id)
[[ "$ORG_A" != "$ORG_B" ]] || { red "org IDs collided ($ORG_A == $ORG_B)"; exit 1; }
green "orgs differ: A=$ORG_A B=$ORG_B"

say "3) each tenant seeds 2 page rows"
seed "$JAR_A" "https://a.local/p1" >/dev/null
seed "$JAR_A" "https://a.local/p2" >/dev/null
seed "$JAR_B" "https://b.local/p1" >/dev/null
seed "$JAR_B" "https://b.local/p2" >/dev/null

say "4) /api/v2/results from each tenant should ONLY return own rows"
echo "--- alice sees ---"; list "$JAR_A"
echo "--- bob sees ---";   list "$JAR_B"

ALEAK=$(curl -s -b "$JAR_A" "$GW/api/v2/results?limit=20" | jq "[.[] | select(.org_id != $ORG_A)] | length")
BLEAK=$(curl -s -b "$JAR_B" "$GW/api/v2/results?limit=20" | jq "[.[] | select(.org_id != $ORG_B)] | length")
if [[ "$ALEAK" != "0" ]]; then red "ALICE LEAK: $ALEAK foreign rows"; exit 1; fi
if [[ "$BLEAK" != "0" ]]; then red "BOB LEAK:   $BLEAK foreign rows"; exit 1; fi
green "no cross-tenant leakage"

say "5) v1 /api/results should not show v2 tenant rows"
V1=$(curl -s "$GW/api/results?limit=50" | jq 'length')
echo "v1 row count = $V1"
V1LEAK=$(curl -s "$GW/api/results?limit=50" | jq "[.[] | select(.url | startswith(\"https://a.local\") or startswith(\"https://b.local\"))] | length")
if [[ "$V1LEAK" != "0" ]]; then red "V1 LEAK: $V1LEAK tenant rows visible to unauth caller"; exit 1; fi
green "v1 path does not leak tenant data"

say "6) bypass attempt: bob hits /api/v2/results trying to spoof org_id via query string"
SPOOF=$(curl -s -b "$JAR_B" "$GW/api/v2/results?org_id=$ORG_A&limit=20" | jq "[.[] | select(.org_id == $ORG_A)] | length")
if [[ "$SPOOF" != "0" ]]; then red "SPOOF LEAK: query-string org_id was honored"; exit 1; fi
green "spoofing query string ignored — RLS enforced from session"

green "===== ALL ASSERTIONS PASS ====="
