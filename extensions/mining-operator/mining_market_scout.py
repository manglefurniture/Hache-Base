#!/usr/bin/env python3
"""Hourly Hache Market Scout. Read-only broker queries, sanitized local report.

Runs strictly as gpt-agent without a Telegram token. No wallet, rental,
bid, approval, shell command, or mining operation is accepted as input.
"""
import datetime as dt
import grp
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile

SOCKET = "/run/hache-mining-operator/agent.sock"
OUTPUT = Path("/var/lib/hache-mining-market/report.json")
MAX_REPLY = 131072
MAX_REPORT = 65536
SOURCE_ACTIONS = ("vast.marketplace", "clore.marketplace")
UTC = dt.timezone.utc


class ScanError(ValueError):
    pass


def utc(value):
    if type(value) is not str or len(value) > 35:
        raise ScanError("invalid_timestamp")
    try:
        stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ScanError("invalid_timestamp") from exc
    if stamp.tzinfo is None:
        raise ScanError("timezone_missing")
    return stamp.astimezone(UTC)


def query_broker(action, *, sock=SOCKET):
    if action not in SOURCE_ACTIONS:
        raise ScanError("not_a_readonly_marketplace")
    payload = json.dumps({"method": "query", "operation": {"action": action}},
                         separators=(",", ":")).encode() + b"\n"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(45)
            connection.connect(sock)
            connection.sendall(payload)
            with connection.makefile("rb") as stream:
                raw = stream.readline(MAX_REPLY + 1)
        if not raw or len(raw) > MAX_REPLY:
            raise ScanError("broker_bad_response")
        data = json.loads(raw)
    except (OSError, ValueError, UnicodeError) as exc:
        raise ScanError("broker_unavailable") from exc
    if type(data) is not dict or data.get("ok") is not True or type(data.get("result")) is not dict:
        raise ScanError("provider_unavailable")
    return data["result"]


def value(v):
    return type(v) in (int, float) and math.isfinite(v) and 0 < v <= 100


def text_label(v, limit=95):
    if type(v) is not str:
        return "Modelo no identificado"
    value = re.sub(r"[\x00-\x1f\x7f-\x9f<>]", "", v).strip()
    return value[:limit] if value else "Modelo no identificado"


def select_offers(vast, clore, now):
    """Reviewable whole-rig quotes, NEVER calculated PRL yield or net profit."""
    if type(vast) is not dict or type(clore) is not dict:
        raise ScanError("missing_provider")
    for data in (vast, clore):
        age = (now - utc(data.get("snapshot_utc"))).total_seconds()
        if not 0 <= age <= 300:
            raise ScanError("stale_provider_quotes")
        if data.get("rental_authorized") is not False:
            raise ScanError("unsafe_provider_response")
    source_rows = (
        ("vast", vast.get("offers"), "hourly_usd"),
        ("clore", clore.get("prl_gpu_models"), "on_demand_usd_hour"),
    )
    selected = []
    for provider, rows, field in source_rows:
        if type(rows) is not list or len(rows) > 80:
            raise ScanError("invalid_marketplace_rows")
        valid = []
        for row in rows:
            if type(row) is not dict:
                continue
            ident = row.get("id")
            count = row.get("num_gpus") if provider == "vast" else row.get("gpu_count_verified")
            cost = row.get(field)
            if type(ident) is not int or not 1 <= ident <= 10**15:
                continue
            if type(count) is not int or not 1 <= count <= 16 or not value(cost):
                continue
            name = row.get("gpu_name") if provider == "vast" else row.get("gpu")
            if not isinstance(name, str) or not name.strip():
                continue
            hint = row.get("gpu_variant")
            if hint not in ("desktop", "laptop", "unverified"):
                hint = "unverified"
            model_key = row.get("gpu_model_key")
            if type(model_key) is not str or not 1 <= len(model_key) <= 85:
                # Still display the candidate; without a normalized family
                # identity it cannot support a same-model price-drop alert.
                model_key = ""
            item = {
                "provider": provider, "offer_id": ident, "gpu_name": text_label(name),
                "gpu_model_key": text_label(model_key, 85).upper() if model_key else "",
                "gpu_count": count, "gpu_variant": hint,
                "gpu_variant_verified": False,
                "on_demand_usd_hour": round(float(cost), 6),
                "net_verified": False,
            }
            if provider == "vast":
                rel = row.get("reliability2")
                if not (type(rel) in (int, float) and math.isfinite(rel) and 0.90 <= rel <= 1):
                    continue
                item["reliability"] = round(rel, 3)
            else:
                floor = row.get("spot_floor_usd_hour")
                if value(floor):
                    item["spot_floor_usd_hour"] = round(float(floor), 6)
            valid.append(item)
        # At most four distinct GPU family / variant combinations per provider;
        # provider outputs are already cheapest-per-model, not cheapest-per-hash.
        valid.sort(key=lambda o: (o["on_demand_usd_hour"], o["offer_id"]))
        seen = set()
        for offer in valid:
            key = (offer["gpu_name"], offer["gpu_variant"], offer["gpu_count"])
            if key in seen:
                continue
            seen.add(key)
            selected.append(offer)
            if sum(o["provider"] == provider for o in selected) >= 4:
                break
    return selected


def pool_observation(now):
    """Pool timestamp ONLY. Wallet totals do not identify production per GPU."""
    command = ["mariadb", "--batch", "--skip-column-names",
               "--execute", "SELECT DATE_FORMAT(MAX(observed_at),"
               "'%Y-%m-%dT%H:%i:%sZ') FROM hache_miner.pool_observations"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=6,
                                check=True)
        timestamp = result.stdout.strip()
        observed = utc(timestamp)
        fresh = 0 <= (now - observed).total_seconds() <= 900
        return timestamp if fresh else None, fresh
    except (OSError, ValueError, subprocess.SubprocessError):
        return None, False


def make_report(vast, clore, now, pool=(None, False)):
    offers = select_offers(vast, clore, now)
    report = {
        "mode": "read_only", "sources_checked": list(SOURCE_ACTIONS),
        "observed_at": now.isoformat(), "pool_observed_at": pool[0],
        "pool_recent": pool[1], "per_gpu_prl_verified": False,
        "prl_market_price_verified": False, "net_profit_verified": False,
        "rental_permitted": False,
        "vast_sample_partial": bool(vast.get("model_variants_partial", False)),
        "clore_model_partial": bool(clore.get("prl_gpu_models_partial", False)),
        "offers": offers,
        "warning": ("Preliminary advertised whole-server On-Demand prices, "
                    "Spot floors are not winning bids. No verified PRL per GPU, "
                    "no current PRL sale price or all-in fees. No rent or spend.")
    }
    encoded = json.dumps(report, separators=(",", ":"), allow_nan=False).encode()
    if len(encoded) > MAX_REPORT:
        raise ScanError("report_too_large")
    return report


def save_report(report, path=OUTPUT, *, uid=None, gid=None):
    path = Path(path)
    info = path.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o007:
        raise ScanError("untrusted_report_directory")
    if uid is not None and info.st_uid != uid:
        raise ScanError("wrong_report_owner")
    if gid is not None and info.st_gid != gid:
        raise ScanError("wrong_report_group")
    payload = json.dumps(report, separators=(",", ":"), allow_nan=False).encode()
    if len(payload) > MAX_REPORT:
        raise ScanError("report_too_large")
    fd, filename = tempfile.mkstemp(prefix=".scan-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(filename, 0o640)
        os.replace(filename, path)
    finally:
        if os.path.exists(filename):
            os.unlink(filename)


def main():
    if os.geteuid() == 0:
        raise ScanError("do_not_run_as_root")
    vast = query_broker("vast.marketplace")
    clore = query_broker("clore.marketplace")
    now = dt.datetime.now(UTC)  # stamp after both network calls, not before
    report = make_report(vast, clore, now, pool_observation(now))
    group = grp.getgrnam("hache-telegram").gr_gid
    save_report(report, uid=os.geteuid(), gid=group)
    print("DUAL_PROVIDER_SCAN_OK=true VAST_OFFERS=" +
          str(sum(o["provider"] == "vast" for o in report["offers"])) +
          " CLORE_OFFERS=" +
          str(sum(o["provider"] == "clore" for o in report["offers"])) +
          " POOL_RECENT=" + str(report["pool_recent"]).lower() +
          " RENTAL_PERMITTED=false")


if __name__ == "__main__":
    try:
        main()
    except (ScanError, OSError, ValueError) as exc:
        # No provider response, wallet, bot token or raw traceback in journald.
        print("SCOUT_ERROR=" + (str(exc) if isinstance(exc, ScanError) else
                                "source_or_storage_unavailable"), file=sys.stderr)
        sys.exit(2)
