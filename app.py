"""FastAPI app — WhatsApp webhook + simple, clean demo UI."""

from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse, HTMLResponse
import httpx
import bot
import db
from config import WA_TOKEN, WA_VERIFY_TOKEN, WA_PHONE_NUMBER_ID, MOCK_MODE

app = FastAPI(title="Tontine Lightning", version="0.1.0")


# ───── WhatsApp Webhook ─────

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """WhatsApp verification handshake."""
    if hub_mode == "subscribe" and hub_token == WA_VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    return PlainTextResponse("Forbidden", status_code=403)


@app.post("/webhook")
async def receive_webhook(request: Request):
    """Handle incoming WhatsApp messages."""
    data = await request.json()
    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        message = changes["value"]["messages"][0]
        phone = message["from"]
        text = message.get("text", {}).get("body", "")

        reply = await bot.handle_message(phone, text)
        await _send_whatsapp(phone, reply)
    except (KeyError, IndexError):
        pass  # ignore non-message events

    return {"status": "ok"}


async def _send_whatsapp(to: str, text: str):
    """Send a WhatsApp message via Cloud API."""
    if not WA_TOKEN:
        return  # skip if no token (demo mode)

    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://graph.facebook.com/v18.0/{WA_PHONE_NUMBER_ID}/messages",
            headers={"Authorization": f"Bearer {WA_TOKEN}"},
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text}
            }
        )


# ───── Clean Simple Demo UI ─────

DEMO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Tontine Lightning — Demo</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #0b141a; color: #e9edef; }
        .container { max-width: 540px; margin: 20px auto; padding: 16px; background: #111b21; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
        h1 { color: #f7931a; font-size: 22px; text-align: center; margin-bottom: 4px; display: flex; align-items: center; justify-content: center; gap: 8px; }
        .subtitle { text-align: center; color: #8696a0; font-size: 13px; margin-bottom: 16px; }
        
        .phone-section { background: #202c33; padding: 10px; border-radius: 8px; margin-bottom: 12px; }
        .phone-label { font-size: 12px; color: #8696a0; margin-bottom: 6px; font-weight: 600; }
        .phone-input { display: flex; gap: 8px; margin-bottom: 8px; }
        .phone-input input { flex: 1; padding: 8px 12px; border: 1px solid #2a3942; border-radius: 6px; background: #111b21; color: #e9edef; font-size: 14px; outline: none; }
        .member-chips { display: flex; gap: 6px; }
        .member-chip { padding: 4px 10px; border-radius: 12px; font-size: 12px; background: #2a3942; color: #e9edef; border: 1px solid #3b4a54; cursor: pointer; transition: all 0.15s; }
        .member-chip:hover, .member-chip.active { background: #005c4b; border-color: #00a884; color: #fff; }

        .quick-btns { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
        .quick-btns button { padding: 6px 12px; border: 1px solid #3b4a54; border-radius: 16px; background: #202c33; color: #e9edef; cursor: pointer; font-size: 12.5px; transition: background 0.15s; }
        .quick-btns button:hover { background: #2a3942; border-color: #f7931a; color: #f7931a; }
        .quick-btns button.primary { background: #005c4b; border-color: #00a884; color: #fff; }

        .chat { background: #0b141a; border: 1px solid #222e35; border-radius: 8px; min-height: 420px; max-height: 55vh; overflow-y: auto; padding: 16px; margin-bottom: 12px; display: flex; flex-direction: column; gap: 10px; }
        .msg { padding: 10px 14px; border-radius: 8px; max-width: 85%; font-size: 14px; white-space: pre-wrap; line-height: 1.45; word-wrap: break-word; }
        .msg.user { background: #005c4b; margin-left: auto; text-align: left; color: #e9edef; border-top-right-radius: 2px; }
        .msg.bot { background: #202c33; margin-right: auto; color: #e9edef; border-top-left-radius: 2px; }
        .msg .sender-tag { font-size: 11px; font-weight: bold; color: #8696a0; margin-bottom: 4px; display: block; }
        .msg.user .sender-tag { color: #aebac1; }

        .input-row { display: flex; gap: 8px; }
        .input-row input { flex: 1; padding: 12px 16px; border: 1px solid #2a3942; border-radius: 24px; background: #202c33; color: #e9edef; font-size: 14px; outline: none; }
        .input-row input:focus { border-color: #00a884; }
        .input-row button { padding: 12px 22px; border: none; border-radius: 24px; background: #00a884; color: #fff; font-weight: bold; cursor: pointer; transition: background 0.15s; }
        .input-row button:hover { background: #008f6f; }
        .footer-tools { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; font-size: 12px; color: #8696a0; }
        .footer-tools a { color: #f7931a; text-decoration: none; cursor: pointer; }
        .footer-tools a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1><span>🟠</span> Tontine Lightning</h1>
        <p class="subtitle">Trustless rotating savings on Bitcoin Lightning • WhatsApp Simulator</p>

        <div class="phone-section">
            <div class="phone-label">CURRENT ACTIVE SENDER (SWITCH FOR MULTI-USER DEMO):</div>
            <div class="phone-input">
                <input id="phone" value="+221771111111" placeholder="Phone number (e.g. +221771111111)" />
            </div>
            <div class="member-chips">
                <button class="member-chip active" onclick="setPhone('+221771111111', this)">Member 1 (+221...1111)</button>
                <button class="member-chip" onclick="setPhone('+221772222222', this)">Member 2 (+221...2222)</button>
                <button class="member-chip" onclick="setPhone('+221773333333', this)">Member 3 (+221...3333)</button>
            </div>
        </div>

        <div class="quick-btns">
            <button class="primary" onclick="send('hi')">👋 hi</button>
            <button onclick="send('balance')">💰 balance</button>
            <button onclick="send('fund 10000')">💳 fund 10000</button>
            <button onclick="send('create Famille 2000 weekly 3')">➕ create tontine</button>
            <button onclick="send('join 1')">👥 join 1</button>
            <button class="primary" onclick="send('pay')">⚡ pay</button>
            <button onclick="send('status')">📋 status</button>
            <button onclick="send('help')">❓ help</button>
        </div>

        <div class="chat" id="chat">
            <div class="msg bot">
                <span class="sender-tag">Tontine Bot</span>
🟠 Welcome to Tontine Lightning!
Send 'hi' to initialize your wallet, or use the quick buttons above to run the demo.
            </div>
        </div>

        <div class="input-row">
            <input id="msg" placeholder="Type a message (e.g. balance, pay, status)..." onkeydown="if(event.key==='Enter')send()" />
            <button onclick="send()">Send</button>
        </div>

        <div class="footer-tools">
            <span>FastAPI + SQLite + LNbits</span>
            <a onclick="clearChat()">Clear Chat</a>
        </div>
    </div>

    <script>
        const chat = document.getElementById('chat');

        function setPhone(num, btn) {
            document.getElementById('phone').value = num;
            document.querySelectorAll('.member-chip').forEach(c => c.classList.remove('active'));
            if (btn) btn.classList.add('active');
        }

        function clearChat() {
            chat.innerHTML = '';
        }

        function addMsg(text, cls, sender) {
            const d = document.createElement('div');
            d.className = 'msg ' + cls;
            
            const tag = document.createElement('span');
            tag.className = 'sender-tag';
            tag.textContent = sender || (cls === 'user' ? 'You' : 'Tontine Bot');
            d.appendChild(tag);

            const content = document.createElement('div');
            content.textContent = text;
            d.appendChild(content);

            chat.appendChild(d);
            chat.scrollTop = chat.scrollHeight;
        }

        async function send(text) {
            const input = document.getElementById('msg');
            const phone = document.getElementById('phone').value.trim();
            text = text || input.value.trim();
            if (!text) return;
            input.value = '';

            addMsg(text, 'user', phone);

            try {
                const r = await fetch('/sim', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({phone, text})
                });
                const data = await r.json();
                addMsg(data.reply, 'bot', 'Tontine Bot');
            } catch(e) {
                addMsg('Error: ' + e, 'bot', 'System');
            }
        }
    </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def demo_ui():
    """Serve the simple demo chat UI."""
    return DEMO_HTML


@app.post("/sim")
async def simulate(request: Request):
    """Simulator endpoint — send a message as any phone number."""
    data = await request.json()
    phone = str(data.get("phone", "+221770000000"))
    text = str(data.get("text", "hi"))
    reply = await bot.handle_message(phone, text)
    return {"reply": reply}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
