# Choopoo — CS-6650 Final Project Documentation

Solo · Kaige Zheng · Spring 2026

This directory contains every artifact for the CS-6650 final-project submission. The architecture and product are real software (not a deck-only artifact); see the parent `choopoo-backend` repo for source.

## Documents

| File | What it is | Rubric deliverable |
|---|---|---|
| [PRESENTATION.md](PRESENTATION.md) | Full presentation deck — vision, architecture (8 services, 5 Kafka topics, transactional outbox, RLS multi-tenancy), features × infra × business mapping, all four experiments, demo path, Q&A | Master document |
| [EXPERIMENTS_REPORT.md](EXPERIMENTS_REPORT.md) / [.pdf](EXPERIMENTS_REPORT.pdf) | Standalone 5-page experiments report — purpose, tradeoff, setup, results, analysis, limitations per experiment | **Experiments (10 marks)** |
| [PROJECT_TIMELINE.md](PROJECT_TIMELINE.md) | Real git-history timeline across 4 repos (Jan 17 → Apr 17, 16 distinct commit days, 70 commits). Honest evidence of activity over time. | **Project Management (5 marks)** |
| [LESSONS_LEARNED.md](LESSONS_LEARNED.md) | Solo reflection — what went wrong + why + course-concept callbacks (USL, CAP/PACELC, queueing, failure detectors, transactional outbox, saga, RLS) | **Lessons Learned (separate Canvas submission)** |
| [PIAZZA_POST_DRAFT.md](PIAZZA_POST_DRAFT.md) | Draft for the Piazza Final Project post — fill in 3 most-similar classmate posts before publishing | **Community Contributions (5 marks)** |

## Asset folder

Charts and AWS console captures referenced from the documents above:

```
assets/
├── exp1-throughput-chart-aws.png       # Producer scaling (Exp 1)
├── exp2-latency-chart-aws.png          # Consumer scaling (Exp 2)
├── exp3-comparison-chart-aws.png       # Resilience modes (Exp 3)
├── exp4-recovery-chart.png             # Fault tolerance (Exp 4)
└── aws-console/
    ├── ecs-pipeline-cluster-services-kai.png
    └── alb-load-balancers-kai.png
```

Charts were generated from the raw experiment JSON in [`../experiments/`](../experiments/) via [`../scripts/generate_report_assets.py`](../scripts/generate_report_assets.py).

## Regenerating the experiments PDF

```bash
cd choopoo-backend/docs
pandoc EXPERIMENTS_REPORT.md -s -c report.css \
    --metadata title="Experiments Report — Choopoo" \
    -o _report.html
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --headless --disable-gpu --no-pdf-header-footer \
    --print-to-pdf=EXPERIMENTS_REPORT.pdf "file://$(pwd)/_report.html"
rm _report.html
```

## Repos linked from these docs

- **Backend** (this repo): https://github.com/Choopoo/choopoo-backend — 8 services (gateway, producer, consumer, summariser, copilot, forecaster, event-extractor, workflow), `experiments/`, `scripts/`
- **Frontend**: https://github.com/Choopoo/choopoo-frontend — React 19 + Vite + Tailwind v4 + react-i18next
- **Infra**: https://github.com/Choopoo/choopoo-infra — `docker-compose.local.yml` + Terraform for ECS Fargate
- **Coursework history (HW1–HW10)**: https://github.com/kdeisgn/NU-Distributed-System-Design-CS6650-2025Fall (`hw9/` is the immediate prerequisite)
