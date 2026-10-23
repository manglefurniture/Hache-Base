#!/usr/bin/env python3
"""Private Telegram alerts for the read-only market scout.

Runs as hache-telegram. Reads only the sanitized spool from gpt-agent,
has no broker permissions and no rental or approval functionality.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import pwd
import grp
import re
import sqlite3
import stat
import sys
from zoneinfo import ZoneInfo

from telegram_proposals import TelegramAPI, load_token, ProposalError

REPORT = Path("/var/lib/hache-mining-market/report.json")
DATABASE = Path("/var/lib/hache-mining-telegram/market-notify.sqlite")
LOCAL_TZ = ZoneInfo("America/Cancun")
UTC = timezone.utc


class NotifyError(ValueError):
    pass


def load_report(path=REPORT, now=None, *, source_uid=None, source_gid=None):
    now = now or datetime.now(UTC)
    path = Path(path)
    directory = path.parent.lstat()
    file_info = path.lstat()
    if (not stat.S_ISDIR(directory.st_mode) or
        directory.st_mode & 0o027 or
        not stat.S_ISREG(file_info.st_mode) or
        file_info.st_mode & 0o027 or
        file_info.st_size < 100 or file_info.st_size > 65536 or
        file_info.st_nlink != 1):
        raise NotifyError("untrusted_report")
    if source_uid is not None and (directory.st_uid != source_uid or file_info.st_uid != source_uid):
        raise NotifyError("wrong_report_owner")
    if source_gid is not None and (directory.st_gid != source_gid or file_info.st_gid != source_gid):
        raise NotifyError("wrong_report_group")
    report = json.loads(path.read_text())
    if type(report) is not dict or report.get("mode") != "read_only" or report.get("rental_permitted") is not False:
        raise NotifyError("invalid_report")
    if report.get("sources_checked") != ["vast.marketplace", "clore.marketplace"] or not (
        report.get("net_profit_verified") is False and
        report.get("per_gpu_prl_verified") is False and
        report.get("prl_market_price_verified") is False
    ):
        raise NotifyError("unexpected_scout_claim")
    stamp = report.get("observed_at")
    if type(stamp) is not str or len(stamp) > 35:
        raise NotifyError("invalid_report_time")
    try:
        observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            raise ValueError("no tz")
        age = now - observed.astimezone(UTC)
    except ValueError as exc:
        raise NotifyError("invalid_report_time") from exc
    if not timedelta(0) <= age <= timedelta(minutes=10):
        raise NotifyError("stale_report")
    offers = report.get("offers")
    if type(offers) is not list or len(offers) > 8:
        raise NotifyError("invalid_offers")
    for offer in offers:
        if type(offer) is not dict or offer.get("net_verified") is not False or offer.get("gpu_variant_verified") is not False:
            raise NotifyError("inaccurate_profit_claim")
        if offer.get("provider") not in ("vast", "clore"):
            raise NotifyError("invalid_provider")
    return report


def prices(report):
    result = {}
    for offer in report["offers"]:
        name = offer.get("gpu_name")
        ident = offer.get("offer_id")
        count = offer.get("gpu_count")
        rate = offer.get("on_demand_usd_hour")
        variant = offer.get("gpu_variant")
        if (type(name) is not str or type(ident) is not int or
            type(count) is not int or variant not in ("desktop", "laptop", "unverified") or
            type(rate) not in (int, float) or not 0 < rate <= 100):
            raise NotifyError("invalid_offer")
        key = json.dumps([offer["provider"], name, variant, count], separators=(",", ":"))
        result[key] = round(float(rate), 6)
    return result


def decide(report, state, now):
    """Initial digest, once a day, or >=12% improved *same-model* quote.

    At most two messages per Cancun calendar day and at least six hours
    between notifications. A Spot minimum alone is never a deal alert.
    """
    old_tick, old_day, sent_today, previous = state
    today = now.astimezone(LOCAL_TZ).date().isoformat()
    count = sent_today if old_day == today else 0
    if count >= 2:
        return "skip"
    if old_tick is None:
        return "initial"
    if now.timestamp() - old_tick < 21600:
        return "skip"
    if now.timestamp() - old_tick >= 86400:
        return "daily_digest"
    current = prices(report)
    for key, value in current.items():
        older = previous.get(key)
        if type(older) in (int, float) and older > 0 and value <= 0.88 * older:
            return "improved_advertised_quote"
    return "skip"


def render(report, reason):
    heading = ("Hache Mining Agent | Comparador Vast + Clore\n"
               "Solo observación: SIN renta, puja ni gasto\n")
    if reason == "improved_advertised_quote":
        heading += "Cambio detectado: bajó una tarifa anunciada comparable.\n"
    elif reason == "daily_digest":
        heading += "Resumen diario de tarifas para revisar.\n"
    else:
        heading += "Primera lectura de ambos proveedores.\n"
    model_tag = {"desktop": "escritorio (etiqueta)", "laptop": "Laptop (etiqueta)",
                 "unverified": "variante desconocida"}
    lines = [heading]
    for provider, description in (("vast", "Vast.ai On-Demand"),
                                  ("clore", "Clore.ai On-Demand / Spot")):
        lines.append(description + ":")
        matches = [o for o in report["offers"] if o["provider"] == provider]
        if not matches:
            lines.append("  Sin muestras aptas en esta consulta (no implica falta de oferta).")
        for offer in matches:
            name = re.sub(r"[\x00-\x1f\x7f-\x9f<>]", "", offer["gpu_name"])[:75]
            line = (f"  #{offer['offer_id']}: {offer['gpu_count']}x {name}"
                    f" [{model_tag[offer['gpu_variant']]}]"
                    f" USD {offer['on_demand_usd_hour']:.4f}/h")
            if provider == "clore" and type(offer.get("spot_floor_usd_hour")) in (int, float):
                line += f" | Spot mínimo {offer['spot_floor_usd_hour']:.4f}/h"
            lines.append(line)
    lines.append("Kryptex pool: " + (
        "datos recientes; NO atribuibles a una GPU" if report["pool_recent"] else
        "dato reciente no disponible"))
    lines.append("Rentabilidad neta: NO verificada (faltan PRL/GPU, precio de venta fresco y costos totales).")
    lines.append("Precios orientativos por servidor; Spot mínimo NO es puja ganadora.")
    return "\n".join(lines)[:3500]


class NotificationState:
    def __init__(self, path=DATABASE):
        self.db = sqlite3.connect(path, timeout=5, isolation_level=None)
        self.db.execute("""CREATE TABLE IF NOT EXISTS market_alert_state (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            last_sent INTEGER NOT NULL, cancun_day TEXT NOT NULL,
            sent_today INTEGER NOT NULL, last_rates TEXT NOT NULL)""")

    def current(self):
        row = self.db.execute(
            "SELECT last_sent,cancun_day,sent_today,last_rates FROM market_alert_state WHERE singleton=1"
        ).fetchone()
        if row is None:
            return None, "", 0, {}
        try:
            record = json.loads(row[3])
        except (TypeError, ValueError) as exc:
            raise NotifyError("corrupt_notification_state") from exc
        if type(record) is not dict or type(row[2]) is not int:
            raise NotifyError("corrupt_notification_state")
        return row[0], row[1], row[2], record

    def saved(self, report, when):
        day = when.astimezone(LOCAL_TZ).date().isoformat()
        old_day = self.current()[1]
        old_count = self.current()[2] if old_day == day else 0
        self.db.execute("""INSERT INTO market_alert_state
            (singleton,last_sent,cancun_day,sent_today,last_rates)
            VALUES(1,?,?,?,?)
            ON CONFLICT(singleton) DO UPDATE SET
                last_sent=excluded.last_sent,
                cancun_day=excluded.cancun_day,
                sent_today=excluded.sent_today,
                last_rates=excluded.last_rates""",
            (int(when.timestamp()), day, old_count + 1,
             json.dumps(prices(report), separators=(",", ":"))))

    def close(self):
        self.db.close()


def send_report(api, chat_id, report, state, now):
    reason = decide(report, state.current(), now)
    if reason == "skip":
        return "unchanged"
    answer = api.call("sendMessage", {
        "chat_id": chat_id, "text": render(report, reason),
        "disable_web_page_preview": True,
    })
    if type(answer) is not dict or type(answer.get("message_id")) is not int:
        raise NotifyError("telegram_receipt_missing")
    state.saved(report, now)
    return reason


def main():
    if os.geteuid() == 0:
        raise NotifyError("do_not_run_as_root")
    now = datetime.now(UTC)
    uid = pwd.getpwnam("gpt-agent").pw_uid
    gid = grp.getgrnam("hache-telegram").gr_gid
    report = load_report(REPORT, now, source_uid=uid, source_gid=gid)
    chat_id = os.getenv("HACHE_TELEGRAM_CHAT_ID")
    user_id = os.getenv("HACHE_TELEGRAM_USER_ID")
    if (not chat_id or not user_id or not chat_id.isdecimal() or
        not user_id.isdecimal() or int(chat_id) < 1 or int(chat_id) != int(user_id)):
        raise NotifyError("invalid_private_recipient")
    state = NotificationState()
    try:
        result = send_report(TelegramAPI(load_token()), int(chat_id), report, state, now)
    finally:
        state.close()
    print("MARKET_NOTIFIER=" + result + " RENTAL_PERMITTED=false")


if __name__ == "__main__":
    try:
        main()
    except (NotifyError, ProposalError, OSError, ValueError, sqlite3.Error) as exc:
        print("MARKET_NOTIFIER_ERROR=" +
              (str(exc) if isinstance(exc, NotifyError) else "delivery_unavailable"),
              file=sys.stderr)
        sys.exit(2)
