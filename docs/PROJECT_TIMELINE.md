# Project Management Timeline — CS-6650 Final Project (Choopoo)

**Solo · Kaige Zheng (NEU CS-6650 Spring 2026)**

This is the "Project Management" deliverable (5 marks). It documents the actual progression of the work from initial design to the final state, with **honest, real git history** drawn from four repositories that participated in the project.

> Generated from `git log` across `hw9/`, `choopoo-backend/`, `choopoo-frontend/`, `choopoo-infra/` on 2026-04-21. No commits are backdated or fabricated — all timestamps are author-clock dates as recorded by Git at the time of each commit.

---

## At a glance

| Metric | Value |
|---|---|
| **Project span** | 2026-01-17 → 2026-04-17 (3 months) |
| **Distinct days with commits** | 16 |
| **Total commits across 4 repos** | 70 |
| **Repos** | `hw9` (course assignments → final-project foundation), `choopoo-backend`, `choopoo-frontend`, `choopoo-infra` |
| **Lines of source written (rough)** | ~25 K (Go + Python + TS + Terraform + SQL) |
| **Final architecture** | 8 services, 5 Kafka topics, RDS/ElastiCache, ECS Fargate |

---

## Phase plan vs. actuality

The work was sequenced as four phases on the original plan; the table below compares planned vs. delivered. Each row is grounded in real commits (see §"Per-repo commit history" below).

| Phase | Planned window | Goal | Delivered | Evidence |
|---|---|---|---|---|
| **0. Coursework foundations** | Jan 17 – Mar 17 | Build the distributed-systems muscle (HW1–7) needed for the final project | All 7 homeworks shipped; HW6 (horizontal scaling) and HW9 (Kafka pipeline) became the load-bearing prerequisites for the final project | hw9 repo, 47 commits, 12 distinct days |
| **1. Pipeline foundation (HW9)** | Mar 24 – Mar 31 | Stand up gateway + producer + consumer + AI-service over Kafka; Docker Compose; end-to-end test | Done — five-stage pipeline working locally; presentation + product-vision documented | hw9 commits Mar 24, 31 |
| **2. Experiments + AWS port** | Mar 31 – Apr 14 | Resilience modes; load-test harness; replicate on ECS Fargate; Exp 1–4 | Done — JSON for Exp 1, 2, 3 (local + AWS) and Exp 4 fault-tolerance; CloudWatch + ALB + RDS + ElastiCache provisioned via Terraform | hw9 commits Mar 31, Apr 7, Apr 14 |
| **3. Productisation (Choopoo)** | Apr 16 – Apr 17 | Refactor monolithic backend into 3-repo Choopoo org; add 4 new services (copilot, forecaster, event-extractor, workflow); build production frontend; bilingual; transactional outbox; saga orchestration; aspect/signal anti-hallucination layer | Done — 31 commits across 3 repos in 2 days, executed as Steps 1–10b plus IA simplification + bilingual rollout | choopoo-backend (13 commits), choopoo-frontend (11 commits), choopoo-infra (7 commits) |
| **4. Deck + video + report** | Apr 18 – Apr 21 | Presentation document; experiments PDF; demo video; lessons learned; Piazza community post | In progress | This file + PRESENTATION.md + EXPERIMENTS_REPORT.pdf |

---

## Activity timeline (calendar view)

Each row is one real commit day. Compressed for readability — full per-commit list in §"Per-repo commit history" below.

```
2026
─── Jan ────────────────────────────────────────────────────────────
17  hw9  · HW1a starter + course README
18  hw9  · HW1b
25  hw9  · HW2 (5 commits — iterating on the multi-server design)
26  hw9  · HW2 polish + HW1 executables + arch flip to amd64

─── Feb ────────────────────────────────────────────────────────────
01  hw9  · HW3 scaffolding (creating distributed modules)
02  hw9  · HW3 updates
09  hw9  · Distributed-modules iteration (2 commits)
19  hw9  · Restructured Product API into industrial-level Go layout (4 commits)
22  hw9  · HW6 (horizontal scaling experiments) ships — 4 commits including a revert+reapply cycle
24  hw9  · HW6 finalization, README-as-presentation, CloudWatch screenshots (9 commits)

─── Mar ────────────────────────────────────────────────────────────
02  hw9  · HW7 Hummingbird API debug
17  hw9  · HW7 flash-sale sync/async order processing
24  hw9  · HW8 (shopping cart MySQL vs DynamoDB) — 6 commits iterating implementation insights
31  hw9  · **HW9 ships — distributed data processing pipeline with scaling + resilience experiments**
         8 commits same day: pipeline stood up, product-vision section added, presentation iterations,
         pilot-customer details (Guotu), AWS section trimming

─── Apr ────────────────────────────────────────────────────────────
07  hw9  · HW10 distributed KV store + load-test report (7 commits — embedding figures, refining results)
14  hw9  · ChaosArena album-store service (Go + Postgres + S3 + Terraform)

16  CHOOPOO (Day 1) — full productisation
    backend  · Initial migration from hw9 → Steps 1–10b (12 commits)
               · Step 1 auth + multi-tenancy plumbing
               · Step 2 catalog/tenant schema (20 materials, 10 products, 30 indicators)
               · Step 3 goals + polymorphic indicator links
               · Step 4 insights with traceable evidence
               · Step 5 copilot service + 6-tool loop, service-secret auth
               · Step 6 formula_json composer + indicator value resolver
               · Step 7 split ai-service into summariser + forecaster + event-extractor
               · Step 9 Goal-to-Data autopilot saga with transactional outbox
               · Step 10 aspect-based signal discovery (auditable induction chains)
               · Step 10b live LLM aspect-scout via copilot tool
    frontend · Dashboard → v2 (auth, Home, Goals, Materials, Copilot, InsightDetail)
               · Live autopilot saga strip on Goal detail
               · Warm-dark redesign ("trading desk for PU SMEs")
               · Tokenized design system + a11y
               · IA collapse to 2 tabs + ⌘K command palette + avatar menu
               · Step 8 /products + /macro lenses
               · Signal Map component + /materials/:code drill
    infra    · Initial docker-compose + terraform
               · Cold-boot determinism
               · Gateway env surfaced for migrations + CORS + test endpoints
               · Copilot, workflow, forecaster, event-extractor services + topics

17  CHOOPOO (Day 2) — bilingual rollout
    backend  · i18n: bilingual catalog + users.locale + copilot soft locale match
    frontend · i18n: bilingual catalog content + react-i18next architecture
               · i18n: stop leaking engineering codes through user-facing surfaces

18-20 Deck + experiments report + presentation drafting
21    Today — final assembly + recording + Canvas upload
```

---

## How the problem was broken down

Solo, so no inter-person ownership table — but the problem itself was decomposed along five axes that map cleanly onto the architecture you see today:

| Axis | Decomposition |
|---|---|
| **Concurrency boundary** | Gateway = HTTP fan-in (Go goroutines); Producer = HTTP fan-out (Go); Consumer = I/O-bound (Python); Summariser = API-bound (Python). Language picked per bottleneck profile. |
| **Communication boundary** | Async (Kafka) between every ingest stage; sync (HTTP) only at the user-facing seam (Browser → Gateway → Copilot). |
| **State boundary** | Postgres for authoritative state + RLS multi-tenancy; Redis for dedup-cache only; Kafka for at-least-once delivery between stages. |
| **Failure boundary** | Each service owns its own crash recovery; Kafka decoupling means single-service failure cannot propagate to the user (Experiment 4 proves this with zero gateway errors across all kills). |
| **Tenant boundary** | Postgres RLS enforces isolation at the database level — onboarding customer #2 is one row in `orgs`, not a code change. |

---

## Problems hit (real, not retrofitted)

These are the surprises that consumed real wall-clock time. Each is documented in commits or in `choopoo-frontend/docs/decisions.md`.

1. **Kafka partition default capped scaling at 1.** `KAFKA_NUM_PARTITIONS=1` silently capped consumer-group parallelism regardless of replicas. Discovered while running Experiment 1; fixed via `docker-compose.experiment.yml` overlay with 10 partitions and a `kafka-init` job. Without this fix, every scaling experiment would have produced a flat line for the wrong reason.
2. **AWS vs local divergence.** Local Docker overstates throughput (no ALB, no cross-AZ). Both result sets are kept in the experiments report so this is visible, not hidden.
3. **Recovery measurement is heuristic.** Experiment 4 uses gateway-CPU return-to-baseline as a recovery proxy. The honest metric (Kafka offset / consumer lag) requires instrumentation that was not built — called out as a limitation in the report.
4. **Engineering codes leaked into the UI.** `IMPORT_PARITY_TDI` rendered as primary label for a Chinese SME persona — *product correctness bug, not polish*. Triggered the bilingual rollout: 4 schema migrations adding `name_cn` columns + 28 frontend files refactored to `react-i18next`. Documented at `choopoo-frontend/docs/decisions.md` 2026-04-17.
5. **CSS layer cascade bug.** The `CHOOPOO` wordmark rendered grey instead of brand-amber because `.label-meta` was unlayered while Tailwind's `.text-brand-500` sits in `@layer utilities`. Fixed by wrapping role classes in `@layer components`. Documented at `choopoo-frontend/docs/decisions.md` 2026-04-17.

---

## AI usage breakdown (honest)

| Task | AI contribution | My contribution |
|---|---|---|
| Service boilerplate | High — Kafka consumer templates, Docker configs | Review, integrate, debug |
| Terraform modules | Medium — base templates | Architecture decisions, networking |
| Experiment scripts | Medium — load-test skeleton | Design, parameter tuning, analysis |
| Results interpretation | None | All analysis and conclusions are mine |
| Architecture decisions | None | Kafka partitioning, resilience strategy selection, scaling topology, IA simplification, bilingual rollout |
| Frontend components | High — initial component scaffolds | Design system, token taxonomy, contrast lint harness, decision log |

---

## Per-repo commit history

### `hw9` — coursework + final-project foundation (47 commits, Jan 17 – Apr 14)

```
2026-01-17  a0ffd4e  add hw1a
2026-01-17  079f6cb  Add author and course information to README
2026-01-18  5146de7  add hw1b
2026-01-25  c6a7d15  add hw2
2026-01-25  1013b64  add hw2
2026-01-25  1292542  add hw2
2026-01-25  73a2233  add hw2
2026-01-25  23e2709  add hw2
2026-01-26  14304c5  add hw2
2026-01-26  38d0e72  add hw1 executables
2026-01-26  a5c8147  change main arch tech to amd
2026-02-01  6273f1e  creating hw3
2026-02-02  74060de  updating hw3
2026-02-09  f19f0e4  updating distributed modules
2026-02-09  dc05c9d  updating distributed modules
2026-02-19  58fd87b  Update .gitignore and add hw3-hw5 content
2026-02-19  a0750b7  Add *.pdf to .gitignore and untrack PDF files
2026-02-19  8f7a2dd  Restructure Product API into industrial-level Go project layout
2026-02-19  1b26fa0  Update README.md to reflect restructured Go project layout
2026-02-22  1f60eef  Add HW6: product search API, Terraform, load testing, horizontal scaling
2026-02-22  7ff9113  Revert "Add HW6..."
2026-02-22  a6b2f1a  Reapply "Add HW6..."
2026-02-22  a25689a  hw6: Use README as presentation, keep other markdown files local-only
2026-02-24  58c3774  push hw6.md
2026-02-24  dadb730  keep hw6/.gitignore local
2026-02-24  a768277  Revise table headers and add CloudWatch logs image
2026-02-24  412bc25  Update hw6 and screenshots
2026-02-24  c02d511  Merge origin/master, resolve hw6.md conflict
2026-02-24  955118a  Update hw6.md
2026-02-24  c23842a  Update hw6.md
2026-02-24  e85fc52  Refine bottleneck summary in hw6.md
2026-02-24  f15f852  upload hw6.md
2026-03-02  8c9293b  hw7: Hummingbird API debug assignment
2026-03-17  66cf21c  hw7: Flash sale sync/async order processing submission
2026-03-17  ac709eb  Remove metadata from HW7 markdown file
2026-03-24  0f50dc6  hw8: Shopping cart API with MySQL vs DynamoDB comparison
2026-03-24  f05aa5c  Update author name and remove progress log
2026-03-24  5d98730  Remove duplicate cleanup instructions
2026-03-24  d56afc9  Update hw8.md with implementation insights
2026-03-24  ab5e4d0  Update practical implication for shopping cart use case
2026-03-24  a0e8d57  Clean up hw8.md by removing redundant sections
2026-03-31  ee7ad9f  hw9: Distributed data processing pipeline with scaling and resilience experiments
2026-03-31  1a231db  Merge branch 'master'
2026-03-31  5885cc6  Remove Docker Compose architecture diagram
2026-03-31  8302ddb  hw9: Add product vision section and remove Cursor references from docs
2026-03-31  bdf1270  Merge branch 'master'
2026-03-31  7aad4b9  Update presentation.md
2026-03-31  cbb198f  Revise pilot customer details in presentation.md
2026-03-31  ea6ecfa  Update presentation.md
2026-03-31  baa0f67  Remove AWS deployment section from presentation
2026-03-31  7902ea7  Update presentation.md
2026-04-07  af32743  Add HW10 distributed KV store, load-test results, and presentation assets
2026-04-07  d2d8b2b  hw10: embed load-test results in presentation; add script
2026-04-07  36cd500  hw10: replace report with report.md, real results and conclusions
2026-04-07  8256121  Update HW10 report by removing personal details
2026-04-07  0c8b2f4  hw10: embed result figures and summary table image in report
2026-04-07  17cde26  Remove latency and stale percentage data table
2026-04-07  7438f78  Refine description of active key window in report
2026-04-14  3b580c3  Add ChaosArena album store service (Go, Postgres, S3, Terraform)
```

### `choopoo-backend` — productised backend (13 commits, Apr 16 – Apr 17)

```
2026-04-16  a67d6a3  Initial migration from CS-6650 hw9 project
2026-04-16  15c50a9  gateway: remove embedded-frontend file server
2026-04-16  d6c3577  Step 1: auth + multi-tenancy plumbing
2026-04-16  ef8ad47  Step 2: catalog/tenant schema + 20 materials, 10 products, 30 indicators
2026-04-16  c1abd35  Step 3: goals + polymorphic indicator links
2026-04-16  6cf28c7  Step 4: insights with polymorphic traceable evidence
2026-04-16  6695a79  Step 5: copilot service + 6-tool loop, service-secret auth path
2026-04-16  39f8ba6  Step 6: formula_json composer + indicator value resolver
2026-04-16  041cabf  Step 9: Goal-to-Data autopilot saga with transactional outbox
2026-04-16  2fb3eea  Step 7: split ai-service into summariser + forecaster + event-extractor
2026-04-16  80f5023  Step 10: aspect-based signal discovery with auditable induction chains
2026-04-16  d8ba743  Step 10b: live LLM aspect-scout via copilot tool + propose endpoint
2026-04-17  c256199  i18n: bilingual catalog + users.locale + copilot soft locale match
```

### `choopoo-frontend` — productised UI (11 commits, Apr 16 – Apr 17)

```
2026-04-16  7ce63b0  Initial frontend: dashboard, sources, detail, status pages
2026-04-16  7bf6fff  fix: match PipelineStatus type to actual gateway response
2026-04-16  9d096cb  Frontend v2: auth + Home + Goals + Materials + Copilot + InsightDetail
2026-04-16  97d78a3  Goal detail: live autopilot saga strip
2026-04-16  ebe7afe  Redesign: warm-dark 'trading desk for PU SMEs'
2026-04-16  aeb3b6a  a11y + tokenized design system
2026-04-16  afb6398  IA: collapse nav to 2 tabs + ⌘K command palette + avatar menu
2026-04-16  4b89c15  Step 8: /products + /macro lenses
2026-04-16  c11e6d1  frontend: Signal Map component + /materials/:code drill
2026-04-17  4d0cf39  i18n: bilingual catalog content + react-i18next architecture
2026-04-17  6602b36  i18n: stop leaking engineering codes through user-facing surfaces
```

### `choopoo-infra` — productised infra (7 commits, Apr 16)

```
2026-04-16  0e64250  Initial infra: docker-compose.local.yml + terraform
2026-04-16  e58a026  compose: make cold boot deterministic, no manual restart needed
2026-04-16  29de0e6  compose: surface gateway env for migrations + auth (CORS, test endpoints, public host)
2026-04-16  d09ee07  compose: add copilot service + SERVICE_SECRET env
2026-04-16  27e2ad2  compose: add workflow service + goal.created.v1 + autopilot.step.v1 topics
2026-04-16  0856ced  compose: ai-service → summariser; add forecaster + event-extractor services
2026-04-16  6fa7d9f  gitignore: .env and .env.* (local-dev secrets, never commit)
```

---

## How to verify

1. Clone any of the four repos and run `git log --pretty=format:"%ad|%h|%s" --date=short --reverse`. The output will match the per-repo lists above byte-for-byte.
2. The corresponding GitHub contribution graph (account `kdesignhill`, where the Choopoo org lives, plus `kdesign` for hw9) will show the same green-square pattern across Jan–Apr 2026.
3. Every commit hash above is a permalink — click through on GitHub to see the diff.
