#!/usr/bin/env python3
"""One-use Clore offer decisions in the existing private Telegram bot.

Acknowledgement only: this module has no commercial API, spend permission,
broker socket, credential, or order binding.
"""
from datetime import datetime
import hashlib
import json
import re
import secrets

from clore_preorder import validate_terms
from clore_cancel_guard import GuardError

SCHEMA = """
CREATE TABLE IF NOT EXISTS clore_telegram_offers(
 nonce TEXT PRIMARY KEY,
 payload TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 created_at INTEGER NOT NULL,
 expires_at INTEGER NOT NULL,
 state TEXT NOT NULL CHECK(state IN
   ('pending','notified','acknowledged','rejected','expired','invalid')),
 message_id INTEGER,
 decided_at INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS clore_telegram_single_open
 ON clore_telegram_offers((1))
 WHERE state IN ('pending','notified');
"""


def init(db):
    db.executescript(SCHEMA)


def create(db, terms, tick):
    """The exact, verified quote determines the immutable Telegram receipt."""
    try:
        raw = validate_terms(terms, tick)
    except (GuardError, ValueError, TypeError) as exc:
        raise ValueError("invalid_clore_offer") from exc
    quote_tick = int(datetime.fromisoformat(
        terms["quote_observed_at"].replace("Z", "+00:00")).timestamp())
    expires = min(tick + 120, quote_tick + 120)
    if expires - tick < 60:
        raise ValueError("clore_quote_too_close_to_expiry")
    nonce = secrets.token_hex(16)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    db.execute("BEGIN IMMEDIATE")
    try:
        # Expired offers cannot approve spending; release the UI slot only
        # after their exact expiry, even across process restarts.
        db.execute("""UPDATE clore_telegram_offers SET state='expired'
           WHERE state IN ('pending','notified') AND expires_at<=?""",(tick,))
        if db.execute("""SELECT 1 FROM clore_telegram_offers
             WHERE state IN ('pending','notified') LIMIT 1""").fetchone():
            raise ValueError("existing_clore_offer")
        db.execute("""INSERT INTO clore_telegram_offers
          (nonce,payload,payload_sha256,created_at,expires_at,state)
          VALUES(?,?,?,?,?,'pending')""",(nonce,raw,digest,tick,expires))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"proposal_id":nonce,"digest":digest,"expires_at":expires,
            "decision_only":True,"rental_permitted":False}


def pending(db,tick):
    return db.execute("""SELECT nonce,payload,expires_at,payload_sha256
          FROM clore_telegram_offers
          WHERE state='pending' AND expires_at>? ORDER BY created_at
          LIMIT 1""",(tick,)).fetchall()


def mark_notified(db,nonce,message_id,tick):
    if type(message_id) is not int or message_id <= 0:
        raise ValueError("invalid_clore_delivery_receipt")
    db.execute("BEGIN IMMEDIATE")
    try:
        changed=db.execute("""UPDATE clore_telegram_offers
          SET state='notified',message_id=?
          WHERE nonce=? AND state='pending' AND expires_at>?""",
          (message_id,nonce,tick)).rowcount
        db.commit()
        return changed==1
    except Exception:
        db.rollback()
        raise


def decide(db,choice,nonce,callback_message_id,tick):
    """Must be called from the parent's authenticated private callback transaction."""
    if choice not in ("accept","reject") or not re.fullmatch("[0-9a-f]{32}",nonce):
        return {"state":"ignored","rental_permitted":False}
    row=db.execute("""SELECT payload,payload_sha256,expires_at,state,message_id
          FROM clore_telegram_offers WHERE nonce=?""",(nonce,)).fetchone()
    if row is None:
        return {"state":"ignored","rental_permitted":False}
    raw,digest,expires,state,message_id=row
    # Telegram callback MUST originate from the exact delivered message, not
    # an old forward, fabricated ID or a similar proposal.
    if type(callback_message_id) is not int or callback_message_id != message_id:
        return {"state":"ignored","rental_permitted":False}
    if state in ("acknowledged","rejected"):
        return {"state":"already_clore_"+state,"rental_permitted":False}
    if state!="notified":
        return {"state":"ignored","rental_permitted":False}
    if tick >= expires:
        decided="expired"
    elif hashlib.sha256(raw.encode()).hexdigest()!=digest:
        decided="invalid"
    else:
        try:
            validate_terms(json.loads(raw),tick)
        except (GuardError,ValueError,TypeError):
            decided="expired"
        else:
            decided="acknowledged" if choice=="accept" else "rejected"
    changed=db.execute("""UPDATE clore_telegram_offers SET state=?,decided_at=?
       WHERE nonce=? AND state='notified' AND message_id=?""",
       (decided,tick,nonce,message_id)).rowcount
    if changed!=1:
        raise ValueError("clore_decision_concurrency")
    return {"state":"clore_"+decided,"proposal_id":nonce,
            "digest":digest,"decision_only":True,"rental_permitted":False}


def status(db,nonce):
    if type(nonce) is not str or not re.fullmatch("[0-9a-f]{32}",nonce):
        raise ValueError("invalid_clore_proposal_id")
    row=db.execute("""SELECT state,payload_sha256,expires_at
          FROM clore_telegram_offers WHERE nonce=?""",(nonce,)).fetchone()
    if row is None:
        raise ValueError("clore_proposal_not_found")
    return {"state":row[0],"digest":row[1],"expires_at":row[2],
            "decision_only":True,"rental_permitted":False}


def message(terms,digest,remaining):
    if remaining < 60 or type(terms) is not dict:
        raise ValueError("clore_proposal_expired")
    return (
        "HACHE MINING AGENT · CLORE SPOT\n"
        "PROPUESTA PARA REVISIÓN — NO CONTRATA\n"
        f"Servidor exacto: #{terms['server_id']}\n"
        f"GPU: {terms['gpu_descriptor']} ({terms['gpu_variant']})\n"
        f"Moneda: USD-Blockchain (saldo USDT/USDC)\n"
        f"Puja diaria máxima: USD {terms['daily_bid_usd']}\n"
        f"Cargo de creación: USD {terms['creation_fee_usd']}\n"
        f"Presupuesto total: USD {terms['max_total_usd']}\n"
        f"Duración autorizable: {terms['max_minutes']} minutos\n"
        f"Imagen fijada: {terms['image']}\n"
        f"Huella SHA256 de términos: {digest}\n"
        f"Vigencia restante: {remaining} segundos\n"
        "Aceptar SOLO registra una decisión asociada a estos términos.\n"
        "NO concede un permiso de gasto, NO alquila ni inicia minería."
    )


def keyboard(nonce):
    return {"inline_keyboard":[[
        {"text":"Registrar aprobación (SIN alquilar)","callback_data":"clore-accept:"+nonce},
        {"text":"Rechazar","callback_data":"clore-reject:"+nonce}
    ]]}
