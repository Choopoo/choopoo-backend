# Lessons Learned — CS-6650 Final Project (Choopoo)

**Kaige Zheng · Solo submission · 2026-04-21**

---

## What I built and owned

I built **Choopoo**, a bilingual TDI price-intelligence trading desk for Chinese polyurethane SME owners, on top of an 8-service distributed pipeline. End-to-end ownership: gateway, producer, consumer, summariser, copilot, forecaster, event-extractor, workflow saga; React 19 + Tailwind v4 frontend with 12 pages and 14 components; Terraform-provisioned ECS Fargate / RDS / ElastiCache / ALB topology in us-west-2; docker-compose local stack; load-test harness; four scaling/resilience experiments with local + AWS result sets.

The work spanned three real months: Jan–Mar inside the `hw9` repo (course assignments → final-project foundation), then a two-day productisation in mid-April refactoring the monolithic backend into the three-repo `Choopoo` org with four newly-split services (copilot, forecaster, event-extractor, workflow), the full bilingual rollout, and the saga-orchestrated autopilot.

---

## What went wrong, and why

### 1. The Kafka partition default silently capped my scaling experiments

**What happened.** Experiment 1 (producer horizontal scaling) initially produced a perfectly flat throughput curve regardless of replica count. I assumed gateway was the bottleneck and almost wrote that as my conclusion.

**Root cause.** `KAFKA_NUM_PARTITIONS=1` (the Confluent image default). A consumer group cannot have more active consumers than partitions, so adding replicas just left the new ones idle. My "negative result" wasn't telling me anything about the gateway — it was telling me my topic geometry was wrong.

**Why it matters as a course lesson.** This is a textbook misuse of Kafka's partition model. The course material on consumer groups warned about this exact failure mode. I read it, internalised it, and *still* missed it because the default behaviour silently passed all my health checks.

**How I'd handle it next time.** Pre-create topics with explicit partition counts in CI before any experiment runs. Add a startup assertion that fails loud if any topic has fewer partitions than `expected_max_consumers`. Treat the default as a code smell, not a starting point.

### 2. I deferred Kafka offset / consumer-lag instrumentation, and Experiment 4 paid for it

**What happened.** Experiment 4 (fault tolerance) measures recovery time as "gateway-CPU returns to pre-kill baseline" — a proxy, not the honest metric. The honest metric is "Kafka consumer lag returns to ~zero."

**Why I cut it.** Adding offset instrumentation felt like infrastructure work that wasn't on the critical path. By the time I was running fault-tolerance experiments I was already past the point where adding it would have been cheap.

**The hidden cost.** Every recovery number in the Experiment 4 table now needs an asterisk in the report — and any defensive question from the grader about the methodology is one I have to concede on. A small upfront investment in observability would have made the entire experiment series defensible without caveats.

**Course-concept callback.** This is exactly the failure-detector latency story from the lectures: you cannot reason about recovery time without a failure-detection signal that is independent of the failing service. Gateway CPU is a side-channel; offset lag is the actual signal.

### 3. Bilingual rollout came too late

**What happened.** The actual end user is a Chinese SME owner. For two days of frontend development, engineering codes like `IMPORT_PARITY_TDI` rendered as primary labels in the UI. By the time I noticed (during a self-review against the product persona), 28 frontend files had hardcoded English JSX strings and four catalog tables had no `name_cn` columns.

**Cost.** Four migrations (0014/0015 add `name_cn` / `description_cn` to `catalog_indicator_template`, `catalog_signal_aspect`, `sources`, plus `users.locale`), full `react-i18next` migration with nine namespaces, two cross-cutting hooks (`useLocalizedField`, `useEnumLabel`). Roughly half a day of refactoring that could have been zero days if i18n had been a day-1 architecture decision.

**The lesson.** "Localisation is a polish step" is wrong when the persona is non-English. It's a schema-layer correctness requirement. Decide the persona before you write the first line of UI code.

### 4. CSS layer cascade bug consumed an hour I didn't have

**What happened.** The `CHOOPOO` wordmark in the nav rendered grey instead of brand-amber. `className="label-meta text-brand-500"` — both classes existed, both were correct. The contrast lint passed. I spent an hour assuming Tailwind purge was eating the brand class.

**Root cause.** `.label-meta { color: var(--color-ink-500); }` was defined *outside* any `@layer`. Unlayered CSS beats all layered CSS in the cascade — including Tailwind's `@layer utilities`. So `.text-brand-500` (utility) lost to `.label-meta` (unlayered) silently.

**The lesson.** Frameworks that rely on layer ordering (Tailwind v4) are unforgiving when you bypass their layer model. Wrapping the role classes in `@layer components` fixed it permanently and gave me a new lint rule. Documented at `choopoo-frontend/docs/decisions.md` 2026-04-17.

### 5. I overestimated how much bandwidth two days of productisation would buy

**What happened.** I planned to refactor the hw9 monolith into the Choopoo org *and* add four new services *and* build a polished frontend in two calendar days (Apr 16–17). The 31-commit burst landed, but it left no slack for the deck, video, or experiments report — those are now compressed into the 18–21 window.

**Why it almost worked.** AI-assisted scaffolding (component shells, Kafka boilerplate, Terraform modules) collapsed what would have been a week of typing into a day. The architecture decisions, integration debugging, and polish were still mine.

**The lesson.** AI velocity changes the *typing* timeline but not the *thinking* timeline. Plan for the integration tax: every new service is one more thing that has to start cleanly in the docker-compose `up` sequence, one more `depends_on` to get right, one more health-check to wire up. Two days for nine new services is the right-shape estimate; two days for nine services *and* a deliverable artifact is not.

---

## What I would do differently

1. **Decide the persona on day 1.** If it's a Chinese SME owner, every schema migration includes `_cn` columns from the start. Saves a half-day of retrofits.
2. **Build observability before experiments.** Kafka offset lag, structured request logs with correlation IDs, and per-service request rate before any load-test runs. The marginal day spent on observability buys you defensible results forever.
3. **Pre-create Kafka topics with the right partition count.** Never let a Confluent default pick your scaling ceiling.
4. **Treat productisation as its own phase, not a closing sprint.** Refactoring the monolith into a multi-repo org with new services should have its own week, not its own weekend.
5. **Write the experiments report as the experiments run, not after.** Every JSON file should have a paragraph of analysis committed alongside it. Trying to reconstruct "what was I testing here" three weeks later is a tax.

---

## Course concepts that showed up in the work

The four experiments map onto specific concepts from the course material — making this section concrete rather than gestural.

| Course concept | Where it showed up in the project |
|---|---|
| **Universal Scalability Law** (Gunther) | Experiment 1's plateau. Adding 5× more producers gave 2 % more throughput because the σ-coherence cost of more parallel publishers was outweighed by the constant α-contention at the gateway accept path. The classic "negative result" shape predicted by USL. |
| **CAP / PACELC** | The architecture deliberately picks AP at the gateway (Kafka decoupling — accept always, eventually consistent downstream) and CP at the consumer-side store (Postgres write-after-read). The frontend `SagaTimeline` polling is a concrete example of "eventual consistency made visible to the user as progress." |
| **Failure detectors and recovery time** | Experiment 4's per-service recovery (Redis 6 s, Producer 11 s, Consumer 31 s) is a measured failure-detector latency story. The slowest case is consumer because it triggers a Kafka group rebalance — a coordination protocol whose latency is the real cost of the partition-based parallelism we get from Kafka. |
| **Queueing theory (M/M/c)** | Experiment 2's bounded p95 under proportional scaling is exactly what M/M/c predicts when you grow arrival rate and service rate together. The moment you stop scaling consumers, the textbook latency cliff shows up — visible at p99 in step 3 (50 conc / 5 consumers), where the tail starts widening. |
| **Transactional outbox + at-least-once delivery** | Used end-to-end for goal-creation. The gateway writes the `goals` row and the `domain_events` row in the same transaction; the in-process relay drains to Kafka and marks `published_at` only after broker ACK. This is the pattern that lets the user see "click → 201 created" instantly while the multi-minute saga runs in the background. |
| **Saga orchestration** | The `workflow` service consumes `goal.created.v1` and runs a multi-step saga whose state lives in `workflow_runs.steps_log` (append-only JSONB). The `SagaTimeline` UI polls this every 1.5 s. The append-only design is the anti-hallucination guarantee for the SME owner: every step the AI took on their behalf is auditable. |
| **Row-level security as a multi-tenancy primitive** | Postgres RLS gated by `current_setting('app.org_id')` is the cheapest practical way to do multi-tenant isolation. The application code can have bugs and tenant data still cannot leak — the database is the source of isolation, not the gateway. |

---

## Closing reflection

The grade-bearing artifact of this course is the four experiments and the report around them. The lasting artifact for me is the architecture — eight services, five Kafka topics, transactional outbox, append-only saga, RLS multi-tenancy, bilingual at the schema layer — which I now believe is the right shape for the SaaS this could become. Whether or not Guotu ever buys it, I built something I'd be willing to put my name on for paying customers.

The biggest single takeaway: **distributed-systems instinct comes from running into the rough edges of the patterns, not from reading about them.** The Kafka partition default, the recovery-measurement heuristic, the layer cascade bug, the bilingual retrofit — none of these were predicted by the lecture notes. All of them are now permanent muscle memory.
