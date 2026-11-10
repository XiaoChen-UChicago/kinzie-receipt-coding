# LedgerLane private-beta backend

This folder is reserved for the new configurable receipt-review product, developed separately from the Kinzie PRD v3 course engine.

**Current status:** Backend source and runnable Docker configuration have been prepared and tested locally, but are **not yet committed to this public repository**. The full source is supplied as `ledgerlane-github-source.zip` in the ChatGPT project delivery. Upload the extracted `commercial/` and root deployment files to this repository before attempting to deploy the private API.

## Capabilities of the tested local v0.2 build
- Workspace-specific item-to-code mapping, job allowlists, vendor aliases, card-to-technician validation and approval thresholds
- FastAPI + SQLite pilot storage; workspaces have separate randomly generated API keys
- CSV receipt import, verified job/cost-code classification, a manual-review dashboard, reviewer notes, audit events and CSV export
- Exactly three generic statuses: `coded`, `needs_review`, and `sent_back`
- No guessing uncertain job numbers, no outbound accounting writes, no direct texting
- 33/33 passing automated tests including 18 immutable Kinzie regressions

## Run locally (after uploading source)
```bash
python -m pip install -r commercial/requirements.txt
export KINZIE_API_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(40))')"
uvicorn commercial.app:APP --reload
```
Visit http://localhost:8000. Use the New workspace setup panel or the administrator API.

**Security:** This is a trusted-pilot prototype, not certified production software. The full build contains `commercial/SECURITY.md` outlining required SSO/RBAC, backup, retention, security audit and database changes prior to processing real client data. GitHub Pages hosts a public static showcase, **not** the private receipt backend.
