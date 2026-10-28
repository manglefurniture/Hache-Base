"""Clore Spot quote consumer in isolated Telegram process. Never sees API key."""
from datetime import datetime, timezone
import html
import json
import math
import socket

SOCKET = "/run/hache-clore-spot/quote.sock"
MAX_REPLY = 4096

class QuoteUnavailable(ValueError):
    pass

def get_quote(server_id, *, sock_path=SOCKET, connector=None):
    if type(server_id) is not int or not 0 < server_id < 10**15:
        raise QuoteUnavailable("invalid_server_id")
    request = (json.dumps({"server_id":server_id},separators=(",",":"))+"\n").encode()
    try:
        connection = connector() if connector else socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        with connection:
            connection.settimeout(17)
            connection.connect(sock_path)
            connection.sendall(request)
            with connection.makefile("rb") as f:
                raw=f.readline(MAX_REPLY+1)
        if not raw or len(raw)>MAX_REPLY or not raw.endswith(b"\n"):
            raise QuoteUnavailable("invalid_quote_reply")
        payload=json.loads(raw)
    except (OSError, ValueError, UnicodeError):
        raise QuoteUnavailable("quote_service_unavailable") from None
    if type(payload) is not dict or payload.get("ok") is not True:
        raise QuoteUnavailable("quote_service_unavailable")
    p=payload.get("result")
    if (type(p) is not dict or p.get("server_id")!=server_id or
            p.get("source")!="clore_spot_marketplace_authenticated_readonly" or
            p.get("currency")!="USD-Blockchain" or
            p.get("rental_permitted") is not False or
            p.get("executable_quote") is not False or
            p.get("net_profit_verified") is not False or
            p.get("online") is not True or p.get("public") is not True):
        raise QuoteUnavailable("unsafe_quote_reply")
    for field in ("minimum_usd_day","highest_bid_usd_day",
                  "illustrative_1pct_usd_day","illustrative_1pct_usd_hour"):
        v=p.get(field)
        if type(v) not in (float,int) or not math.isfinite(v) or not 0<=v<=100000:
            raise QuoteUnavailable("invalid_quote_values")
    if p["illustrative_1pct_usd_day"]<max(p["minimum_usd_day"],p["highest_bid_usd_day"]):
        raise QuoteUnavailable("invalid_quote_values")
    for field in ("bid_count","active_bids","own_bids"):
        if type(p.get(field)) is not int or not 0 <= p[field] <= 1000:
            raise QuoteUnavailable("invalid_quote_values")
    try:
        stamp=datetime.fromisoformat(p["observed_at"].replace("Z","+00:00"))
        now=datetime.now(timezone.utc)
        age=(now-stamp.astimezone(timezone.utc)).total_seconds()
    except (ValueError,KeyError,AttributeError):
        raise QuoteUnavailable("invalid_quote_timestamp") from None
    if stamp.tzinfo is None or not 0 <= age <= 120:
        raise QuoteUnavailable("stale_quote_reply")
    return p

def format_quote(p):
    """Only validated numeric data, no untrusted host names or HTML injection."""
    return (
        f"<b>Clore Spot · servidor #{p['server_id']}</b>\n"
        f"Piso Spot del host: US$ {p['minimum_usd_day']:.4f}/día\n"
        f"Puja competidora máxima: US$ {p['highest_bid_usd_day']:.4f}/día\n"
        f"Ofertas vigentes: {p['bid_count']} (activas: {p['active_bids']})\n"
        f"Ejemplo orientativo para superar la competencia (+1 %): "
        f"US$ {p['illustrative_1pct_usd_day']:.4f}/día "
        f"(US$ {p['illustrative_1pct_usd_hour']:.4f}/hora)\n\n"
        "<b>NO es una cotización ejecutable ni una puja ganadora garantizada.</b> "
        "El mínimo de Clore puede cambiar y faltan comisiones, rendimiento "
        "real de PRL y rentabilidad neta. No se ha pujado ni alquilado."
    )
