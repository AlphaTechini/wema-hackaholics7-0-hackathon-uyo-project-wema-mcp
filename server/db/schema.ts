import { relations } from "drizzle-orm/_relations";
import { pgTable, varchar, integer, timestamp } from "drizzle-orm/pg-core";

export const Users = pgTable('users', {
  acc_no: integer().primaryKey(),
  first_name: varchar({ length: 20 }).notNull(),
  last_name: varchar({ length: 20 }).notNull(),
  email: varchar({ length: 55 }).notNull().unique(),
  pin: varchar({ length: 255 }).notNull(),
  phone_no: integer(),
  acc_balance: integer().notNull().default(100000),
  created_at: timestamp({ mode: 'date' }).defaultNow().notNull(),
  updated_at: timestamp({ mode: 'date' }).defaultNow().$onUpdate(() => new Date()).notNull(),
});

export const TelegramSecurity = pgTable('telegram_security', {
  telegram_user_id: varchar({ length: 64 }).primaryKey(),
  failed_switch_attempts: integer().notNull().default(0),
  banned_at: timestamp({ mode: 'date' }),
  updated_at: timestamp({ mode: 'date' }).defaultNow().$onUpdate(() => new Date()).notNull(),
});

export const Transfers = pgTable('transactions', {
  id: integer().primaryKey().generatedAlwaysAsIdentity(),
  sender_acc: integer().references(() => Users.acc_no).notNull(),
  receiver_acc: integer().references(() => Users.acc_no).notNull(),
  amount: integer().notNull(),
  comment: varchar({ length: 250 }),
  created_at: timestamp({ mode: 'date' }).defaultNow().notNull(),
});

export const userRelations = relations(Users, ({ many }) => ({
  sentTransfers: many(Transfers, { relationName: 'sent' }),
  receiveTransfers: many(Transfers, { relationName: 'received' }),
}));

export const transferRelations = relations(Transfers, ({ one }) => ({
  sender: one(Users, {
    fields: [Transfers.sender_acc],
    references: [Users.acc_no],
    relationName: 'sent',
  }),
  receiver: one(Users, {
    fields: [Transfers.receiver_acc],
    references: [Users.acc_no],
    relationName: 'received',
  }),
}));
