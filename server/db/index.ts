import 'dotenv/config';
import { drizzle } from 'drizzle-orm/postgres-js';
import postgres from 'postgres';
import * as schema from './schema.js';

const client = postgres(process.env.DATABASE_URL!);

// In drizzle-orm RC4, passing a pre-existing client with schema requires the
// single-object form: drizzle({ client, schema }). The two-argument overload
// no longer accepts schema in its second param's type. The `as any` is needed
// to bypass the overload union narrowing bug in this RC's .d.ts file — the
// runtime behavior is correct per the driver source.
export const db = (drizzle as any)({ client, schema });