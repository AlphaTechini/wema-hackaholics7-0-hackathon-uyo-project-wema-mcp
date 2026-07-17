import argon2 from 'argon2';
import crypto from 'crypto';
import { eq } from 'drizzle-orm';
import { db } from '../db/index.js';
import { Users } from '../db/schema.js';

const MIN_ACCOUNT_NUMBER = 1_000_000_000;
const MAX_ACCOUNT_NUMBER = 2_147_483_647;
const ACCOUNT_NUMBER_RANGE = BigInt(MAX_ACCOUNT_NUMBER - MIN_ACCOUNT_NUMBER + 1);

export type CreateAccountInput = {
  first_name: string;
  last_name: string;
  email: string;
  phone_no?: number;
  pin: string;
};

export type CreatedAccount = {
  acc_no: number;
  first_name: string;
  last_name: string;
  email: string;
  phone_no: number | null;
  acc_balance: number;
  created_at: Date;
};

export class AccountAlreadyExistsError extends Error {
  readonly code = '23505';

  constructor() {
    super('Email already exists');
    this.name = 'AccountAlreadyExistsError';
  }
}

function generateInitialAccountNumber(email: string): number {
  const hash = crypto.createHash('sha256').update(email).digest('hex');
  const hashValue = BigInt(`0x${hash.substring(0, 15)}`);
  return MIN_ACCOUNT_NUMBER + Number(hashValue % ACCOUNT_NUMBER_RANGE);
}

function nextAccountNumber(accountNumber: number): number {
  return accountNumber === MAX_ACCOUNT_NUMBER
    ? MIN_ACCOUNT_NUMBER
    : accountNumber + 1;
}

function isUniqueViolation(error: unknown): boolean {
  if (typeof error !== 'object' || error === null) {
    return false;
  }

  const databaseError = error as { code?: unknown; cause?: unknown };
  return databaseError.code === '23505' || isUniqueViolation(databaseError.cause);
}

export async function createAccount(input: CreateAccountInput): Promise<CreatedAccount> {
  const hashedPin = await argon2.hash(input.pin);
  const [existingUser] = await db
    .select({ email: Users.email })
    .from(Users)
    .where(eq(Users.email, input.email))
    .limit(1);

  if (existingUser) {
    throw new AccountAlreadyExistsError();
  }

  let accountNumber = generateInitialAccountNumber(input.email);

  for (let attempt = 0; attempt < Number(ACCOUNT_NUMBER_RANGE); attempt += 1) {
    try {
      const [newUser] = await db.insert(Users).values({
        acc_no: accountNumber,
        first_name: input.first_name,
        last_name: input.last_name,
        email: input.email,
        phone_no: input.phone_no,
        pin: hashedPin,
      }).returning({
        acc_no: Users.acc_no,
        first_name: Users.first_name,
        last_name: Users.last_name,
        email: Users.email,
        phone_no: Users.phone_no,
        acc_balance: Users.acc_balance,
        created_at: Users.created_at,
      });

      return newUser;
    } catch (error) {
      if (!isUniqueViolation(error)) {
        throw error;
      }

      const [emailOwner] = await db
        .select({ email: Users.email })
        .from(Users)
        .where(eq(Users.email, input.email))
        .limit(1);

      if (emailOwner) {
        throw new AccountAlreadyExistsError();
      }

      accountNumber = nextAccountNumber(accountNumber);
    }
  }

  throw new Error('No available account numbers remain');
}
