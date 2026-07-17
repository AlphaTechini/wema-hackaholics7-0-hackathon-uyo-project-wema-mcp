import { inArray } from 'drizzle-orm';
import { closeDatabase, db } from '../db/index.js';
import { Users } from '../db/schema.js';
import { createAccount } from '../services/createAccount.js';

const seedUsers = Array.from({ length: 25 }, (_, index) => {
  const number = String(index + 1).padStart(2, '0');

  return {
    first_name: `Seed${number}`,
    last_name: 'User',
    email: `seed.user.${number}@example.com`,
    phone_no: 801000000 + index,
    pin: '2468',
  };
});

async function seed(): Promise<void> {
  const seedEmails = seedUsers.map(({ email }) => email);
  const existingUsers: Array<{ email: string }> = await db
    .select({ email: Users.email })
    .from(Users)
    .where(inArray(Users.email, seedEmails));
  const existingEmails = new Set(existingUsers.map(({ email }) => email));

  let created = 0;
  let skipped = 0;

  for (const user of seedUsers) {
    if (existingEmails.has(user.email)) {
      skipped += 1;
      continue;
    }

    const account = await createAccount(user);
    created += 1;
    console.log(`Created ${account.email} with account number ${account.acc_no}`);
  }

  console.log(`Seed complete: ${created} created, ${skipped} skipped.`);
}

try {
  await seed();
} finally {
  await closeDatabase();
}
