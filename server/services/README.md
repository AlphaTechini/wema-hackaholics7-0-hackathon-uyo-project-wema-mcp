# Services

This directory contains reusable application operations shared by HTTP controllers and non-HTTP entry points.

To find account creation, PIN hashing, and deterministic account-number logic, visit [createAccount.ts](createAccount.ts).

To find account PIN verification, failed-attempt tracking, and Telegram bans, visit [verifyAccountPin.ts](verifyAccountPin.ts).

The database connection used by the services can be found in [../db/index.ts](../db/index.ts).
