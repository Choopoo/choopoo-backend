# choopoo-backend

Distributed backend for the Choopoo TDI Price Intelligence Platform. Originally built as the CS-6650 final project.

## Architecture

```
Client → Gateway (Go) → Kafka → Producer (Go, crawler) → Kafka → Consumer (Python) → Postgres
                                                                        ↓
                                                            AI Service (Python) → Postgres
```

| Service | Language | Port | Purpose |
|---|---|---|---|
| `gateway` | Go (chi) | 8080 | HTTP API — crawl submission, results, health |
| `producer` | Go | — | Kafka consumer → HTML crawler → publish raw pages |
| `consumer` | Python | — | Kafka consumer → score + persist to Postgres |
| `ai-service` | Python | — | AI analysis with resilience patterns (retry, circuit breaker) |

Infra (Kafka, Redis, Postgres) lives in [choopoo-infra](https://github.com/Choopoo/choopoo-infra).

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/crawl` | Submit URLs with `material` + `source_label` |
| `GET` | `/api/results` | Filtered results (`?material=TDI&domain=100ppi.com&limit=50`) |
| `GET` | `/api/results/{id}` | Single result with AI summary |
| `GET` | `/api/status` | Pipeline health |
| `GET` | `/health` | Liveness probe |

## Local development

Use `choopoo-infra/docker-compose.local.yml` to run the full stack (backend + Kafka/Redis/Postgres + frontend).

Standalone backend-only stack: `docker-compose up` in this repo.

## Experiments

Four scaling/resilience experiments in `experiments/`:
1. `exp1` — throughput baseline
2. `exp2` — horizontal scaling (consumer replicas)
3. `exp3` — latency under load
4. `exp4_fault_tolerance` — recovery from service kill
