#!/usr/bin/env python3
"""Root-only, one-time private Telegram chat discovery. Does not rent or issue grants.

Reads an existing root-owned Telegram bot token, requests only recent /pair CODE updates over
Telegram HTTPS, and installs a root-only recipient EnvironmentFile. Never prints
the token or Telegram message bodies.
"""
import argparse
import os
from pathlib import Path
import re
import stat
import sys
import time

from telegram_proposals import ProposalError, TelegramAPI

TOKEN_FILE = Path("/etc/hache-mining-agent/telegram_token")
RECIPIENT_FILE = Path("/etc/hache-mining-agent/telegram-recipient.env")


def read_token(path=TOKEN_FILE, owner_uid=0):
    path = Path(path)
    folder = path.parent.lstat()
    if (not stat.S_ISDIR(folder.st_mode) or folder.st_uid != owner_uid or
            folder.st_mode & 0o077):
        raise ProposalError("untrusted_credentials_directory")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != owner_uid or
                info.st_mode & 0o077 or info.st_nlink != 1 or info.st_size > 256):
            raise ProposalError("untrusted_bot_token")
        with os.fdopen(fd, "r", encoding="ascii") as file:
            fd = -1
            token = file.read(257).strip()
        if not re.fullmatch(r"[0-9]{5,15}:[A-Za-z0-9_-]{30,90}", token):
            raise ProposalError("invalid_bot_token")
        return token
    finally:
        if fd >= 0:
            os.close(fd)


def discover_private_pair(api, code, now=None):
    if type(code) is not str or not re.fullmatch(r'[a-f0-9]{16}', code):
        raise ProposalError('invalid_pairing_code')
    now = int(time.time() if now is None else now)
    updates = api.call("getUpdates", {
        "offset": 0, "limit": 100, "timeout": 0, "allowed_updates": ["message"]
    })
    if type(updates) is not list or len(updates) > 100:
        raise ProposalError("invalid_telegram_updates")
    candidates = set()
    for update in updates:
        if type(update) is not dict:
            continue
        message = update.get("message")
        if type(message) is not dict:
            continue
        chat, user, text = message.get("chat"), message.get("from"), message.get("text")
        stamp = message.get("date")
        if (type(chat) is not dict or type(user) is not dict or
                chat.get("type") != "private" or user.get("is_bot") is True or
                type(chat.get("id")) is not int or type(user.get("id")) is not int or
                chat["id"] <= 0 or user["id"] <= 0 or type(text) is not str or
                type(stamp) is not int or not 0 <= now - stamp <= 300):
            continue
        if text.strip() == "/pair " + code:
            candidates.add((chat["id"], user["id"]))
    if not candidates:
        raise ProposalError("pair_code_not_received_in_private_chat")
    if len(candidates) > 1:
        raise ProposalError("ambiguous_private_pairings")
    return next(iter(candidates))


def write_recipient(chat_id, user_id, path=RECIPIENT_FILE, owner_uid=0):
    folder = Path(path).parent.lstat()
    if (not stat.S_ISDIR(folder.st_mode) or folder.st_uid != owner_uid or
            folder.st_mode & 0o077):
        raise ProposalError("untrusted_recipient_directory")
    if type(chat_id) is not int or type(user_id) is not int or chat_id <= 0 or user_id <= 0:
        raise ProposalError("invalid_recipient")
    payload = f"HACHE_TELEGRAM_CHAT_ID={chat_id}\nHACHE_TELEGRAM_USER_ID={user_id}\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise ProposalError("recipient_already_configured_refusing_overwrite") from exc
    try:
        with os.fdopen(fd, "w", encoding="ascii") as file:
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
    except Exception:
        Path(path).unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair-code", required=True,
                        help="Fresh, random, 16-char hex code entered by owner in bot chat")
    parser.add_argument("--write-config", action="store_true",
                        help="Create recipient EnvironmentFile exactly once")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ProposalError("root_required_for_token_access")
    api = TelegramAPI(read_token())
    chat_id, user_id = discover_private_pair(api, args.pair_code)
    if args.write_config:
        write_recipient(chat_id, user_id)
    print(f"PRIVATE_CHAT_FOUND CHAT_ID={chat_id} USER_ID={user_id} "
          f"RECIPIENT_FILE={'CREATED' if args.write_config else 'NOT_MODIFIED'} "
          "RENTAL_PERMITTED=false")


if __name__ == "__main__":
    try:
        main()
    except (ProposalError, OSError, UnicodeError) as exc:
        code = str(exc) if isinstance(exc, ProposalError) else "onboarding_unavailable"
        print(f"TELEGRAM_ONBOARDING_ERROR={code} RENTAL_PERMITTED=false")
        sys.exit(2)
