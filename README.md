# LedgerLane — Expense Intelligence

**A configurable, human-first receipt coding and review platform for field-service teams.**

[**Open the interactive website**](https://xiaochen-uchicago.github.io/kinzie-receipt-coding/)

## Overview

LedgerLane is a Python/FastAPI **private-beta prototype** that checks line-item receipts against a company's explicitly configured jobs, card owners, vendor aliases, cost codes and approval thresholds.

The public website is a portfolio-style **product preview and local CSV explorer**. It does not connect to the backend or collect customer data. The backend provides its own review workspace at `/` when run locally.

## Product functionality

- Workspace-specific policies and isolated API credentials.
- CSV import with itemized receipt grouping and validation.
- Deterministic decisions: `coded`, `needs_review`, `sent_back`.
- Review inbox with supporting evidence and recorded reviewer notes.
- Explicit correction/re-evaluation with revision history.
- Workspace audit history and safe CSV export.
- No automatic accounting, messaging or payments.

## Explore the source

- [Configurable decision engine](commercial/engine.py)
- [FastAPI backend](commercial/app.py)
- [Review workspace interface](commercial/static/index.html)
- [Backend test suite](commercial/tests/test_engine.py)
- [Security & pilot limitations](commercial/SECURITY.md)
- [Mock receipt input example](commercial/example_receipts.csv)
- [Deployment example](render.yaml)

## Run locally

Requires Python 3.11+.

```bash
python -m pip install -r commercial/requirements.txt
export KINZIE_API_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(40))')"
export KINZIE_DB="./local-receipts.sqlite3"
uvicorn commercial.app:APP --host 127.0.0.1 --port 8000
```

Visit http://127.0.0.1:8000 or, in development, http://127.0.0.1:8000/docs. Create a workspace with `POST /api/workspaces` using the administrator key. The response provides a separate one-time workspace key, which is required in the review workspace UI. **Never enter the administrator key into that UI.**

```bash
python -m pytest commercial/tests/ -q
```

## Origin: Kinzie coursework

LedgerLane evolved from the University of Chicago AI Agent Management team's **fictional Kinzie Field Services** case. The original course-specific engine passed 30/30 Door 3 verdict checks and was subsequently tested on a 60-receipt fictional day-one log.

The new generic product is **separate from** that course-specific ruleset; those historical scores are not production accuracy claims. Local product development ran 36/36 tests on the complete development checkout. GitHub Actions independently tests the files presently checked into this repository.

## Current deployment status

- **GitHub Pages**: public product overview and fictional CSV review demonstration, live.
- **FastAPI backend**: source checked in and runnable locally, but **not yet deployed as a secure multi-tenant service**.
- **Real customer use**: not approved. SQLite, shared workspace API keys, and development deployment settings are insufficient for storing real financial records.

A cloud pilot needs managed storage and backups, user-level identity with MFA, granular access control, encryption, retention rules, rate limits, security testing and a supervised customer validation process. Refer to [SECURITY.md](commercial/SECURITY.md).

*LedgerLane is a provisional product name; no trademark or regulatory clearance has been performed.*
