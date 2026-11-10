# Security and responsible use

**LedgerLane is a private-beta prototype. It is not ready for real financial data or production use.**

- The app has an administrator API key and separately generated hashed workspace keys. Keys are not browser-persisted.
- Every workspace resource must be explicitly scoped by its workspace ID and matching API key.
- Review decisions are audit events and never silently override the immutable classifier outcome.
- Corrected receipts are re-evaluated explicitly with revision history.
- No SMS, email, payment, or accounting integration is enabled.
- Only mock data may be used in public previews or GitHub issues.
- Before real customer pilots: adopt managed PostgreSQL, user-level authentication and MFA, role-based authorization, key rotation, encryption/backups, rate limits, incident response, retention controls, independent penetration testing and appropriate legal/privacy review.
- Public GitHub Pages is static. Never place administrator keys or business receipt data on it.

See the commercial package and its test suite for actual implementation details.
