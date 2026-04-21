# Choopoo — CS-6650 Final Project

Solo · Kaige Zheng · Northeastern University · Spring 2026

---

## One-paragraph overview

**Choopoo is a bilingual TDI price-intelligence trading desk for small Chinese polyurethane (PU) manufacturers**, built on a horizontally-scalable, fault-tolerant distributed pipeline. The pilot customer is Guotu New Materials — a 60 000-ton-per-year hardener maker in Guangdong — whose biggest cost driver is TDI (toluene diisocyanate), a chemical whose price swings 10–15 % in a single month. Choopoo replaces the procurement manager's two-hour daily routine of hand-polling ten supplier pricing sites with a daily morning dashboard, an LLM copilot, and an autopilot saga that sets up tracking for new goals without manual configuration. The course experiments quantify that the distributed backend is what makes the daily-use product feasible at SME scale.

---

## What this directory is for

This is the **Final Project submission** for CS-6650 Scalable Distributed Systems. Every artifact the rubric asks for lives in this folder:

| Rubric item | Mark weight | Deliverable here | Where to upload on Canvas |
|---|---|---|---|
| Video | 5 | YouTube unlisted URL (see Piazza post) | Canvas text field — YouTube URL |
| Code | 5 | Three-repo `Choopoo` org + HW1–HW10 history (see "Repo map" below) | Canvas text field — repo URLs |
| Project Management | 5 | [`PROJECT_TIMELINE.md`](PROJECT_TIMELINE.md) + GitHub contribution graph | Canvas text field — this URL |
| **Experiments** | **10** | [`EXPERIMENTS_REPORT.pdf`](EXPERIMENTS_REPORT.pdf) (≤5 pages) | Canvas file upload |
| Community Contributions | 5 | [`PIAZZA_POST_DRAFT.md`](PIAZZA_POST_DRAFT.md) (posted as Piazza thread) | Canvas link to Piazza post |
| Lessons Learned | separate | [`LESSONS_LEARNED.md`](LESSONS_LEARNED.md) | Separate Canvas submission |

---

## End-to-end modifications — what was done across the project

The final project is the culmination of three months of work that started in `hw9/` (monolithic single-team project) and ended in the three-repo `Choopoo` org as a productised SaaS-shape application. The headline changes, in chronological order:

### Phase 0 — Coursework foundation (Jan–Mar)

HW1–HW10 built the distributed-systems muscle needed for the final project. HW6 (horizontal scaling behind an ALB with Terraform) and HW9 (Kafka-based multi-stage pipeline with producer/consumer/AI-service) became the direct ancestors of the Choopoo backend. The HW9 presentation, product vision doc, and experiment JSON are the source material for the final project's first four services and first four experiments.

### Phase 1 — Pipeline foundation & AWS port (Mar 24 – Apr 14)

Four services (gateway / producer / consumer / ai-service), five-stage Kafka-decoupled pipeline, Docker Compose for local, Terraform for ECS Fargate + RDS + ElastiCache + ALB + Cloud Map. All four experiments ran against this stack:

- **Local Docker:** `choopoo-backend/experiments/{exp1,exp2,exp3,exp4_fault_tolerance}/`
- **AWS ECS Fargate (us-west-2, ALB-fronted):** `choopoo-backend/experiments/aws/{exp1,exp2,exp3}/`

### Phase 2 — Productisation into the `Choopoo` org (Apr 16 – Apr 17)

A two-day intensive refactor migrated the monolithic `hw9/` backend into three independent repositories under the `Choopoo` GitHub org and added four new services:

- **`copilot`** — FastAPI, Anthropic SDK, locale-aware system prompt, bilingual conversational surface
- **`forecaster`** — AutoETS on indicator time series, every 5 min, writes `insights`
- **`event-extractor`** — regex supply-event detection over crawled `pages`, every 60 s, writes `insights`
- **`workflow`** — saga orchestrator, consumes `goal.created.v1` Kafka topic, runs append-only multi-step plan

The productisation layer added:
- **Transactional outbox** at the gateway (Postgres `domain_events` row + goroutine relay to Kafka — makes goal-creation atomic from the user's perspective even though the saga runs for minutes)
- **Postgres row-level security (RLS)** gated by `current_setting('app.org_id')` — multi-tenant isolation enforced by the database, not the application
- **React 19 frontend** — 12 pages, 14 components, Bloomberg-feel warm-dark design system with WCAG-AA contrast lint enforced by Playwright
- **Full `react-i18next` bilingual stack** + four schema migrations adding `name_cn` / `description_cn` / `users.locale` columns (the "engineering codes leaking into the UI" correctness bug — see [`LESSONS_LEARNED.md`](LESSONS_LEARNED.md))
- **Information-architecture simplification** — collapsed from 5-tab nav to 2 tabs (`Desk` + `Ask`) + ⌘K command palette + avatar menu for admin surfaces
- **Signal Map** — per-material auditable active/candidate/rejected "information axes" with induction chains and example events (anti-hallucination primitive for the non-technical SME owner)

### Phase 3 — AWS coverage of productisation services (Apr 21)

Terraform for the four newer services (copilot, forecaster, event-extractor, workflow) added in [`choopoo-infra/terraform/services_productisation.tf`](https://github.com/Choopoo/choopoo-infra/blob/main/terraform/services_productisation.tf) with ECR repos, CloudWatch log groups, docker build/push, Fargate task defs, ECS services, and Cloud Map registration for the gateway so enrich-plane services can reach it at `gateway.pipeline.local:8080`. `terraform validate` passes. The stack is **deploy-ready** but not currently applied — the course experiments ran against the original four services, which is the evidence the report stands on.

### Phase 4 — Final-project documentation (Apr 18 – Apr 21)

All deliverables in this directory:
- Presentation deck ([`PRESENTATION.md`](PRESENTATION.md))
- 5-page experiments report ([`EXPERIMENTS_REPORT.pdf`](EXPERIMENTS_REPORT.pdf))
- Real git-history project timeline ([`PROJECT_TIMELINE.md`](PROJECT_TIMELINE.md))
- Solo reflection ([`LESSONS_LEARNED.md`](LESSONS_LEARNED.md))
- Piazza community-contribution post draft with analysis of three classmate projects ([`PIAZZA_POST_DRAFT.md`](PIAZZA_POST_DRAFT.md))

---

## Navigation — where to find what

### Repo map

| Repo | URL | What's inside | Highlights |
|---|---|---|---|
| **choopoo-backend** (this repo) | https://github.com/Choopoo/choopoo-backend | 8 services in `services/`, load-test harness in `scripts/`, raw experiment JSON in `experiments/`, this docs folder | `main` is current product code; `submission/cs6650-final` adds `docs/` |
| **choopoo-frontend** | https://github.com/Choopoo/choopoo-frontend | React 19 + Vite + TS + Tailwind v4 + TanStack Query + Recharts + react-i18next | `docs/decisions.md` is an append-only log of every non-obvious frontend choice |
| **choopoo-infra** | https://github.com/Choopoo/choopoo-infra | `docker-compose.local.yml` + Terraform for ECS Fargate + deploy README | Deploys all 8 services to AWS |
| **Coursework** (HW1–HW10) | https://github.com/kdeisgn/NU-Distributed-System-Design-CS6650-2025Fall | HW1–HW10 + the `hw9/` monolith that preceded Choopoo | 47 commits over 3 months — primary "activity over time" evidence |

### File map inside `choopoo-backend/`

```
choopoo-backend/
├── services/
│   ├── gateway/          # Go (chi) — HTTP API, transactional outbox, RLS
│   ├── producer/         # Go — Kafka → HTTP crawl → Kafka
│   ├── consumer/         # Python — Kafka → score + persist + dedupe
│   ├── summariser/       # Python — Kafka → LLM (backoff/BP/CB resilience)
│   ├── copilot/          # Python (FastAPI) — Anthropic SDK, bilingual
│   ├── forecaster/       # Python — AutoETS, service-secret HTTP
│   ├── event-extractor/  # Python — regex, service-secret HTTP
│   └── workflow/         # Python — saga orchestrator, Kafka consumer
├── scripts/
│   ├── load_test.py                 # Async aiohttp load generator
│   ├── run_experiments.py           # Local Docker experiment runner
│   ├── run_aws_experiments.py       # ECS Fargate experiment runner
│   ├── analyze_exp4_recovery.py     # Recovery-time analysis
│   ├── generate_report_assets.py    # Regenerates every chart from JSON
│   └── ecs_stop_task_experiment.py  # AWS equivalent of docker kill
├── experiments/                     # Raw JSON results (local Docker)
│   ├── exp1/                        # Producer horizontal scaling
│   ├── exp2/                        # Consumer scaling
│   ├── exp3/                        # Resilience patterns
│   ├── exp4_fault_tolerance/        # docker kill + recovery
│   └── aws/                         # Same experiments on ECS Fargate
├── docker-compose.yml               # Standalone backend-only stack
└── docker-compose.experiment.yml    # Overlay for scaling experiments
```

### File map inside this `docs/` folder

```
docs/
├── README.md                 # ← you are here
├── PRESENTATION.md           # Full deck — vision + architecture + exp's + demo path
├── EXPERIMENTS_REPORT.md     # Source for the 5-page PDF
├── EXPERIMENTS_REPORT.pdf    # Canvas upload (10 marks)
├── PROJECT_TIMELINE.md       # Real git-log timeline across 4 repos
├── LESSONS_LEARNED.md        # Solo reflection, honest
├── PIAZZA_POST_DRAFT.md      # Community-contribution post (fill in video URL before posting)
├── report.css                # Style used to generate the 5-page PDF
└── assets/
    ├── exp1-throughput-chart-aws.png
    ├── exp2-latency-chart-aws.png
    ├── exp3-comparison-chart-aws.png
    ├── exp4-recovery-chart.png
    └── aws-console/
        ├── ecs-pipeline-cluster-services-kai.png
        └── alb-load-balancers-kai.png
```

### Branch strategy (why `submission/cs6650-final` exists)

- **`main`** on `choopoo-backend` holds the product code only — clean of any academic-submission artifacts.
- **`submission/cs6650-final`** holds the `docs/` folder you are reading right now. Everything the grader needs lives on this branch. Rebasing, merging, or re-pushing `main` never affects the academic artifacts.

---

## Experiments — what we did, why, and what we learned

The four experiments were designed to test one core claim: **does the Kafka-decoupled architecture actually buy the properties a daily-use SME product needs?** Each experiment maps to a specific stakeholder question an SME-product PM would ask. This section gives the **purpose and conclusion** of each; the detailed setup, tables, charts, and limitations live in [`EXPERIMENTS_REPORT.pdf`](EXPERIMENTS_REPORT.pdf).

### Why these four experiments in this order

The experiments build on each other as an argument:

1. First we test whether **adding producer replicas increases throughput** (does horizontal scaling work at all?).
2. Then we test whether we can **keep tail latency bounded while load and consumers grow together** (is it multi-tenant-able?).
3. Then we stress the most likely failure mode — the **external LLM rate-limits or fails** — and compare three industry-standard resilience patterns.
4. Finally we break things on purpose — **kill services under sustained load** — and measure recovery.

### Experiment 1 — Producer horizontal scaling

**Question we were answering.** If we onboard ten SME owners tracking different material portfolios, does simply adding more producer replicas increase how much work the pipeline absorbs per second?

**Outcome.** No. Throughput stayed essentially flat (~47 rps) when sweeping producer replicas 2 → 5 → 10 on AWS. The bottleneck is upstream — the single gateway task saturates first.

**Takeaway.** This is the most useful *negative* result in the whole study. It tells us producer is the wrong scaling knob for this workload; the gateway is. For a product PM, this is exactly the conversation you want *before* spending money on more crawlers. The next engineering investment should be multi-replica gateway behind the ALB target group — a one-line `ecs update-service` change.

### Experiment 2 — Consumer scaling & bottleneck migration

**Question we were answering.** If we scale both *load* and *consumer replicas* proportionally, does throughput grow near-linearly while tail latency stays bounded? That's the property that lets the desk serve a growing number of SME tenants without latency cliffs.

**Outcome.** Yes. Throughput on AWS went 23 → 96 → 213 rps as concurrency × consumer count grew roughly 10×. p95 stayed bounded in a tight 246–282 ms range across the whole sweep. Zero errors.

**Takeaway.** The **consumer tier is the right horizontal-scaling axis** for this pipeline. Adding one consumer per ~10× load step keeps tail latency flat. The shape of the p99 at the highest load (287 → 254 → 310 ms) is the first hint of bottleneck migration into the DB write path and Kafka rebalance pauses — something we would need sustained load to characterise fully.

### Experiment 3 — Resilience pattern comparison (backoff vs. backpressure vs. circuit breaker)

**Question we were answering.** When the AI tier degrades (our simulated 30 % failure rate, 200 ms added latency), which of the three classic resilience patterns best preserves end-to-end throughput and tail behaviour at the gateway?

**Outcome.** All three patterns absorbed 30 % downstream failure with **zero gateway errors**. The Kafka-decoupled architecture is doing real work here — the gateway never directly calls the LLM. At the tail, circuit breaker showed the highest p95/p99 (the cost of the half-open probe rejecting attempts fast); backoff had the cleanest median latency; backpressure sat in between.

**Takeaway.** There is no universal winner — **the right pattern depends on the failure profile**. Backoff is the clean default for *transient and bursty* failure. Circuit breaker wins when the downstream is unhealthy *long enough that retries would amplify the problem*. Backpressure wins when *budget enforcement* matters more than peak throughput. For Choopoo's copilot (where Claude rate-limits are correlated bursts, not uniform random), circuit breaker is likely the right production default.

### Experiment 4 — Fault tolerance & recovery

**Question we were answering.** When a core service crashes at 2 a.m., does the user-facing desk go dark? How long until the system heals?

**Outcome.** **Zero HTTP errors across all three kills** (producer, consumer, Redis) under sustained load. Kafka's queue-and-retry semantics keep the front door open while the back end recovers. Recovery times: Redis 6 s, producer 11 s, consumer 31 s. The consumer kill is slowest because it triggers a Kafka consumer-group rebalance.

**Takeaway.** **The architecture passes the basic single-service chaos test.** The deliberate choice to put Kafka between *every* stage is what makes this possible — a design with direct HTTP between services would have failed all three kills. The 31-second consumer rebalance is the dominant recovery bound and the number that should go in any SLA document. One honest limitation: recovery was measured by gateway-CPU return-to-baseline, not by Kafka consumer-lag — the more honest metric requires offset instrumentation we did not build.

### The five headline cross-experiment takeaways

1. **The right scaling knob is the consumer tier, not the producer tier.** Producer scaling plateaus at ~5 replicas; consumer scaling stays linear with concurrency.
2. **Kafka decoupling pays for itself.** Every fault and every resilience test posted zero gateway errors. The cost is operational complexity (rebalance pauses, partition tuning, offset bookkeeping) quantified in seconds.
3. **Resilience patterns are not interchangeable.** Pick by failure profile — transient vs. sustained vs. budgeted.
4. **Local Docker results lie in predictable directions.** Local overstates throughput (no ALB, no cross-AZ) and understates tail variance. Always re-run on the target environment before quoting numbers.
5. **The product story and the infrastructure story are the same story.** A daily trading desk for SME owners cannot be flaky, cannot drop messages when a service crashes, and cannot stall when Claude rate-limits. The four experiments each defend one of those promises with measured numbers.

---

## How to reproduce

### Run the full stack locally

```bash
git clone git@github.com:Choopoo/choopoo-infra.git
git clone git@github.com:Choopoo/choopoo-backend.git
git clone git@github.com:Choopoo/choopoo-frontend.git

cd choopoo-infra
docker compose -f docker-compose.local.yml up --build
# Frontend: http://localhost:3000
# Gateway:  http://localhost:8081/health
```

### Deploy to AWS ECS Fargate

Provisions all 8 services + RDS + ElastiCache + ALB + Cloud Map. See `choopoo-infra/README.md` for the full deploy story.

```bash
cd choopoo-infra/terraform
terraform init
terraform plan -out=plan.tfout
terraform apply plan.tfout
# Output alb_dns_name is the public endpoint
```

### Re-run the experiments

```bash
# Local Docker:
cd choopoo-backend
python3 scripts/run_experiments.py --experiment 1   # Producer scaling
python3 scripts/run_experiments.py --experiment 2   # Consumer scaling
python3 scripts/run_experiments.py --experiment 3   # Resilience patterns
python3 scripts/run_experiments.py --experiment 4   # Fault tolerance
python3 scripts/analyze_exp4_recovery.py            # Recovery-time calculation

# AWS ECS Fargate (requires credentials + deployed stack):
GATEWAY_URL=http://<alb-dns-name> python3 scripts/run_aws_experiments.py --experiment 1
```

### Regenerate the experiments PDF

```bash
cd choopoo-backend/docs
pandoc EXPERIMENTS_REPORT.md -s -c report.css \
    --metadata title="Experiments Report — Choopoo" -o _report.html
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --headless --disable-gpu --no-pdf-header-footer \
    --print-to-pdf=EXPERIMENTS_REPORT.pdf "file://$(pwd)/_report.html"
rm _report.html
```

### Regenerate all experiment charts

```bash
cd choopoo-backend
python3 scripts/generate_report_assets.py
# Overwrites the PNGs in docs/assets/ from the JSON in experiments/
```

---

## Honest limitations

In the interest of transparency (and because the rubric values this):

- **Recovery time in Experiment 4** is measured by gateway-CPU return-to-baseline, not by Kafka consumer-lag. The more defensible metric requires offset instrumentation that was not built.
- **Producer-side throughput plateau in Experiment 1** is correctly identified as "producers alone don't help past N=5" — we did not independently sweep gateway count to prove the gateway is the bottleneck.
- **Local Docker vs. AWS divergence** is real and both result sets are kept explicitly so the divergence is visible. Local is not a faithful proxy for production.
- **The four newer productisation services** (copilot, forecaster, event-extractor, workflow) have Terraform definitions in `choopoo-infra/terraform/services_productisation.tf` but are **not currently applied to AWS**. The experiments that earn the 10-mark rubric weight ran against the original four services on the AWS stack, which is the evidence the report stands on.

---

## Contact

Kaige Zheng · kaigezhengzz@gmail.com · CS-6650 Spring 2026 · Northeastern University
