# Piazza "Final Projects" post — Choopoo TDI Price Intelligence Platform

**Status: DRAFT.** Wait for at least 2–3 classmate Final-Project posts to land before posting so the §"Three most-similar projects" section has real targets. Replace the `TODO:` placeholders with the actual classmates' post titles + authors + 1–2 sentences each.

> Posting category on Piazza: **Final Projects**
> Tag: **community-contribution**

---

## Subject line

`[Final Project] Choopoo — bilingual TDI price-intelligence trading desk on a distributed pipeline (8 services, 4 experiments, ECS Fargate)`

---

## Body

Hi all — solo final project. Choopoo is a bilingual trading desk for Chinese polyurethane SME owners, built on top of a horizontally-scalable, fault-tolerant distributed pipeline. The course experiments measure whether the backend is what makes the daily-use product feasible at SME scale.

**🎥 Video** — *[insert YouTube/Loom unlisted link after upload]*

**📄 Experiments report (5-page PDF)** — *[insert link to EXPERIMENTS_REPORT.pdf in the choopoo-backend repo]*

**💻 Code**
- Backend (8 services, Go + Python): https://github.com/Choopoo/choopoo-backend
- Frontend (React 19 + Vite + Tailwind v4 + react-i18next): https://github.com/Choopoo/choopoo-frontend
- Infra (Docker Compose + Terraform for ECS Fargate): https://github.com/Choopoo/choopoo-infra
- Coursework + final-project foundation history (HW1–HW10): https://github.com/kdeisgn/NU-Distributed-System-Design-CS6650-2025Fall (`hw9/` and earlier)

**📐 Architecture in one paragraph.** Three planes — Ingest (producer → consumer → summariser, all async via Kafka), Enrich (event-extractor + forecaster + workflow saga), Serve (gateway + copilot, sync HTTP behind ALB). Five Kafka topics (`crawl-jobs`, `page-metadata`, `analysis-results`, `goal.created.v1`, `autopilot.step.v1`). Transactional outbox at the gateway means goal-creation is atomic from the user's perspective even though the saga runs for minutes. Postgres row-level security makes onboarding the next SME tenant a one-row insert, not a code change.

**🧪 Four experiments.**
1. **Producer horizontal scaling** — flat at AWS 47 rps regardless of replica count → gateway is the real ceiling, not producer count. Useful negative result that saves money.
2. **Consumer scaling + bottleneck migration** — near-linear 23 → 96 → 213 rps as concurrency × consumer-count grows together; p95 stays bounded.
3. **Resilience pattern comparison** — backoff vs. backpressure vs. circuit breaker under 30 % AI-API failure. All three absorb failure with zero gateway errors; CB has highest p95/p99 (half-open probe cost).
4. **Fault tolerance & recovery** — `docker kill` producer/consumer/redis under sustained load. Zero gateway errors across all kills; recovery 6 s (Redis) → 11 s (producer) → 31 s (consumer, due to Kafka group rebalance).

**🔑 Key takeaways.** (a) The right scaling knob is the consumer tier, not the producer tier. (b) Kafka decoupling pays for itself: every fault test posts zero gateway errors. (c) Resilience patterns are not interchangeable — pick by failure profile. (d) Local Docker results lie in predictable directions; always re-run on the target environment.

---

## Three most-similar Final Projects

**1. [TODO: classmate post title + author]**
- *Similarities:* TODO — e.g., "also event-driven with a broker between stages"
- *Differences:* TODO — e.g., "uses SQS instead of Kafka, so partition-based parallelism is replaced by visibility-timeout-based delivery semantics"
- *What I learned from it:* TODO — one specific thing you'd borrow

**2. [TODO: classmate post title + author]**
- *Similarities:* TODO
- *Differences:* TODO
- *What I learned from it:* TODO

**3. [TODO: classmate post title + author]**
- *Similarities:* TODO
- *Differences:* TODO
- *What I learned from it:* TODO

---

## Footer

Thanks to Prof. Ian Gorton + the TAs for a course that genuinely changed how I think about systems. Happy to chat — comments here or DM works.

— Kaige Zheng (kaigezhengzz@gmail.com)
