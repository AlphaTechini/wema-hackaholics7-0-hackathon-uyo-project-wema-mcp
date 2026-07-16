CREATE TABLE "transactions" (
	"id" integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "transactions_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1),
	"sender_acc" integer NOT NULL,
	"receiver_acc" integer NOT NULL,
	"amount" integer NOT NULL,
	"comment" varchar(250),
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "users" (
	"acc_no" integer PRIMARY KEY,
	"first_name" varchar(20) NOT NULL,
	"last_name" varchar(20) NOT NULL,
	"email" varchar(55) NOT NULL UNIQUE,
	"pin" varchar(255) NOT NULL,
	"phone_no" integer,
	"acc_balance" integer DEFAULT 100000 NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "transactions" ADD CONSTRAINT "transactions_sender_acc_users_acc_no_fkey" FOREIGN KEY ("sender_acc") REFERENCES "users"("acc_no");--> statement-breakpoint
ALTER TABLE "transactions" ADD CONSTRAINT "transactions_receiver_acc_users_acc_no_fkey" FOREIGN KEY ("receiver_acc") REFERENCES "users"("acc_no");