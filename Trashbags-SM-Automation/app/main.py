"""The web server: receives DM notifications and runs the reply pipeline (Req 2).

Endpoints:
  GET  /webhook   - Meta's verification handshake
  POST /webhook   - receives DM events, acknowledges fast, processes in background
  GET  /health        - uptime monitoring checks this (Req 7)
  POST /simulate      - run a fake DM through the whole pipeline (great for demos)
  POST /resume        - hand a paused conversation back to the bot
  GET  /chat          - browser chat UI for testing (handles any characters)
  GET  /dashboard     - human-friendly view of every conversation + AI decisions
  GET  /conversations - the same data as JSON
"""

import asyncio
import html
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from . import database, instagram
from .ai import generate_reply
from .instagram import get_sender_profile
from .config import get_settings
from .notifier import notify
from .takeover import check_takeover


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.get_connection()  # create tables on boot
    yield


app = FastAPI(title="Instagram DM Automation", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    """Uptime monitors (e.g. UptimeRobot) ping this; if it stops answering you get alerted (Req 7)."""
    return {"status": "ok"}


@app.get("/webhook")
def verify_webhook(request: Request) -> Response:
    """Meta calls this once to verify the webhook URL (Req 2)."""
    settings = get_settings()
    params = request.query_params
    if (params.get("hub.mode") == "subscribe"
            and params.get("hub.verify_token") == settings.ig_verify_token):
        return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
    return Response(content="Verification failed", status_code=403)


@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
    """Receive DM events from Meta (Req 2).

    We verify the signature, queue each message for background processing, and
    return 200 immediately — so Meta doesn't time out, and a burst of messages
    doesn't block the server.
    """
    raw = await request.body()
    if not instagram.verify_signature(raw, request.headers.get("X-Hub-Signature-256")):
        return Response(content="Bad signature", status_code=403)

    data = await request.json()
    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event.get("sender", {}).get("id")
            message = event.get("message", {})
            text = message.get("text")
            # Skip echoes (our own sent messages) and non-text events.
            if not sender_id or not text or message.get("is_echo"):
                continue
            background_tasks.add_task(handle_message, sender_id, text)

    return Response(content="EVENT_RECEIVED", media_type="text/plain")


async def handle_message(sender_id: str, text: str) -> None:
    """The core pipeline for one incoming DM: log -> AI -> takeover -> send (Req 3-6)."""
    settings = get_settings()
    database.log_message(sender_id, "incoming", text)

    # If a human has taken over this chat, the bot stays silent (Req 5).
    if database.is_paused(sender_id):
        return

    # 1. Look up the sender's profile (username + follower count) so the AI can
    #    apply affiliate thresholds without asking the customer. Returns None
    #    gracefully when no access token is configured (pre-Meta-approval).
    sender_profile = await get_sender_profile(sender_id)

    # 2. Ask the AI (with automatic fallback if it's down/slow) — Req 3
    result = await generate_reply(
        database.recent_history(sender_id), text, sender_profile=sender_profile,
        bot_message_count=database.outgoing_message_count(sender_id),
    )
    database.log_ai_response(
        sender_id, result.reply_text, result.confidence, result.needs_human,
        result.model, result.latency_ms, result.fallback_used,
    )

    # 3. Affiliate/sponsorship inquiries are the only thing a human handles — Req 5
    should_pause, reason = check_takeover(text, result.needs_human, result.reason)
    if should_pause:
        database.pause_conversation(sender_id, reason)
        await notify(
            subject=f"New affiliate/sponsorship inquiry (chat {sender_id})",
            body=(f"{reason}\n"
                  f"Customer said: {text!r}\n"
                  f"The bot is paused for this chat. POST /resume to hand it back."),
        )
        # The AI reply already points them to the affiliate page; send it promptly.
    elif not result.fallback_used:
        # Normal auto-reply: wait a random, human-like interval so it doesn't look
        # like an instant bot (configurable via RESPONSE_DELAY_*_MINUTES).
        await asyncio.sleep(settings.random_response_delay_seconds())
    # (On an AI fallback we send the holding line promptly and stay un-paused.)

    outgoing = result.reply_text

    # Business collab inquiries (>=5k followers) get no auto-reply at all —
    # the AI leaves reply_text empty and we just leave it flagged for the owner.
    if not outgoing.strip():
        return

    # 4. Send the reply, retrying on failure; alert if it never goes through — Req 4
    try:
        await instagram.send_message(sender_id, outgoing)
        database.log_message(sender_id, "outgoing", outgoing)
    except instagram.InstagramSendError as exc:
        database.log_error("send_message", str(exc))
        await notify(
            subject=f"⚠️ Couldn't send reply to {sender_id}",
            body=f"Gave up after {settings.send_max_retries} retries: {exc}",
        )


# --- Demo / ops endpoints -------------------------------------------------

class SimulatedMessage(BaseModel):
    sender_id: str = "demo_user"
    text: str
    # Optional: simulate a known sender so you can test follower-count thresholds
    # without a live Instagram account. In production these come from the Graph API.
    username: str = ""
    follower_count: int | None = None


@app.post("/simulate")
async def simulate(msg: SimulatedMessage) -> dict:
    """Run a fake DM through the AI + takeover logic WITHOUT touching Instagram.

    Perfect for the meeting demo before your Meta app is approved: you can show
    the AI replying, the confidence score, and human-takeover triggering live.
    """
    database.log_message(msg.sender_id, "incoming", msg.text)

    # Build a synthetic sender profile if follower_count was supplied directly
    # (test mode). In production this comes from get_sender_profile() in handle_message.
    sender_profile: dict | None = None
    if msg.follower_count is not None:
        sender_profile = {
            "username": msg.username or msg.sender_id,
            "follower_count": msg.follower_count,
        }

    result = await generate_reply(
        database.recent_history(msg.sender_id), msg.text, sender_profile=sender_profile,
        bot_message_count=database.outgoing_message_count(msg.sender_id),
    )
    database.log_ai_response(
        msg.sender_id, result.reply_text, result.confidence, result.needs_human,
        result.model, result.latency_ms, result.fallback_used,
    )
    should_pause, reason = check_takeover(msg.text, result.needs_human, result.reason)
    settings = get_settings()
    outgoing = result.reply_text

    # The live bot delays normal auto-replies; affiliate replies and AI fallbacks go
    # out promptly. We only REPORT the delay here so the demo/test returns instantly.
    delay_seconds = (
        0.0 if (should_pause or result.fallback_used)
        else settings.random_response_delay_seconds()
    )

    # Record the same outcome the real pipeline would, so the dashboard shows the
    # full story (bot reply + human-takeover status). We skip only the actual
    # Instagram send and the owner alert — this is still a no-network dry run.
    if should_pause:
        database.pause_conversation(msg.sender_id, reason)
    database.log_message(msg.sender_id, "outgoing", outgoing)

    return {
        "customer_message": msg.text,
        "sender_profile": sender_profile,  # None when no follower_count supplied
        "ai_reply": result.reply_text,
        "confidence": result.confidence,
        "fallback_used": result.fallback_used,
        "latency_ms": result.latency_ms,
        "human_takeover": should_pause,
        "takeover_reason": reason,
        "response_delay_minutes": round(delay_seconds / 60, 1),  # live wait; not applied in simulate
        "would_send": outgoing,
    }


class ResumeRequest(BaseModel):
    sender_id: str


@app.post("/resume")
def resume(req: ResumeRequest) -> dict:
    """Hand a paused conversation back to the bot once the human is done (Req 5)."""
    database.resume_conversation(req.sender_id)
    return {"status": "resumed", "sender_id": req.sender_id}


# --- Centralized message viewer ------------------------------------------

@app.get("/conversations")
def conversations() -> dict:
    """Every conversation with its full timeline, as JSON (Req 6)."""
    convos = database.list_conversations()
    for c in convos:
        c["timeline"] = database.conversation_timeline(c["sender_id"])
    return {"count": len(convos), "conversations": convos}


@app.get("/chat", response_class=HTMLResponse)
def chat_ui() -> HTMLResponse:
    """A simple browser chat interface for testing the bot without any JSON or terminal fuss."""
    return HTMLResponse(content=_CHAT_PAGE)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    """A single page that lists every conversation (one card per customer) with its
    transcript and the AI's decision on each message. Handy to leave open in the demo."""
    convos = database.list_conversations()
    total_messages = sum(c["message_count"] for c in convos)
    flagged = sum(1 for c in convos if c["paused"])

    cards = "".join(_render_conversation(c) for c in convos) or (
        '<p class="empty">No messages yet. Send one with the <code>/simulate</code> '
        "endpoint and refresh this page.</p>"
    )

    return HTMLResponse(content=_PAGE.format(
        conversation_count=len(convos),
        message_count=total_messages,
        flagged_count=flagged,
        cards=cards,
    ))


def _render_conversation(c: dict) -> str:
    if c["paused"]:
        status = f'<span class="badge human">🔴 Human handling — {html.escape(c["paused_reason"] or "flagged")}</span>'
    else:
        status = '<span class="badge bot">🟢 Bot active</span>'

    rows = "".join(_render_event(e) for e in database.conversation_timeline(c["sender_id"]))
    return _CARD.format(
        sender=html.escape(c["sender_id"]),
        count=c["message_count"],
        last_at=html.escape(c["last_at"]),
        status=status,
        rows=rows,
    )


def _render_event(e: dict) -> str:
    if e["kind"] == "incoming":
        return f'<div class="msg customer"><span class="who">Customer</span>{html.escape(e["text"])}</div>'
    if e["kind"] == "outgoing":
        return f'<div class="msg bot"><span class="who">Bot</span>{html.escape(e["text"])}</div>'
    # AI decision chip
    if e["fallback_used"]:
        verdict = "⏳ fallback (AI slow/down)"
    elif e["needs_human"]:
        verdict = "🚩 flagged for human"
    else:
        verdict = "✅ auto-replied"
    conf = "—" if e["confidence"] is None else f'{e["confidence"]:.2f}'
    return (f'<div class="decision">🤖 AI decision · confidence {conf} · '
            f'{verdict} · {e["latency_ms"]} ms</div>')


_CARD = """
<section class="card">
  <header>
    <div><span class="sender">👤 {sender}</span> <span class="meta">{count} messages · last {last_at}</span></div>
    {status}
  </header>
  <div class="thread">{rows}</div>
</section>
"""

_CHAT_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trashbags DM Tester</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; background: #f5f6f8; display: flex; flex-direction: column; height: 100vh; }
  header { background: #1c1e21; color: #fff; padding: 16px 20px; font-size: 16px; font-weight: 600; flex-shrink: 0; }
  header span { font-size: 12px; font-weight: 400; opacity: .6; margin-left: 10px; }
  #thread { flex: 1; overflow-y: auto; padding: 20px 16px; display: flex; flex-direction: column; gap: 10px; }
  .bubble { max-width: 70%; padding: 10px 14px; border-radius: 18px; font-size: 14px; line-height: 1.45; word-break: break-word; }
  .bubble .who { font-size: 10px; text-transform: uppercase; letter-spacing: .04em; opacity: .55; margin-bottom: 4px; }
  .customer { align-self: flex-end; background: #0866ff; color: #fff; border-bottom-right-radius: 4px; }
  .bot { align-self: flex-start; background: #fff; border: 1px solid #e4e6eb; border-bottom-left-radius: 4px; }
  .meta { align-self: flex-start; font-size: 11px; color: #8a8d91; padding: 2px 6px; }
  .flag { align-self: flex-start; background: #fde8e8; color: #b42318; font-size: 11px; padding: 4px 10px; border-radius: 999px; margin-top: -4px; }
  .typing { align-self: flex-start; color: #8a8d91; font-size: 13px; font-style: italic; }
  footer { background: #fff; border-top: 1px solid #e4e6eb; padding: 12px 16px; display: flex; flex-direction: column; gap: 8px; flex-shrink: 0; }
  .demo-row { display: flex; gap: 10px; align-items: center; }
  .demo-row label { font-size: 11px; color: #8a8d91; white-space: nowrap; }
  #followers { width: 110px; border: 1px solid #d1d5db; border-radius: 14px; padding: 6px 10px; font-size: 12px; outline: none; font-family: inherit; }
  #followers:focus { border-color: #0866ff; }
  .demo-note { font-size: 10px; color: #b0b3b8; }
  .send-row { display: flex; gap: 10px; }
  #msg { flex: 1; border: 1px solid #d1d5db; border-radius: 22px; padding: 10px 16px; font-size: 14px; outline: none; resize: none; height: 42px; line-height: 1.4; font-family: inherit; }
  #msg:focus { border-color: #0866ff; }
  #send { background: #0866ff; color: #fff; border: none; border-radius: 22px; padding: 10px 20px; font-size: 14px; font-weight: 600; cursor: pointer; white-space: nowrap; }
  #send:disabled { opacity: .5; cursor: default; }
  .empty { text-align: center; color: #b0b3b8; font-size: 13px; margin-top: 60px; }
</style>
</head>
<body>
<header>Trashbags DM Bot Tester <span>replies shown instantly (delay skipped in test mode)</span></header>
<div id="thread"><p class="empty">Type a message below and hit Send to chat with the bot.</p></div>
<footer>
  <div class="demo-row">
    <label for="followers">Simulated follower count:</label>
    <input id="followers" type="number" min="0" placeholder="e.g. 3000">
    <span class="demo-note">Demo only &mdash; live DMs pull this from Meta automatically.</span>
  </div>
  <div class="send-row">
    <textarea id="msg" placeholder="Type a customer message..." rows="1"></textarea>
    <button id="send">Send</button>
  </div>
</footer>
<script>
  const thread    = document.getElementById('thread');
  const input     = document.getElementById('msg');
  const btn       = document.getElementById('send');
  const followers = document.getElementById('followers');
  const sender = 'chat_' + Math.random().toString(36).slice(2, 8);

  function addBubble(cls, who, text) {
    const d = document.createElement('div');
    d.className = 'bubble ' + cls;
    d.innerHTML = '<span class="who">' + who + '</span>' + escHtml(text);
    thread.appendChild(d);
    thread.scrollTop = thread.scrollHeight;
    return d;
  }
  function addMeta(text, cls) {
    const d = document.createElement('div');
    d.className = cls || 'meta';
    d.textContent = text;
    thread.appendChild(d);
    thread.scrollTop = thread.scrollHeight;
  }
  function escHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
  // Remove the placeholder on first send
  function clearEmpty() {
    const e = thread.querySelector('.empty');
    if (e) e.remove();
  }

  async function send() {
    const text = input.value.trim();
    if (!text) return;
    clearEmpty();
    input.value = '';
    input.style.height = 'auto';
    btn.disabled = true;

    addBubble('customer', 'You (customer)', text);

    const typing = document.createElement('div');
    typing.className = 'typing';
    typing.textContent = 'Bot is thinking...';
    thread.appendChild(typing);
    thread.scrollTop = thread.scrollHeight;

    // Demo-only: lets you simulate a known follower count to test flagging
    // thresholds. Real DMs never send this from the browser — production
    // pulls the real follower count from the Meta Graph API server-side.
    const followerCount = followers.value.trim() ? parseInt(followers.value, 10) : null;

    try {
      const res = await fetch('/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // JSON.stringify handles all special characters automatically
        body: JSON.stringify({ sender_id: sender, text: text, follower_count: followerCount })
      });
      const data = await res.json();
      typing.remove();
      addBubble('bot', 'Trashbags bot', data.ai_reply);
      if (data.human_takeover) {
        addMeta('🚩 Flagged to owner: ' + data.takeover_reason, 'flag');
      } else {
        addMeta('Would send after ~' + data.response_delay_minutes + ' min · confidence ' + (data.confidence * 100).toFixed(0) + '%');
      }
    } catch(e) {
      typing.remove();
      addMeta('⚠️ Could not reach the bot server.', 'flag');
    }
    btn.disabled = false;
    input.focus();
  }

  btn.addEventListener('click', send);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });
  // Auto-grow textarea
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  });
</script>
</body>
</html>"""


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="15">
<title>Instagram DM Automation — Dashboard</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; background: #f5f6f8; color: #1c1e21; }}
  header.top {{ background: #1c1e21; color: #fff; padding: 18px 28px; }}
  header.top h1 {{ margin: 0; font-size: 18px; }}
  .stats {{ display: flex; gap: 28px; padding: 16px 28px; background: #fff; border-bottom: 1px solid #e4e6eb; }}
  .stats div {{ font-size: 13px; color: #65676b; }}
  .stats b {{ display: block; font-size: 22px; color: #1c1e21; }}
  main {{ padding: 24px 28px; max-width: 860px; margin: 0 auto; }}
  .card {{ background: #fff; border: 1px solid #e4e6eb; border-radius: 12px; margin-bottom: 20px; overflow: hidden; }}
  .card header {{ display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 1px solid #e4e6eb; background: #fafbfc; }}
  .sender {{ font-weight: 600; }}
  .meta {{ color: #8a8d91; font-size: 12px; margin-left: 8px; }}
  .badge {{ font-size: 12px; padding: 4px 10px; border-radius: 999px; font-weight: 600; }}
  .badge.bot {{ background: #e3f5e8; color: #1a7f37; }}
  .badge.human {{ background: #fde8e8; color: #b42318; }}
  .thread {{ padding: 16px 18px; display: flex; flex-direction: column; gap: 8px; }}
  .msg {{ max-width: 75%; padding: 9px 13px; border-radius: 14px; font-size: 14px; line-height: 1.4; }}
  .msg .who {{ display: block; font-size: 10px; text-transform: uppercase; letter-spacing: .04em; opacity: .55; margin-bottom: 3px; }}
  .msg.customer {{ align-self: flex-start; background: #eef0f2; border-bottom-left-radius: 4px; }}
  .msg.bot {{ align-self: flex-end; background: #0866ff; color: #fff; border-bottom-right-radius: 4px; }}
  .decision {{ align-self: center; font-size: 11px; color: #65676b; background: #f0f2f5; padding: 3px 10px; border-radius: 999px; }}
  .empty {{ text-align: center; color: #8a8d91; padding: 60px 0; }}
  code {{ background: #e4e6eb; padding: 1px 5px; border-radius: 4px; }}
</style>
</head>
<body>
  <header class="top"><h1>📥 Instagram DM Automation — Dashboard</h1></header>
  <div class="stats">
    <div><b>{conversation_count}</b> conversations</div>
    <div><b>{message_count}</b> messages logged</div>
    <div><b>{flagged_count}</b> flagged for a human</div>
  </div>
  <main>{cards}</main>
</body>
</html>"""
