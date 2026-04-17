# AGENTS.md — choopoo-backend

Hi. You're an agent. Read this first; it points at the rest.

## What this is

Multi-tenant procurement + market-intel copilot backend for Chinese PU
SMEs. Modular monolith + event-driven workers, deliberately not
microservices-per-entity. Postgres + RLS for tenant isolation, Kafka
for the outbox + worker fan-out, Redis for sessions, Anthropic SDK for
copilot.

## Where things live

- `services/gateway/` — Go (chi). HTTP API + auth + RLS-aware tx
  middleware + outbox relay. The single ingress.
  - `migrations/` — golang-migrate, embedded; runs on gateway boot.
  - `v2_*.go` — bilingual catalog, indicators, aspects, goals, copilot proxy.
  - `auth.go` — magic-link + session cookie + `users.locale` toggle.
  - `tenant.go` — `withTenantTx` middleware (sets `app.org_id` GUC + `SET LOCAL ROLE tenant_user`).
  - `outbox.go` — `domain_events` → Kafka relay.
- `services/composer/` — Python. Composes derived/spread indicators
  per the `formula_json` recursive evaluator.
- `services/copilot/` — FastAPI + Anthropic SDK. Tool-use loop in
  `anthropic_loop.py`; tools dispatch HTTP calls back to the gateway
  using `X-Service-Secret` + `X-Org-Id` headers (so RLS still enforces).
- `services/workflow/` — Python. Saga orchestrator
  (`saga.py:_compose_setup_body`).
- `services/summariser/` — Python. Insight body generator.
- `services/event-extractor/` — Python. Regex lexicon over crawled
  pages; emits structured events.
- `services/forecaster/` — Python. AutoETS polling loop.

## Read before editing

- `services/gateway/migrations/README.md` — migration discipline.
- This file — for the bilingual / locale rules below.

## Locale + bilingual columns

The catalog carries Chinese + English in adjacent columns:

| Table | English | Chinese |
|---|---|---|
| `catalog_raw_material` | `name` | `name_cn` |
| `catalog_finished_product` | `name` | `name_cn` |
| `product_families` | `name` | `name_cn` |
| `catalog_indicator_template` | `name` + `description` | `name_cn` + `description_cn` |
| `catalog_signal_aspect` | `name` + `description` | `name_cn` + `description_cn` |
| `sources` | `label` | `label_cn` |

`users.locale` (en | zh-CN) is the user's preference. Handlers
return BOTH languages on every catalog payload — the frontend
picks via `useLocalizedField`. Don't conditionally select one or
the other server-side.

## Maintenance contract

After every code change, ask these questions:

1. Added a new catalog column with user-facing prose?
   → add the matching `_cn` column in the same migration; populate
   both. Update the table above.
2. Added a Go handler that returns DB rows containing user-facing
   prose? → SELECT both English and Chinese columns; include both in
   the JSON response.
3. Touched the copilot system prompt or any saga/summariser template?
   → preserve the rule that LLM output should match the user's input
   language (best-effort, no header plumbing — Phase 3 strict mode is
   deferred; see frontend `docs/decisions.md` 2026-04-17).
4. Added a new endpoint? → respect `withTenantTx` for tenant-scoped
   data; `requireServiceSecret` for inter-service.

## Dev loop

```bash
cd choopoo-infra
docker compose -f docker-compose.local.yml up -d
# gateway runs migrations on boot
docker logs -f choopoo-infra-gateway-1
```

Magic-link login (dev mode returns the link):

```bash
curl -s localhost:8081/auth/magic-link \
  -H 'Content-Type: application/json' \
  -d '{"email":"owner@demo.choopoo.cn"}' | jq -r .dev_link
```

Toggle locale:

```bash
curl -s -b $JAR -X PATCH localhost:8081/api/v2/me \
  -H 'Content-Type: application/json' \
  -d '{"locale":"zh-CN"}'
```

## What this file is NOT

- Not architecture deep-dive — that lives in code comments per service.
- Not a tutorial — link out, don't duplicate.
- Stay under ~150 lines.
