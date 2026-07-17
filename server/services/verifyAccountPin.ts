import argon2 from 'argon2';
import { eq } from 'drizzle-orm';
import { db } from '../db/index.js';
import { TelegramSecurity, Users } from '../db/schema.js';

const MAX_FAILED_SWITCH_ATTEMPTS = 3;

export type VerifyAccountPinInput = {
  telegram_user_id: string;
  account_number: number;
  pin: string;
};

export type VerifyAccountPinResult =
  | { status: 'verified'; account_number: number; first_name: string; last_name: string }
  | { status: 'failed'; attempts_remaining: number }
  | { status: 'banned' };

export async function isTelegramUserBanned(telegramUserId: string): Promise<boolean> {
  const [security] = await db
    .select({ banned_at: TelegramSecurity.banned_at })
    .from(TelegramSecurity)
    .where(eq(TelegramSecurity.telegram_user_id, telegramUserId))
    .limit(1);

  return Boolean(security?.banned_at);
}

export async function verifyAccountPin(
  input: VerifyAccountPinInput,
): Promise<VerifyAccountPinResult> {
  const [security] = await db
    .select({
      failed_switch_attempts: TelegramSecurity.failed_switch_attempts,
      banned_at: TelegramSecurity.banned_at,
    })
    .from(TelegramSecurity)
    .where(eq(TelegramSecurity.telegram_user_id, input.telegram_user_id))
    .limit(1);

  if (security?.banned_at || (security?.failed_switch_attempts ?? 0) >= MAX_FAILED_SWITCH_ATTEMPTS) {
    return { status: 'banned' };
  }

  const [account] = await db
    .select({
      acc_no: Users.acc_no,
      first_name: Users.first_name,
      last_name: Users.last_name,
      pin: Users.pin,
    })
    .from(Users)
    .where(eq(Users.acc_no, input.account_number))
    .limit(1);

  const validPin = account ? await argon2.verify(account.pin, input.pin) : false;
  if (!validPin) {
    const failedAttempts = (security?.failed_switch_attempts ?? 0) + 1;
    const banned = failedAttempts >= MAX_FAILED_SWITCH_ATTEMPTS;

    await db.insert(TelegramSecurity).values({
      telegram_user_id: input.telegram_user_id,
      failed_switch_attempts: failedAttempts,
      banned_at: banned ? new Date() : null,
    }).onConflictDoUpdate({
      target: TelegramSecurity.telegram_user_id,
      set: {
        failed_switch_attempts: failedAttempts,
        banned_at: banned ? new Date() : null,
        updated_at: new Date(),
      },
    });

    return banned
      ? { status: 'banned' }
      : { status: 'failed', attempts_remaining: MAX_FAILED_SWITCH_ATTEMPTS - failedAttempts };
  }

  await db.insert(TelegramSecurity).values({
    telegram_user_id: input.telegram_user_id,
    failed_switch_attempts: 0,
    banned_at: null,
  }).onConflictDoUpdate({
    target: TelegramSecurity.telegram_user_id,
    set: {
      failed_switch_attempts: 0,
      banned_at: null,
      updated_at: new Date(),
    },
  });

  return {
    status: 'verified',
    account_number: account.acc_no,
    first_name: account.first_name,
    last_name: account.last_name,
  };
}
