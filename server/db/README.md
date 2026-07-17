# Database

This directory contains the database schema definitions, initializations, and migration scripts.

I use Drizzle ORM configured with the Postgres driver for lightweight, type-safe database interactions.

- The database connection can be found in [index.ts](index.ts).
- To find the table schemas visit [schema.ts](schema.ts).
- To find persistent Telegram switch-attempt and ban storage visit [schema.ts](schema.ts) and [migrations](migrations/).
