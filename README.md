# LedgerLane · Receipt Intelligence

**A configurable, human-first receipt coding workflow for field-service teams.**

[**View the live portfolio demo**](https://xiaochen-uchicago.github.io/kinzie-receipt-coding/)

## The problem

Small field-service and operations teams manually translate emailed or photographed receipts into job numbers, cost categories, billable status, and accounting exports. A wrong job or code can create downstream billing problems. Our product direction is to automate **verifiable** classifications and route exceptions to a human rather than guessing.

## Two codebases, intentionally separate

**1. Original academic engine — Kinzie PRD v3.** A fictional University of Chicago case study, with 12 explicit decision rules, 30 reference cases and a 60-receipt day-one log. The original engine and immutable golden files are preserved.

**2. LedgerLane private-beta engine (v0.2).** A new configurable Python/FastAPI product prototype that supports isolated customer workspaces, validated CSV imports, company-specific item codes, verified job/card mappings, a review inbox, evidence, reviewer notes, audit history and safe CSV export. A production rollout must not treat this prototype as validated financial software.

### Product safety philosophy

- Never guess unknown jobs or cost codes.
- Match card holders and job identifiers against the company's configured reference tables.
- Check amounts with decimal-cents precision.
- Flag duplicate receipts, personal items, and over-limit expenses for review.
- Never send texts, write into accounting systems, or mark an uncertain expense as coded merely because it was reviewed.

## What works today

The public site is a **static interactive case-study dashboard and CSV-output explorer**. It does not ingest private customer receipts on a server. The new private-beta backend is built locally and packaged separately pending a secure deployment and a full source-code push.

The project test suite currently passes **33/33** local regression and product tests. That is an engineering test result, not evidence of financial compliance, operational accuracy for real clients, or security certification.

## Open development work

- Integrate the private-beta backend source into this GitHub repository without uploading real customer information.
- Secure application hosting, managed database, secret storage, identity and access management, backup/restore.
- Real customer discovery and chart-of-accounts onboarding.
- Human correction workflow, approval routing, accounting integration and real-world pilot validation.
- Security, privacy and legal review before any customer financial data is processed.

The brand name **LedgerLane** is provisional; no trademark clearance has been performed.

University of Chicago · AI Agent Management project · fictional case study.
