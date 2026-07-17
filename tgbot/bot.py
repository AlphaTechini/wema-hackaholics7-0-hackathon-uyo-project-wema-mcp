"""
bot.py
------
Telegram banking bot backed by the Wema MCP API + Groq/Gemini AI.

Flow
----
  /start  →  Introduction and capabilities  →  Conversational banking assistant
              │
              ├── 💸 Transfer      → ask account → ask amount → confirm → send
              └── 📋 History       → fetch statement through MCP

Free-text at any time falls through to the Groq assistant with Gemini failover.
Voice messages are transcribed then handled the same way.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from openai import OpenAI
from groq import Groq
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from mcp_client import McpClient

# Load shared config, then override with environment-specific file.
# APP_ENV defaults to "local" → .env.local; set APP_ENV=production for Docker.
load_dotenv()
_env = os.getenv("APP_ENV", "local")
load_dotenv(f".env.{_env}", override=True)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "qwen/qwen3-32b")
GROQ_REASONING_EFFORT: str = os.getenv("GROQ_REASONING_EFFORT", "none")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
MCP_URL: str = os.getenv("MCP_SERVER_URL", "http://localhost:3870/mcp")
DEFAULT_ACCOUNT_ID: str = os.getenv("DEFAULT_ACCOUNT_ID", "1000000000")
PORT: int = int(os.getenv("PORT", "8080"))
WEBHOOK_BASE_URL: str = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")
WEBHOOK_PATH: str = os.getenv("TELEGRAM_WEBHOOK_PATH", "telegram").strip("/")
WEBHOOK_SECRET: str = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")

# Gemini handles transcription natively via the same OpenAI-compat endpoint.
TRANSCRIPTION_MODEL: str = os.getenv("TRANSCRIPTION_MODEL", "gemini-2.5-flash-lite")
TRANSCRIPTION_FALLBACK: str = "gemini-2.5-flash"

# ---------------------------------------------------------------------------
# Silent Guardian Mode
# ---------------------------------------------------------------------------
# If the user enters this PIN instead of the real PIN, the session enters
# guardian mode. Every debit action (transfer, topup) shows a fake-success
# screen but is silently blocked. A covert alert is sent to GUARDIAN_ALERT_CHAT_ID.
#
# Design principles:
#   • The screen must look IDENTICAL to a real success — same ref format,
#     same balance display. An attacker watching cannot tell the difference.
#   • The real balance is never touched.
#   • The alert goes to a separate Telegram chat (ops/security team).
#   • Guardian mode persists for the full session. Logout clears it.
#   • The account is NOT frozen automatically — freezing would tip off the attacker.
#     Freeze is the response to INJECTION attacks, not coercion. (See mcp_server.py.)
#
DISTRESS_PIN: str = os.getenv("DISTRESS_PIN", "0000")
GUARDIAN_ALERT_CHAT_ID: str = os.getenv("GUARDIAN_ALERT_CHAT_ID", "")   # set in .env

# ---------------------------------------------------------------------------
# ConversationHandler states
# ---------------------------------------------------------------------------

# Top-level states
(
    STATE_MENU,          # main menu shown, idle
    STATE_TRANSFER_TO,   # waiting for recipient
    STATE_TRANSFER_AMT,  # waiting for transfer amount
    STATE_TRANSFER_NOTE, # waiting for narration
    STATE_TOPUP_TYPE,    # waiting for airtime/data choice
    STATE_TOPUP_NET,     # waiting for network choice
    STATE_TOPUP_PHONE,   # waiting for phone number
    STATE_TOPUP_AMT,     # waiting for topup amount
    STATE_TOPUP_PLAN,    # waiting for data plan (data only)
    STATE_CONFIRM_PIN,   # waiting for re-entry of PIN to authorise a debit
) = range(10)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AI provider clients
# ---------------------------------------------------------------------------

groq_client = Groq(api_key=GROQ_API_KEY, max_retries=0, timeout=30.0) if GROQ_API_KEY else None
gemini_client = (
    OpenAI(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=GEMINI_API_KEY,
        max_retries=0,
        timeout=30.0,
    )
    if GEMINI_API_KEY
    else None
)

AI_PROVIDERS: dict[str, tuple[Any, str]] = {
    "groq": (groq_client, GROQ_MODEL),
    "gemini": (gemini_client, GEMINI_MODEL),
}

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Tool schemas — loaded from tools.json (single source of truth)
# ---------------------------------------------------------------------------

_TOOLS_PATH = os.path.join(os.path.dirname(__file__), "tools.json")
with open(_TOOLS_PATH) as _f:
    TOOLS: list[dict] = json.load(_f)


SYSTEM_PROMPT = (
    "You are a helpful ALAT by Wema Bank assistant inside a Telegram chat.\n\n"

    "FORMATTING RULES — Telegram only supports a limited Markdown subset. "
    "You MUST follow these rules exactly or the message will render broken:\n"
    "  • Bold: wrap with single asterisks → *bold text*\n"
    "  • Italic: wrap with single underscores → _italic text_\n"
    "  • Monospace/code: wrap with backticks → `code`\n"
    "  • NEVER use double asterisks (**bold**) — Telegram does NOT support it.\n"
    "  • NEVER use double underscores (__italic__) — not supported.\n"
    "  • NEVER use markdown headers (# ## ###) — not supported.\n"
    "  • NEVER use triple backticks (```code blocks```) in conversational replies.\n"
    "  • For bullet lists use a plain dash or emoji, not markdown list syntax.\n\n"

    "CONTENT RULES:\n"
    "  • Format all money amounts with the ₦ symbol and commas, e.g. ₦150,000.00.\n"
    "  • Keep replies concise and friendly.\n"
    "  • Use the provided tools whenever you need live banking data.\n"
    "  • After completing a transaction always quote the reference number in monospace.\n\n"

    "ACCOUNT CREATION RULES:\n"
    "  Parse account fields from any order and store them in conversation context.\n"
    "  Map the first name before the last name and detect Gmail addresses as email.\n"
    "  Ask only for the next missing non-PIN field. Ask for the PIN last, by itself.\n"
    "  Call create_account once with all fields only after the PIN is collected.\n"
    "  Never repeat or expose a PIN.\n\n"

    "TRANSFER RULES:\n"
    "  create_transfer requires sender_acc, receiver_acc, amount, and PIN.\n"
    "  The bot collects the PIN through its confirmation gate before dispatch.\n"
    "  Never call a tool with invented account numbers or ambiguous amounts."
)

# ---------------------------------------------------------------------------
# MCP client and local conversation history
# ---------------------------------------------------------------------------

MCP_CLIENT = McpClient(MCP_URL)
_conversation_history: dict[str, list[dict[str, str]]] = {}


async def mcp_call(tool_name: str, params: dict, user_id: str = "") -> dict:
    return await MCP_CLIENT.call_tool(tool_name, params)


async def mcp_get_history(user_id: str) -> list[dict]:
    return _conversation_history.get(user_id, [])


async def mcp_save_history(user_id: str, user_message: str, assistant_reply: str) -> None:
    history = _conversation_history.setdefault(user_id, [])
    history.extend([
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": assistant_reply},
    ])
    _conversation_history[user_id] = history[-10:]


async def mcp_clear_history(user_id: str) -> None:
    _conversation_history.pop(user_id, None)


# ---------------------------------------------------------------------------
# Silent Guardian helpers
# ---------------------------------------------------------------------------

import random as _random
import string as _string

def _fake_ref() -> str:
    """Generate a plausible-looking transaction reference."""
    return "TX" + "".join(_random.choices(_string.digits, k=8))


async def _send_guardian_alert(
    bot,
    user_id: str,
    account_id: str,
    action: str,
    details: dict,
) -> None:
    """
    Fire a covert alert to the security/ops Telegram chat.
    Runs as a fire-and-forget — never raises; never shows anything to the user.
    """
    if not GUARDIAN_ALERT_CHAT_ID:
        logger.warning("GUARDIAN_ALERT_CHAT_ID not set — alert not delivered.")
        return
    try:
        detail_lines = "\n".join(f"  {k}: {v}" for k, v in details.items())
        msg = (
            f"🚨 *SILENT GUARDIAN ALERT*\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🕐 Time: `{__import__('datetime').datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC`\n"
            f"👤 Telegram user ID: `{user_id}`\n"
            f"🏦 Account: `{account_id}`\n"
            f"⚠️ Action attempted: *{action}*\n"
            f"📋 Details:\n{detail_lines}\n\n"
            f"_Transaction was silently blocked. Account is still active._"
        )
        await bot.send_message(
            chat_id=GUARDIAN_ALERT_CHAT_ID,
            text=msg,
            parse_mode="Markdown",
        )
        logger.warning(
            "GUARDIAN ALERT fired | user=%s account=%s action=%s",
            user_id, account_id, action,
        )
    except Exception as exc:
        logger.error("Failed to send guardian alert: %s", exc)


# ---------------------------------------------------------------------------
# AI engine
# ---------------------------------------------------------------------------

def _chat(provider: str, messages: list[dict], **kwargs):
    provider_client, model = AI_PROVIDERS[provider]
    if provider_client is None:
        raise RuntimeError(f"{provider} API key is not configured")
    if provider == "groq":
        kwargs.setdefault("reasoning_effort", GROQ_REASONING_EFFORT)
    return provider_client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.3,
        max_tokens=1024,
        **kwargs,
    )


def _provider_order(preferred_provider: str | None) -> list[str]:
    providers = ["groq", "gemini"]
    if preferred_provider in providers:
        providers.remove(preferred_provider)
        providers.insert(0, preferred_provider)
    return providers


def _chat_with_failover(
    messages: list[dict],
    preferred_provider: str | None,
    failed_providers: set[str],
    **kwargs,
) -> tuple[Any, str]:
    last_error: Exception | None = None
    for provider in _provider_order(preferred_provider):
        if provider in failed_providers:
            continue
        try:
            response = _chat(provider, messages, **kwargs)
            return response, provider
        except Exception as exc:
            failed_providers.add(provider)
            last_error = exc
            logger.exception("AI provider %s failed; trying fallback", provider)
    raise RuntimeError("All AI providers failed") from last_error


def _message_payload(message: Any) -> dict:
    if hasattr(message, "model_dump"):
        return message.model_dump(exclude_none=True)
    return message if isinstance(message, dict) else dict(message)


async def process_message_with_ai(
    user_message: str,
    user_id: str = "anon",
    update: Update | None = None,
    context: ContextTypes.DEFAULT_TYPE | None = None,
) -> str:
    """
    Full round-trip with tool calling, model fallback, and per-user history.

    Handles two model behaviours:
      • Models that emit ALL tool calls in one response (parallel tool use)
      • Models that emit ONE tool call per response and expect the result
        before deciding on the next call (sequential tool use — common on
        free-tier models)

    The loop runs until the model either:
      (a) returns a plain text answer (no more tool calls), or
      (b) returns a debit tool call → intercepted, queued, returns __PIN_GATE__

    Debit tool calls are NEVER sent to MCP. They are queued in
    context.user_data and the PIN gate is shown to the user.
    """
    history = await mcp_get_history(user_id)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": user_message},
    ]

    failed_providers: set[str] = set()
    try:
        current_response, chosen_provider = _chat_with_failover(
            messages,
            preferred_provider=None,
            failed_providers=failed_providers,
            tools=TOOLS,
            tool_choice="auto",
        )
    except Exception:
        logger.exception("All AI providers failed on the initial request")
        return "⚠️ The AI service is temporarily unavailable. Please try again shortly."
    logger.info("Using AI provider: %s", chosen_provider)

    # ── Multi-turn tool loop ───────────────────────────────────────────────
    # Cap at 6 iterations to prevent infinite loops on misbehaving models
    debit_queue: list[dict] = []

    for _iteration in range(6):
        assistant_msg = current_response.choices[0].message
        finish_reason = current_response.choices[0].finish_reason

        # No tool calls on this turn.
        # If we haven't queued any debit actions yet and this is an early iteration,
        # the model may have skipped tool use entirely (common on free-tier models for
        # multi-recipient requests). Inject a firm reminder and force it to use tools.
        if not assistant_msg.tool_calls:
            if not debit_queue and _iteration == 0:
                # The model answered in plain text without calling any tools.
                # Append its reply as context then demand tool calls explicitly.
                if assistant_msg.content:
                    messages.append({"role": "assistant", "content": assistant_msg.content})
                messages.append({
                    "role": "user",
                    "content": (
                        "You must use the available tools to complete this request. "
                        "Do not ask clarifying questions — all the information needed "
                        "is already in the conversation. "
                        "If the request involves multiple recipients or phone numbers, "
                        "call the relevant tool once per recipient in parallel, right now."
                    ),
                })
                try:
                    current_response, chosen_provider = _chat_with_failover(
                        messages,
                        preferred_provider=chosen_provider,
                        failed_providers=failed_providers,
                        tools=TOOLS,
                        tool_choice="required",
                    )
                except Exception:
                    logger.exception("All AI providers failed during tool recovery")
                    return "⚠️ The AI service is temporarily unavailable. Please try again shortly."
                continue   # re-enter loop with the forced response
            answer = (assistant_msg.content or "").strip()
            break

        messages.append(_message_payload(assistant_msg))

        # Separate debit from safe tool calls
        safe_tool_calls  = [tc for tc in assistant_msg.tool_calls
                            if tc.function.name not in _DEBIT_TOOLS]
        debit_tool_calls = [tc for tc in assistant_msg.tool_calls
                            if tc.function.name in _DEBIT_TOOLS]

        # Execute safe tool calls and collect their results
        for tc in safe_tool_calls:
            func_name = tc.function.name
            try:
                func_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                func_args = {}
            logger.info("Safe tool call: %s(%s)", func_name, func_args)
            try:
                result = await mcp_call(func_name, func_args, user_id=user_id)
            except Exception as exc:
                result = {"error": str(exc)}
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

        # Collect debit calls into the queue — do NOT execute them
        for tc in debit_tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            args.pop("pin", None)
            logger.info("Debit tool queued (PIN required): %s(%s)", tc.function.name, args)
            # Add a synthetic tool result so the message array stays valid
            # (the model expects a result for every tool_call_id it emitted)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps({
                    "status": "pending_pin_confirmation",
                    "message": "This transaction requires PIN confirmation from the user.",
                }),
            })
            debit_queue.append({
                "tool":   tc.function.name,
                "params": args,
                "source": "ai",
            })

        # Ask model to continue — it may issue more tool calls or give an answer.
        # Force tool_choice="required" when safe calls were just processed but no
        # debit calls have been queued yet: this prevents the model from writing a
        # premature text summary instead of issuing the remaining debit tool calls.
        # Once at least one debit is queued we relax to "auto" — the model may then
        # emit more debit calls or produce a confirmation text, either is correct.
        _follow_up_tool_choice = (
            "required"
            if safe_tool_calls and not debit_queue
            else "auto"
        )
        try:
            current_response, chosen_provider = _chat_with_failover(
                messages,
                preferred_provider=chosen_provider,
                failed_providers=failed_providers,
                tools=TOOLS,
                tool_choice=_follow_up_tool_choice,
            )
        except Exception:
            logger.exception("All AI providers failed during tool follow-up")
            return "⚠️ The AI service is temporarily unavailable. Please try again shortly."

    else:
        # Loop cap hit — shouldn't happen in normal usage
        answer = "I processed your request but couldn't summarise the result. Please try again."

    # ── Route debit queue to PIN gate ─────────────────────────────────────
    if debit_queue:
        if update is None or context is None:
            return "⚠️ Cannot authorise transaction — please use the menu buttons."

        # Persist the user message NOW, before leaving this function.
        # Without this, the next turn has no memory of what was requested
        # (e.g. "those numbers" would be unresolvable on follow-up prompts).
        # The assistant reply summarises what was queued so the model has
        # accurate context when the user asks about the same recipients later.
        _queued_summaries = " | ".join(
            _pending_summary({"tool": item["tool"], "params": item["params"]})
            for item in debit_queue
        )
        await mcp_save_history(
            user_id,
            user_message,
            f"Queued {len(debit_queue)} transaction(s) pending PIN confirmation: {_queued_summaries}",
        )

        # Load queue: first item → pending, rest → tx_queue
        first_item = debit_queue[0]
        _queue_enqueue(context, debit_queue[1:])

        logger.info(
            "Debit queue loaded | user=%s items=%d first=%s",
            user_id, len(debit_queue), first_item["tool"],
        )

        await _request_pin_confirmation(
            update, context,
            tool=first_item["tool"],
            params=first_item["params"],
            source="ai",
        )
        return "__PIN_GATE__"

    # ── No debits — save history and return answer ─────────────────────────
    await mcp_save_history(user_id, user_message, answer)
    return answer


# ---------------------------------------------------------------------------
# Voice transcription
# ---------------------------------------------------------------------------

async def transcribe_voice(file_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    if gemini_client is None:
        raise RuntimeError("Voice transcription is not configured.")

    audio_b64 = base64.b64encode(file_bytes).decode("utf-8")
    fmt = mime_type.split("/")[-1].split(";")[0].strip() or "ogg"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "input_audio", "input_audio": {"data": audio_b64, "format": fmt}},
                {"type": "text", "text": "Transcribe this audio exactly. Return only the transcription."},
            ],
        }
    ]
    for model in (TRANSCRIPTION_MODEL, TRANSCRIPTION_FALLBACK):
        try:
            resp = gemini_client.chat.completions.create(
                model=model, messages=messages, temperature=0.0, max_tokens=512
            )
            text = (resp.choices[0].message.content or "").strip()
            logger.info("Transcription via %s: %s", model, text[:120])
            return text
        except Exception:
            logger.exception("Transcription error with %s", model)
            continue
    raise RuntimeError("Voice transcription is temporarily unavailable.")

# ---------------------------------------------------------------------------
# UI helpers — keyboards & screen builders
# ---------------------------------------------------------------------------

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💸 Transfer", callback_data="menu:transfer"),
            InlineKeyboardButton("📋 History",  callback_data="menu:history"),
        ],
        [
            InlineKeyboardButton("🚪 Logout", callback_data="menu:logout"),
        ],
    ])


def back_keyboard(back_to: str = "main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Menu", callback_data=f"back:{back_to}")]
    ])


def network_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("MTN",     callback_data="net:MTN"),
            InlineKeyboardButton("Airtel",  callback_data="net:Airtel"),
        ],
        [
            InlineKeyboardButton("Glo",     callback_data="net:Glo"),
            InlineKeyboardButton("9mobile", callback_data="net:9mobile"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="back:main")],
    ])


def topup_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📞 Airtime", callback_data="topuptype:airtime"),
            InlineKeyboardButton("🌐 Data",    callback_data="topuptype:data"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="back:main")],
    ])


DATA_PLANS: dict[str, list[tuple[str, str]]] = {
    "MTN":     [("500MB – 1 day ₦100",  "500MB-1day"), ("1GB – 7 days ₦300",   "1GB-7days"),
                ("2GB – 30 days ₦500",  "2GB-30days"), ("5GB – 30 days ₦1500", "5GB-30days")],
    "Airtel":  [("750MB – 1 day ₦200",  "750MB-1day"), ("1.5GB – 7 days ₦500", "1.5GB-7days"),
                ("3GB – 30 days ₦1000", "3GB-30days"), ("6GB – 30 days ₦2000", "6GB-30days")],
    "Glo":     [("1GB – 1 day ₦200",    "1GB-1day"),   ("2GB – 7 days ₦500",   "2GB-7days"),
                ("5GB – 30 days ₦1500", "5GB-30days"), ("10GB – 30 days ₦2500","10GB-30days")],
    "9mobile": [("500MB – 1 day ₦150",  "500MB-1day"), ("1GB – 7 days ₦400",   "1GB-7days"),
                ("3GB – 30 days ₦1200", "3GB-30days"), ("5GB – 30 days ₦2000", "5GB-30days")],
}

PLAN_PRICES: dict[str, float] = {
    "500MB-1day": 100, "1GB-7days": 300, "2GB-30days": 500,  "5GB-30days": 1500,
    "750MB-1day": 200, "1.5GB-7days": 500, "3GB-30days": 1000, "6GB-30days": 2000,
    "1GB-1day":   200, "2GB-7days":  500, "10GB-30days": 2500,
    "1GB-7days-9mobile": 400, "3GB-30days-9mobile": 1200, "5GB-30days-9mobile": 2000,
}


def data_plan_keyboard(network: str) -> InlineKeyboardMarkup:
    plans = DATA_PLANS.get(network, [])
    rows = [[InlineKeyboardButton(label, callback_data=f"plan:{key}")]
            for label, key in plans]
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="back:main")])
    return InlineKeyboardMarkup(rows)


def fmt_amount(amount: float) -> str:
    return f"₦{amount:,.2f}"


def welcome_text(name: str, account_id: str) -> str:
    return (
        f"🏦 *ALAT by Wema Bank*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👤 *{name}*\n"
        f"🔢 Account: `{account_id}`\n\n"
        f"What would you like to do today?"
    )

# ---------------------------------------------------------------------------
# Conversation start
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Introduce the assistant and begin a banking conversation."""
    user = update.effective_user
    context.user_data.clear()
    context.user_data["name"] = user.first_name or "there"

    await update.message.reply_text(
        f"🏦 *Welcome to ALAT by Wema*\n\n"
        f"Hello, *{user.first_name or 'there'}*! 👋\n\n"
        "I can help you:\n"
        "- Create a new account\n"
        "- Update account details\n"
        "- View a transaction statement\n"
        "- Prepare and confirm a transfer\n\n"
        "What would you like to do first? If you are opening a new account, start with your first and last name. I will collect only the information required for your request, and I will never ask for an account PIN before it is necessary.",
        parse_mode="Markdown",
    )
    return STATE_MENU


async def show_main_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    edit: bool = False,
) -> int:
    """Display (or refresh) the main menu."""
    name = context.user_data.get("name", "Customer")
    account_id = context.user_data.get("account_id", DEFAULT_ACCOUNT_ID)
    text = welcome_text(name, account_id)

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=main_menu_keyboard()
        )
    else:
        target = update.message or (update.callback_query.message if update.callback_query else None)
        if target:
            await target.reply_text(
                text, parse_mode="Markdown", reply_markup=main_menu_keyboard()
            )
    return STATE_MENU

# ---------------------------------------------------------------------------
# Main menu callback dispatcher
# ---------------------------------------------------------------------------

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Route inline button presses from the main menu."""
    query = update.callback_query
    await query.answer()
    data = query.data  # e.g. "menu:balance"

    if data == "menu:transfer":
        return await start_transfer(update, context)
    if data == "menu:history":
        return await show_history(update, context)
    if data == "menu:logout":
        return await do_logout(update, context)
    if data.startswith("back:"):
        return await show_main_menu(update, context, edit=True)
    return STATE_MENU


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.edit_message_text(
        "Balance lookup is not exposed by the current Wema MCP API.",
        reply_markup=back_keyboard(),
    )
    return STATE_MENU


# ---------------------------------------------------------------------------
# Transaction history
# ---------------------------------------------------------------------------

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    account_id = context.user_data.get("account_id", DEFAULT_ACCOUNT_ID)

    await query.edit_message_text("⏳ Loading transactions…")
    try:
        data = await mcp_call(
            "get_statement",
            {"account_number": int(account_id), "limit": 7},
        )

        lines = [f"📋 *Recent Transactions*\n━━━━━━━━━━━━━━━━"]
        for txn in data.get("data", []):
            sent = txn.get("sender_acc") == int(account_id)
            sign = "🔴 -" if sent else "🟢 +"
            amount = fmt_amount(abs(txn.get("amount", 0)))
            counterparty = txn.get("receiver_acc") if sent else txn.get("sender_acc")
            lines.append(
                f"\n{sign}{amount}\n"
                f"  {'To' if sent else 'From'} account `{counterparty}`\n"
                f"  📅 {txn.get('created_at', 'unknown')}  |  `{txn.get('id', '?')}`"
            )
        if len(lines) == 1:
            lines.append("\nNo transactions found.")
        text = "\n".join(lines)
    except Exception as exc:
        text = f"⚠️ Could not fetch history: {exc}"

    await query.edit_message_text(
        text, parse_mode="Markdown", reply_markup=back_keyboard()
    )
    return STATE_MENU

# ---------------------------------------------------------------------------
# Transfer flow  (3 steps: recipient → amount → narration → execute)
# ---------------------------------------------------------------------------

async def start_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.edit_message_text(
        "💸 *Transfer Money*\n━━━━━━━━━━━━━━━━\n\n"
        "Enter the *recipient's numeric account number*:\n"
        "_(for example, 1234567890)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="back:main")]
        ]),
    )
    return STATE_TRANSFER_TO


async def transfer_got_recipient(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    recipient = (update.message.text or "").strip()
    if not recipient.isdigit():
        await update.message.reply_text("❌ Enter a numeric account number:")
        return STATE_TRANSFER_TO

    context.user_data["transfer_to"] = int(recipient)
    context.user_data["transfer_to_name"] = recipient
    confirm_text = f"✅ Recipient account `{recipient}`\n\n"

    await update.message.reply_text(
        f"{confirm_text}💸 How much do you want to send?\n"
        f"Enter amount in Naira _(e.g. 5000)_:",
        parse_mode="Markdown",
    )
    return STATE_TRANSFER_AMT


async def transfer_got_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = (update.message.text or "").strip().replace(",", "").replace("₦", "")
    try:
        amount = int(raw)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid amount (e.g. *5000*):", parse_mode="Markdown")
        return STATE_TRANSFER_AMT

    context.user_data["transfer_amount"] = amount
    recipient_name = context.user_data.get("transfer_to_name", context.user_data.get("transfer_to"))

    await update.message.reply_text(
        f"📝 Add a *narration / note* for this transfer to *{recipient_name}*\n"
        f"_(or type *skip* to leave it blank)_:",
        parse_mode="Markdown",
    )
    return STATE_TRANSFER_NOTE


async def transfer_got_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    note = (update.message.text or "").strip()
    if note.lower() == "skip":
        note = ""
    context.user_data["transfer_note"] = note

    account_id = context.user_data.get("account_id", DEFAULT_ACCOUNT_ID)
    recipient = context.user_data["transfer_to"]
    recipient_name = context.user_data.get("transfer_to_name", recipient)
    amount = context.user_data["transfer_amount"]

    # Route through PIN confirmation — no direct API call from here
    return await _request_pin_confirmation(
        update, context,
        tool="create_transfer",
        params={
            "sender_acc":   int(account_id),
            "receiver_acc": int(recipient),
            "amount":       amount,
            "comment":      note,
        },
        source="button",
    )

# ---------------------------------------------------------------------------
# Airtime / Data topup flow
# ---------------------------------------------------------------------------

async def start_topup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.edit_message_text(
        "📱 *Airtime & Data Topup*\n━━━━━━━━━━━━━━━━\n\n"
        "What would you like to buy?",
        parse_mode="Markdown",
        reply_markup=topup_type_keyboard(),
    )
    return STATE_TOPUP_TYPE


async def topup_got_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    topup_type = query.data.split(":")[1]   # "airtime" or "data"
    context.user_data["topup_type"] = topup_type

    await query.edit_message_text(
        f"{'📞 Airtime' if topup_type == 'airtime' else '🌐 Data'} Topup\n\n"
        "Select your *network*:",
        parse_mode="Markdown",
        reply_markup=network_keyboard(),
    )
    return STATE_TOPUP_NET


async def topup_got_network(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    network = query.data.split(":")[1]
    context.user_data["topup_network"] = network
    topup_type = context.user_data.get("topup_type", "airtime")

    await query.edit_message_text(
        f"*{network}* selected ✅\n\n"
        "📲 Enter the *phone number* to top up\n_(e.g. 08012345678)_:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="back:main")]
        ]),
    )
    return STATE_TOPUP_PHONE


async def topup_got_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = (update.message.text or "").strip()
    context.user_data["topup_phone"] = phone
    topup_type = context.user_data.get("topup_type", "airtime")
    network = context.user_data.get("topup_network", "")

    if topup_type == "data":
        await update.message.reply_text(
            f"🌐 *{network} Data Plans*\n━━━━━━━━━━━━━━━━\n\nChoose a plan:",
            parse_mode="Markdown",
            reply_markup=data_plan_keyboard(network),
        )
        return STATE_TOPUP_PLAN
    else:
        await update.message.reply_text(
            f"💵 Enter airtime *amount* in Naira _(e.g. 200)_:",
            parse_mode="Markdown",
        )
        return STATE_TOPUP_AMT


async def topup_got_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User selected a data plan from the inline keyboard."""
    query = update.callback_query
    await query.answer()
    plan_key = query.data.split(":")[1]
    context.user_data["topup_plan"] = plan_key

    amount = PLAN_PRICES.get(plan_key, 0)
    context.user_data["topup_amount"] = amount

    network = context.user_data.get("topup_network", "")
    phone   = context.user_data.get("topup_phone", "")
    plan_label = next(
        (label for label, key in DATA_PLANS.get(network, []) if key == plan_key),
        plan_key,
    )

    await query.edit_message_text(
        f"📋 *Confirm data bundle*\n"
        f"📱 {phone} | {network}\n"
        f"🌐 {plan_label} — {fmt_amount(amount)}",
        parse_mode="Markdown",
    )
    return await _request_topup_pin(update, context, amount)


async def topup_got_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User typed an airtime amount."""
    raw = (update.message.text or "").strip().replace(",", "").replace("₦", "")
    try:
        amount = float(raw)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "⚠️ Enter a valid amount (e.g. *200*):", parse_mode="Markdown"
        )
        return STATE_TOPUP_AMT

    context.user_data["topup_amount"] = amount
    context.user_data["topup_plan"] = None
    return await _request_topup_pin(update, context, amount)


async def _request_topup_pin(
    update: Update, context: ContextTypes.DEFAULT_TYPE, amount: float
) -> int:
    """Build topup params and forward to the shared PIN confirmation gate."""
    params: dict = {
        "account_id":   context.user_data.get("account_id", DEFAULT_ACCOUNT_ID),
        "phone_number": context.user_data.get("topup_phone", ""),
        "network":      context.user_data.get("topup_network", ""),
        "topup_type":   context.user_data.get("topup_type", "airtime"),
        "amount":       amount,
    }
    plan = context.user_data.get("topup_plan")
    if plan:
        params["data_plan"] = plan

    return await _request_pin_confirmation(
        update, context, tool="buy_airtime_data", params=params, source="button"
    )

# ---------------------------------------------------------------------------
# Transaction Queue
# ---------------------------------------------------------------------------
# When the AI returns multiple debit tool calls in a single response, they
# are loaded into a FIFO queue in context.user_data["tx_queue"]. The user
# then confirms (or cancels) each item one at a time with their PIN.
#
# Queue entry shape:
#   { "tool": str, "params": dict, "source": "ai" | "button" }
#
# Invariant: context.user_data["pending"] always holds the *current* item
# being confirmed (the head of the queue). The queue itself holds the
# *remaining* items after the current one.
#
# Guardian mode on any item silently blocks that item AND drains the rest
# of the queue with fake successes — the attacker watching the screen sees
# each "succeed" in sequence while nothing real executes.
# ---------------------------------------------------------------------------

def _queue_enqueue(context: ContextTypes.DEFAULT_TYPE, items: list[dict]) -> None:
    """Load a list of pending actions into the transaction queue."""
    context.user_data["tx_queue"] = list(items)


def _queue_pop(context: ContextTypes.DEFAULT_TYPE) -> dict | None:
    """Remove and return the next item from the queue, or None if empty."""
    queue = context.user_data.get("tx_queue", [])
    if not queue:
        return None
    next_item = queue.pop(0)
    context.user_data["tx_queue"] = queue
    return next_item


def _queue_remaining(context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return the number of items still in the queue (not counting current)."""
    return len(context.user_data.get("tx_queue", []))


def _queue_clear(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wipe the entire queue and the current pending item."""
    context.user_data["tx_queue"] = []
    context.user_data.pop("pending", None)


def _queue_status_banner(context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Return a one-line progress indicator, e.g. '(1 of 3)'.
    Returns empty string when there is only a single pending item.
    """
    # Total = 1 (current) + remaining
    remaining = _queue_remaining(context)
    total = remaining + 1
    if total <= 1:
        return ""
    done = total - remaining
    return f"_({done} of {total})_\n"


# ---------------------------------------------------------------------------
# PIN Confirmation Gate
# ---------------------------------------------------------------------------
# Every debit (transfer, topup, bill payment, AI-initiated send) must pass
# through here before the banking API is called.
#
# Flow:
#   finalise_<action>()  →  _request_pin_confirmation()  →  STATE_CONFIRM_PIN
#                                                               │
#                           handle_confirm_pin() ◄──────────── user types PIN
#                                │
#                     correct PIN → _dispatch_pending_action() → execute
#                     wrong PIN   → cancel, show main menu
#
# AI-initiated debits: process_message_with_ai detects that the model wants
# to call a debit tool, stores the pending call in context.user_data["pending"],
# and asks the user for PIN confirmation before forwarding to MCP.
# ---------------------------------------------------------------------------

# Tools that must be PIN-gated (MCP also enforces ownership; this is UX gate)
_DEBIT_TOOLS = {"create_transfer"}


def _pending_summary(pending: dict) -> str:
    """Human-readable one-liner for the pending action confirmation prompt."""
    tool = pending.get("tool", "")
    params = pending.get("params", {})
    if tool == "create_transfer":
        return (
            f"Transfer *{fmt_amount(float(params.get('amount', 0)))}* "
            f"to account *{params.get('receiver_acc', '?')}*"
            f"{' - ' + params['comment'] if params.get('comment') else ''}"
        )
    if tool == "buy_airtime_data":
        t = params.get("topup_type", "topup").capitalize()
        return (
            f"{t} *{fmt_amount(float(params.get('amount', 0)))}* "
            f"({params.get('network', '?')}) → `{params.get('phone_number', '?')}`"
        )
    if tool == "pay_bill":
        return (
            f"Pay *{fmt_amount(float(params.get('amount', 0)))}* "
            f"to *{params.get('provider_id', '?')}* "
            f"(customer `{params.get('customer_identifier', '?')}`)"
        )
    if tool == "debit_wallet":
        return f"Debit *{fmt_amount(float(params.get('amount', 0)))}* from wallet"
    return f"Execute *{tool}*"


async def _request_pin_confirmation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    tool: str,
    params: dict,
    source: str = "button",
) -> int:
    """
    Store the pending action and prompt for PIN re-entry.
    Shows a queue progress banner when multiple transactions are queued,
    e.g. '(1 of 3)' so the user knows how many are still to come.
    Returns STATE_CONFIRM_PIN.
    """
    context.user_data["pending"] = {"tool": tool, "params": params, "source": source}
    summary = _pending_summary({"tool": tool, "params": params})
    banner  = _queue_status_banner(context)   # "(1 of 3)\n" or ""

    prompt = (
        f"🔐 *Confirm Transaction*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{banner}"
        f"{summary}\n\n"
        f"Enter your *4-digit PIN* to authorise, or type *cancel*:"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(prompt, parse_mode="Markdown")
    else:
        await update.message.reply_text(prompt, parse_mode="Markdown")

    return STATE_CONFIRM_PIN


async def handle_confirm_pin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Validate the confirmation PIN.

    Correct PIN  → dispatch current item → advance queue → loop or finish
    Distress PIN → activate guardian mode → dispatch (fake) → drain rest silently
    Wrong PIN    → cancel current item AND clear the entire queue for safety
    'cancel'     → cancel current item AND clear the entire queue
    """
    text = (update.message.text or "").strip()

    # ── Cancel ────────────────────────────────────────────────────────────
    if text.lower() == "cancel":
        remaining = _queue_remaining(context)
        _queue_clear(context)
        msg = "↩️ Transaction cancelled."
        if remaining:
            msg += f"\n_{remaining} further transaction{'s' if remaining > 1 else ''} also cancelled._"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return await show_main_menu(update, context)

    # ── Validate transaction PIN before sending it to the API ──────────────
    is_distress = (text == DISTRESS_PIN)
    if (not text.isdigit() or len(text) < 4 or len(text) > 20) and not is_distress:
        remaining = _queue_remaining(context)
        _queue_clear(context)
        msg = "❌ *Invalid PIN format.* Transaction cancelled for your safety."
        if remaining:
            msg += f"\n_{remaining} further transaction{'s' if remaining > 1 else ''} also cancelled._"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return await show_main_menu(update, context)

    pending = context.user_data.pop("pending", None)
    if not pending:
        return await show_main_menu(update, context)

    if not is_distress:
        pending["params"]["pin"] = text

    # ── Distress PIN — activate guardian mode for this and all remaining ──
    if is_distress:
        context.user_data["guardian_mode"] = True

    return await _dispatch_pending_action(update, context, pending)


async def _dispatch_pending_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    pending: dict,
) -> int:
    """
    Execute one PIN-confirmed action, then advance the transaction queue.

    After execution (real or fake):
      - If more items remain in tx_queue → pop next, show PIN prompt for it
      - If queue is empty → show main menu
    Guardian mode fake-succeeds the current item then drains the remainder
    the same way, so every queued transaction appears to succeed.
    """
    tool    = pending["tool"]
    params  = pending["params"]
    user_id = str(update.effective_user.id)

    processing = await update.message.reply_text("⏳ Processing…")

    # ── Guardian mode: fake success, then advance queue ───────────────────
    if context.user_data.get("guardian_mode"):
        fake_ref = _fake_ref()
        amount   = float(params.get("amount", 0))
        fake_bal = context.user_data.get("balance", 0.0)
        text = (
            f"✅ *Transaction Successful!*\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"{_pending_summary(pending)}\n"
            f"🔖 Ref: `{fake_ref}`\n\n"
            f"💰 New balance: *{fmt_amount(fake_bal - amount)}*"
        )
        await processing.edit_text(text, parse_mode="Markdown")
        await _send_guardian_alert(
            update.get_bot(),
            user_id=user_id,
            account_id=context.user_data.get("account_id", DEFAULT_ACCOUNT_ID),
            action=f"{tool.upper()} (BLOCKED — guardian mode)",
            details=params,
        )
        # Drain next item in queue (also fake) or return to menu
        return await _advance_queue(update, context)

    # ── Real dispatch ─────────────────────────────────────────────────────
    try:
        result = await mcp_call(tool, params, user_id=user_id)

        if tool == "create_transfer":
            text = (
                f"✅ *Transfer Successful!*\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"👤 To account: *{params.get('receiver_acc')}*\n"
                f"💸 Amount: *{fmt_amount(float(params.get('amount', 0)))}*\n"
                f"📝 Note: _{params.get('comment') or 'N/A'}_\n"
                f"🔖 Ref: `{result.get('data', {}).get('id', '?')}`"
            )

        elif tool == "buy_airtime_data":
            emoji = "🌐" if params.get("topup_type") == "data" else "📞"
            text = (
                f"✅ *Topup Successful!*\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"{emoji} *{params.get('topup_type','').capitalize()}* — {params.get('network')}\n"
                f"📲 `{params.get('phone_number')}`\n"
                f"💸 *{fmt_amount(float(params.get('amount', 0)))}*\n"
                f"🔖 Ref: `{result.get('reference', '?')}`\n\n"
                f"💰 New balance: *{fmt_amount(result.get('new_balance', 0))}*"
            )
            context.user_data["balance"] = result.get("new_balance", 0)

        elif tool == "pay_bill":
            text = (
                f"✅ *Bill Payment Successful!*\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"🏢 *{result.get('provider_name', params.get('provider_id'))}*\n"
                f"🔢 Customer: `{params.get('customer_identifier')}`\n"
                f"💸 *{fmt_amount(float(params.get('amount', 0)))}*\n"
                f"🔖 Ref: `{result.get('reference', '?')}`\n\n"
                f"💰 New balance: *{fmt_amount(result.get('new_balance', 0))}*"
            )
            if result.get("token"):
                text += f"\n⚡ Token: `{result['token']}`"
            context.user_data["balance"] = result.get("new_balance", 0)

        else:
            text = f"✅ Done.\n🔖 Ref: `{result.get('reference', result.get('status', 'ok'))}`"

    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", exc.response.text)
        except Exception:
            detail = exc.response.text
        text = f"❌ Transaction failed: {detail}"
        await processing.edit_text(text, parse_mode="Markdown")
        return await _handle_failed_transaction(update, context)
    except Exception as exc:
        text = f"❌ Transaction failed: {exc}"
        await processing.edit_text(text, parse_mode="Markdown")
        return await _handle_failed_transaction(update, context)

    # Show result — queue will add the next prompt
    await processing.edit_text(text, parse_mode="Markdown")

    # ── Advance the queue ─────────────────────────────────────────────────
    return await _advance_queue(update, context)


async def _handle_failed_transaction(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """
    Called after a transaction error.
    - If nothing is left in the queue → go back to main menu.
    - If more transactions are queued → ask the user whether to continue or abort.
      The answer is handled by handle_queue_continue_callback (inline button).
    """
    remaining = _queue_remaining(context)
    if remaining == 0:
        return await show_main_menu(update, context)

    # Store state: we're mid-queue after a failure, waiting for user decision
    context.user_data["queue_paused_on_error"] = True

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"▶️ Continue ({remaining} left)", callback_data="queue:continue"
            ),
            InlineKeyboardButton("🛑 Cancel rest", callback_data="queue:abort"),
        ]
    ])
    await update.message.reply_text(
        f"⚠️ The transaction above failed.\n"
        f"There {'is' if remaining == 1 else 'are'} still "
        f"*{remaining}* transaction{'s' if remaining > 1 else ''} in the queue.\n\n"
        f"What would you like to do?",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return STATE_MENU   # stay alive so the callback can fire


async def handle_queue_continue_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle the Continue / Cancel rest buttons shown after a failed transaction."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop("queue_paused_on_error", None)

    if query.data == "queue:abort":
        remaining = _queue_remaining(context)
        _queue_clear(context)
        await query.edit_message_text(
            f"🛑 Remaining {remaining} transaction{'s' if remaining != 1 else ''} cancelled.",
            parse_mode="Markdown",
        )
        return await show_main_menu(update, context)

    # queue:continue — pop and prompt for next item
    await query.edit_message_text("▶️ Continuing with next transaction…")
    return await _advance_queue(update, context)


async def _advance_queue(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """
    Pop the next item from tx_queue and prompt for its PIN,
    or return to the main menu if the queue is empty.
    """
    next_item = _queue_pop(context)
    if next_item is None:
        # All transactions processed — back to menu
        return await show_main_menu(update, context)

    # More items remain — prompt for the next one
    return await _request_pin_confirmation(
        update, context,
        tool=next_item["tool"],
        params=next_item["params"],
        source=next_item.get("source", "ai"),
    )


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

async def do_logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user_id = str(update.effective_user.id)
    _queue_clear(context)          # discard any in-flight transaction queue
    context.user_data.clear()
    await mcp_clear_history(user_id)
    await query.edit_message_text(
        "👋 *Your session has ended.*\n\nType /start to begin again.",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Free-text AI fallback (works at any state)
# ---------------------------------------------------------------------------

async def ai_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Any free-text message not consumed by a specific state → AI assistant."""
    user_text = update.message.text or ""
    user_id = str(update.effective_user.id)
    logger.info("AI fallback [%s]: %s", user_id, user_text)

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    processing = await update.message.reply_text("⏳ Thinking…")

    response = await process_message_with_ai(
        user_text, user_id=user_id, update=update, context=context
    )

    # Debit tool detected — PIN gate is already showing; delete the spinner
    if response == "__PIN_GATE__":
        await processing.delete()
        return STATE_CONFIRM_PIN

    await processing.edit_text(response)
    return STATE_MENU


# ---------------------------------------------------------------------------
# Voice handler
# ---------------------------------------------------------------------------

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    voice = update.message.voice or update.message.audio
    if not voice:
        await update.message.reply_text("⚠️ Couldn't read the audio.")
        return STATE_MENU

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    processing = await update.message.reply_text("🎙 Transcribing…")

    try:
        tg_file = await context.bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        await tg_file.download_to_drive(tmp_path)
        with open(tmp_path, "rb") as f:
            audio_bytes = f.read()
        os.unlink(tmp_path)
    except Exception as exc:
        await processing.edit_text(f"⚠️ Failed to download voice message: {exc}")
        return STATE_MENU

    try:
        transcript = await transcribe_voice(audio_bytes, mime_type="audio/ogg")
    except RuntimeError as exc:
        await processing.edit_text(f"⚠️ {exc}")
        return STATE_MENU

    if not transcript:
        await processing.edit_text("⚠️ Couldn't make out what you said.")
        return STATE_MENU

    await processing.edit_text(f'🎙 _"{transcript}"_\n\n⏳ Thinking…', parse_mode="Markdown")
    response = await process_message_with_ai(
        transcript,
        user_id=str(update.effective_user.id),
        update=update,
        context=context,
    )
    if response == "__PIN_GATE__":
        await processing.delete()
        return STATE_CONFIRM_PIN
    await processing.edit_text(
        f'🎙 _"{transcript}"_\n\n{response}', parse_mode="Markdown"
    )
    return STATE_MENU


# ---------------------------------------------------------------------------
# Main — wire everything together
# ---------------------------------------------------------------------------

def main() -> None:
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set")
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set")
    if not WEBHOOK_BASE_URL:
        raise ValueError("WEBHOOK_BASE_URL is not set")
    if not WEBHOOK_PATH:
        raise ValueError("TELEGRAM_WEBHOOK_PATH must not be empty")
    if not WEBHOOK_SECRET:
        raise ValueError("TELEGRAM_WEBHOOK_SECRET is not set")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            # ── Main menu (idle) ───────────────────────────────────────────
            STATE_MENU: [
                CallbackQueryHandler(menu_callback, pattern=r"^(menu:|back:)"),
                CallbackQueryHandler(handle_queue_continue_callback, pattern=r"^queue:"),
                MessageHandler(filters.VOICE | filters.AUDIO, handle_voice),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ai_fallback),
            ],

            # ── Transfer ───────────────────────────────────────────────────
            STATE_TRANSFER_TO: [
                CallbackQueryHandler(menu_callback, pattern=r"^back:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_got_recipient),
            ],
            STATE_TRANSFER_AMT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_got_amount),
            ],
            STATE_TRANSFER_NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_got_note),
            ],

            # ── Topup ──────────────────────────────────────────────────────
            STATE_TOPUP_TYPE: [
                CallbackQueryHandler(topup_got_type,    pattern=r"^topuptype:"),
                CallbackQueryHandler(menu_callback,     pattern=r"^back:"),
            ],
            STATE_TOPUP_NET: [
                CallbackQueryHandler(topup_got_network, pattern=r"^net:"),
                CallbackQueryHandler(menu_callback,     pattern=r"^back:"),
            ],
            STATE_TOPUP_PHONE: [
                CallbackQueryHandler(menu_callback,     pattern=r"^back:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, topup_got_phone),
            ],
            STATE_TOPUP_PLAN: [
                CallbackQueryHandler(topup_got_plan,    pattern=r"^plan:"),
                CallbackQueryHandler(menu_callback,     pattern=r"^back:"),
            ],
            STATE_TOPUP_AMT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, topup_got_amount),
            ],

            # ── PIN confirmation (gates all debits) ────────────────────────
            STATE_CONFIRM_PIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirm_pin),
            ],
        },
        fallbacks=[
            CommandHandler("start", cmd_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, ai_fallback),
        ],
        allow_reentry=True,
    )

    app.add_handler(conv)

    webhook_url = f"{WEBHOOK_BASE_URL}/{WEBHOOK_PATH}"
    logger.info(
        "Bot starting — primary: %s/%s  fallback: gemini/%s  MCP: %s  webhook: %s",
        "groq",
        GROQ_MODEL,
        GEMINI_MODEL,
        MCP_URL,
        webhook_url,
    )
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=webhook_url,
        secret_token=WEBHOOK_SECRET,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
