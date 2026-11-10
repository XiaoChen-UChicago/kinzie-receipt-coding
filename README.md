# Kinzie Receipt Coding Agent — Interactive Web Demo

**University of Chicago · AI Agent Management · Table 6**

> This is a fictional course project. Kinzie Field Services and named employees are fictional.

A PRD v3 receipt-coding rules engine. It assigns one of three verdicts: `coded`, `ask Tom`, or `sent back`. It never submits an external form, texts a technician, or guesses an uncertain job.

## Web showcase

[Open interactive web demo](https://xiaochen-uchicago.github.io/kinzie-receipt-coding/)

The website is a **client-side showcase and CSV review tool**. It does not run the Python backend on GitHub Pages. Upload an output CSV from the Python engine to explore and filter it without submitting information to a server.

**Test findings:** 30/30 official verdicts on Door 3; rebuilt PRD v3 result 30/30 on the team's full-answer assessment. Day-one log: 60 receipts (5 coded, 52 ask Tom, 3 sent back), including 49 requiring OPEN 1 human resolution. These scores are from the project test set and are not production validation.

## Python engine and full sources

The original complete repository, including `AGENTS.md`, `docs/prd_v3.md`, `receipt_agent/`, `agent/`, `tests/`, `outputs/`, and the full interactive site, is available as a repository ZIP supplied with the project. Upload/extract the full source tree to this repository to make the code and all test artifacts browsable in GitHub.

## Deployment

Enable GitHub Pages from **Settings → Pages → Deploy from a branch → main / (root)**. The root `index.html` is the web demo. If Pages settings are disabled, enable them before the public website URL will work.

## Design and limitations

- Rules come from PRD v3 only.
- No rule may silently resolve OPEN 1–7.
- No external form submission or messaging.
- No arbitrary choice between two equally plausible job numbers.
