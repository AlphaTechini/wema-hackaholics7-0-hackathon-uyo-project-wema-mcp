# ONE-SHOT BUILD PROMPT — Telegram Banking Bot
# File: prompts/tg_bot_prompt.md
# Language-agnostic. Attach tools.json when submitting this prompt.
# -------------------------------------------------------------------

You are an expert in building conversational Telegram bots with AI tool-calling
backends. Build a complete Telegram banking bot from scratch using the
specification below. The implementation language and Telegram SDK are your
choice. The hard constraints are: Telegram Bot API, inline keyboard support,
OpenAI-compatible LLM for free-text, and all security requirements in this spec.

Attach `tools.json` before submitting. The AI engine must load tool schemas
from that file at startup — do not hardcode them.

---

## What the Bot Is

An OPay/Moniepoint-style banking assistant inside Telegram backed by ALAT by
Wema Bank. It has two parallel interaction modes:

1. Button UI — structured multi-step forms triggered by inline keyboard buttons.
   Deterministic. Never involves the AI. Reads call the banking API directly;
   all debits are routed to the PIN confirmation gate before execution.

2. AI free-text — any message that does not belong to a structured form state
   is handled by an LLM with access to all tools in `tools.json` via MCP.
   Debit tool calls from the AI are intercepted before MCP dispatch and routed
   through the same PIN confirmation gate as button flows.

Both modes coexist. A user can tap a button, type a free-text follow-up, tap
another button — all in sequence within the same session.

---

## User Journey

```
/start
  └─► Welcome: "Welcome to ALAT by Wema, Hello <first_name> 👋"
        "Please enter your 4-digit PIN:"
          ├─► Wrong PIN  → "❌ Incorrect PIN. Try again."   (loop)
          ├─► Real PIN   → fetch account name from banking API
          │               → register ownership with MCP
          │               → show main menu
          └─► Distress PIN → same screen as real PIN ← silent guardian mode
                             (see §Silent Guardian Mode)

Main Menu
  ┌─────────────────────────────────────┐
  │  🏦 ALAT by Wema Bank               │
  │  👤 <Account Name>                  │
  │  🔢 Account: <account_id>           │
  │  What would you like to do today?   │
  │                                     │
  │  [💰 Balance]   [💸 Transfer]       │
  │  [📱 Airtime/Data]  [📋 History]    │
  │  [🚪 Logout]                        │
  └─────────────────────────────────────┘

💰 Balance  →  GET /accounts/{id}/balance  →  formatted card
📋 History  →  GET /accounts/{id}/transactions?limit=7  →  7 transactions

💸 Transfer (button flow)
  1. Enter recipient (account ID or phone)
     → POST /accounts/validate  →  show name or warn
  2. Enter amount
  3. Enter narration (or "skip")
  4. ── PIN GATE ──  "🔐 Confirm: Transfer ₦X to Name — Enter PIN:"
       correct PIN  →  execute  →  ✅ success card
       wrong PIN    →  "❌ Incorrect PIN. Transaction cancelled."  →  menu
       "cancel"     →  menu

📱 Airtime/Data (button flow)
  1. [📞 Airtime] or [🌐 Data]
  2. [MTN] [Airtel] [Glo] [9mobile]
  3. Enter phone number
  4a. (Airtime) Enter amount
  4b. (Data)    Select plan from inline keyboard
  5. ── PIN GATE ──  "🔐 Confirm: Airtime ₦X (MTN) → 080... — Enter PIN:"
       correct PIN  →  execute  →  ✅ success card
       wrong PIN    →  cancelled  →  menu

🚪 Logout
  →  Clear session
  →  DELETE /context/{user_id}   on MCP
  →  DELETE /ownership/{user_id} on MCP
  →  "👋 You've been logged out."
```

Every screen except the PIN inputs must have a cancel / back button.

---

## Conversation States

Implement a state machine with exactly these 11 states:

| State | Waiting for |
|---|---|
| `AWAIT_PIN` | 4-digit login PIN (real or distress) |
| `MENU` | Button tap or free-text AI command |
| `TRANSFER_RECIPIENT` | Recipient identifier text |
| `TRANSFER_AMOUNT` | Amount text |
| `TRANSFER_NOTE` | Narration text or "skip" |
| `TOPUP_TYPE` | Airtime/Data inline button |
| `TOPUP_NETWORK` | Network inline button |
| `TOPUP_PHONE` | Phone number text |
| `TOPUP_PLAN` | Data plan inline button (data path) |
| `TOPUP_AMOUNT` | Amount text (airtime path) |
| `CONFIRM_PIN` | Re-entry of PIN to authorise a debit ← security gate |

Free-text in `MENU` → AI engine.
Free-text in any `TRANSFER_*` or `TOPUP_*` state that doesn't match the
expected format → re-prompt in the same state, do not pass to AI.
Text in `CONFIRM_PIN` → PIN validation only, never AI.

---

## Security Features

### Silent Guardian Mode

Implement a second "distress PIN" (`DISTRESS_PIN` env var). When the user
enters this PIN at `AWAIT_PIN` or `CONFIRM_PIN`, the session enters
`guardian_mode = true`.

**Guardian mode behaviour:**

- Every debit action (transfer, topup, bill payment) shows a success screen
  that is **visually identical** to a real success:
  - Same ✅ heading
  - Plausible fake reference number (e.g. `TX73829104`)
  - Balance display decremented by the attempted amount
- The real banking API is never called. No money moves.
- A covert alert is sent immediately to `GUARDIAN_ALERT_CHAT_ID`
  (a separate Telegram chat — your ops/security team). Alert content:
  - Timestamp (UTC)
  - Telegram user ID
  - Account ID
  - Action attempted (e.g. `TRANSFER (BLOCKED)`)
  - Amount, recipient, reference shown
  - Label: `"BLOCKED — distress PIN at login"` or
    `"BLOCKED — distress PIN at confirmation"`
- The alert is fire-and-forget. Failure to deliver must never surface to the user.

**Why not freeze?** The attacker is physically present and watching the screen.
Freezing is visible and could escalate the danger. Guardian mode leaves the
account appearing fully functional.

**Distress PIN at `CONFIRM_PIN`:** the real PIN was used to log in, but the
user enters the distress PIN at the confirmation step. This scenario must also
activate guardian mode and fire the alert.

**Do not log or display the distress PIN value** anywhere in the application
or its logs.

---

### PIN Confirmation Gate (CONFIRM_PIN state)

All debit operations — whether triggered by button or by an AI tool call —
must pass through `CONFIRM_PIN` before any money moves.

**Debit tools that require PIN confirmation:**

```
send_money    buy_airtime_data    pay_bill    debit_wallet
```

**Button-driven flow:** after collecting all form inputs, instead of calling
the banking API immediately, transition to `CONFIRM_PIN` with the pending
action stored in session:

```json
{ "tool": "send_money", "params": { ... }, "source": "button" }
```

Show the user a human-readable summary of what they are about to authorise
before asking for the PIN:

| Tool | Summary format |
|---|---|
| `send_money` | `Transfer ₦5,000.00 to Tolu Balogun — school fees` |
| `buy_airtime_data` | `Airtime ₦500.00 (MTN) → 08012345678` |
| `pay_bill` | `Pay ₦10,500.00 to DSTV (customer 12345678)` |
| `debit_wallet` | `Debit ₦2,000.00 from wallet` |

**AI-driven debit flow:**

When the AI returns tool calls that include one or more debit tools:
1. Execute all non-debit tool calls in the response immediately via MCP.
2. Collect ALL debit tool calls into a FIFO transaction queue.
3. Set the first item as `pending` in session.
4. Store the remaining items in `tx_queue` in session.
5. Transition to `CONFIRM_PIN`, showing the first item's summary with a
   progress banner: `(1 of N)` when N > 1.
6. After each PIN confirmation, advance the queue:
   - Pop the next item → show its PIN prompt → repeat
   - When queue is empty → return to main menu
7. Return the sentinel `"__PIN_GATE__"` from the AI processing function so
   the handler knows the state has already been transitioned.

**Queue termination rules:**

| Event | Queue behaviour |
|---|---|
| Correct PIN | Execute item → advance → next prompt (or menu) |
| Wrong PIN | Cancel current item + clear entire queue; show count of cancelled items |
| "cancel" typed | Cancel current item + clear entire queue; show count |
| Distress PIN (at any item) | Activate guardian mode; fake-success current item; drain all remaining with fake successes; each fires a guardian alert |
| Logout | Clear queue before wiping session |

**Progress banner format** — prepend to PIN confirmation prompt when queue > 1:
```
_(1 of 3)_
```

**Correct PIN at CONFIRM_PIN:** execute `_dispatch_pending_action()`.
**Distress PIN at CONFIRM_PIN:** activate guardian mode, show fake success,
fire alert, do not call banking API.
**Wrong PIN at CONFIRM_PIN:** show "❌ Incorrect PIN. Transaction cancelled.",
clear pending action, return to `MENU`.
**"cancel" at CONFIRM_PIN:** clear pending action, return to `MENU`.

---

## AI Engine Requirements

### Models and fallback

Use any LLM provider that supports OpenAI-compatible tool calling. Read primary
model, API key, and base URL from environment variables. Implement a fallback
chain: on HTTP 429, try the next model immediately — no sleeping.

### Tool calling

Load `tools.json` at startup. Pass the full array as `tools` with
`tool_choice: "auto"`. Include `user_id` (Telegram user ID as a string) in
every `POST /call` payload to MCP.

When the model returns tool calls:
1. Separate debit tools from safe tools.
2. Execute safe tools via MCP immediately.
3. If a debit tool is present, store it as pending and transition to
   `CONFIRM_PIN` (do not execute). Return `"__PIN_GATE__"` to the caller.
4. If no debit tool, collect all tool results, send a second LLM call for the
   natural-language answer, return the answer.

### Conversation context

Before every AI call:
1. `GET /context/{user_id}` from MCP — up to 10 messages (5 pairs).
2. `messages = [system_prompt, ...history, user_message]`
3. After producing the final answer, `POST /context/{user_id}`
   `{ user_message, assistant_reply }`.

Save only the original user text and final assistant text — not tool-call
intermediate messages.

### System prompt

```
You are a helpful ALAT by Wema Bank assistant inside a Telegram chat.

TOOL USE: Use the provided tools whenever you need live banking data or need
to perform a banking action. Never refuse a banking request because you
"don't have access" — you always have access via tools.

MULTI-STEP REASONING: For compound commands (e.g. "buy 1000 airtime for
08123456789 on Glo"), identify all required tool parameters from the user's
message and call the tool in one shot. Do not ask follow-up questions if all
required parameters are already present in the user's message.

DEBIT ACTIONS: When you call send_money, buy_airtime_data, pay_bill, or
debit_wallet, the system will ask the user to confirm with their PIN before
execution. You do not need to ask for confirmation yourself — the system
handles it. Simply call the tool with correct parameters.

FORMATTING — Telegram Markdown (strictly enforced):
  - Bold:   *text*    NEVER **text**
  - Italic: _text_    NEVER __text__
  - Code:   `text`
  - NEVER use # headers
  - NEVER use triple backticks in replies
  - Use a plain dash (-) or emoji for bullet lists

MONEY: Format all amounts with ₦ and thousands commas: ₦150,000.00.
REFERENCES: Always show transaction references in monospace: `REF`.
ERRORS: Explain tool errors in plain language. Never show raw JSON to the user.
```

---

## MCP Integration

| Bot action | MCP call |
|---|---|
| AI safe tool call | `POST /call` → `{ tool, params, user_id }` |
| AI debit tool call | Store as pending → transition to CONFIRM_PIN (do not call MCP yet) |
| After PIN confirmed | `POST /call` → `{ tool, params, user_id }` |
| Before AI call | `GET /context/{user_id}` |
| After AI answer | `POST /context/{user_id}` → `{ user_message, assistant_reply }` |
| On login (after PIN accepted) | `POST /ownership/{user_id}` → `{ account_ids: [...] }` |
| On logout | `DELETE /context/{user_id}` then `DELETE /ownership/{user_id}` |

If MCP returns 403 on a tool call, show: "⚠️ Access denied for that account."
If MCP returns 400 with a vague message, show: "⚠️ That request could not be processed."
If MCP is unreachable, show: "⚠️ Banking services are temporarily unavailable."
Never expose raw error JSON to the user.

---

## Voice Message Support

1. Download audio from Telegram to a temp file.
2. Encode as base64.
3. Send to STT model (read from `STT_MODEL` env var; fall back to
   `STT_FALLBACK_MODEL` on 429).
4. Show transcription: `🎙 "<transcript>"`
5. Pass transcript through the same AI engine as normal text.
6. Handle `"__PIN_GATE__"` sentinel the same way as in text flow.
7. Delete temp file.

---

## Session and Authentication

Session must store at minimum:
- `account_id`, `account_name`, `logged_in: true`
- `guardian_mode: bool` (default false)
- `pending: { tool, params, source }` (set when routing to CONFIRM_PIN)

Clear entire session on `/start` or logout.
Do not log or store raw PIN values (real or distress).

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | — | Bot token from @BotFather |
| `LLM_API_KEY` | Yes | — | API key for LLM provider |
| `LLM_BASE_URL` | No | OpenAI default | Base URL for OpenAI-compatible API |
| `PRIMARY_MODEL` | Yes | — | Primary model name |
| `FALLBACK_MODELS` | No | `[]` | Comma-separated fallback model names |
| `STT_MODEL` | No | — | Speech-to-text model |
| `STT_FALLBACK_MODEL` | No | — | Fallback STT model |
| `MCP_URL` | Yes | — | MCP server base URL |
| `BANKING_API_URL` | Yes | — | Banking API base URL (for direct reads) |
| `DEMO_PIN` | Yes | — | Real 4-digit login PIN |
| `DISTRESS_PIN` | Yes | — | Distress PIN (do not use 0000 in production) |
| `GUARDIAN_ALERT_CHAT_ID` | Yes | — | Telegram chat ID for silent guardian alerts |

---

## Error Handling Rules

1. All fallback models rate-limited → "⚠️ All AI models are busy. Try again shortly."
2. MCP 403 → "⚠️ Access denied for that account."
3. MCP 400 (vague) → "⚠️ That request could not be processed."
4. MCP unreachable → "⚠️ Banking services are temporarily unavailable."
5. Banking API insufficient funds / frozen account → extract `detail` field,
   show in plain language. Never show raw JSON.
6. Voice download failure → "⚠️ Failed to download your voice message."
7. STT failure → "⚠️ Could not transcribe your voice message."
8. Unknown button callback → answer the query silently to remove the spinner.

---

## Verification

After building, demonstrate:

1. `/start` → PIN prompt appears.
2. Correct PIN (`DEMO_PIN`) → main menu with 5 buttons.
3. 💰 Balance → formatted balance card.
4. 💸 Transfer → complete 3-step form → 🔐 PIN confirmation screen with
   summary → enter PIN → ✅ success card with reference.
5. 📱 Airtime → full flow → 🔐 PIN confirmation → ✅ success.
6. Free-text `"send ₦2000 to demo456"` → AI calls `send_money` → intercepted →
   🔐 PIN confirmation shown → enter PIN → ✅ success via MCP.
7. Free-text `"what was my last transaction?"` → AI calls
   `get_transaction_history` directly (no PIN gate — read-only) → result shown.
8. Enter distress PIN at login → main menu appears normally → attempt transfer →
   🔐 PIN screen → enter any PIN → ✅ fake success card shown, guardian alert
   fires to `GUARDIAN_ALERT_CHAT_ID`, money unchanged.
9. Enter real PIN at login → attempt transfer → enter distress PIN at
   confirmation step → ✅ fake success shown, alert fires labelled
   "BLOCKED — distress PIN at confirmation".
10. 🚪 Logout → session cleared → `DELETE /context` and `DELETE /ownership`
    called on MCP → subsequent tool calls return 403.
11. Free-text `"send ₦2k to Tolu and buy ₦500 MTN airtime for 08012345678"` →
    AI queues 2 debit calls → 🔐 _(1 of 2)_ Transfer ₦2,000 prompt →
    enter PIN → ✅ transfer success → 🔐 _(2 of 2)_ Airtime ₦500 prompt →
    enter PIN → ✅ topup success → main menu.
12. Same compound command, wrong PIN on first item → "❌ Incorrect PIN.
    Transaction cancelled. 1 further transaction also cancelled." → menu.
13. Same compound command, distress PIN on second item → first item executes
    normally, second shows fake success, guardian alert fires for the second
    item labelled "BLOCKED — guardian mode".
