#!/usr/bin/env python3
"""Clore budget-consent preview. NEVER places bids, grants spend or calls provider POST.

Runs inside the isolated Telegram account. An accepted receipt here is
proof of a user's intent to review an exact quote, NOT a financial grant.
A future independent financial executor must verify and authorize again.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_UP
import hashlib
import html
import json
import re
import secrets

from telegram_clore_search import SearchError, get as get_snapshot
from telegram_clore_competition import get_quote, QuoteUnavailable
from telegram_prl_scenario import get_pool_snapshot, compute, ProfitError

SCHEMA = """
CREATE TABLE IF NOT EXISTS clore_bid_previews(
 nonce TEXT PRIMARY KEY, source_nonce TEXT NOT NULL,
 update_id INTEGER NOT NULL UNIQUE, server_id INTEGER NOT NULL,
 terms_json TEXT NOT NULL, digest TEXT NOT NULL,
 created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('prepared','notified','reviewed','rejected','expired')),
 message_id INTEGER, decided_at INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS clore_bid_one_open
 ON clore_bid_previews((1)) WHERE state IN ('prepared','notified');
"""
MAX_AGE = 90

class BidPreviewError(ValueError):
    pass

def init(db):
    db.executescript(SCHEMA)

def money(value, name):
    if type(value) is not str or not re.fullmatch(r"[0-9]{1,4}(?:\.[0-9]{1,2})?",value):
        raise BidPreviewError("invalid_"+name)
    try:
        number=Decimal(value)
    except InvalidOperation:
        raise BidPreviewError("invalid_"+name) from None
    if not number.is_finite() or not Decimal("0.01") <= number <= Decimal("1000"):
        raise BidPreviewError("invalid_"+name)
    return number

def parse_command(command):
    """Exact server selection is mandatory; never infer a paid action."""
    if type(command) is not str or not command.startswith("/puja"):
        return None
    m=re.fullmatch(r"/puja ([1-9][0-9]{0,14}) ([0-9]{1,4}(?:\.[0-9]{1,2})?) "
                   r"([0-9]{1,4}(?:\.[0-9]{1,2})?) "
                   r"(1[0-9]{3}|[1-9][0-9]{0,2})",command)
    if not m:
        return {"help":True}
    ident,day,budget,minutes=m.groups()
    minutes=int(minutes)
    if not 2 <= minutes <= 1440:
        return {"help":True}
    try:
        bid=money(day,"daily_bid")
        cap=money(budget,"total_budget")
    except BidPreviewError:
        return {"help":True}
    if bid > 100 or cap > 1000:
        return {"help":True}
    return {"server_id":int(ident),"day":f"{bid:.2f}",
            "budget":f"{cap:.2f}","minutes":minutes}

def action(command):
    if command.get("help"):
        return "bid-help"
    return (f"bid-prepare:{command['server_id']}:{command['day']}:"
            f"{command['budget']}:{command['minutes']}")

def from_action(value):
    if value=="bid-help":
        return {"help":True}
    m=re.fullmatch(r"bid-prepare:([1-9][0-9]{0,14}):([0-9]{1,4}\.[0-9]{2}):"
                   r"([0-9]{1,4}\.[0-9]{2}):([0-9]{1,4})",value)
    if not m:
        raise BidPreviewError("invalid_bid_action")
    return parse_command(f"/puja {m[1]} {m[2]} {m[3]} {m[4]}") or {"help":True}

def lookup_selected(db, server_id, tick):
    # The server must have been selected by the owner and still appear
    # in the exact short-lived marketplace snapshot.
    rows=db.execute("""SELECT nonce FROM gpu_search_snapshots
      WHERE selected_id=? AND expires_at>? ORDER BY created_at DESC LIMIT 2""",
      (server_id,tick)).fetchall()
    if not rows:
        raise BidPreviewError("selected_offer_expired")
    for (nonce,) in rows:
        snap=get_snapshot(db,nonce,tick)
        matched=[x for x in snap["offers"] if x["id"]==server_id]
        if len(matched)!=1:
            raise BidPreviewError("untrusted_selected_offer")
        # Selection must have been delivered in the private chat.
        if not db.execute("SELECT 1 FROM gpu_selection_messages WHERE nonce=? "
                          "AND selected_id=? LIMIT 1",(nonce,server_id)).fetchone():
            continue
        return nonce,matched[0]
    raise BidPreviewError("selection_not_delivered")

def evaluate(db, command, tick, *, quote_reader=get_quote, pool_reader=get_pool_snapshot):
    if command.get("help"):
        raise BidPreviewError("invalid_budget_command")
    server_id=command["server_id"]
    nonce,offer=lookup_selected(db,server_id,tick)
    bid=money(command["day"],"daily_bid")
    budget=money(command["budget"],"total_budget")
    minutes=command["minutes"]
    if not 2<=minutes<=1440:
        raise BidPreviewError("invalid_duration")
    try:
        quote=quote_reader(server_id)
        if quote["server_id"]!=server_id or quote["rental_permitted"] is not False:
            raise BidPreviewError("unsafe_spot_quote")
        # A higher competing offer may require a larger bid at execution,
        # but never silently raise the user's declared maximum.
        min_day=Decimal(str(quote["minimum_usd_day"]))
        top=Decimal(str(quote["highest_bid_usd_day"]))
        guide=Decimal(str(quote["illustrative_1pct_usd_day"]))
        if bid < min_day or (top>0 and bid<guide):
            raise BidPreviewError("bid_below_current_competition")
        if minutes>Decimal(str(quote["server_mrl_hours"]))*60:
            raise BidPreviewError("duration_exceeds_provider_mrl")
    except (QuoteUnavailable,KeyError,TypeError,InvalidOperation,ValueError) as exc:
        if isinstance(exc,BidPreviewError):
            raise
        raise BidPreviewError("spot_quote_unavailable") from None
    # Budget is USD-Blockchain (USDT/USDC-equivalent USD), not a guarantee.
    # 20% operational cushion plus $1 *hypothetical* creation fee headroom.
    estimated=(bid*Decimal(minutes)/Decimal(1440))*Decimal("1.20")+Decimal("1")
    if budget<estimated:
        raise BidPreviewError("total_budget_below_cautious_reserve")
    try:
        market=pool_reader()
        scenario_offer={**offer,"floor_usd_hour":float(bid/24)}
        scenario=compute(scenario_offer,market)
    except (ProfitError,ValueError,TypeError):
        raise BidPreviewError("prl_economic_data_unavailable") from None
    if scenario["stress_margin_usd_day"] <= 0:
        raise BidPreviewError("projected_negative_downside_margin")
    expiry=min(tick+MAX_AGE,int(datetime.fromisoformat(
        quote["observed_at"].replace("Z","+00:00")).timestamp())+120)
    if expiry-tick<30:
        raise BidPreviewError("spot_quote_too_old")
    terms={
        "server_id":server_id,"snapshot_nonce":nonce,
        "gpu":offer["gpu"],"variant_label":offer["variant"],
        "bid_max_usd_day":f"{bid:.2f}",
        "total_max_usd_blockchain":f"{budget:.2f}",
        "duration_max_minutes":minutes,
        "estimate_with_reserve_usd":f"{estimated.quantize(Decimal('0.01'),rounding=ROUND_UP):.2f}",
        "estimated_margin_stress_usd_day":scenario["stress_margin_usd_day"],
        "quote_observed_at":quote["observed_at"],
        "price_floor_usd_day":quote["minimum_usd_day"],
        "competitor_top_usd_day":quote["highest_bid_usd_day"],
        "pool_source":scenario["source"],
        "rental_permitted":False,
        "provider_mutation":False,
        "financial_grant":False,
        "image_and_creation_fee_verified":False
    }
    return terms,expiry

def create(db, *, update_id, command, tick, quote_reader=get_quote,
           pool_reader=get_pool_snapshot):
    if type(update_id) is not int or type(tick) is not int:
        raise BidPreviewError("invalid_request")
    row=db.execute("SELECT nonce FROM clore_bid_previews WHERE update_id=?",(update_id,)).fetchone()
    if row:
        return row[0]
    terms,expiry=evaluate(db,command,tick,quote_reader=quote_reader,pool_reader=pool_reader)
    raw=json.dumps(terms,sort_keys=True,separators=(",",":"),allow_nan=False)
    digest=hashlib.sha256(raw.encode()).hexdigest()
    db.execute("UPDATE clore_bid_previews SET state='expired' "
               "WHERE state IN ('prepared','notified') AND expires_at<=?",(tick,))
    if db.execute("SELECT 1 FROM clore_bid_previews WHERE state IN ('prepared','notified') LIMIT 1").fetchone():
        raise BidPreviewError("existing_budget_preview")
    nonce=secrets.token_hex(16)
    db.execute("INSERT INTO clore_bid_previews VALUES(?,?,?,?,?,?,?,?,'prepared',NULL,NULL)",
               (nonce,terms["snapshot_nonce"],update_id,terms["server_id"],raw,digest,tick,expiry))
    return nonce

def render(db,nonce,tick):
    row=db.execute("SELECT terms_json,expires_at,state FROM clore_bid_previews WHERE nonce=?",
                   (nonce,)).fetchone()
    if not row or tick>=row[1] or row[2] not in ("prepared","notified"):
        raise BidPreviewError("budget_preview_expired")
    t=json.loads(row[0])
    msg=(
        f"<b>Preautorización de límites — Clore #{t['server_id']}</b>\n"
        f"GPU anunciada: {html.escape(t['gpu'])}\n"
        f"Puja máxima: US$ {t['bid_max_usd_day']}/día\n"
        f"Tope total: US$ {t['total_max_usd_blockchain']} (USD-Blockchain)\n"
        f"Tiempo máximo: {t['duration_max_minutes']} min\n"
        f"Reserva ilustrativa: US$ {t['estimate_with_reserve_usd']}\n"
        f"Margen adverso estimado: US$ {t['estimated_margin_stress_usd_day']:+.2f}/día\n"
        f"Piso Clore al consultar: US$ {t['price_floor_usd_day']:.4f}/día\n"
        f"Mayor puja al consultar: US$ {t['competitor_top_usd_day']:.4f}/día\n"
        f"Vigencia: {row[1]-tick} segundos\n\n"
        "<b>La aprobación registra límites, NO CONTRATA.</b> "
        "Faltan comisión de creación real, imagen por SHA, validación "
        "de GPU, autorización financiera independiente y protección "
        "de orden desde antes del POST. No se gastan USDT."
    )
    return {"text":msg,"parse_mode":"HTML","reply_markup":{"inline_keyboard":[[
        {"text":"Confirmar límites (SIN PUJAR)","callback_data":"bid-review:"+nonce},
        {"text":"Cancelar","callback_data":"bid-reject:"+nonce}
    ]] }}

def mark_sent(db,nonce,message_id,tick):
    if type(message_id) is not int or message_id<=0:
        raise BidPreviewError("invalid_message_receipt")
    row=db.execute("UPDATE clore_bid_previews SET state='notified',message_id=? "
                   "WHERE nonce=? AND state='prepared' AND expires_at>?",
                   (message_id,nonce,tick)).rowcount
    if not row:
        existing=db.execute("SELECT message_id FROM clore_bid_previews WHERE nonce=?",
                            (nonce,)).fetchone()
        if not existing or existing[0]!=message_id:
            raise BidPreviewError("not_notifiable")
    return True

def decide(db,nonce,message_id,choice,tick):
    if (type(nonce) is not str or not re.fullmatch(r"[0-9a-f]{32}",nonce)
            or choice not in ("review","reject")
            or type(message_id) is not int):
        return "invalid_budget_confirmation"
    row=db.execute("SELECT state,message_id,expires_at,terms_json,digest FROM clore_bid_previews "
                   "WHERE nonce=?",(nonce,)).fetchone()
    if not row or row[1]!=message_id:
        return "invalid_budget_confirmation"
    if row[0] in ("reviewed","rejected"):
        return "already_budget_decided"
    if row[0]!="notified" or tick>=row[2]:
        return "budget_expired"
    if hashlib.sha256(row[3].encode()).hexdigest()!=row[4]:
        return "budget_tampered"
    state="reviewed" if choice=="review" else "rejected"
    db.execute("UPDATE clore_bid_previews SET state=?,decided_at=? "
               "WHERE nonce=? AND state='notified'",(state,tick,nonce))
    return ("budget_limits_recorded_no_spend" if choice=="review"
            else "budget_limits_rejected")
