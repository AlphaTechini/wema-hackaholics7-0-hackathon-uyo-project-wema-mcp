import 'dotenv/config';
import { drizzle } from 'drizzle-orm/postgres-js';
import postgres from 'postgres';
import {migrate} from 'drizzle-orm/postgres-js/migrator';

const client = postgres(process.env.DATABASE_URL!, { prepare: false, max: 1 });

const db = drizzle({ client });

async function migration() {

  try {
    console.log("Schema Migration launched");
    
    await migrate(db, {migrationsFolder: './db/migrations'} ); 
  }
  catch (error) {
    console.error(error);
  }
}

migration();

