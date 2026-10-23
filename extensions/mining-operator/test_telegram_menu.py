"""Telegram interactive menu: private, read-only, no rental paths."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location("telegram_menu", ROOT / "telegram_menu.py")
menu = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(menu)
TPSPEC = importlib.util.spec_from_file_location("telegram_proposals", ROOT / "telegram_proposals.py")
tp = importlib.util.module_from_spec(TPSPEC)
TPSPEC.loader.exec_module(tp)
USER = CHAT = 8125
NOW = datetime.now(timezone.utc).replace(microsecond=0)


def market(now=NOW):
    return {
        "mode": "read_only", "rental_permitted": False,
        "sources_checked": ["vast.marketplace", "clore.marketplace"],
        "observed_at": now.isoformat(), "pool_recent": True,
        "per_gpu_prl_verified": False, "prl_market_price_verified": False,
        "net_profit_verified": False,
        "offers": [
            {"provider": "vast", "offer_id": 246, "gpu_name": "<b>RTX 5090</b>",
             "gpu_variant": "unverified", "gpu_variant_verified": False,
             "gpu_count": 1, "net_verified": False, "on_demand_usd_hour": 0.4},
            {"provider": "clore", "offer_id": 987, "gpu_name": "RTX 3060",
             "gpu_variant": "laptop", "gpu_variant_verified": False,
             "gpu_count": 2, "net_verified": False, "on_demand_usd_hour": 0.10,
             "spot_floor_usd_hour": 0.05}
        ]
    }


def cb(data, update_id=1, user=USER, chat=CHAT, chat_type="private"):
    return {"update_id": update_id, "callback_query": {
        "id": "menu-query", "data": data, "from": {"id": user},
        "message": {"chat": {"id": chat, "type": chat_type}}}}


def message(text, update_id=1, user=USER, chat=CHAT, chat_type="private"):
    return {"update_id": update_id, "message": {
        "text": text, "from": {"id": user}, "chat": {"id": chat, "type": chat_type}}}


class FakeTelegram:
    def __init__(self):
        self.calls = []
        self.updates = []
        self.fail_send = False

    def __call__(self, url, data):
        method = url.rsplit("/", 1)[-1]
        self.calls.append((method, data))
        if method == "sendMessage" and self.fail_send:
            return {"ok": False}
        return {"ok": True, "result": (
            self.updates if method == "getUpdates"
            else {"message_id": 111} if method == "sendMessage" else True)}


class MenuTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "market" / "report.json"
        self.path.parent.mkdir(mode=0o750)
        self.path.write_text(json.dumps(market()))
        self.path.chmod(0o640)
        self.store = tp.ProposalStore(str(Path(self.tmp.name) / "store.sqlite"))
        self.fake = FakeTelegram()
        self.channel = tp.TelegramChannel(
            self.store, tp.TelegramAPI("1234567:"+"a"*35, transport=self.fake), CHAT, USER)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def answer(self, action):
        return menu.reply(action, path=self.path, now=NOW,
                          owner_uid=os.getuid(), owner_gid=os.getgid())

    def test_all_menu_callbacks_are_static_and_readonly(self):
        actions = [button["callback_data"]
                   for row in menu.markup()["inline_keyboard"] for button in row]
        self.assertEqual(len(actions), len(set(actions)))
        self.assertEqual(set(actions), menu.CALLBACKS)
        self.assertTrue(all(len(a) < 64 and a.startswith("menu:") for a in actions))
        self.assertNotIn("rent", " ".join(actions))

    def test_offers_escape_host_input_and_do_not_invent_profit(self):
        vast = self.answer("vast")
        self.assertIn("&lt;b&gt;RTX 5090&lt;/b&gt;", vast)
        self.assertNotIn("<b>RTX 5090</b>", vast)
        self.assertIn("NO verificada", vast)
        clore = self.answer("clore")
        self.assertIn("Spot desde US$ 0.0500/h", clore)
        self.assertIn("piso indicativo", clore)
        self.assertIn("ganancia neta fiable", self.answer("profit"))
        self.assertIn("Vast.ai: 1", self.answer("status"))

    def test_stale_report_and_symlink_are_not_accepted(self):
        self.path.write_text(json.dumps(market(NOW - timedelta(hours=2))))
        self.assertIn("Datos no disponibles", self.answer("vast"))
        self.path.unlink()
        target = Path(self.tmp.name) / "another.json"
        target.write_text(json.dumps(market()))
        self.path.symlink_to(target)
        self.assertIn("Datos no disponibles", self.answer("clore"))

    def test_report_modes_cannot_claim_approval_or_rentals(self):
        cases = [{"rental_permitted": True}, {"net_profit_verified": True},
                 {"sources_checked": ["vast.marketplace"]}]
        for row in cases:
            with self.subTest(row=row):
                report = market()
                report.update(row)
                self.path.unlink(missing_ok=True)
                self.path.write_text(json.dumps(report))
                self.path.chmod(0o640)
                self.assertIn("Datos no disponibles", self.answer("status"))

    def test_authentication_and_commands(self):
        self.assertEqual(self.store.process_update(cb("menu:vast", user=999), CHAT, USER)["state"], "ignored")
        self.assertEqual(self.store.process_update(cb("menu:clore", update_id=2, chat_type="group"), CHAT, USER)["state"], "ignored")
        self.assertEqual(self.store.process_update(cb("menu:clore", update_id=3), CHAT, USER), {
            "state": "menu", "action": "clore", "rental_permitted": False})
        self.assertEqual(self.store.process_update(message("/menu", update_id=4), CHAT, USER)["action"], "home")
        self.assertEqual(self.store.process_update(message("/rent 987", update_id=5), CHAT, USER)["state"], "ignored")
        self.assertEqual(self.store.process_update(message("/estado", update_id=6, user=123), CHAT, USER)["state"], "ignored")
        self.assertEqual(self.store.process_update(message("/estado", update_id=7), CHAT, USER)["action"], "status")
        self.assertEqual(self.store.process_update(cb("menu:rent", update_id=8), CHAT, USER)["state"], "ignored")

    def test_poll_routes_owner_action_and_never_mutates_provider(self):
        self.fake.updates = [message("/menu", 1), cb("menu:guards", 2)]
        self.channel.poll_once(int(NOW.timestamp()))
        methods = [name for name, _ in self.fake.calls]
        self.assertEqual(methods, ["getUpdates", "sendMessage", "sendMessage", "answerCallbackQuery"])
        send = self.fake.calls[1][1]
        self.assertEqual(send["chat_id"], CHAT)
        self.assertEqual(send["reply_markup"], menu.markup())
        self.assertIn("Sin controles de apagado", self.fake.calls[2][1]["text"])
        self.assertEqual(self.fake.calls[0][1]["allowed_updates"], ["callback_query", "message"])
        self.assertFalse(any("rent" in name.lower() or "order" in name.lower() for name in methods))
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0], 0)

    def test_menu_reply_survives_send_error_and_cursor_commit(self):
        self.fake.updates = [message("/menu", 16)]
        self.fake.fail_send = True
        with self.assertRaisesRegex(tp.ProposalError, "telegram_unavailable"):
            self.channel.poll_once(int(NOW.timestamp()))
        self.assertEqual(self.store.pending_menu(), [(16, "home")])
        cursor = self.store.db.execute(
            "SELECT update_id FROM telegram_cursor WHERE singleton=1").fetchone()[0]
        self.assertEqual(cursor, 16)
        self.fake.fail_send = False
        self.fake.calls.clear()
        self.fake.updates = []
        self.channel.poll_once(int(NOW.timestamp()))
        self.assertEqual([name for name, _ in self.fake.calls],
                         ["sendMessage", "getUpdates"])
        self.assertEqual(self.store.pending_menu(), [])
        self.assertIn("AGENTE DE MINERÍA", self.fake.calls[0][1]["text"])

    def test_replay_does_not_duplicate_delivered_menu(self):
        self.fake.updates = [cb("menu:home", update_id=17)]
        self.channel.poll_once(int(NOW.timestamp()))
        self.assertEqual(self.store.pending_menu(), [])
        self.fake.calls.clear()
        self.fake.updates = [cb("menu:home", update_id=17)]
        self.channel.poll_once(int(NOW.timestamp()))
        self.assertEqual([name for name, _ in self.fake.calls],
                         ["getUpdates", "answerCallbackQuery"])

    def test_command_from_foreign_user_sends_nothing(self):
        self.fake.updates = [message("/menu", user=123)]
        self.channel.poll_once(int(NOW.timestamp()))
        self.assertEqual([x[0] for x in self.fake.calls], ["getUpdates"])

if __name__ == "__main__":
    unittest.main()
