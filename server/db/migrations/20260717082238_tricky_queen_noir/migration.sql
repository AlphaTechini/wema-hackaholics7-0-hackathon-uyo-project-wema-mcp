CREATE TABLE "telegram_security" (
	"telegram_user_id" varchar(64) PRIMARY KEY,
	"failed_switch_attempts" integer DEFAULT 0 NOT NULL,
	"banned_at" timestamp,
	"updated_at" timestamp DEFAULT now() NOT NULL
);
