# Scripts

This directory contains explicit operational scripts that use the server's existing application and database layers. Seed scripts use deterministic inputs so they can be rerun without creating duplicate records.

To find the user onboarding seed logic, visit [seed-users.ts](seed-users.ts).

The database connection used by these scripts can be found in [../db/index.ts](../db/index.ts).

The account creation logic used by these scripts can be found in [../services/createAccount.ts](../services/createAccount.ts).
