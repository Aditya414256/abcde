# Reliability repair verification

The audit's API, checkout, pharmacy setup, review, migration and CI failures are
fixed on `fix/complete-user-flows-20261116` (PR #3).

Verification before release:
- Combined local API suite: 98 passed, 1 skipped, 4 remote-storage tests excluded.
- Fresh and adopted SQLite schemas upgrade successfully; adopted user data survives.
- GitHub Actions PostgreSQL concurrency job passed on the repair branch.
- Browser tests passed for store-name escaping, pharmacy setup, first inventory,
  document upload/admin verification, delivery draft refresh, lost-response recovery,
  prescription approval and completed delivery. Screenshots inspected.
- Additional pickup refresh/new-order regression added for final CI verification.

Production database data is not migrated or seeded by this repair. Source schema
changes repair new database initialization and do not add new model columns.
Production smoke tests run after deployment success and require the expected SHA.
