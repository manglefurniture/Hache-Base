#!/usr/bin/env python3
"""Private read-only Telegram menu over sanitized hourly market reports.

No broker connection, shell, SQL, provider writes, grants or rental actions.
"""
from datetime import datetime, timedelta, timezone
import grp
import html
import json
import os
from pathlib import Path
import pwd
import stat
from zoneinfo import ZoneInfo

REPORT = Path("/var/lib/hache-mining-market/report.json")
UTC = timezone.utc
CANCUN = ZoneInfo("America/Cancun")
ACTIONS = frozenset(("home", "vast", "clore", "status", "profit", "guards", "help"))
CALLBACKS = frozenset("menu:" + name for name in ACTIONS)


class MenuError(ValueError):
    pass


def markup():
    return {"inline_keyboard": [
        [{"text": "Ofertas Vast.ai", "callback_data": "menu:vast"},
         {"text": "Ofertas Clore.ai", "callback_data": "menu:clore"}],
        [{"text": "Estado del radar", "callback_data": "menu:status"},
         {"text": "Rentabilidad", "callback_data": "menu:profit"}],
        [{"text": "Watchdogs", "callback_data": "menu:guards"},
         {"text": "Ayuda", "callback_data": "menu:help"}],
        [{"text": "Menú principal", "callback_data": "menu:home"}],
    ]}


def load_report(path=REPORT, now=None, *, owner_uid=None, owner_gid=None):
    """Only consume the scout's non-secret, group-readable, read-only report."""
    now = now or datetime.now(UTC)
    path = Path(path)
    parent = path.parent.lstat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_mode & 0o027:
        raise MenuError("untrusted_report_directory")
    if owner_uid is not None and parent.st_uid != owner_uid:
        raise MenuError("unexpected_directory_owner")
    if owner_gid is not None and parent.st_gid != owner_gid:
        raise MenuError("unexpected_directory_group")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as handle:
        meta = os.fstat(handle.fileno())
        if (not stat.S_ISREG(meta.st_mode) or meta.st_mode & 0o027 or
                meta.st_nlink != 1 or not 100 <= meta.st_size <= 65536):
            raise MenuError("untrusted_report_file")
        if owner_uid is not None and meta.st_uid != owner_uid:
            raise MenuError("unexpected_file_owner")
        if owner_gid is not None and meta.st_gid != owner_gid:
            raise MenuError("unexpected_file_group")
        raw = handle.read(65537)
    if len(raw) > 65536:
        raise MenuError("report_too_large")
    try:
        report = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise MenuError("invalid_json") from exc
    if (type(report) is not dict or report.get("mode") != "read_only" or
            report.get("sources_checked") != ["vast.marketplace", "clore.marketplace"] or
            report.get("rental_permitted") is not False or
            report.get("net_profit_verified") is not False or
            report.get("per_gpu_prl_verified") is not False or
            report.get("prl_market_price_verified") is not False):
        raise MenuError("unsafe_report")
    try:
        instant = datetime.fromisoformat(report["observed_at"].replace("Z", "+00:00"))
        if instant.tzinfo is None:
            raise ValueError("missing_timezone")
        age = now - instant.astimezone(UTC)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise MenuError("invalid_report_date") from exc
    if not timedelta(0) <= age <= timedelta(minutes=90):
        raise MenuError("stale_report")
    offers = report.get("offers")
    if type(offers) is not list or len(offers) > 8:
        raise MenuError("invalid_offers")
    for offer in offers:
        if (type(offer) is not dict or offer.get("provider") not in ("vast", "clore") or
                offer.get("net_verified") is not False or
                offer.get("gpu_variant_verified") is not False or
                type(offer.get("offer_id")) is not int or
                type(offer.get("gpu_count")) is not int or
                type(offer.get("gpu_name")) is not str or
                not 1 <= len(offer["gpu_name"]) <= 95 or
                type(offer.get("on_demand_usd_hour")) not in (float, int) or
                not 0 < offer["on_demand_usd_hour"] <= 100 or
                offer.get("gpu_variant") not in ("desktop", "laptop", "unverified")):
            raise MenuError("invalid_offer")
    return report


def reply(action, *, path=REPORT, now=None, owner_uid=None, owner_gid=None):
    if action not in ACTIONS:
        raise MenuError("unknown_action")
    if action == "home":
        return ("<b>HACHE · AGENTE DE MINERÍA</b>\n"
                "Elige qué necesitas consultar. El radar analiza Vast.ai y Clore.ai "
                "cada hora. Los botones son de <b>solo lectura</b>; "
                "no rentan, pujan ni detienen máquinas.")
    if action == "help":
        return ("<b>Comandos del bot</b>\n"
                "/start o /menu — abrir menú\n"
                "/ofertas — ver las últimas ofertas Vast.ai\n"
                "/estado — último escaneo\n"
                "/ayuda — mostrar ayuda\n\n"
                "Las consultas muestran el último reporte disponible. "
                "No son búsquedas nuevas en tiempo real. "
                "<b>Rentas, cancelaciones y reinicios no están habilitados desde Telegram.</b>")
    if action == "guards":
        return ("<b>Supervisión de máquinas</b>\n"
                "Este canal todavía no recibe un estado verificado en vivo de "
                "los watchdogs de Vast.ai y Clore.ai. "
                "No interpretes este menú como confirmación de que una renta esté protegida.\n"
                "<b>Sin controles de apagado ni gastos desde el bot.</b>")
    now = now or datetime.now(UTC)
    if owner_uid is None:
        owner_uid = pwd.getpwnam("gpt-agent").pw_uid
    if owner_gid is None:
        owner_gid = grp.getgrnam("hache-telegram").gr_gid
    try:
        report = load_report(path, now, owner_uid=owner_uid, owner_gid=owner_gid)
    except (MenuError, OSError, KeyError, ValueError):
        return ("<b>Datos no disponibles</b>\n"
                "No hay un reporte íntegro y reciente de Vast.ai + Clore.ai. "
                "No se muestran ofertas antiguas como actuales. "
                "No se ha solicitado ninguna renta ni puja.")
    when = datetime.fromisoformat(report["observed_at"].replace("Z", "+00:00")).astimezone(CANCUN)
    heading = f"<i>Última lectura: {when:%d/%m/%Y %H:%M} Cancún · escaneo horario</i>"
    if action == "status":
        vast = sum(x["provider"] == "vast" for x in report["offers"])
        clore = sum(x["provider"] == "clore" for x in report["offers"])
        return (f"<b>Estado del radar</b>\n{heading}\n"
                f"Vast.ai: {vast} ofertas mostradas\nClore.ai: {clore} ofertas mostradas\n"
                f"Kryptex: {'lectura agregada reciente' if report.get('pool_recent') is True else 'sin lectura reciente'}\n"
                "<b>Rentabilidad neta NO verificada.</b>\n"
                "Sin orden de renta, puja ni apagado.")
    if action == "profit":
        return (f"<b>Rentabilidad PRL</b>\n{heading}\n"
                "Todavía no hay producción PRL por GPU, precio de venta y "
                "cargos completos verificados para estas ofertas. "
                "<b>No es posible calcular una ganancia neta fiable.</b>\n"
                "Un precio Spot mínimo no es una puja ganadora.")
    provider = action
    items = [x for x in report["offers"] if x["provider"] == provider]
    lines = [f"<b>{'Vast.ai' if provider == 'vast' else 'Clore.ai'} · ofertas anunciadas</b>", heading]
    if not items:
        lines.append("No hay ofertas válidas en el último reporte.")
    for item in items:
        label = html.escape(item["gpu_name"][:60], quote=True)
        variant = {"desktop": "escritorio*", "laptop": "Laptop*",
                   "unverified": "tipo sin verificar"}[item["gpu_variant"]]
        lines.append(
            f"\n<b>{item['gpu_count']}× {label}</b> ({variant}) · #{item['offer_id']}\n"
            f"On-Demand: US$ {item['on_demand_usd_hour']:.4f}/h")
        floor = item.get("spot_floor_usd_hour")
        if provider == "clore" and type(floor) in (int, float) and 0 < floor <= 100:
            lines.append(f"Spot desde US$ {floor:.4f}/h (piso indicativo)")
    lines.append("\n*Variante declarada por el proveedor, hardware no verificado.")
    lines.append("<b>Rentabilidad NO verificada. No se ha contratado nada.</b>")
    return "\n".join(lines)
