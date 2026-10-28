#!/usr/bin/env python3
"""Private Telegram proposals: acknowledge only. No rental, shell or root grants."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import ssl
import sys
import time
import urllib.error
import urllib.request

from telegram_menu import CALLBACKS as MENU_CALLBACKS, markup as menu_markup, reply as menu_reply
import clore_telegram_proposals as clore_decisions
import telegram_clore_search as gpu_search

FIELDS = {"provider", "offer_id", "machine_id", "host_id", "gpu_name",
          "gpu_count", "max_hourly_usd", "max_total_usd", "max_minutes",
          "projected_net_usd", "quote_observed_at"}


class ProposalError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def validate_offer(value, now=None):
    if type(value) is not dict or set(value) != FIELDS or value["provider"] != "vast":
        raise ProposalError("invalid_offer_contract")
    for name in ("offer_id", "machine_id", "host_id", "gpu_count", "max_minutes"):
        item = value[name]
        upper = 16 if name == "gpu_count" else 1440 if name == "max_minutes" else 10**15
        if type(item) is not int or not 1 <= item <= upper:
            raise ProposalError("invalid_" + name)
    if type(value["gpu_name"]) is not str or not re.fullmatch(r"[A-Za-z0-9 _-]{1,80}", value["gpu_name"]):
        raise ProposalError("invalid_gpu")
    for name, maximum in (("max_hourly_usd", 100), ("max_total_usd", 1000), ("projected_net_usd", 1000)):
        item = value[name]
        if type(item) not in (int, float) or not math.isfinite(item):
            raise ProposalError("invalid_" + name)
        if name == "projected_net_usd":
            if not -1000 <= item <= maximum:
                raise ProposalError("invalid_net")
        elif not 0 < item <= maximum:
            raise ProposalError("invalid_" + name)
    if value["max_hourly_usd"] * value["max_minutes"] / 60 > value["max_total_usd"] + 1e-9:
        raise ProposalError("compute_cost_exceeds_budget")
    stamp = value["quote_observed_at"]
    if type(stamp) is not str or len(stamp) > 35:
        raise ProposalError("invalid_quote_date")
    try:
        instant = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProposalError("invalid_quote_date") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ProposalError("quote_timezone_required")
    now = now or datetime.now(timezone.utc)
    if not timedelta(0) <= now - instant.astimezone(timezone.utc) <= timedelta(minutes=2):
        raise ProposalError("quote_not_fresh")
    return value


class ProposalStore:
    def __init__(self, path):
        self.db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS proposals(
            nonce TEXT PRIMARY KEY, provider TEXT NOT NULL, offer_id INTEGER NOT NULL,
            payload TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
            created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
            state TEXT NOT NULL, telegram_message_id INTEGER, decided_at INTEGER);
          CREATE TABLE IF NOT EXISTS audit(
            id INTEGER PRIMARY KEY, nonce TEXT NOT NULL, event TEXT NOT NULL, at INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS telegram_cursor(
            singleton INTEGER PRIMARY KEY CHECK(singleton=1), update_id INTEGER NOT NULL);
          INSERT OR IGNORE INTO telegram_cursor VALUES(1,-1);
          CREATE TABLE IF NOT EXISTS menu_outbox(
            update_id INTEGER PRIMARY KEY, action TEXT NOT NULL, created_at INTEGER NOT NULL);
        """)
        clore_decisions.init(self.db)
        gpu_search.init(self.db)

    def close(self):
        self.db.close()

    def prepare(self, offer, now=None):
        now = now or datetime.now(timezone.utc)
        payload = canonical(validate_offer(offer, now))
        tick = int(now.timestamp())
        nonce = secrets.token_hex(16)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            clash = self.db.execute("""SELECT 1 FROM proposals
                 WHERE provider=? AND offer_id=? AND expires_at>?
                 AND state IN ('pending','notified') LIMIT 1""",
                (offer["provider"], offer["offer_id"], tick)).fetchone()
            if clash:
                raise ProposalError("duplicate_active_offer")
            self.db.execute("""INSERT INTO proposals
                (nonce,provider,offer_id,payload,payload_sha256,created_at,expires_at,state)
                VALUES(?,?,?,?,?,?,?,'pending')""",
                (nonce, offer["provider"], offer["offer_id"], payload, digest(offer), tick, tick+300))
            self.db.execute("INSERT INTO audit(nonce,event,at) VALUES(?,?,?)",
                            (nonce, "created", tick))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"proposal_id": nonce, "digest": digest(offer),
                "expires_at": tick+300, "rental_permitted": False}

    def prepare_clore(self, terms, now=None):
        tick = int((now or datetime.now(timezone.utc)).timestamp())
        try:
            return clore_decisions.create(self.db, terms, tick)
        except ValueError as exc:
            raise ProposalError(str(exc)) from exc

    def pending_clore(self, now=None):
        return clore_decisions.pending(self.db, int(time.time() if now is None else now))

    def mark_clore_notified(self, nonce, message_id, now=None):
        return clore_decisions.mark_notified(
            self.db, nonce, message_id, int(time.time() if now is None else now))

    def clore_status(self, nonce):
        return clore_decisions.status(self.db, nonce)

    def pending(self, now=None):
        tick = int(time.time() if now is None else now)
        return self.db.execute("""SELECT nonce,payload,expires_at FROM proposals
               WHERE state='pending' AND expires_at>? ORDER BY created_at LIMIT 10""",
               (tick,)).fetchall()

    def mark_notified(self, nonce, message_id, now=None):
        tick = int(time.time() if now is None else now)
        if type(message_id) is not int or message_id <= 0:
            raise ProposalError("invalid_message_id")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            changed = self.db.execute("""UPDATE proposals SET state='notified',telegram_message_id=?
              WHERE nonce=? AND state='pending' AND expires_at>?""",
              (message_id, nonce, tick)).rowcount
            if changed:
                self.db.execute("INSERT INTO audit(nonce,event,at) VALUES(?,?,?)",
                                (nonce, "notified", tick))
            self.db.commit()
            return bool(changed)
        except Exception:
            self.db.rollback()
            raise

    def process_update(self, update, chat_id, user_id, now=None):
        tick = int(time.time() if now is None else now)
        if type(update) is not dict or type(update.get("update_id")) is not int:
            raise ProposalError("invalid_update")
        update_id = update["update_id"]
        if not 0 <= update_id < 2**63:
            raise ProposalError("invalid_update_id")
        answer = {"state": "ignored", "rental_permitted": False}
        self.db.execute("BEGIN IMMEDIATE")
        try:
            last = self.db.execute("SELECT update_id FROM telegram_cursor WHERE singleton=1").fetchone()[0]
            if update_id <= last:
                self.db.commit()
                return answer
            callback = update.get("callback_query")
            if type(callback) is dict:
                origin, msg, data = callback.get("from"), callback.get("message"), callback.get("data")
                chat = msg.get("chat") if type(msg) is dict else None
                if (type(origin) is dict and type(chat) is dict and
                        type(origin.get("id")) is int and origin["id"] == user_id and
                        type(chat.get("id")) is int and chat["id"] == chat_id and
                        chat.get("type") == "private" and type(data) is str):
                    match = re.fullmatch(r"(approve|reject):([0-9a-f]{32})", data)
                    if match:
                        choice, nonce = match.groups()
                        row = self.db.execute("""SELECT payload,payload_sha256,expires_at,state
                             FROM proposals WHERE nonce=?""", (nonce,)).fetchone()
                        if row is not None and row[3] == "notified":
                            state = ("expired" if row[2] <= tick else
                                     "invalid" if hashlib.sha256(row[0].encode()).hexdigest() != row[1] else
                                     "acknowledged" if choice == "approve" else "rejected")
                            changed = self.db.execute("""UPDATE proposals SET state=?,decided_at=?
                                    WHERE nonce=? AND state='notified'""",
                                    (state, tick, nonce)).rowcount
                            if changed:
                                self.db.execute("INSERT INTO audit(nonce,event,at) VALUES(?,?,?)",
                                                (nonce, state, tick))
                                answer.update(state=state, proposal_id=nonce)
                        elif row is not None and row[3] in ("acknowledged", "rejected"):
                            # The owner might retry the button after Telegram dropped
                            # the first callback acknowledgement. Do not imply failure.
                            answer.update(state="already_" + row[3], proposal_id=nonce)
                    elif re.fullmatch(r"clore-(accept|reject):([0-9a-f]{32})", data):
                        exact = re.fullmatch(r"clore-(accept|reject):([0-9a-f]{32})", data)
                        answer = clore_decisions.decide(
                            self.db, exact.group(1), exact.group(2),
                            msg.get("message_id"), tick)
                        if answer["state"].startswith("clore_"):
                            self.db.execute(
                                "INSERT INTO audit(nonce,event,at) VALUES(?,?,?)",
                                (exact.group(2), answer["state"], tick))
                    elif data in MENU_CALLBACKS:
                        # Existing static menu callbacks remain read-only.
                        answer.update(state="menu", action=data.split(":", 1)[1])
                    elif re.fullmatch(r"gpu-page:[a-f0-9]{16}:[0-9]{1,3}", data):
                        _, nonce, page_no = data.split(":")
                        page_message = msg.get("message_id")
                        try:
                            gpu_search.page(self.db, nonce, int(page_no), tick)
                            bound = self.db.execute(
                                "SELECT 1 FROM gpu_search_pages WHERE nonce=? AND message_id=?",
                                (nonce, page_message)).fetchone()
                            if not bound:
                                raise gpu_search.SearchError("unbound_page_message")
                            answer.update(state="menu", action=data)
                        except gpu_search.SearchError:
                            answer.update(state="gpu_invalid")
                    elif re.fullmatch(r"gpu-pick:[a-f0-9]{16}:[1-9][0-9]{0,14}", data):
                        _, nonce, offer_id = data.split(":")
                        try:
                            if gpu_search.select(self.db, nonce, int(offer_id),
                                                 msg.get("message_id"), tick):
                                answer.update(state="gpu_selected", nonce=nonce)
                            else:
                                answer.update(state="gpu_already_selected")
                        except gpu_search.SearchError:
                            answer.update(state="gpu_invalid")
            message = update.get("message")
            if type(message) is dict:
                origin, chat = message.get("from"), message.get("chat")
                if (type(origin) is dict and type(chat) is dict and
                        type(origin.get("id")) is int and origin["id"] == user_id and
                        type(chat.get("id")) is int and chat["id"] == chat_id and
                        chat.get("type") == "private"):
                    commands = {"/start": "home", "/menu": "home",
                                "/ofertas": "vast", "/estado": "status",
                                "/ayuda": "help"}
                    command = message.get("text")
                    if type(command) is str and command in commands:
                        answer.update(state="menu", action=commands[command])
                    elif type(command) is str and (command == "/gpu" or command.startswith("/gpu ")):
                        requested = gpu_search.parse_command(command)
                        if requested is not None:
                            answer.update(state="menu", action=gpu_search.search_action(requested))
            if answer["state"] in ("menu", "gpu_selected"):
                # Cursor and response outbox commit atomically.
                action = (answer["action"] if answer["state"] == "menu"
                          else "gpu-selected:" + answer["nonce"])
                self.db.execute("""INSERT OR IGNORE INTO menu_outbox(update_id,action,created_at)
                     VALUES(?,?,?)""", (update_id, action, tick))
            self.db.execute("UPDATE telegram_cursor SET update_id=? WHERE singleton=1", (update_id,))
            self.db.commit()
            return answer
        except Exception:
            self.db.rollback()
            raise

    def pending_menu(self):
        return self.db.execute("""SELECT update_id,action FROM menu_outbox
                 ORDER BY update_id LIMIT 10""").fetchall()

    def mark_menu_sent(self, update_id):
        self.db.execute("DELETE FROM menu_outbox WHERE update_id=?", (update_id,))

    def status(self, nonce):
        if type(nonce) is not str or not re.fullmatch("[0-9a-f]{32}", nonce):
            raise ProposalError("invalid_proposal_id")
        row = self.db.execute("SELECT state,expires_at,payload_sha256 FROM proposals WHERE nonce=?",
                              (nonce,)).fetchone()
        if row is None:
            raise ProposalError("proposal_not_found")
        return {"state": row[0], "expires_at": row[1],
                "digest": row[2], "rental_permitted": False}


class TelegramAPI:
    def __init__(self, token, transport=None):
        if type(token) is not str or not re.fullmatch(r"\d{5,15}:[A-Za-z0-9_-]{30,90}", token):
            raise ProposalError("invalid_token")
        self.endpoint = "https://api.telegram.org/bot" + token + "/"
        self.transport = transport or self._post

    @staticmethod
    def _post(url, data):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
        req = urllib.request.Request(url, data=canonical(data).encode(),
            method="POST", headers={"Content-Type": "application/json"})
        with opener.open(req, timeout=35) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ProposalError("telegram_response_too_large")
        return json.loads(raw)

    def call(self, method, data):
        if method not in ("sendMessage", "getUpdates", "answerCallbackQuery"):
            raise ProposalError("method_not_allowed")
        try:
            result = self.transport(self.endpoint + method, data)
            if type(result) is not dict or result.get("ok") is not True:
                raise ProposalError("telegram_unavailable")
            return result["result"]
        except (OSError, ValueError, KeyError) as exc:
            raise ProposalError("telegram_unavailable") from exc


def proposal_text(offer, seconds_remaining):
    if type(seconds_remaining) is not int or seconds_remaining <= 0:
        raise ProposalError("proposal_expired")
    return (
        "Hache Mining Agent - propuesta SIN contratar\n"
        f"Vast #{offer['offer_id']} | maquina {offer['machine_id']} | host {offer['host_id']}\n"
        f"GPU: {offer['gpu_count']} x {offer['gpu_name']}\n"
        f"Tarifa cotizada: USD {offer['max_hourly_usd']:.4f}/hora\n"
        f"Duracion: {offer['max_minutes']} min\n"
        f"Presupuesto indicado: USD {offer['max_total_usd']:.2f}\n"
        f"Neto estimado, no garantizado: USD {offer['projected_net_usd']:.2f}\n"
        f"Tiempo restante al enviar: {seconds_remaining} segundos. Faltan validar costos extra y autorizacion comercial.\n"
        "Aceptar SOLO registra tu decision: no habilita rentas ni gasto."
    )


class TelegramChannel:
    def __init__(self, store, api, chat_id, user_id):
        if type(chat_id) is not int or chat_id <= 0 or type(user_id) is not int or user_id <= 0:
            raise ProposalError("invalid_recipient")
        self.store, self.api, self.chat_id, self.user_id = store, api, chat_id, user_id

    def send_pending(self, now=None):
        sent = 0
        tick = int(time.time() if now is None else now)
        for nonce, raw, expires_at in self.store.pending(tick):
            remaining = expires_at - tick
            # Do not send almost-expired proposals that may mislead the owner.
            if remaining < 60:
                continue
            answer = self.api.call("sendMessage", {
                "chat_id": self.chat_id, "text": proposal_text(json.loads(raw), remaining),
                "reply_markup": {"inline_keyboard": [[
                    {"text": "Registrar aceptacion", "callback_data": "approve:" + nonce},
                    {"text": "Rechazar", "callback_data": "reject:" + nonce}
                ]]}
            })
            if type(answer) is not dict or type(answer.get("message_id")) is not int:
                raise ProposalError("invalid_delivery_receipt")
            sent += int(self.store.mark_notified(nonce, answer["message_id"], now))
        return sent

    def send_clore_pending(self, now=None):
        tick = int(time.time() if now is None else now)
        sent = 0
        for nonce, raw, expires, digest in self.store.pending_clore(tick):
            remaining = expires - tick
            if remaining < 60:
                continue
            receipt = self.api.call("sendMessage", {
                "chat_id": self.chat_id,
                "text": clore_decisions.message(json.loads(raw), digest, remaining),
                "reply_markup": clore_decisions.keyboard(nonce),
            })
            if type(receipt) is not dict or type(receipt.get("message_id")) is not int or receipt["message_id"] <= 0:
                raise ProposalError("invalid_clore_delivery_receipt")
            sent += int(self.store.mark_clore_notified(nonce, receipt["message_id"], tick))
        return sent

    def flush_menu_pending(self):
        delivered = 0
        for update_id, action in self.store.pending_menu():
            now = int(time.time())
            payload = None
            receipt_binding = None
            if action == "gpu-help":
                payload = {"text": ("Buscar GPUs Spot: /gpu 5090, /gpu 5090 laptop, "
                                    "/gpu 4070 ti super escritorio x2. "
                                    "Solo consulta y selección; no ejecuta pujas."),
                           "parse_mode": "HTML"}
            elif action.startswith("gpu-search:"):
                try:
                    q = gpu_search.parse_action(action)
                    candidates = gpu_search.fetch()
                    matches, total = gpu_search.offers(candidates, q)
                    if not matches:
                        payload = {"text": "No se encontraron ofertas Spot de esa GPU y cantidad. "
                                           "Prueba otro filtro. No se realizó ninguna puja.",
                                   "parse_mode": "HTML"}
                    else:
                        nonce = gpu_search.create(self.store.db, q, matches, total, now)
                        payload = gpu_search.page_reply(self.store.db, nonce, 0, now)
                        receipt_binding = (nonce, 0)
                except gpu_search.SearchError:
                    payload = {"text": "Clore no ofrece una respuesta válida ahora. "
                                       "Vuelve a consultar /gpu más tarde. No se gastó nada.",
                               "parse_mode": "HTML"}
            elif action.startswith("gpu-page:"):
                try:
                    _, nonce, n = action.split(":")
                    page_no = int(n)
                    payload = gpu_search.page_reply(self.store.db, nonce, page_no, now)
                    receipt_binding = (nonce, page_no)
                except (gpu_search.SearchError, ValueError):
                    payload = {"text": "La consulta Spot caducó. Repite /gpu para obtener precios nuevos.",
                               "parse_mode": "HTML"}
            elif action.startswith("gpu-selected:"):
                try:
                    payload = {"text": gpu_search.selected_reply(self.store.db, action.split(":")[1], now),
                               "parse_mode": "HTML"}
                except gpu_search.SearchError:
                    payload = {"text": "Selección caducada; repite /gpu. No se realizó ninguna puja.",
                               "parse_mode": "HTML"}
            else:
                payload = {"text": menu_reply(action), "parse_mode": "HTML",
                           "reply_markup": menu_markup()}
            result = self.api.call("sendMessage", {
                "chat_id": self.chat_id, "disable_web_page_preview": True, **payload,
            })
            if type(result) is not dict or type(result.get("message_id")) is not int or result["message_id"] <= 0:
                raise ProposalError("invalid_menu_delivery_receipt")
            if receipt_binding:
                gpu_search.record_page(self.store.db, *receipt_binding, result["message_id"], now)
            self.store.mark_menu_sent(update_id)
            delivered += 1
        return delivered

    def poll_once(self, now=None):
        # A failed send must not erase an authenticated owner command.
        self.flush_menu_pending()
        last = self.store.db.execute(
            "SELECT update_id FROM telegram_cursor WHERE singleton=1").fetchone()[0]
        updates = self.api.call("getUpdates", {
            "offset": last+1, "timeout": 20, "limit": 50,
            "allowed_updates": ["callback_query", "message"]})
        if type(updates) is not list or len(updates) > 50:
            raise ProposalError("invalid_telegram_updates")
        results = []
        for update in updates:
            result = self.store.process_update(update, self.chat_id, self.user_id, now)
            if result["state"] in ("menu", "gpu_selected"):
                # The read-only response survives restarts and send failures.
                self.flush_menu_pending()
            callback = update.get("callback_query") if type(update) is dict else None
            if type(callback) is dict and type(callback.get("id")) is str:
                self.api.call("answerCallbackQuery", {
                    "callback_query_id": callback["id"],
                    "text": ("Aceptacion registrada (sin rentar)" if result["state"] == "acknowledged"
                             else "Rechazo registrado" if result["state"] == "rejected"
                             else "Aceptacion ya registrada" if result["state"] == "already_acknowledged"
                             else "Rechazo ya registrado" if result["state"] == "already_rejected"
                             else "Consulta enviada" if result["state"] == "menu"
                             else "Oferta seleccionada, SIN pujar" if result["state"] == "gpu_selected"
                             else "Ya hay una selección" if result["state"] == "gpu_already_selected"
                             else "Oferta vencida o no vinculada" if result["state"] == "gpu_invalid"
                             else "Decisión Clore registrada (SIN alquilar)" if result["state"] == "clore_acknowledged"
                             else "Propuesta Clore rechazada" if result["state"] == "clore_rejected"
                             else "Decisión Clore ya registrada" if result["state"] == "already_clore_acknowledged"
                             else "Rechazo Clore ya registrado" if result["state"] == "already_clore_rejected"
                             else "Propuesta Clore inválida o caducada" if result["state"] in ("clore_expired","clore_invalid")
                             else "No autorizado o vencido")})
            results.append(result)
        return results


def load_token():
    cred = os.getenv("CREDENTIALS_DIRECTORY")
    if not cred:
        raise ProposalError("systemd_credentials_required")
    return (Path(cred) / "telegram_token").read_text().strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare-file")
    modes.add_argument("--prepare-clore-file")
    modes.add_argument("--status")
    modes.add_argument("--clore-status")
    modes.add_argument("--poll-once", action="store_true")
    modes.add_argument("--poll", action="store_true")
    parser.add_argument("--chat-id", type=int)
    parser.add_argument("--user-id", type=int)
    args = parser.parse_args(argv)
    store = ProposalStore(args.database)
    try:
        if args.prepare_file:
            path = Path(args.prepare_file)
            if path.stat().st_size > 8192:
                raise ProposalError("oversized_input")
            answer = store.prepare(json.loads(path.read_text()))
        elif args.prepare_clore_file:
            path = Path(args.prepare_clore_file)
            if path.stat().st_size > 8192:
                raise ProposalError("oversized_input")
            answer = store.prepare_clore(json.loads(path.read_text()))
        elif args.clore_status:
            answer = store.clore_status(args.clore_status)
        elif args.status:
            answer = store.status(args.status)
        else:
            if args.chat_id is None or args.user_id is None:
                raise ProposalError("recipient_required")
            channel = TelegramChannel(store, TelegramAPI(load_token()), args.chat_id, args.user_id)
            if args.poll_once:
                answer = {"sent": channel.send_pending() + channel.send_clore_pending(),
                          "callbacks": channel.poll_once(), "rental_permitted": False}
            else:
                while True:
                    try:
                        channel.send_pending()
                        channel.send_clore_pending()
                        channel.poll_once()
                    except ProposalError:
                        time.sleep(5)
        if not args.poll:
            print(canonical(answer))
    finally:
        store.close()


if __name__ == "__main__":
    try:
        main()
    except (ProposalError, sqlite3.Error, OSError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, ProposalError) else "input_or_storage_error"
        print(canonical({"ok": False, "error": reason, "rental_permitted": False}))
        sys.exit(2)
