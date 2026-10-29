#!/usr/bin/env python3
"""Owner-requested Clore Spot discovery for Telegram. Public GET only; never bid."""
from http.client import HTTPException
import html
import json
import math
import re
import secrets
import sqlite3
import ssl
import urllib.error
import urllib.request

API = "https://api.clore.ai/v1/marketplace"
MAX_RESPONSE = 8 * 1024 * 1024
MAX_ROWS = 10000
MAX_MATCHES = 100
PAGE_SIZE = 5
SNAPSHOT_TTL = 180

class SearchError(ValueError):
    pass

def parse_command(value):
    """Accept /gpu 5090 [laptop|desktop] [xN], never arbitrary Telegram text."""
    if type(value) is not str or not value.startswith("/gpu"):
        return None
    if value == "/gpu":
        return {"help": True}
    if not re.fullmatch(r"/gpu(?:@[A-Za-z0-9_]{5,32})? [A-Za-z0-9 ]{3,60}(?: x(?:[1-9]|1[0-6]))?", value, re.I):
        return {"help": True}
    words = value.split()[1:]
    count = 1
    if words and re.fullmatch(r"x(?:[1-9]|1[0-6])", words[-1], re.I):
        count = int(words.pop()[1:])
    variant = "any"
    if words and words[-1].lower() in ("laptop", "desktop", "escritorio"):
        variant = "desktop" if words.pop().lower() in ("desktop", "escritorio") else "laptop"
    model = " ".join(words).upper().strip()
    if not 3 <= len(model) <= 45 or not re.fullmatch(r"[A-Z0-9 ]+", model):
        return {"help": True}
    return {"model": model, "variant": variant, "count": count}

def search_action(query):
    if query.get("help"):
        return "gpu-help"
    return "gpu-search:" + query["model"] + ":" + query["variant"] + ":" + str(query["count"])

def parse_action(action):
    if type(action) is not str or len(action) > 110:
        raise SearchError("invalid_search_action")
    if action == "gpu-help":
        return {"help": True}
    match = re.fullmatch(r"gpu-search:([A-Z0-9 ]{3,45}):(any|desktop|laptop):(1[0-6]|[1-9])", action)
    if not match:
        raise SearchError("invalid_search_action")
    return {"model": match[1], "variant": match[2], "count": int(match[3])}

def fetch(*, transport=None):
    """One fixed public HTTPS endpoint. No redirect, API key or user URL."""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
    transport = transport or opener.open
    req = urllib.request.Request(API, method="GET",
                                 headers={"Accept": "application/json", "User-Agent": "Hache-Clore-ReadOnly/1"})
    try:
        with transport(req, timeout=22) as response:
            if getattr(response, "status", 200) != 200:
                raise SearchError("clore_not_available")
            body = response.read(MAX_RESPONSE + 1)
    except (OSError, urllib.error.URLError, TimeoutError, HTTPException) as exc:
        raise SearchError("clore_not_available") from exc
    if len(body) > MAX_RESPONSE:
        raise SearchError("clore_response_too_large")
    try:
        obj = json.loads(body)
    except (ValueError, UnicodeError) as exc:
        raise SearchError("clore_invalid_reply") from exc
    if (type(obj) is not dict or obj.get("code") != 0 or
            type(obj.get("servers")) is not list or len(obj["servers"]) > MAX_ROWS):
        raise SearchError("clore_invalid_reply")
    return obj["servers"]

def money(value):
    if type(value) not in (float, int) and not (type(value) is str and len(value) < 20):
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return round(num / 24, 6) if math.isfinite(num) and 0 < num < 2400 else None


def model_name(value):
    """Keep the complete GPU model and suffixes, removing only vendor labels."""
    if type(value) is not str:
        return ""
    name = re.sub(r"\s+", " ", value.upper().replace("-", " ")).strip()
    name = re.sub(r"^(?:(?:NVIDIA|GEFORCE|AMD|RADEON|INTEL)\s+)+", "", name)
    name = re.sub(r"\s+(?:LAPTOP|MOBILE)(?:\s+GPU)?$", "", name)
    name = re.sub(r"\s+GPU$", "", name)
    return name


def choose(server, query):
    """Require whole-rig exact GPU count; rank by floor, NOT invented profit."""
    if type(server) is not dict or server.get("rented") is not False:
        return None
    ident = server.get("id")
    specs = server.get("specs")
    gpus = server.get("gpu_array")
    price = server.get("price")
    if (type(ident) is not int or not 0 < ident < 10**15 or
            type(specs) is not dict or type(price) is not dict or
            type(gpus) is not list):
        return None
    label = specs.get("gpu")
    if type(label) is not str or len(label) > 150:
        return None
    count_match = re.match(r"^([1-9][0-9]?)x\s+(.+)$", label, re.I)
    if not count_match or int(count_match[1]) != len(gpus) or len(gpus) != query["count"]:
        return None
    # All model words must occur in order (e.g. 4070 TI SUPER).
    family = re.sub(r"\s+", " ", count_match[2].upper())
    # Compare the complete model instead of a prefix: 4070, 4070 TI and
    # 4070 TI SUPER are three different GPU products (likewise 5090 D).
    actual = model_name(family)
    requested = model_name(query["model"])
    if not requested or not any(c.isdigit() for c in requested):
        return None
    if actual != requested and not actual.endswith(" " + requested):
        return None
    # Clore gpu_array contains per-device model labels. Count alone does not
    # prove a uniform rig: reject a mixed 4070/5090 listing.
    if any(type(name) is not str or not 1 <= len(name) <= 120 or
           model_name(name) != actual for name in gpus):
        return None
    variant = "laptop" if re.search(r"\b(?:LAPTOP|MOBILE)\b", family) else "desktop_label"
    if query["variant"] == "laptop" and variant != "laptop":
        return None
    if query["variant"] == "desktop" and variant != "desktop_label":
        return None
    # Native USD-Blockchain minimum is directly comparable; converted crypto
    # offers are intentionally excluded here (not all-in executable quotes).
    spot = price.get("spot")
    ondemand = price.get("on_demand")
    if type(spot) is not dict or type(ondemand) is not dict:
        return None
    floor = money(spot.get("USD-Blockchain"))
    regular = money(ondemand.get("USD-Blockchain"))
    if floor is None or regular is None:
        return None
    net = specs.get("net")
    country = net.get("cc", "") if type(net) is dict else ""
    if type(country) is not str or not re.fullmatch(r"[A-Z]{2}", country):
        country = "??"
    ram = specs.get("gpuram")
    ram = round(float(ram), 1) if type(ram) in (int, float) and 0 < ram < 1024 else None
    return {"id": ident, "gpu": family[:95], "gpu_count": query["count"],
            "variant": variant, "floor_usd_hour": floor,
            "on_demand_usd_hour": regular, "country": country, "vram_gb": ram}

def offers(servers, query):
    if query.get("help"):
        raise SearchError("invalid_gpu_model")
    if type(servers) is not list:
        raise SearchError("invalid_marketplace")
    matches = [item for server in servers if (item := choose(server, query)) is not None]
    matches.sort(key=lambda x: (x["floor_usd_hour"], x["id"]))
    total = len(matches)
    return matches[:MAX_MATCHES], total

SCHEMA = """
CREATE TABLE IF NOT EXISTS gpu_search_snapshots(
 nonce TEXT PRIMARY KEY, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
 query TEXT NOT NULL, offers TEXT NOT NULL, total INTEGER NOT NULL,
 selected_id INTEGER
);
CREATE TABLE IF NOT EXISTS gpu_search_pages(
 nonce TEXT NOT NULL, page INTEGER NOT NULL, message_id INTEGER NOT NULL,
 PRIMARY KEY(nonce,page,message_id),
 FOREIGN KEY(nonce) REFERENCES gpu_search_snapshots(nonce)
);
CREATE TABLE IF NOT EXISTS gpu_selection_messages(
 nonce TEXT PRIMARY KEY, selected_id INTEGER NOT NULL, message_id INTEGER NOT NULL,
 FOREIGN KEY(nonce) REFERENCES gpu_search_snapshots(nonce)
);
"""

def init(db):
    db.executescript(SCHEMA)

def create(db, query, matches, total, tick):
    if len(matches) > MAX_MATCHES or total < len(matches):
        raise SearchError("invalid_search_snapshot")
    init(db)
    nonce = secrets.token_hex(8)
    db.execute("INSERT INTO gpu_search_snapshots VALUES(?,?,?,?,?,?,NULL)",
               (nonce, tick, tick + SNAPSHOT_TTL,
                json.dumps(query, sort_keys=True), json.dumps(matches, sort_keys=True), total))
    return nonce

def get(db, nonce, tick):
    if not re.fullmatch(r"[a-f0-9]{16}", nonce):
        raise SearchError("invalid_snapshot")
    row = db.execute("SELECT expires_at,query,offers,total,selected_id FROM gpu_search_snapshots WHERE nonce=?",
                     (nonce,)).fetchone()
    if not row or tick >= row[0]:
        raise SearchError("gpu_snapshot_expired")
    return {"query": json.loads(row[1]), "offers": json.loads(row[2]),
            "total": row[3], "selected_id": row[4]}

def page(db, nonce, page_number, tick):
    snap = get(db, nonce, tick)
    items = snap["offers"]
    last = max(0, (len(items) - 1) // PAGE_SIZE)
    if type(page_number) is not int or not 0 <= page_number <= last:
        raise SearchError("invalid_gpu_page")
    return snap, items[page_number*PAGE_SIZE:(page_number+1)*PAGE_SIZE], last

def page_reply(db, nonce, page_number, tick):
    snap, items, last = page(db, nonce, page_number, tick)
    q = snap["query"]
    lines = [f"<b>Clore Spot · {html.escape(q['model'])} · {q['count']} GPU</b>",
             f"Filtro: {html.escape(q['variant'])}. Encontradas: {snap['total']}; guardadas: {len(snap['offers'])}.",
             f"Página {page_number+1}/{last+1} · snapshot válido 3 minutos"]
    keyboard = []
    for item in items:
        variant = "Laptop (etiqueta)" if item["variant"] == "laptop" else "sin Laptop en etiqueta"
        lines.append(f"\n<b>#{item['id']}</b> · {html.escape(item['gpu'])}\n"
                     f"{item['country']} · {variant} · piso Spot US$ {item['floor_usd_hour']:.4f}/h"
                     f" · On-Demand US$ {item['on_demand_usd_hour']:.4f}/h")
        keyboard.append([{"text": f"Seleccionar #{item['id']}",
                          "callback_data": f"gpu-pick:{nonce}:{item['id']}"}])
    nav = []
    if page_number > 0:
        nav.append({"text": "Anterior", "callback_data": f"gpu-page:{nonce}:{page_number-1}"})
    if page_number < last:
        nav.append({"text": "Siguiente", "callback_data": f"gpu-page:{nonce}:{page_number+1}"})
    keyboard.append([{"text": "Comparar escenarios PRL",
                      "callback_data": f"gpu-rank:{nonce}"}])
    if nav:
        keyboard.append(nav)
    lines.append("\n<b>Ranking por precio mínimo publicado, NO por rentabilidad neta.</b>\n"
                 "Piso Spot no garantiza puja ganadora; equipo y disponibilidad requieren revalidación."
                 "\nSeleccionar no puja ni gasta.")
    return {"text": "\n".join(lines), "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": keyboard}}

def record_page(db, nonce, page_number, message_id, tick):
    page(db, nonce, page_number, tick)
    if type(message_id) is not int or message_id <= 0:
        raise SearchError("invalid_page_receipt")
    db.execute("INSERT OR IGNORE INTO gpu_search_pages VALUES(?,?,?)",
               (nonce, page_number, message_id))

def select(db, nonce, offer_id, message_id, tick):
    snap = get(db, nonce, tick)
    if type(offer_id) is not int or type(message_id) is not int:
        raise SearchError("invalid_choice")
    row = db.execute("SELECT page FROM gpu_search_pages WHERE nonce=? AND message_id=?",
                     (nonce, message_id)).fetchone()
    if not row:
        raise SearchError("unbound_page_message")
    choice = next((x for x in snap["offers"][row[0]*PAGE_SIZE:(row[0]+1)*PAGE_SIZE]
                   if x["id"] == offer_id), None)
    if choice is None:
        raise SearchError("offer_not_on_page")
    if snap["selected_id"] is not None:
        return False
    if db.execute("UPDATE gpu_search_snapshots SET selected_id=? WHERE nonce=? AND selected_id IS NULL",
                  (offer_id, nonce)).rowcount != 1:
        return False
    return True

def selected_reply(db, nonce, tick):
    snap = get(db, nonce, tick)
    item = next((x for x in snap["offers"] if x["id"] == snap["selected_id"]), None)
    if item is None:
        raise SearchError("selection_missing")
    return (f"<b>Oferta seleccionada #{item['id']}</b>\n"
            f"GPU: {html.escape(item['gpu'])}\n"
            f"Piso Spot mostrado: US$ {item['floor_usd_hour']:.4f}/h\n"
            "Se registró tu selección, sin puja ni alquiler.\n"
            "<b>Falta:</b> confirmar precio ejecutable, rentabilidad neta, "
            "presupuesto máximo, consentimiento financiero y watchdog antes de ofertar.")


def record_selection_message(db, nonce, message_id, tick):
    snap = get(db, nonce, tick)
    if type(message_id) is not int or not 0 < message_id < 10**15:
        raise SearchError("invalid_selection_receipt")
    selected_id = snap["selected_id"]
    if type(selected_id) is not int:
        raise SearchError("selection_missing")
    # First successful Telegram delivery binds the action; retries cannot move it.
    db.execute("INSERT OR IGNORE INTO gpu_selection_messages VALUES(?,?,?)",
               (nonce, selected_id, message_id))

def verify_quote_callback(db, nonce, server_id, message_id, tick):
    snap = get(db, nonce, tick)
    if type(server_id) is not int or server_id != snap["selected_id"]:
        raise SearchError("mismatched_quote_server")
    if type(message_id) is not int:
        raise SearchError("invalid_quote_message")
    row = db.execute(
        "SELECT selected_id FROM gpu_selection_messages "
        "WHERE nonce=? AND message_id=?", (nonce, message_id)).fetchone()
    if row is None or row[0] != server_id:
        raise SearchError("quote_not_bound_to_message")
    return server_id
