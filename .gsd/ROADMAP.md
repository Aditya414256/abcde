# Reliability repair plan

1. Validate API payloads and preserve omitted profile fields; expose pharmacy setup.
2. Connect pharmacy/admin controls and remove unsafe store event interpolation.
3. Persist delivery drafts and reuse retry keys, including uploaded prescriptions.
4. Repair migrations and run deployment checks after successful deployments.
5. Run regression and browser flows, commit, publish, and verify production.
