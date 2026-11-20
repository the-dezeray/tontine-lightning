"""FastAPI app — WhatsApp webhook + authentic WhatsApp Web simulator with full interactive menus."""

from __future__ import annotations

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

import bot
import db
from config import MOCK_MODE, WA_PHONE_NUMBER_ID, WA_TOKEN, WA_VERIFY_TOKEN

app = FastAPI(title="Tontine Lightning", version="0.3.0")


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

    async with httpx.AsyncClient(timeout=20.0) as client:
        await client.post(
            f"https://graph.facebook.com/v18.0/{WA_PHONE_NUMBER_ID}/messages",
            headers={"Authorization": f"Bearer {WA_TOKEN}"},
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text},
            },
        )


# ───── Helper for WhatsApp Interactive Buttons ─────


def _get_contextual_buttons(text: str, reply: str) -> list[dict]:
    """Return WhatsApp interactive quick-reply buttons based on response context."""
    t = text.lower().strip()
    r = reply.lower()

    if "welcome" in r or "interactive menu" in r or t in {"hi", "hello", "start", "menu"}:
        return [
            {"label": "💰 Check Balance", "cmd": "balance"},
            {"label": "⚡ Pay Round", "cmd": "pay"},
            {"label": "➕ Create Tontine", "cmd": "create_modal"},
            {"label": "📋 Group Status", "cmd": "status"},
        ]
    if "created!" in r or "tontine '" in r:
        return [
            {"label": "⚡ Pay Round", "cmd": "pay"},
            {"label": "📋 View Status", "cmd": "status"},
            {"label": "💰 Check Balance", "cmd": "balance"},
        ]
    if "joined tontine" in r:
        return [
            {"label": "⚡ Pay Round", "cmd": "pay"},
            {"label": "📋 View Status", "cmd": "status"},
            {"label": "💰 Check Balance", "cmd": "balance"},
        ]
    if "balance:" in r:
        return [
            {"label": "⚡ Pay Round", "cmd": "pay"},
            {"label": "💳 Fund (+10k sats)", "cmd": "fund 10000"},
            {"label": "📋 Group Status", "cmd": "status"},
            {"label": "☰ Main Menu", "cmd": "menu"},
        ]
    if "paid" in r or "all paid!" in r:
        return [
            {"label": "📋 View Status", "cmd": "status"},
            {"label": "💰 Check Balance", "cmd": "balance"},
            {"label": "☰ Main Menu", "cmd": "menu"},
        ]
    if "tontine:" in r or "round:" in r:
        return [
            {"label": "⚡ Pay Round", "cmd": "pay"},
            {"label": "💰 Check Balance", "cmd": "balance"},
            {"label": "➕ Create Another", "cmd": "create_modal"},
        ]
    if "added" in r and "sats" in r:
        return [
            {"label": "💰 Check Balance", "cmd": "balance"},
            {"label": "⚡ Pay Round", "cmd": "pay"},
            {"label": "➕ Create Tontine", "cmd": "create_modal"},
        ]
    return [
        {"label": "💰 Balance", "cmd": "balance"},
        {"label": "⚡ Pay", "cmd": "pay"},
        {"label": "📋 Status", "cmd": "status"},
        {"label": "☰ Menu", "cmd": "menu"},
    ]


# ───── WhatsApp Web UI HTML & Assets ─────

MODE_BADGE = "MOCK MODE" if MOCK_MODE else "REAL LNbits"

DEMO_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>WhatsApp — Tontine Lightning</title>
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='50' fill='%2325D366'/><path d='M50 20 L30 55 L48 55 L42 80 L70 45 L52 45 Z' fill='white'/></svg>">
    <style>
        :root {
            --wa-bg: #0c1317;
            --wa-app-bg: #111b21;
            --wa-panel-bg: #111b21;
            --wa-header-bg: #202c33;
            --wa-border: #222e35;
            --wa-hover: #202c33;
            --wa-active: #2a3942;
            --wa-bubble-in: #202c33;
            --wa-bubble-out: #005c4b;
            --wa-text-primary: #e9edef;
            --wa-text-secondary: #8696a0;
            --wa-text-muted: #667781;
            --wa-green: #00a884;
            --wa-green-bright: #25d366;
            --wa-blue-ticks: #53bdeb;
            --wa-input-bg: #2a3942;
            --wa-bitcoin: #f7931a;
            --wa-modal-bg: #1f2c34;
            --wa-button-card: #233138;
            --wa-button-hover: #2d3e47;
            --wa-shadow: rgba(11, 20, 26, 0.4);
            --wa-chat-bg: #0b141a;
            --wa-banner-bg: #182229;
        }

        body.light-theme {
            --wa-bg: #d1d7db;
            --wa-app-bg: #ffffff;
            --wa-panel-bg: #ffffff;
            --wa-header-bg: #f0f2f5;
            --wa-border: #e9edef;
            --wa-hover: #f5f6f6;
            --wa-active: #eaeef0;
            --wa-bubble-in: #ffffff;
            --wa-bubble-out: #d9fdd3;
            --wa-text-primary: #111b21;
            --wa-text-secondary: #667781;
            --wa-text-muted: #8696a0;
            --wa-green: #008069;
            --wa-green-bright: #25d366;
            --wa-blue-ticks: #53bdeb;
            --wa-input-bg: #f0f2f5;
            --wa-bitcoin: #d97706;
            --wa-modal-bg: #ffffff;
            --wa-button-card: #f0f2f5;
            --wa-button-hover: #e4e7ea;
            --wa-shadow: rgba(0, 0, 0, 0.15);
            --wa-chat-bg: #efeae2;
            --wa-banner-bg: #ffeecd;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        html, body { height: 100%; width: 100%; overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: var(--wa-bg); color: var(--wa-text-primary); }

        /* Top ribbon for desktop WhatsApp Web */
        .app-ribbon {
            position: absolute; top: 0; left: 0; width: 100%; height: 127px;
            background: var(--wa-green); z-index: 0;
        }

        /* App container */
        .app-layout {
            position: relative; z-index: 1; display: flex; width: 100%; height: 100%;
            max-width: 1600px; margin: 0 auto; background: var(--wa-app-bg);
            box-shadow: 0 6px 18px var(--wa-shadow);
        }

        @media (min-width: 1400px) {
            .app-layout { height: calc(100% - 38px); top: 19px; border-radius: 4px; overflow: hidden; }
        }

        /* ───── Left Sidebar (Chats & Personas) ───── */
        .sidebar {
            width: 400px; min-width: 340px; height: 100%; border-right: 1px solid var(--wa-border);
            display: flex; flex-direction: column; background: var(--wa-panel-bg); flex-shrink: 0;
            transition: transform 0.3s ease;
        }

        .sidebar-header {
            height: 60px; padding: 10px 16px; background: var(--wa-header-bg);
            display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--wa-border);
        }

        .user-avatar-wrap {
            display: flex; align-items: center; gap: 12px; cursor: pointer;
        }

        .user-avatar {
            width: 40px; height: 40px; border-radius: 50%; background: #00a884;
            display: flex; align-items: center; justify-content: center; font-weight: 600;
            color: #fff; font-size: 15px; position: relative;
        }

        .user-avatar .status-dot {
            position: absolute; bottom: 0; right: 0; width: 11px; height: 11px;
            background: var(--wa-green-bright); border: 2px solid var(--wa-header-bg); border-radius: 50%;
        }

        .user-info-text { display: flex; flex-direction: column; }
        .user-name-title { font-size: 14px; font-weight: 600; color: var(--wa-text-primary); }
        .user-phone-sub { font-size: 12px; color: var(--wa-text-secondary); }

        .header-actions { display: flex; align-items: center; gap: 6px; }
        .icon-btn {
            width: 40px; height: 40px; border-radius: 50%; border: none; background: transparent;
            color: var(--wa-text-secondary); display: flex; align-items: center; justify-content: center;
            cursor: pointer; transition: background 0.2s, color 0.2s; position: relative;
        }
        .icon-btn:hover { background: var(--wa-hover); color: var(--wa-text-primary); }
        .icon-btn svg { width: 22px; height: 22px; fill: currentColor; }

        /* Search Bar */
        .search-box-wrap {
            padding: 8px 14px; background: var(--wa-panel-bg); border-bottom: 1px solid var(--wa-border);
        }
        .search-input-pill {
            display: flex; align-items: center; background: var(--wa-input-bg);
            border-radius: 8px; padding: 6px 12px; gap: 10px;
        }
        .search-input-pill svg { width: 18px; height: 18px; fill: var(--wa-text-muted); flex-shrink: 0; }
        .search-input-pill input {
            border: none; background: transparent; color: var(--wa-text-primary); width: 100%;
            font-size: 13.5px; outline: none;
        }

        /* Filter Chips */
        .filter-chips {
            display: flex; gap: 8px; padding: 8px 14px 10px; border-bottom: 1px solid var(--wa-border);
            overflow-x: auto; scrollbar-width: none;
        }
        .filter-chips::-webkit-scrollbar { display: none; }
        .chip {
            padding: 5px 12px; border-radius: 16px; font-size: 12px; background: var(--wa-hover);
            color: var(--wa-text-secondary); border: none; cursor: pointer; white-space: nowrap; font-weight: 500;
        }
        .chip.active { background: #005c4b; color: #fff; }
        
        /* Status/Stories Section */
        .status-section {
            padding: 12px 14px; border-bottom: 1px solid var(--wa-border);
            overflow-x: auto; scrollbar-width: none;
        }
        .status-section::-webkit-scrollbar { display: none; }
        .status-stories {
            display: flex; gap: 12px;
        }
        .status-item {
            display: flex; flex-direction: column; align-items: center; gap: 4px; cursor: pointer;
            min-width: 60px;
        }
        .status-avatar {
            width: 52px; height: 52px; border-radius: 50%; position: relative;
            border: 2.5px solid var(--wa-green-bright); padding: 2px; background: var(--wa-panel-bg);
        }
        .status-avatar img {
            width: 100%; height: 100%; border-radius: 50%; object-fit: cover;
            background: linear-gradient(135deg, #667781, #8696a0);
        }
        .status-name {
            font-size: 11px; color: var(--wa-text-secondary); text-align: center;
            max-width: 60px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }

        /* Chats List */
        .chats-list { flex: 1; overflow-y: auto; }
        .section-label {
            padding: 10px 16px 6px; font-size: 11px; font-weight: 700; color: var(--wa-text-muted);
            text-transform: uppercase; letter-spacing: 0.6px;
        }

        .chat-item {
            display: flex; align-items: center; padding: 12px 16px; gap: 14px; cursor: pointer;
            border-bottom: 1px solid rgba(255,255,255,0.03); transition: background 0.15s;
        }
        .chat-item:hover { background: var(--wa-hover); }
        .chat-item.active { background: var(--wa-active); }

        .chat-avatar {
            width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center;
            justify-content: center; font-weight: bold; font-size: 18px; flex-shrink: 0; color: #fff;
            position: relative;
        }
        .chat-avatar.bot { background: linear-gradient(135deg, #f7931a, #e67e22); box-shadow: 0 2px 8px rgba(247,147,26,0.3); }
        .chat-avatar.user1 { background: #00a884; }
        .chat-avatar.user2 { background: #3498db; }
        .chat-avatar.user3 { background: #9b59b6; }
        .chat-avatar.user4 { background: #e74c3c; }

        .chat-details { flex: 1; min-width: 0; }
        .chat-title-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
        .chat-title {
            font-size: 15px; font-weight: 600; color: var(--wa-text-primary);
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: flex; align-items: center; gap: 5px;
        }
        .verified-badge { color: var(--wa-green-bright); display: inline-flex; align-items: center; }
        .verified-badge svg { width: 15px; height: 15px; fill: currentColor; }

        .chat-time { font-size: 12px; color: var(--wa-text-muted); white-space: nowrap; }
        .chat-snippet-row { display: flex; justify-content: space-between; align-items: center; }
        .chat-snippet {
            font-size: 13px; color: var(--wa-text-secondary); white-space: nowrap;
            overflow: hidden; text-overflow: ellipsis;
        }
        .unread-badge {
            background: var(--wa-green); color: #fff; font-size: 11px; font-weight: bold;
            padding: 2px 7px; border-radius: 10px; min-width: 18px; text-align: center;
        }
        .pin-icon { color: var(--wa-text-muted); font-size: 13px; }

        /* Custom Phone Input bar in Sidebar */
        .custom-phone-card {
            padding: 12px 16px; background: rgba(0,0,0,0.15); border-top: 1px solid var(--wa-border);
        }
        .custom-phone-title { font-size: 12px; color: var(--wa-text-muted); margin-bottom: 6px; font-weight: 600; }
        .custom-phone-input-row { display: flex; gap: 6px; }
        .custom-phone-input-row input {
            flex: 1; padding: 8px 10px; border-radius: 6px; border: 1px solid var(--wa-border);
            background: var(--wa-input-bg); color: var(--wa-text-primary); font-size: 13px; outline: none;
        }
        .custom-phone-input-row button {
            padding: 8px 14px; border-radius: 6px; border: none; background: var(--wa-green);
            color: #fff; font-weight: 600; font-size: 12px; cursor: pointer;
        }

        /* ───── Right Chat Area ───── */
        .chat-area {
            flex: 1; display: flex; flex-direction: column; height: 100%; position: relative;
            background: var(--wa-chat-bg);
        }

        /* WhatsApp Doodle pattern overlay */
        .chat-doodle-bg {
            position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 0; pointer-events: none;
            opacity: 0.06;
            background-image: radial-gradient(circle at 10px 10px, #fff 1.5px, transparent 0), radial-gradient(circle at 40px 40px, #fff 1.5px, transparent 0);
            background-size: 60px 60px;
        }
        body.light-theme .chat-doodle-bg { opacity: 0.12; filter: invert(1); }

        /* Chat Header */
        .chat-header {
            height: 60px; padding: 10px 16px; background: var(--wa-header-bg);
            border-bottom: 1px solid var(--wa-border); display: flex; align-items: center;
            justify-content: space-between; z-index: 2; flex-shrink: 0;
        }

        .chat-contact-info {
            display: flex; align-items: center; gap: 12px; cursor: pointer;
        }

        .back-btn-mobile {
            display: none; border: none; background: transparent; color: var(--wa-text-primary);
            padding: 6px; cursor: pointer; margin-right: 4px;
        }
        .back-btn-mobile svg { width: 22px; height: 22px; fill: currentColor; }

        .chat-header-avatar {
            width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg, #f7931a, #e67e22);
            display: flex; align-items: center; justify-content: center; font-size: 18px; color: #fff; font-weight: bold;
        }

        .chat-header-meta { display: flex; flex-direction: column; }
        .chat-header-name {
            font-size: 15px; font-weight: 600; color: var(--wa-text-primary); display: flex; align-items: center; gap: 6px;
        }
        .mode-pill {
            font-size: 10px; font-weight: 700; background: var(--wa-bitcoin); color: #000;
            padding: 1px 7px; border-radius: 10px; text-transform: uppercase; letter-spacing: 0.5px;
        }
        .chat-header-status { font-size: 12px; color: var(--wa-text-secondary); }
        .chat-header-status.typing { color: var(--wa-green-bright); font-weight: 600; }

        /* Top Demo Progress Banner (during 1-click walkthrough) */
        .demo-step-banner {
            display: none; background: #005c4b; color: #fff; padding: 8px 16px; font-size: 13px;
            font-weight: 500; align-items: center; justify-content: space-between; z-index: 2;
            border-bottom: 1px solid rgba(0,0,0,0.2); animation: fadeIn 0.3s;
        }
        .demo-step-banner.active { display: flex; }
        .demo-step-progress { display: flex; align-items: center; gap: 8px; }
        .demo-spinner {
            width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.4);
            border-top-color: #fff; border-radius: 50%; animation: spin 0.8s linear infinite;
        }
        .demo-stop-btn {
            background: rgba(0,0,0,0.3); border: none; color: #fff; padding: 3px 10px;
            border-radius: 12px; font-size: 11px; cursor: pointer;
        }

        /* Messages Container */
        .chat-messages {
            flex: 1; overflow-y: auto; padding: 16px 24px; position: relative; z-index: 1;
            display: flex; flex-direction: column; gap: 8px;
        }

        /* WhatsApp Encryption & Date pills */
        .sys-badge-wrap { display: flex; justify-content: center; margin: 6px 0 10px; }
        .encryption-pill {
            background: var(--wa-banner-bg); color: var(--wa-text-secondary); font-size: 12px;
            padding: 8px 16px; border-radius: 8px; text-align: center; max-width: 480px;
            line-height: 1.4; box-shadow: 0 1px 2px rgba(0,0,0,0.15); display: flex; align-items: center; gap: 8px;
        }
        .encryption-pill svg { width: 14px; height: 14px; fill: #ffd279; flex-shrink: 0; }
        .date-pill {
            background: var(--wa-header-bg); color: var(--wa-text-secondary); font-size: 11.5px;
            padding: 4px 12px; border-radius: 8px; font-weight: 600; letter-spacing: 0.3px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }

        /* Message Bubbles */
        .msg-row { display: flex; width: 100%; position: relative; margin-bottom: 4px; animation: popIn 0.2s ease-out; }
        .msg-row.out { justify-content: flex-end; }
        .msg-row.in { justify-content: flex-start; }

        .bubble {
            max-width: 82%; min-width: 120px; padding: 8px 12px 6px; border-radius: 8px;
            position: relative; line-height: 1.45; font-size: 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.25);
            word-wrap: break-word; white-space: pre-wrap;
        }
        .msg-row.out .bubble {
            background: var(--wa-bubble-out); color: var(--wa-text-primary); border-top-right-radius: 0;
        }
        .msg-row.in .bubble {
            background: var(--wa-bubble-in); color: var(--wa-text-primary); border-top-left-radius: 0;
        }

        .bubble-text { margin-bottom: 4px; }
        .bubble-text b, .bubble-text strong { font-weight: 700; color: #fff; }
        body.light-theme .bubble-text b, body.light-theme .bubble-text strong { color: #111; }
        .bubble-text code {
            font-family: SFMono-Regular, Consolas, Monaco, monospace; font-size: 12.5px;
            background: rgba(0,0,0,0.25); padding: 2px 5px; border-radius: 4px;
        }

        .bubble-meta {
            display: flex; align-items: center; justify-content: flex-end; gap: 4px;
            font-size: 11px; color: var(--wa-text-secondary); user-select: none; margin-top: 2px;
        }
        .single-tick svg, .double-tick svg { width: 15px; height: 15px; fill: var(--wa-text-secondary); }
        .blue-ticks svg { width: 15px; height: 15px; fill: var(--wa-blue-ticks); }
        
        /* Message Actions (Reply, React, Forward, Delete) */
        .msg-actions {
            position: absolute; top: -30px; right: 10px; background: var(--wa-modal-bg);
            border: 1px solid var(--wa-border); border-radius: 8px; padding: 4px;
            display: none; flex-direction: row; gap: 2px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 30; animation: popIn 0.15s ease-out;
        }
        .msg-row:hover .msg-actions { display: flex; }
        .msg-action-btn {
            width: 32px; height: 32px; border: none; background: transparent;
            color: var(--wa-text-secondary); cursor: pointer; border-radius: 6px;
            display: flex; align-items: center; justify-content: center; transition: all 0.15s;
        }
        .msg-action-btn:hover { background: var(--wa-hover); color: var(--wa-text-primary); }
        .msg-action-btn svg { width: 16px; height: 16px; fill: currentColor; }
        
        /* Message Reactions */
        .msg-reaction {
            position: absolute; bottom: -8px; right: 8px; background: var(--wa-panel-bg);
            border: 2px solid var(--wa-chat-bg); border-radius: 12px; padding: 2px 8px;
            font-size: 12px; display: flex; align-items: center; gap: 3px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2); cursor: pointer;
            transition: transform 0.1s; z-index: 5;
        }
        .msg-reaction:hover { transform: scale(1.1); }
        .msg-row.out .msg-reaction { right: auto; left: 8px; }
        
        /* Reply Preview inside bubble */
        .reply-preview {
            background: rgba(0,0,0,0.15); border-left: 3px solid var(--wa-green);
            padding: 6px 10px; border-radius: 6px; margin-bottom: 6px; font-size: 12.5px;
            cursor: pointer; transition: background 0.15s;
        }
        .reply-preview:hover { background: rgba(0,0,0,0.25); }
        .reply-author { font-weight: 600; color: var(--wa-green); margin-bottom: 2px; }
        .reply-text { color: var(--wa-text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        
        /* Voice Message */
        .voice-msg {
            display: flex; align-items: center; gap: 10px; padding: 8px 0;
        }
        .voice-play-btn {
            width: 36px; height: 36px; border-radius: 50%; background: var(--wa-green);
            border: none; color: #fff; display: flex; align-items: center; justify-content: center;
            cursor: pointer; flex-shrink: 0; transition: transform 0.1s;
        }
        .voice-play-btn:active { transform: scale(0.9); }
        .voice-play-btn svg { width: 16px; height: 16px; fill: #fff; }
        .voice-waveform {
            flex: 1; height: 24px; display: flex; align-items: center; gap: 2px;
        }
        .voice-bar {
            width: 3px; background: var(--wa-text-secondary); border-radius: 2px;
            transition: height 0.3s;
        }
        .voice-duration { font-size: 12px; color: var(--wa-text-secondary); white-space: nowrap; }

        /* Interactive Action Buttons attached to Bot Messages */
        .wa-button-group {
            display: flex; flex-direction: column; gap: 4px; margin-top: 8px; border-top: 1px solid rgba(255,255,255,0.08);
            padding-top: 6px;
        }
        .wa-action-btn {
            background: var(--wa-button-card); border: none; color: var(--wa-green-bright);
            font-size: 13.5px; font-weight: 600; padding: 9px 14px; border-radius: 6px;
            cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px;
            transition: background 0.15s, transform 0.05s; width: 100%;
        }
        .wa-action-btn:hover { background: var(--wa-button-hover); }
        .wa-action-btn:active { transform: scale(0.98); }

        /* Quick Action Bar (Horizontal scrolling pills above input) */
        .quick-actions-bar {
            padding: 8px 16px; background: var(--wa-header-bg); border-top: 1px solid var(--wa-border);
            display: flex; gap: 8px; overflow-x: auto; scrollbar-width: none; z-index: 2; flex-shrink: 0;
        }
        .quick-actions-bar::-webkit-scrollbar { display: none; }
        .action-chip {
            padding: 6px 14px; border-radius: 18px; border: 1px solid var(--wa-border);
            background: var(--wa-input-bg); color: var(--wa-text-primary); font-size: 12.5px;
            font-weight: 500; cursor: pointer; white-space: nowrap; display: flex; align-items: center;
            gap: 6px; transition: all 0.2s;
        }
        .action-chip:hover { border-color: var(--wa-green); color: var(--wa-green-bright); background: var(--wa-hover); }
        .action-chip.primary { background: #005c4b; border-color: #005c4b; color: #fff; font-weight: 600; }
        .action-chip.primary:hover { background: #007a63; }

        /* Bottom Input Bar */
        .chat-input-bar {
            height: 62px; padding: 8px 16px; background: var(--wa-header-bg);
            border-top: 1px solid var(--wa-border); display: flex; align-items: center; gap: 10px;
            z-index: 2; flex-shrink: 0; position: relative;
        }
        .input-pill {
            flex: 1; height: 42px; background: var(--wa-input-bg); border-radius: 21px;
            display: flex; align-items: center; padding: 0 16px; gap: 8px;
        }
        .input-pill input {
            flex: 1; border: none; background: transparent; color: var(--wa-text-primary);
            font-size: 14.5px; outline: none;
        }
        .send-btn-circle {
            width: 44px; height: 44px; border-radius: 50%; border: none; background: var(--wa-green);
            color: #fff; display: flex; align-items: center; justify-content: center; cursor: pointer;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3); transition: transform 0.1s, background 0.2s;
        }
        .send-btn-circle:hover { background: #008f6f; }
        .send-btn-circle:active { transform: scale(0.92); }
        .send-btn-circle svg { width: 20px; height: 20px; fill: #fff; }

        /* Typing indicator bubble */
        .typing-bubble {
            display: none; align-items: center; gap: 4px; padding: 10px 16px;
            background: var(--wa-bubble-in); border-radius: 12px; width: fit-content;
            margin-bottom: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.2);
        }
        .typing-bubble.active { display: flex; }
        .typing-dot {
            width: 7px; height: 7px; background: var(--wa-text-secondary); border-radius: 50%;
            animation: bounce 1.3s infinite;
        }
        .typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .typing-dot:nth-child(3) { animation-delay: 0.4s; }

        /* ───── Popups & WhatsApp Interactive Modals ───── */

        /* Slash Command Auto-complete Box */
        .slash-popup {
            position: absolute; bottom: 70px; left: 16px; right: 16px; max-width: 440px;
            background: var(--wa-modal-bg); border: 1px solid var(--wa-border); border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.4); display: none; flex-direction: column;
            overflow: hidden; z-index: 10; animation: slideUp 0.15s ease-out;
        }
        .slash-popup.active { display: flex; }
        .slash-item {
            padding: 10px 16px; display: flex; align-items: center; justify-content: space-between;
            cursor: pointer; border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .slash-item:hover { background: var(--wa-hover); }
        .slash-cmd { font-weight: 600; color: var(--wa-green-bright); font-size: 14px; }
        .slash-desc { font-size: 12px; color: var(--wa-text-secondary); }

        /* Attachment Popover (+ / Paperclip) */
        .attach-popup {
            position: absolute; bottom: 72px; left: 60px; background: var(--wa-modal-bg);
            border: 1px solid var(--wa-border); border-radius: 14px; padding: 12px;
            display: none; grid-template-columns: repeat(3, 1fr); gap: 14px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5); z-index: 10; animation: popIn 0.2s ease-out;
        }
        .attach-popup.active { display: grid; }
        .attach-item {
            display: flex; flex-direction: column; align-items: center; gap: 6px; cursor: pointer;
            padding: 8px; border-radius: 8px; transition: background 0.15s;
        }
        .attach-item:hover { background: var(--wa-hover); }
        .attach-icon-circle {
            width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center;
            justify-content: center; font-size: 22px; color: #fff;
        }
        .attach-label { font-size: 11.5px; font-weight: 500; color: var(--wa-text-secondary); }

        /* Emoji Tray */
        .emoji-popup {
            position: absolute; bottom: 72px; left: 16px; background: var(--wa-modal-bg);
            border: 1px solid var(--wa-border); border-radius: 12px; padding: 10px;
            display: none; grid-template-columns: repeat(6, 1fr); gap: 8px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5); z-index: 10;
        }
        .emoji-popup.active { display: grid; }
        .emoji-btn {
            font-size: 24px; padding: 6px; background: transparent; border: none; cursor: pointer;
            border-radius: 6px; display: flex; align-items: center; justify-content: center;
        }
        .emoji-btn:hover { background: var(--wa-hover); }

        /* 3-Dots Options Menu */
        .options-menu {
            position: absolute; top: 60px; right: 16px; width: 230px; background: var(--wa-modal-bg);
            border: 1px solid var(--wa-border); border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,0.4);
            display: none; flex-direction: column; padding: 6px 0; z-index: 20; animation: fadeIn 0.15s;
        }
        .options-menu.active { display: flex; }
        .menu-row {
            padding: 10px 18px; font-size: 13.5px; color: var(--wa-text-primary); cursor: pointer;
            display: flex; align-items: center; gap: 10px; transition: background 0.15s;
        }
        .menu-row:hover { background: var(--wa-hover); color: var(--wa-green-bright); }
        .menu-divider { height: 1px; background: var(--wa-border); margin: 4px 0; }

        /* ───── Modal Overlays (Full WhatsApp Interactive Menu, Forms) ───── */
        .modal-overlay {
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.65); z-index: 50; display: none; align-items: center;
            justify-content: center; padding: 16px; backdrop-filter: blur(2px);
        }
        .modal-overlay.active { display: flex; }

        .modal-sheet {
            width: 100%; max-width: 480px; max-height: 90vh; background: var(--wa-modal-bg);
            border: 1px solid var(--wa-border); border-radius: 14px; display: flex; flex-direction: column;
            overflow: hidden; box-shadow: 0 16px 40px rgba(0,0,0,0.6); animation: slideUp 0.25s ease-out;
        }

        .modal-header {
            padding: 14px 20px; background: var(--wa-header-bg); border-bottom: 1px solid var(--wa-border);
            display: flex; align-items: center; justify-content: space-between;
        }
        .modal-title { font-size: 16px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
        .close-modal-btn {
            background: transparent; border: none; color: var(--wa-text-secondary); cursor: pointer;
            font-size: 20px; line-height: 1; padding: 4px;
        }
        .close-modal-btn:hover { color: var(--wa-text-primary); }

        .modal-body { padding: 18px 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; }

        /* Form elements inside modals */
        .form-group { display: flex; flex-direction: column; gap: 6px; }
        .form-label { font-size: 13px; font-weight: 600; color: var(--wa-text-secondary); }
        .form-input {
            padding: 11px 14px; border-radius: 8px; border: 1px solid var(--wa-border);
            background: var(--wa-input-bg); color: var(--wa-text-primary); font-size: 14px; outline: none;
        }
        .form-input:focus { border-color: var(--wa-green); }

        .chips-selector { display: flex; flex-wrap: wrap; gap: 8px; }
        .preset-chip {
            padding: 7px 14px; border-radius: 16px; border: 1px solid var(--wa-border);
            background: var(--wa-hover); color: var(--wa-text-primary); font-size: 12.5px;
            cursor: pointer; transition: all 0.15s; font-weight: 500;
        }
        .preset-chip:hover { border-color: var(--wa-green); }
        .preset-chip.active { background: #005c4b; color: #fff; border-color: #005c4b; }

        .calc-preview {
            font-size: 12.5px; color: var(--wa-bitcoin); background: rgba(247,147,26,0.1);
            padding: 8px 12px; border-radius: 8px; border-left: 3px solid var(--wa-bitcoin);
        }

        .modal-footer {
            padding: 12px 20px; background: var(--wa-header-bg); border-top: 1px solid var(--wa-border);
            display: flex; justify-content: flex-end; gap: 10px;
        }
        .modal-btn {
            padding: 10px 18px; border-radius: 20px; font-size: 13.5px; font-weight: 600; cursor: pointer;
            border: none; transition: background 0.15s;
        }
        .modal-btn.secondary { background: var(--wa-hover); color: var(--wa-text-primary); }
        .modal-btn.primary { background: var(--wa-green); color: #fff; }
        .modal-btn.primary:hover { background: #008f6f; }

        /* Interactive Menu List Picker Sections */
        .menu-section-header {
            font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--wa-text-muted);
            letter-spacing: 0.5px; margin-top: 6px;
        }
        .menu-list-item {
            display: flex; align-items: center; justify-content: space-between; padding: 12px 14px;
            border-radius: 10px; background: var(--wa-button-card); cursor: pointer;
            border: 1px solid transparent; transition: all 0.15s;
        }
        .menu-list-item:hover {
            background: var(--wa-button-hover); border-color: var(--wa-green); transform: translateY(-1px);
        }
        .menu-item-left { display: flex; align-items: center; gap: 12px; }
        .menu-item-icon { font-size: 20px; }
        .menu-item-text { display: flex; flex-direction: column; }
        .menu-item-title { font-size: 14px; font-weight: 600; color: var(--wa-text-primary); }
        .menu-item-desc { font-size: 12px; color: var(--wa-text-secondary); }
        .menu-item-arrow { color: var(--wa-text-muted); font-size: 14px; }

        /* Animations */
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes popIn { from { opacity: 0; transform: scale(0.96); } to { opacity: 1; transform: scale(1); } }
        @keyframes slideUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes bounce { 0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; } 40% { transform: scale(1); opacity: 1; } }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* Responsive Mobile Styles */
        @media (max-width: 768px) {
            .app-ribbon { display: none; }
            .sidebar { width: 100%; position: absolute; z-index: 10; top: 0; left: 0; }
            .sidebar.hidden-mobile { transform: translateX(-100%); }
            .back-btn-mobile { display: block; }
            .chat-area { width: 100%; }
            .bubble { max-width: 90%; }
            .quick-actions-bar { padding: 6px 10px; gap: 6px; }
            .action-chip { padding: 5px 10px; font-size: 11.5px; }
            .msg-actions { top: -25px; }
            .msg-action-btn { width: 28px; height: 28px; }
            .status-section { padding: 8px 10px; }
            .filter-chips { padding: 6px 10px; }
        }
        
        /* Swipe gesture indicator */
        .swipe-indicator {
            position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%);
            background: rgba(0,0,0,0.7); color: #fff; padding: 8px 16px;
            border-radius: 20px; font-size: 12px; display: none; z-index: 100;
            animation: fadeIn 0.3s;
        }
        .swipe-indicator.active { display: block; }
    </style>
</head>
<body>
    <div class="app-ribbon"></div>

    <div class="app-layout">
        <!-- ───── Left Sidebar (Chats & Personas) ───── -->
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <div class="user-avatar-wrap" onclick="togglePersonaPicker()" title="Current Active WhatsApp User">
                    <div class="user-avatar" id="currentAvatar">FD<div class="status-dot"></div></div>
                    <div class="user-info-text">
                        <span class="user-name-title" id="currentName">Fatou Diop</span>
                        <span class="user-phone-sub" id="currentPhone">+221771234567</span>
                    </div>
                </div>
                <div class="header-actions">
                    <button class="icon-btn" onclick="openInteractiveMenu()" title="WhatsApp Menu">
                        <svg viewBox="0 0 24 24"><path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/></svg>
                    </button>
                    <button class="icon-btn" onclick="runOneClickDemo()" title="Run 1-Click Multi-Member Demo">
                        <svg viewBox="0 0 24 24"><path d="M7 2v11h3v9l7-12h-4l4-8z"/></svg>
                    </button>
                    <button class="icon-btn" onclick="toggleOptionsMenu()" title="Menu options">
                        <svg viewBox="0 0 24 24"><path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"/></svg>
                    </button>
                </div>
            </div>

            <!-- Search box -->
            <div class="search-box-wrap">
                <div class="search-input-pill">
                    <svg viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
                    <input id="searchInput" placeholder="Search or start new chat" oninput="filterChatList()" />
                </div>
            </div>

            <!-- Status/Stories Section (WhatsApp-like) -->
            <div class="status-section">
                <div class="status-stories">
                    <div class="status-item" onclick="showStatusModal()">
                        <div class="status-avatar">
                            <img src="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='50' fill='%2325D366'/><path d='M50 20 L30 55 L48 55 L42 80 L70 45 L52 45 Z' fill='white'/></svg>" />
                        </div>
                        <div class="status-name">My Status</div>
                    </div>
                    <div class="status-item">
                        <div class="status-avatar" style="border-color: var(--wa-text-muted);">
                            <img src="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='50' fill='%23667781'/></svg>" />
                        </div>
                        <div class="status-name">Fatou</div>
                    </div>
                    <div class="status-item">
                        <div class="status-avatar" style="border-color: var(--wa-text-muted);">
                            <img src="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='50' fill='%233498db'/></svg>" />
                        </div>
                        <div class="status-name">Moussa</div>
                    </div>
                </div>
            </div>

            <!-- Filter Chips -->
            <div class="filter-chips">
                <button class="chip active" onclick="setFilter(this, 'all')">All</button>
                <button class="chip" onclick="setFilter(this, 'unread')">Unread</button>
                <button class="chip" onclick="setFilter(this, 'groups')">Tontines</button>
                <button class="chip" onclick="setFilter(this, 'members')">Members</button>
            </div>

            <!-- Chats List -->
            <div class="chats-list" id="chatsList">
                <div class="section-label">Official Bot</div>
                <!-- Primary Bot Chat -->
                <div class="chat-item active" onclick="selectBotChat()">
                    <div class="chat-avatar bot">⚡</div>
                    <div class="chat-details">
                        <div class="chat-title-row">
                            <span class="chat-title">
                                Tontine Lightning
                                <span class="verified-badge" title="Official Verified WhatsApp Business Bot">
                                    <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                                </span>
                            </span>
                            <span class="chat-time" id="botLastTime">Now</span>
                        </div>
                        <div class="chat-snippet-row">
                            <span class="chat-snippet" id="botLastSnippet">Tap to manage savings group...</span>
                            <span class="unread-badge">BOT</span>
                        </div>
                    </div>
                </div>

                <div class="section-label">Switch Member Persona</div>
                <!-- Member 1: Fatou Diop -->
                <div class="chat-item" onclick="switchPersona('+221771234567', 'Fatou Diop', 'FD', 'user1')">
                    <div class="chat-avatar user1">FD</div>
                    <div class="chat-details">
                        <div class="chat-title-row">
                            <span class="chat-title">🇸🇳 Fatou Diop (Admin)</span>
                            <span class="chat-time">+221...4567</span>
                        </div>
                        <div class="chat-snippet-row">
                            <span class="chat-snippet">Group initiator • Creator</span>
                            <span class="pin-icon">📌</span>
                        </div>
                    </div>
                </div>

                <!-- Member 2: Moussa Sow -->
                <div class="chat-item" onclick="switchPersona('+221772345678', 'Moussa Sow', 'MS', 'user2')">
                    <div class="chat-avatar user2">MS</div>
                    <div class="chat-details">
                        <div class="chat-title-row">
                            <span class="chat-title">🇸🇳 Moussa Sow</span>
                            <span class="chat-time">+221...5678</span>
                        </div>
                        <div class="chat-snippet-row">
                            <span class="chat-snippet">Tontine member #2</span>
                        </div>
                    </div>
                </div>

                <!-- Member 3: Awa Ndiaye -->
                <div class="chat-item" onclick="switchPersona('+221773456789', 'Awa Ndiaye', 'AN', 'user3')">
                    <div class="chat-avatar user3">AN</div>
                    <div class="chat-details">
                        <div class="chat-title-row">
                            <span class="chat-title">🇸🇳 Awa Ndiaye</span>
                            <span class="chat-time">+221...6789</span>
                        </div>
                        <div class="chat-snippet-row">
                            <span class="chat-snippet">Tontine member #3</span>
                        </div>
                    </div>
                </div>

                <!-- Member 4: Ousmane Ba -->
                <div class="chat-item" onclick="switchPersona('+221774567890', 'Ousmane Ba', 'OB', 'user4')">
                    <div class="chat-avatar user4">OB</div>
                    <div class="chat-details">
                        <div class="chat-title-row">
                            <span class="chat-title">🇸🇳 Ousmane Ba</span>
                            <span class="chat-time">+221...7890</span>
                        </div>
                        <div class="chat-snippet-row">
                            <span class="chat-snippet">Tontine member #4</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Custom Phone input -->
            <div class="custom-phone-card">
                <div class="custom-phone-title">Use Custom Phone Number</div>
                <div class="custom-phone-input-row">
                    <input id="customPhoneInput" placeholder="+221..." value="+221771234567" />
                    <button onclick="applyCustomPhone()">Switch</button>
                </div>
            </div>
        </aside>

        <!-- ───── Right Main Chat Area ───── -->
        <main class="chat-area">
            <div class="chat-doodle-bg"></div>

            <!-- Chat Header -->
            <div class="chat-header">
                <div class="chat-contact-info" onclick="openBotInfoModal()">
                    <button class="back-btn-mobile" onclick="toggleSidebarMobile()" title="Back to chats">
                        <svg viewBox="0 0 24 24"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
                    </button>
                    <div class="chat-header-avatar">⚡</div>
                    <div class="chat-header-meta">
                        <div class="chat-header-name">
                            Tontine Lightning
                            <span class="verified-badge">
                                <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                            </span>
                            <span class="mode-pill">__MODE_BADGE__</span>
                        </div>
                        <div class="chat-header-status" id="headerStatus">Official WhatsApp Bot • online</div>
                    </div>
                </div>

                <div class="header-actions">
                    <button class="icon-btn" onclick="openInteractiveMenu()" title="WhatsApp Menu">
                        <svg viewBox="0 0 24 24"><path d="M4 6h16v2H4zm0 5h16v2H4zm0 5h16v2H4z"/></svg>
                    </button>
                    <button class="icon-btn" onclick="runOneClickDemo()" title="Run 1-Click Multi-Member Demo">
                        <svg viewBox="0 0 24 24"><path d="M7 2v11h3v9l7-12h-4l4-8z"/></svg>
                    </button>
                    <button class="icon-btn" onclick="toggleOptionsMenu()" title="Menu options">
                        <svg viewBox="0 0 24 24"><path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"/></svg>
                    </button>
                </div>
            </div>

            <!-- 1-Click Demo Step Banner -->
            <div class="demo-step-banner" id="demoBanner">
                <div class="demo-step-progress">
                    <div class="demo-spinner"></div>
                    <span id="demoStepText">Running 1-Click Multi-Member Demo...</span>
                </div>
                <button class="demo-stop-btn" onclick="stopDemo()">Stop</button>
            </div>

            <!-- Messages Stream -->
            <div class="chat-messages" id="chatMessages">
                <!-- Encryption Notice -->
                <div class="sys-badge-wrap">
                    <div class="encryption-pill">
                        <svg viewBox="0 0 24 24"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/></svg>
                        <span>Messages are end-to-end encrypted. Rotating savings groups powered trustlessly by Bitcoin Lightning.</span>
                    </div>
                </div>

                <!-- Date Divider -->
                <div class="sys-badge-wrap">
                    <div class="date-pill">TODAY</div>
                </div>
            </div>

            <!-- Typing bubble -->
            <div style="padding: 0 24px;">
                <div class="typing-bubble" id="typingBubble">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>

            <!-- Quick Action Pills Bar (WhatsApp Menu Shortcuts) -->
            <div class="quick-actions-bar">
                <button class="action-chip primary" onclick="openInteractiveMenu()">☰ Menu</button>
                <button class="action-chip" onclick="sendCmd('balance')">💰 Balance</button>
                <button class="action-chip" onclick="sendCmd('pay')">⚡ Pay Round</button>
                <button class="action-chip" onclick="openCreateModal()">➕ Create Tontine</button>
                <button class="action-chip" onclick="openJoinModal()">👥 Join Group</button>
                <button class="action-chip" onclick="openFundModal()">💳 Fund (+10k)</button>
                <button class="action-chip" onclick="sendCmd('status')">📋 Status</button>
                <button class="action-chip" onclick="runOneClickDemo()">🚀 1-Click Demo</button>
                <button class="action-chip" onclick="sendCmd('help')">❓ Help</button>
            </div>

            <!-- Message Input Bar -->
            <div class="chat-input-bar">
                <button class="icon-btn" onclick="toggleEmojiTray()" title="Emojis">
                    <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm3.5-9c.83 0 1.5-.67 1.5-1.5S16.33 8 15.5 8 14 8.67 14 9.5s.67 1.5 1.5 1.5zm-7 0c.83 0 1.5-.67 1.5-1.5S9.33 8 8.5 8 7 8.67 7 9.5 7.67 11 8.5 11zm3.5 6.5c2.33 0 4.31-1.46 5.11-3.5H6.89c.8 2.04 2.78 3.5 5.11 3.5z"/></svg>
                </button>
                <button class="icon-btn" onclick="toggleAttachTray()" title="Attachment & Actions">
                    <svg viewBox="0 0 24 24"><path d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5a2.5 2.5 0 0 1 5 0v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5a2.5 2.5 0 0 0 5 0V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z"/></svg>
                </button>

                <div class="input-pill">
                    <input id="messageInput" placeholder="Type a message or '/' for commands..."
                           oninput="handleInputTyping(this.value)"
                           onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();submitMessage();}" />
                </div>

                <button class="send-btn-circle" id="sendBtn" onclick="submitMessage()" title="Send">
                    <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
                </button>

                <!-- Slash commands autocomplete box -->
                <div class="slash-popup" id="slashPopup">
                    <div class="slash-item" onclick="selectSlash('/balance')">
                        <span class="slash-cmd">/balance</span>
                        <span class="slash-desc">Check wallet sats & CFA franc value</span>
                    </div>
                    <div class="slash-item" onclick="selectSlash('/pay')">
                        <span class="slash-cmd">/pay</span>
                        <span class="slash-desc">Pay contribution for active round</span>
                    </div>
                    <div class="slash-item" onclick="selectSlash('/status')">
                        <span class="slash-cmd">/status</span>
                        <span class="slash-desc">View tontine round, payments & recipient</span>
                    </div>
                    <div class="slash-item" onclick="selectSlash('/menu')">
                        <span class="slash-cmd">/menu</span>
                        <span class="slash-desc">Open full WhatsApp interactive menu</span>
                    </div>
                    <div class="slash-item" onclick="selectSlash('/create Famille 2000 weekly 3')">
                        <span class="slash-cmd">/create</span>
                        <span class="slash-desc">create &lt;name&gt; &lt;sats&gt; &lt;weekly|monthly&gt; &lt;members&gt;</span>
                    </div>
                    <div class="slash-item" onclick="selectSlash('/join 1')">
                        <span class="slash-cmd">/join</span>
                        <span class="slash-desc">join &lt;id&gt; — Join an existing group</span>
                    </div>
                    <div class="slash-item" onclick="selectSlash('/fund 10000')">
                        <span class="slash-cmd">/fund</span>
                        <span class="slash-desc">fund &lt;sats&gt; — Add demo sats</span>
                    </div>
                    <div class="slash-item" onclick="selectSlash('/help')">
                        <span class="slash-cmd">/help</span>
                        <span class="slash-desc">Show full command guide</span>
                    </div>
                </div>

                <!-- Attachment Tray Popup -->
                <div class="attach-popup" id="attachPopup">
                    <div class="attach-item" onclick="closeAllPopups(); sendCmd('pay');">
                        <div class="attach-icon-circle" style="background:#00a884;">⚡</div>
                        <span class="attach-label">Pay Round</span>
                    </div>
                    <div class="attach-item" onclick="closeAllPopups(); openFundModal();">
                        <div class="attach-icon-circle" style="background:#3498db;">💰</div>
                        <span class="attach-label">Fund Wallet</span>
                    </div>
                    <div class="attach-item" onclick="closeAllPopups(); openCreateModal();">
                        <div class="attach-icon-circle" style="background:#9b59b6;">➕</div>
                        <span class="attach-label">Create Tontine</span>
                    </div>
                    <div class="attach-item" onclick="closeAllPopups(); openJoinModal();">
                        <div class="attach-icon-circle" style="background:#e67e22;">👥</div>
                        <span class="attach-label">Join Group</span>
                    </div>
                    <div class="attach-item" onclick="closeAllPopups(); sendCmd('status');">
                        <div class="attach-icon-circle" style="background:#1abc9c;">📊</div>
                        <span class="attach-label">Status</span>
                    </div>
                    <div class="attach-item" onclick="closeAllPopups(); runOneClickDemo();">
                        <div class="attach-icon-circle" style="background:#e74c3c;">🚀</div>
                        <span class="attach-label">Auto Demo</span>
                    </div>
                </div>

                <!-- Emoji Tray Popup -->
                <div class="emoji-popup" id="emojiPopup">
                    <button class="emoji-btn" onclick="insertEmoji('👍')">👍</button>
                    <button class="emoji-btn" onclick="insertEmoji('❤️')">❤️</button>
                    <button class="emoji-btn" onclick="insertEmoji('⚡')">⚡</button>
                    <button class="emoji-btn" onclick="insertEmoji('💰')">💰</button>
                    <button class="emoji-btn" onclick="insertEmoji('🟠')">🟠</button>
                    <button class="emoji-btn" onclick="insertEmoji('🇸🇳')">🇸🇳</button>
                    <button class="emoji-btn" onclick="insertEmoji('🚀')">🚀</button>
                    <button class="emoji-btn" onclick="insertEmoji('🎉')">🎉</button>
                    <button class="emoji-btn" onclick="insertEmoji('👥')">👥</button>
                    <button class="emoji-btn" onclick="insertEmoji('🔒')">🔒</button>
                    <button class="emoji-btn" onclick="insertEmoji('✅')">✅</button>
                    <button class="emoji-btn" onclick="insertEmoji('🏆')">🏆</button>
                </div>
            </div>

            <!-- 3-Dots Dropdown Menu -->
            <div class="options-menu" id="optionsMenu">
                <div class="menu-row" onclick="closeOptionsMenu(); openInteractiveMenu();">
                    <span>📋</span> WhatsApp Menu
                </div>
                <div class="menu-row" onclick="closeOptionsMenu(); runOneClickDemo();">
                    <span>🚀</span> 1-Click Multi-Member Demo
                </div>
                <div class="menu-row" onclick="closeOptionsMenu(); openCreateModal();">
                    <span>➕</span> Create New Tontine
                </div>
                <div class="menu-row" onclick="closeOptionsMenu(); sendCmd('fund 10000');">
                    <span>💳</span> Quick Fund (+10,000 sats)
                </div>
                <div class="menu-divider"></div>
                <div class="menu-row" onclick="closeOptionsMenu(); toggleTheme();">
                    <span>🌓</span> Toggle Dark / Light
                </div>
                <div class="menu-row" onclick="closeOptionsMenu(); toggleSound();">
                    <span id="soundMenuIcon">🔊</span> Toggle Sounds
                </div>
                <div class="menu-divider"></div>
                <div class="menu-row" onclick="closeOptionsMenu(); clearChat();">
                    <span>🧹</span> Clear Chat
                </div>
                <div class="menu-row" onclick="closeOptionsMenu(); resetDatabase();">
                    <span>🔄</span> Reset Demo Database
                </div>
                <div class="menu-row" onclick="closeOptionsMenu(); openBotInfoModal();">
                    <span>ℹ️</span> Bot & Architecture Info
                </div>
            </div>
        </main>
    </div>

    <!-- ───── MODAL 1: Full WhatsApp Interactive Menu Sheet ───── -->
    <div class="modal-overlay" id="interactiveMenuModal" onclick="if(event.target===this)closeInteractiveMenu()">
        <div class="modal-sheet">
            <div class="modal-header">
                <div class="modal-title">
                    <span>📋</span> WhatsApp Interactive Menu
                </div>
                <button class="close-modal-btn" onclick="closeInteractiveMenu()">✕</button>
            </div>
            <div class="modal-body">
                <div class="menu-section-header">💳 Wallet & Lightning</div>
                <div class="menu-list-item" onclick="selectMenuItem('balance')">
                    <div class="menu-item-left">
                        <span class="menu-item-icon">💰</span>
                        <div class="menu-item-text">
                            <span class="menu-item-title">Check Balance</span>
                            <span class="menu-item-desc">View sats balance and XOF (CFA) conversion</span>
                        </div>
                    </div>
                    <span class="menu-item-arrow">›</span>
                </div>
                <div class="menu-list-item" onclick="selectMenuItem('fund 10000')">
                    <div class="menu-item-left">
                        <span class="menu-item-icon">⚡</span>
                        <div class="menu-item-text">
                            <span class="menu-item-title">Fund Wallet (+10,000 sats)</span>
                            <span class="menu-item-desc">Instant demo Bitcoin top-up (~40,000 XOF)</span>
                        </div>
                    </div>
                    <span class="menu-item-arrow">›</span>
                </div>
                <div class="menu-list-item" onclick="closeInteractiveMenu(); openFundModal();">
                    <div class="menu-item-left">
                        <span class="menu-item-icon">📥</span>
                        <div class="menu-item-text">
                            <span class="menu-item-title">Custom Sat Funding</span>
                            <span class="menu-item-desc">Specify any sat amount</span>
                        </div>
                    </div>
                    <span class="menu-item-arrow">›</span>
                </div>

                <div class="menu-section-header">👥 Tontine Groups</div>
                <div class="menu-list-item" onclick="closeInteractiveMenu(); openCreateModal();">
                    <div class="menu-item-left">
                        <span class="menu-item-icon">➕</span>
                        <div class="menu-item-text">
                            <span class="menu-item-title">Create Tontine Group</span>
                            <span class="menu-item-desc">Launch a trustless rotating savings circle</span>
                        </div>
                    </div>
                    <span class="menu-item-arrow">›</span>
                </div>
                <div class="menu-list-item" onclick="closeInteractiveMenu(); openJoinModal();">
                    <div class="menu-item-left">
                        <span class="menu-item-icon">🔗</span>
                        <div class="menu-item-text">
                            <span class="menu-item-title">Join Tontine Group</span>
                            <span class="menu-item-desc">Enter group ID to participate</span>
                        </div>
                    </div>
                    <span class="menu-item-arrow">›</span>
                </div>
                <div class="menu-list-item" onclick="selectMenuItem('status')">
                    <div class="menu-item-left">
                        <span class="menu-item-icon">📊</span>
                        <div class="menu-item-text">
                            <span class="menu-item-title">Tontine Status</span>
                            <span class="menu-item-desc">See rounds, member checklist & payout winner</span>
                        </div>
                    </div>
                    <span class="menu-item-arrow">›</span>
                </div>

                <div class="menu-section-header">⚡ Payments & Rounds</div>
                <div class="menu-list-item" onclick="selectMenuItem('pay')">
                    <div class="menu-item-left">
                        <span class="menu-item-icon">💸</span>
                        <div class="menu-item-text">
                            <span class="menu-item-title">Pay Round Contribution</span>
                            <span class="menu-item-desc">Send this round's share; auto-pays pot when all pay</span>
                        </div>
                    </div>
                    <span class="menu-item-arrow">›</span>
                </div>

                <div class="menu-section-header">🚀 Automated Demo</div>
                <div class="menu-list-item" onclick="closeInteractiveMenu(); runOneClickDemo();">
                    <div class="menu-item-left">
                        <span class="menu-item-icon">🎯</span>
                        <div class="menu-item-text">
                            <span class="menu-item-title">1-Click Multi-Member Demo</span>
                            <span class="menu-item-desc">Simulates 3 members, funding, joining & pot payout!</span>
                        </div>
                    </div>
                    <span class="menu-item-arrow">›</span>
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn secondary" onclick="closeInteractiveMenu()">Close</button>
            </div>
        </div>
    </div>

    <!-- ───── MODAL 2: Create Tontine Interactive Form ───── -->
    <div class="modal-overlay" id="createModal" onclick="if(event.target===this)closeCreateModal()">
        <div class="modal-sheet">
            <div class="modal-header">
                <div class="modal-title"><span>➕</span> Create New Tontine</div>
                <button class="close-modal-btn" onclick="closeCreateModal()">✕</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Tontine Group Name</label>
                    <input class="form-input" id="newTontineName" value="Famille Diop" placeholder="e.g. Famille, Dakar Devs" />
                    <div class="chips-selector" style="margin-top:4px;">
                        <span class="preset-chip" onclick="document.getElementById('newTontineName').value='Famille Diop'">Famille Diop</span>
                        <span class="preset-chip" onclick="document.getElementById('newTontineName').value='Dakar Bitcoin Devs'">Dakar Bitcoin Devs</span>
                        <span class="preset-chip" onclick="document.getElementById('newTontineName').value='Marché Sandaga'">Marché Sandaga</span>
                        <span class="preset-chip" onclick="document.getElementById('newTontineName').value='Tontine Keur Massar'">Keur Massar</span>
                    </div>
                </div>

                <div class="form-group">
                    <label class="form-label">Contribution Amount per Member (sats)</label>
                    <input class="form-input" id="newTontineAmount" type="number" value="2000" min="100" max="100000" oninput="updateCreateCalc()" />
                    <div class="chips-selector" style="margin-top:4px;">
                        <span class="preset-chip" onclick="setCreateAmount(1000)">1,000 sats</span>
                        <span class="preset-chip active" id="chip2000" onclick="setCreateAmount(2000)">2,000 sats</span>
                        <span class="preset-chip" onclick="setCreateAmount(5000)">5,000 sats</span>
                        <span class="preset-chip" onclick="setCreateAmount(10000)">10,000 sats</span>
                    </div>
                </div>

                <div class="calc-preview" id="createCalcPreview">
                    💡 2,000 sats ≈ 8,000 CFA (XOF) per round. Pot with 3 members = 6,000 sats (24,000 XOF).
                </div>

                <div class="form-group">
                    <label class="form-label">Cycle Frequency</label>
                    <div class="chips-selector">
                        <span class="preset-chip active" id="cycleWeekly" onclick="setCycle('weekly')">Weekly (7 days)</span>
                        <span class="preset-chip" id="cycleMonthly" onclick="setCycle('monthly')">Monthly (30 days)</span>
                    </div>
                </div>

                <div class="form-group">
                    <label class="form-label">Maximum Members</label>
                    <div class="chips-selector">
                        <span class="preset-chip" onclick="setMembers(2)">2</span>
                        <span class="preset-chip active" id="members3" onclick="setMembers(3)">3 (Recommended)</span>
                        <span class="preset-chip" onclick="setMembers(4)">4</span>
                        <span class="preset-chip" onclick="setMembers(5)">5</span>
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn secondary" onclick="closeCreateModal()">Cancel</button>
                <button class="modal-btn primary" onclick="submitCreateTontine()">Create Tontine</button>
            </div>
        </div>
    </div>

    <!-- ───── MODAL 3: Join Tontine Interactive Form ───── -->
    <div class="modal-overlay" id="joinModal" onclick="if(event.target===this)closeJoinModal()">
        <div class="modal-sheet">
            <div class="modal-header">
                <div class="modal-title"><span>👥</span> Join Tontine Group</div>
                <button class="close-modal-btn" onclick="closeJoinModal()">✕</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Tontine Group ID</label>
                    <input class="form-input" id="joinTontineId" type="number" value="1" placeholder="Enter Tontine ID (e.g. 1)" />
                </div>
                <div class="calc-preview">
                    💡 Ask the group creator for their Tontine ID. If you just created one, the ID is usually <b>1</b>.
                </div>
                <div class="form-group">
                    <label class="form-label">Active Groups Found:</label>
                    <div id="activeTontinesList" style="display:flex; flex-direction:column; gap:6px;">
                        <span style="font-size:12px; color:var(--wa-text-secondary);">Loading active groups...</span>
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn secondary" onclick="closeJoinModal()">Cancel</button>
                <button class="modal-btn primary" onclick="submitJoinTontine()">Join Group</button>
            </div>
        </div>
    </div>

    <!-- ───── MODAL 4: Fund Wallet Interactive Form ───── -->
    <div class="modal-overlay" id="fundModal" onclick="if(event.target===this)closeFundModal()">
        <div class="modal-sheet">
            <div class="modal-header">
                <div class="modal-title"><span>💳</span> Fund Bitcoin Wallet</div>
                <button class="close-modal-btn" onclick="closeFundModal()">✕</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Amount in Satoshis</label>
                    <input class="form-input" id="fundAmountInput" type="number" value="10000" min="1" max="1000000" oninput="updateFundCalc()" />
                    <div class="chips-selector" style="margin-top:6px;">
                        <span class="preset-chip" onclick="setFundAmount(1000)">+1,000</span>
                        <span class="preset-chip" onclick="setFundAmount(5000)">+5,000</span>
                        <span class="preset-chip active" onclick="setFundAmount(10000)">+10,000</span>
                        <span class="preset-chip" onclick="setFundAmount(50000)">+50,000</span>
                    </div>
                </div>
                <div class="calc-preview" id="fundCalcPreview">
                    💡 10,000 sats ≈ 40,000 CFA (XOF). Added instantly in demo mode.
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn secondary" onclick="closeFundModal()">Cancel</button>
                <button class="modal-btn primary" onclick="submitFundWallet()">Add Sats</button>
            </div>
        </div>
    </div>

    <!-- ───── MODAL 5: Bot & Architecture Info ───── -->
    <div class="modal-overlay" id="botInfoModal" onclick="if(event.target===this)closeBotInfoModal()">
        <div class="modal-sheet">
            <div class="modal-header">
                <div class="modal-title"><span>🟠</span> Tontine Lightning Overview</div>
                <button class="close-modal-btn" onclick="closeBotInfoModal()">✕</button>
            </div>
            <div class="modal-body" style="font-size:13.5px; line-height:1.5;">
                <p><b>Tontine Lightning</b> replaces human trust with Bitcoin Lightning in rotating savings groups across West Africa.</p>
                <div class="calc-preview" style="margin:8px 0;">
                    <b>Key Features:</b><br>
                    • Custodial Lightning wallets via WhatsApp<br>
                    • Automated round collections & instant pot payouts<br>
                    • No human treasurer holding pool funds<br>
                    • Rate limited & phone-hash protected
                </div>
                <p style="color:var(--wa-text-secondary); font-size:12px;">Built for the Dakar Bitcoin Hackathon by BTrust. Integrated with LNbits API & WhatsApp Cloud Webhooks.</p>
            </div>
            <div class="modal-footer">
                <button class="modal-btn primary" onclick="closeBotInfoModal()">Got it</button>
            </div>
        </div>
    </div>

    <!-- Audio Context for subtle WhatsApp clicks -->
    <div class="swipe-indicator" id="swipeIndicator">⬅️ Swipe to see chats</div>
    
    <script>
        // State
        let currentPhone = '+221771234567';
        let currentName = 'Fatou Diop';
        let soundEnabled = true;
        let selectedCycle = 'weekly';
        let selectedMembers = 3;
        let isDemoRunning = false;
        let demoStopRequested = false;

        // Sound generator (synthesized WhatsApp pop/click)
        function playAudioTone(freq, type, duration) {
            if (!soundEnabled) return;
            try {
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = type || 'sine';
                osc.frequency.setValueAtTime(freq, ctx.currentTime);
                gain.gain.setValueAtTime(0.08, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start();
                osc.stop(ctx.currentTime + duration);
            } catch(e) {}
        }
        function playSendSound() { playAudioTone(520, 'sine', 0.12); }
        function playReceiveSound() { playAudioTone(780, 'triangle', 0.15); }

        // Formatting timestamp
        function getCurrentTime() {
            const now = new Date();
            let h = now.getHours();
            let m = now.getMinutes();
            const ampm = h >= 12 ? 'PM' : 'AM';
            h = h % 12; h = h ? h : 12;
            m = m < 10 ? '0' + m : m;
            return `${h}:${m} ${ampm}`;
        }

        // WhatsApp Markdown parser (*bold*, _italic_, ~strike~, `code`)
        function formatWAMarkdown(text) {
            if (!text) return '';
            let s = text
                .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                .replace(/\*([^\*]+)\*/g, "<strong>$1</strong>")
                .replace(/_([^_]+)_/g, "<em>$1</em>")
                .replace(/~([^~]+)~/g, "<del>$1</del>")
                .replace(/```([^`]+)```/g, "<pre><code>$1</code></pre>")
                .replace(/`([^`]+)`/g, "<code>$1</code>");
            return s;
        }

        // Add message to chat feed
        function appendMessage(text, isUser = false, buttons = []) {
            const container = document.getElementById('chatMessages');
            const row = document.createElement('div');
            row.className = 'msg-row ' + (isUser ? 'out' : 'in');
            row.dataset.msgId = Date.now(); // Unique message ID

            const bubble = document.createElement('div');
            bubble.className = 'bubble';

            const bubbleText = document.createElement('div');
            bubbleText.className = 'bubble-text';
            bubbleText.innerHTML = formatWAMarkdown(text);
            bubble.appendChild(bubbleText);

            // Message action buttons (hover menu)
            const actions = document.createElement('div');
            actions.className = 'msg-actions';
            actions.innerHTML = `
                <button class="msg-action-btn" title="Reply" onclick="replyToMessage(this, '${text.slice(0, 50)}')">
                    <svg viewBox="0 0 24 24"><path d="M10 9V5l-7 7 7 7v-4.1c5 0 8.5 1.6 11 5.1-1-5-4-10-11-11z"/></svg>
                </button>
                <button class="msg-action-btn" title="React" onclick="reactToMessage(this)">
                    <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm3.5-9c.83 0 1.5-.67 1.5-1.5S16.33 8 15.5 8 14 8.67 14 9.5s.67 1.5 1.5 1.5zm-7 0c.83 0 1.5-.67 1.5-1.5S9.33 8 8.5 8 7 8.67 7 9.5 7.67 11 8.5 11zm3.5 6.5c2.33 0 4.31-1.46 5.11-3.5H6.89c.8 2.04 2.78 3.5 5.11 3.5z"/></svg>
                </button>
                <button class="msg-action-btn" title="Forward" onclick="forwardMessage('${text.slice(0, 50)}')">
                    <svg viewBox="0 0 24 24"><path d="M12 8V4l8 8-8 8v-4H4V8z"/></svg>
                </button>
                <button class="msg-action-btn" title="Star" onclick="starMessage(this)">
                    <svg viewBox="0 0 24 24"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>
                </button>
            `;
            row.appendChild(actions);

            // Metadata row (time + ticks)
            const meta = document.createElement('div');
            meta.className = 'bubble-meta';
            const timeSpan = document.createElement('span');
            timeSpan.textContent = getCurrentTime();
            meta.appendChild(timeSpan);

            if (isUser) {
                const ticks = document.createElement('span');
                ticks.className = 'blue-ticks';
                ticks.innerHTML = `<svg viewBox="0 0 16 15"><path d="M15.01 3.316l-.478-.372a.365.365 0 0 0-.51.063L8.666 9.879a.32.32 0 0 1-.484.033l-.358-.325a.319.319 0 0 0-.484.032l-.378.483a.418.418 0 0 0 .036.541l1.32 1.266c.143.14.361.125.484-.033l6.272-8.048a.366.366 0 0 0-.064-.512zm-4.1 0l-.478-.372a.365.365 0 0 0-.51.063L4.566 9.879a.32.32 0 0 1-.484.033L1.891 7.769a.366.366 0 0 0-.515.006l-.423.433a.364.364 0 0 0 .006.514l3.258 3.185c.143.14.361.125.484-.033l6.272-8.048a.365.365 0 0 0-.063-.51z"/></svg>`;
                meta.appendChild(ticks);
            }
            bubble.appendChild(meta);

            // Render native WhatsApp action buttons under bot message if provided
            if (!isUser && buttons && buttons.length > 0) {
                const btnGroup = document.createElement('div');
                btnGroup.className = 'wa-button-group';
                buttons.forEach(b => {
                    const btn = document.createElement('button');
                    btn.className = 'wa-action-btn';
                    btn.textContent = b.label;
                    btn.onclick = () => {
                        if (b.cmd === 'create_modal') openCreateModal();
                        else if (b.cmd === 'join_modal') openJoinModal();
                        else if (b.cmd === 'menu') openInteractiveMenu();
                        else sendCmd(b.cmd);
                    };
                    btnGroup.appendChild(btn);
                });
                bubble.appendChild(btnGroup);
            }

            row.appendChild(bubble);
            container.appendChild(row);
            container.scrollTop = container.scrollHeight;

            if (isUser) playSendSound();
            else playReceiveSound();

            // Update snippet on left sidebar
            document.getElementById('botLastSnippet').textContent = text.slice(0, 38) + (text.length > 38 ? '...' : '');
            document.getElementById('botLastTime').textContent = getCurrentTime();
        }

        // New WhatsApp-like features
        let replyingTo = null;
        
        function replyToMessage(btn, text) {
            replyingTo = { text: text.slice(0, 50), author: 'Bot' };
            const input = document.getElementById('messageInput');
            input.placeholder = `Replying to: "${text.slice(0, 30)}..."`;
            input.focus();
            input.style.background = 'rgba(0, 168, 132, 0.1)';
            
            // Add cancel button
            const cancelBtn = document.createElement('button');
            cancelBtn.className = 'icon-btn';
            cancelBtn.innerHTML = '✕';
            cancelBtn.style.position = 'absolute';
            cancelBtn.style.right = '70px';
            cancelBtn.onclick = () => {
                replyingTo = null;
                input.placeholder = "Type a message or '/' for commands...";
                input.style.background = '';
                cancelBtn.remove();
            };
            document.querySelector('.chat-input-bar').appendChild(cancelBtn);
        }

        function reactToMessage(btn) {
            const row = btn.closest('.msg-row');
            // Toggle between reactions
            let existing = row.querySelector('.msg-reaction');
            if (existing) {
                existing.remove();
            } else {
                const reactions = ['❤️', '👍', '😂', '😮', '😢', '🙏'];
                const reaction = reactions[Math.floor(Math.random() * reactions.length)];
                const bubble = row.querySelector('.bubble');
                const reactionEl = document.createElement('div');
                reactionEl.className = 'msg-reaction';
                reactionEl.textContent = reaction;
                reactionEl.onclick = () => reactionEl.remove();
                bubble.appendChild(reactionEl);
                playAudioTone(600, 'sine', 0.08);
            }
        }

        function forwardMessage(text) {
            const input = document.getElementById('messageInput');
            input.value = '➡️ Forwarded: ' + text.slice(0, 100);
            input.focus();
        }

        function starMessage(btn) {
            btn.style.color = btn.style.color === 'gold' ? '' : 'gold';
            playAudioTone(700, 'triangle', 0.1);
        }

        function playVoice(btn) {
            const isPaused = btn.innerHTML.includes('M8 5v14');
            if (isPaused) {
                btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6 6h12v12H6z"/></svg>';
                playAudioTone(440, 'sine', 2);
                setTimeout(() => {
                    btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>';
                }, 2000);
            } else {
                btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>';
            }
        }

        // Show/hide typing indicator
        function setTyping(isTyping) {
            const bubble = document.getElementById('typingBubble');
            const status = document.getElementById('headerStatus');
            if (isTyping) {
                bubble.classList.add('active');
                status.textContent = 'typing...';
                status.classList.add('typing');
                const container = document.getElementById('chatMessages');
                container.scrollTop = container.scrollHeight;
            } else {
                bubble.classList.remove('active');
                status.textContent = 'Official WhatsApp Bot • online';
                status.classList.remove('typing');
            }
        }

        // Send a message to /sim
        async function sendMessage(text) {
            if (!text || !text.trim()) return;
            text = text.trim();
            closeAllPopups();
            appendMessage(text, true);

            setTyping(true);
            try {
                const res = await fetch('/sim', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({phone: currentPhone, text: text})
                });
                const data = await res.json();
                await new Promise(r => setTimeout(r, 380)); // realistic WhatsApp typing delay
                setTyping(false);
                appendMessage(data.reply, false, data.buttons || []);
            } catch(e) {
                setTyping(false);
                appendMessage('⚠️ Error communicating with bot: ' + e, false);
            }
        }

        function submitMessage() {
            const input = document.getElementById('messageInput');
            const val = input.value;
            input.value = '';
            sendMessage(val);
        }

        function sendCmd(cmd) {
            sendMessage(cmd);
        }

        // Persona switching
        function switchPersona(phone, name, initials, colorClass) {
            currentPhone = phone;
            currentName = name;
            document.getElementById('currentName').textContent = name;
            document.getElementById('currentPhone').textContent = phone;
            const avatar = document.getElementById('currentAvatar');
            avatar.textContent = initials;
            avatar.className = 'user-avatar ' + colorClass;
            document.getElementById('customPhoneInput').value = phone;

            // Highlight in list
            document.querySelectorAll('.chat-item').forEach(el => el.classList.remove('active'));
            event.currentTarget.classList.add('active');

            // Send notification in chat
            appendMessage(`📱 *Switched active phone to:* ${name} (${phone})\nYou are now interacting as this WhatsApp user.`, false, [
                {label: "💰 Check Balance", cmd: "balance"},
                {label: "⚡ Pay Round", cmd: "pay"},
                {label: "📋 Group Status", cmd: "status"}
            ]);
        }

        function applyCustomPhone() {
            const val = document.getElementById('customPhoneInput').value.trim();
            if (!val) return;
            currentPhone = val;
            currentName = 'Custom (' + val.slice(-4) + ')';
            document.getElementById('currentName').textContent = currentName;
            document.getElementById('currentPhone').textContent = val;
            document.getElementById('currentAvatar').textContent = '📱';
            appendMessage(`📱 Switched active phone to custom number: ${val}`, false);
        }

        // Slash command suggestions
        function handleInputTyping(val) {
            const popup = document.getElementById('slashPopup');
            if (val.startsWith('/')) {
                popup.classList.add('active');
            } else {
                popup.classList.remove('active');
            }
        }

        function selectSlash(cmd) {
            const input = document.getElementById('messageInput');
            input.value = cmd.startsWith('/') ? cmd.slice(1) : cmd;
            document.getElementById('slashPopup').classList.remove('active');
            input.focus();
        }

        function insertEmoji(char) {
            const input = document.getElementById('messageInput');
            input.value += char;
            input.focus();
            document.getElementById('emojiPopup').classList.remove('active');
        }

        // Toggle Trays
        function toggleAttachTray() {
            closeAllPopups(['attachPopup']);
            document.getElementById('attachPopup').classList.toggle('active');
        }

        function toggleEmojiTray() {
            closeAllPopups(['emojiPopup']);
            document.getElementById('emojiPopup').classList.toggle('active');
        }

        function toggleOptionsMenu() {
            closeAllPopups(['optionsMenu']);
            document.getElementById('optionsMenu').classList.toggle('active');
        }
        
        function toggleTheme() {
            document.body.classList.toggle('light-theme');
            const isLight = document.body.classList.contains('light-theme');
            localStorage.setItem('wa-theme', isLight ? 'light' : 'dark');
            playAudioTone(500, 'sine', 0.1);
            closeAllPopups();
        }

        function toggleSidebarMobile() {
            document.getElementById('sidebar').classList.toggle('hidden-mobile');
        }
        
        // Load saved theme
        if (localStorage.getItem('wa-theme') === 'light') {
            document.body.classList.add('light-theme');
        }
        
        function toggleSound() {
            soundEnabled = !soundEnabled;
            const icon = document.getElementById('soundMenuIcon');
            icon.textContent = soundEnabled ? '🔊' : '🔇';
            localStorage.setItem('wa-sound', soundEnabled ? 'on' : 'off');
            if (soundEnabled) playAudioTone(600, 'sine', 0.1);
        }
        
        if (localStorage.getItem('wa-sound') === 'off') {
            soundEnabled = false;
            document.getElementById('soundMenuIcon').textContent = '🔇';
        }
        
        function clearChat() {
            const container = document.getElementById('chatMessages');
            container.innerHTML = `
                <div class="sys-badge-wrap">
                    <div class="encryption-pill">
                        <svg viewBox="0 0 24 24"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/></svg>
                        <span>Messages are end-to-end encrypted. Rotating savings groups powered trustlessly by Bitcoin Lightning.</span>
                    </div>
                </div>
                <div class="sys-badge-wrap">
                    <div class="date-pill">TODAY</div>
                </div>
            `;
            playAudioTone(400, 'sine', 0.1);
        }
        
        async function resetDatabase() {
            if (!confirm('Reset demo database? This will clear all tontines, wallets, and rounds.')) return;
            try {
                await fetch('/api/reset', { method: 'POST' });
                clearChat();
                appendMessage('✅ Demo database reset successfully! All tontines and wallets cleared.', false, [
                    {label: "👋 Register", cmd: "hi"},
                    {label: "💰 Check Balance", cmd: "balance"},
                    {label: "➕ Create Tontine", cmd: "create_modal"}
                ]);
            } catch(e) {
                appendMessage('⚠️ Error resetting database: ' + e, false);
            }
        }
        
        function closeOptionsMenu() {
            document.getElementById('optionsMenu').classList.remove('active');
        }
        
        function openBotInfoModal() {
            closeAllPopups();
            document.getElementById('botInfoModal').classList.add('active');
        }
        
        function closeBotInfoModal() {
            document.getElementById('botInfoModal').classList.remove('active');
        }
        
        function selectBotChat() {
            // Already on bot chat, just highlight
            document.querySelectorAll('.chat-item').forEach(el => {
                if (el.textContent.includes('Tontine Lightning')) {
                    el.classList.add('active');
                } else {
                    el.classList.remove('active');
                }
            });
        }
        
        function togglePersonaPicker() {
            // Could expand this to show a persona selection modal
            appendMessage('💡 *Tip:* Click any member name in the left sidebar to switch your active WhatsApp identity!', false);
        }
        
        function filterChatList() {
            const query = document.getElementById('searchInput').value.toLowerCase();
            document.querySelectorAll('.chat-item').forEach(item => {
                const text = item.textContent.toLowerCase();
                item.style.display = text.includes(query) ? 'flex' : 'none';
            });
        }
        
        function setFilter(btn, type) {
            document.querySelectorAll('.filter-chips .chip').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            // Could filter by type (all, unread, groups, members)
        }
        
        function showStatusModal() {
            appendMessage('📸 *Status Updates*\n\nView 24-hour status stories from your tontine members. Feature coming soon!', false, [
                {label: "✅ Got it", cmd: "menu"}
            ]);
        }

        function closeAllPopups(except = []) {
            ['attachPopup', 'emojiPopup', 'optionsMenu', 'slashPopup'].forEach(id => {
                if (!except.includes(id)) {
                    const el = document.getElementById(id);
                    if (el) el.classList.remove('active');
                }
            });
        }

        document.addEventListener('click', (e) => {
            if (!e.target.closest('.chat-input-bar') && !e.target.closest('.header-actions')) {
                closeAllPopups();
            }
        });

        // Modals Management
        function openInteractiveMenu() {
            closeAllPopups();
            document.getElementById('interactiveMenuModal').classList.add('active');
        }
        function closeInteractiveMenu() {
            document.getElementById('interactiveMenuModal').classList.remove('active');
        }
        function selectMenuItem(cmd) {
            closeInteractiveMenu();
            sendCmd(cmd);
        }

        function openCreateModal() {
            closeAllPopups();
            updateCreateCalc();
            document.getElementById('createModal').classList.add('active');
        }
        function closeCreateModal() {
            document.getElementById('createModal').classList.remove('active');
        }
        function setCreateAmount(sats) {
            document.getElementById('newTontineAmount').value = sats;
            document.querySelectorAll('#createModal .preset-chip').forEach(c => c.classList.remove('active'));
            if (event) event.target.classList.add('active');
            updateCreateCalc();
        }
        function setCycle(c) {
            selectedCycle = c;
            document.getElementById('cycleWeekly').classList.toggle('active', c === 'weekly');
            document.getElementById('cycleMonthly').classList.toggle('active', c === 'monthly');
        }
        function setMembers(n) {
            selectedMembers = n;
            document.querySelectorAll('#createModal .form-group:last-child .preset-chip').forEach(c => c.classList.remove('active'));
            if (event) event.target.classList.add('active');
            updateCreateCalc();
        }
        function updateCreateCalc() {
            const sats = parseInt(document.getElementById('newTontineAmount').value) || 2000;
            const xof = Math.round(sats * 4);
            const totalPot = sats * selectedMembers;
            const totalXof = Math.round(totalPot * 4);
            document.getElementById('createCalcPreview').innerHTML =
                `💡 <b>${sats.toLocaleString()} sats</b> ≈ ${xof.toLocaleString()} CFA per round. Total pot with ${selectedMembers} members = <b>${totalPot.toLocaleString()} sats</b> (~${totalXof.toLocaleString()} CFA).`;
        }
        function submitCreateTontine() {
            const name = document.getElementById('newTontineName').value.trim() || 'Famille';
            const amount = document.getElementById('newTontineAmount').value || '2000';
            closeCreateModal();
            sendMessage(`create ${name} ${amount} ${selectedCycle} ${selectedMembers}`);
        }

        async function openJoinModal() {
            closeAllPopups();
            document.getElementById('joinModal').classList.add('active');
            const listEl = document.getElementById('activeTontinesList');
            listEl.innerHTML = '<span style="font-size:12px;color:var(--wa-text-secondary);">Checking active groups...</span>';
            try {
                const res = await fetch('/api/tontines');
                const data = await res.json();
                if (data.tontines && data.tontines.length > 0) {
                    listEl.innerHTML = '';
                    data.tontines.forEach(t => {
                        const item = document.createElement('div');
                        item.className = 'preset-chip';
                        item.style.display = 'flex';
                        item.style.justifyContent = 'space-between';
                        item.style.width = '100%';
                        item.innerHTML = `<span><b>#${t.id} ${t.name}</b> (${t.amount_sats.toLocaleString()} sats)</span> <span>${t.member_count}/${t.max_members} members</span>`;
                        item.onclick = () => {
                            document.getElementById('joinTontineId').value = t.id;
                        };
                        listEl.appendChild(item);
                    });
                } else {
                    listEl.innerHTML = '<span style="font-size:12px;color:var(--wa-text-muted);">No groups yet. Create one first!</span>';
                }
            } catch(e) {
                listEl.innerHTML = '<span style="font-size:12px;color:var(--wa-text-muted);">ID 1 (Default)</span>';
            }
        }
        function closeJoinModal() {
            document.getElementById('joinModal').classList.remove('active');
        }
        function submitJoinTontine() {
            const id = document.getElementById('joinTontineId').value.trim() || '1';
            closeJoinModal();
            sendMessage(`join ${id}`);
        }

        function openFundModal() {
            closeAllPopups();
            document.getElementById('fundModal').classList.add('active');
        }
        function closeFundModal() {
            document.getElementById('fundModal').classList.remove('active');
        }
        function setFundAmount(sats) {
            document.getElementById('fundAmountInput').value = sats;
            updateFundCalc();
        }
        function updateFundCalc() {
            const sats = parseInt(document.getElementById('fundAmountInput').value) || 10000;
            const xof = Math.round(sats * 4);
            document.getElementById('fundCalcPreview').innerHTML =
                `💡 <b>${sats.toLocaleString()} sats</b> ≈ ${xof.toLocaleString()} CFA (XOF). Added instantly in demo mode.`;
        }
        function submitFundWallet() {
            const sats = document.getElementById('fundAmountInput').value.trim() || '10000';
            closeFundModal();
            sendMessage(`fund ${sats}`);
        }

        function openBotInfoModal() {
            closeAllPopups();
            document.getElementById('botInfoModal').classList.add('active');
        }
        function closeBotInfoModal() {
            document.getElementById('botInfoModal').classList.remove('active');
        }

        function clearChat() {
            const container = document.getElementById('chatMessages');
            container.innerHTML = `
                <div class="sys-badge-wrap">
                    <div class="encryption-pill">
                        <svg viewBox="0 0 24 24"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/></svg>
                        <span>Chat history cleared locally. Tap below to begin a new rotation.</span>
                    </div>
                </div>
            `;
            appendMessage("🟠 Welcome back! Send 'hi' or tap below to start.", false, [
                {label: "👋 Start (hi)", cmd: "hi"},
                {label: "💰 Balance", cmd: "balance"},
                {label: "📋 Menu", cmd: "menu"}
            ]);
        }

        async function resetDatabase() {
            if (!confirm("Reset demo database? This will clear all test users and tontines.")) return;
            try {
                await fetch('/api/reset', {method: 'POST'});
                clearChat();
                appendMessage("🔄 Demo database reset successfully. You have a fresh slate!", false);
            } catch(e) {
                alert("Error resetting DB: " + e);
            }
        }

        function toggleTheme() {
            document.body.classList.toggle('light-theme');
        }

        function toggleSound() {
            soundEnabled = !soundEnabled;
            document.getElementById('soundMenuIcon').textContent = soundEnabled ? '🔊' : '🔇';
        }

        function toggleSidebarMobile() {
            document.getElementById('sidebar').classList.toggle('hidden-mobile');
        }

        function selectBotChat() {
            document.querySelectorAll('.chat-item').forEach(el => el.classList.remove('active'));
            event.currentTarget.classList.add('active');
        }

        function setFilter(btn, type) {
            document.querySelectorAll('.filter-chips .chip').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
        }

        function filterChatList() {
            const query = document.getElementById('searchInput').value.toLowerCase();
            document.querySelectorAll('.chats-list .chat-item').forEach(item => {
                const text = item.textContent.toLowerCase();
                item.style.display = text.includes(query) ? 'flex' : 'none';
            });
        }

        // ───── 1-CLICK MULTI-MEMBER LIVE DEMO ─────
        async function runOneClickDemo() {
            if (isDemoRunning) return;
            isDemoRunning = true;
            demoStopRequested = false;

            const banner = document.getElementById('demoBanner');
            const stepText = document.getElementById('demoStepText');
            banner.classList.add('active');

            const sleep = ms => new Promise(r => setTimeout(r, ms));
            const p1 = '+221771111111', p2 = '+221772222222', p3 = '+221773333333';

            const steps = [
                {phone: p1, name: 'Fatou Diop', text: 'hi', desc: 'Step 1/8: Fatou registering wallet...'},
                {phone: p1, name: 'Fatou Diop', text: 'fund 10000', desc: 'Step 2/8: Fatou funding 10,000 sats...'},
                {phone: p1, name: 'Fatou Diop', text: 'create Famille 2000 weekly 3', desc: 'Step 3/8: Fatou creating Tontine group...'},
                {phone: p2, name: 'Moussa Sow', text: 'fund 10000', desc: 'Step 4/8: Moussa funding 10,000 sats...'},
                {phone: p2, name: 'Moussa Sow', text: 'join 1', desc: 'Step 5/8: Moussa joining Tontine #1...'},
                {phone: p3, name: 'Awa Ndiaye', text: 'fund 10000', desc: 'Step 6/8: Awa funding and joining...'},
                {phone: p3, name: 'Awa Ndiaye', text: 'join 1', desc: 'Step 6/8: Awa joining Tontine #1...'},
                {phone: p1, name: 'Fatou Diop', text: 'pay', desc: 'Step 7/8: Fatou paying round 1...'},
                {phone: p2, name: 'Moussa Sow', text: 'pay', desc: 'Step 7/8: Moussa paying round 1...'},
                {phone: p3, name: 'Awa Ndiaye', text: 'pay', desc: 'Step 8/8: Awa paying -> Triggers pot payout!'},
                {phone: p1, name: 'Fatou Diop', text: 'balance', desc: 'Final: Checking updated balance & next round status...'}
            ];

            try {
                for (const step of steps) {
                    if (demoStopRequested) break;
                    stepText.textContent = `⚡ Demo: ${step.desc}`;
                    currentPhone = step.phone;
                    currentName = step.name;
                    document.getElementById('currentName').textContent = step.name;
                    document.getElementById('currentPhone').textContent = step.phone;

                    await sendMessage(step.text);
                    await sleep(1400);
                }
            } catch(e) {
                console.error(e);
            } finally {
                banner.classList.remove('active');
                isDemoRunning = false;
            }
        }

        function stopDemo() {
            demoStopRequested = true;
            document.getElementById('demoBanner').classList.remove('active');
            isDemoRunning = false;
        }

        // Initialize greeting on first load
        window.onload = function() {
            appendMessage(
                "🟠 *Welcome to Tontine Lightning!*\n\n" +
                "Trustless rotating savings on Bitcoin Lightning via WhatsApp.\n\n" +
                "⚡ *Tap a menu button below or type a command to begin:*",
                false,
                [
                    {label: "👋 Register (hi)", cmd: "hi"},
                    {label: "💰 Check Balance", cmd: "balance"},
                    {label: "➕ Create Tontine", cmd: "create_modal"},
                    {label: "📋 Main Menu", cmd: "menu"},
                    {label: "🚀 1-Click Demo", cmd: "demo_walkthrough"}
                ]
            );
            
            // Mobile swipe gestures for sidebar
            let touchStartX = 0;
            let touchEndX = 0;
            const chatArea = document.querySelector('.chat-area');
            const sidebar = document.getElementById('sidebar');
            const indicator = document.getElementById('swipeIndicator');
            
            chatArea.addEventListener('touchstart', (e) => {
                touchStartX = e.changedTouches[0].screenX;
            }, {passive: true});
            
            chatArea.addEventListener('touchend', (e) => {
                touchEndX = e.changedTouches[0].screenX;
                handleSwipe();
            }, {passive: true});
            
            function handleSwipe() {
                const swipeDistance = touchEndX - touchStartX;
                if (swipeDistance > 100) { // Swipe right
                    sidebar.classList.remove('hidden-mobile');
                    indicator.classList.remove('active');
                } else if (swipeDistance < -100) { // Swipe left
                    sidebar.classList.add('hidden-mobile');
                }
            }
            
            // Show swipe indicator on mobile after 2 seconds
            if (window.innerWidth <= 768) {
                setTimeout(() => {
                    indicator.classList.add('active');
                    setTimeout(() => indicator.classList.remove('active'), 3000);
                }, 2000);
            }
        };
    </script>
</body>
</html>""".replace("__MODE_BADGE__", MODE_BADGE)


@app.get("/", response_class=HTMLResponse)
async def demo_ui():
    """Serve the authentic WhatsApp Web chat UI."""
    return DEMO_HTML


@app.post("/sim")
async def simulate(request: Request):
    """Simulator endpoint — send a message as any phone number."""
    data = await request.json()
    phone = str(data.get("phone", "+221770000000"))
    text = str(data.get("text", "hi"))

    reply = await bot.handle_message(phone, text)
    buttons = _get_contextual_buttons(text, reply)

    return {"reply": reply, "buttons": buttons}


@app.get("/api/tontines")
async def list_active_tontines():
    """List active tontines for UI group picker."""
    return {"tontines": db.get_all_active_tontines()}


@app.post("/api/reset")
async def reset_demo_endpoint():
    """Reset demo database for interactive walkthroughs."""
    db.reset_demo_db()
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
