import importlib.util
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "telegram_proposals", Path(__file__).with_name("telegram_proposals.py"))
tp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tp)
NOW = datetime.now(timezone.utc).replace(microsecond=0)
USER = CHAT = 2211


def offer(**changes):
    row = {"provider": "vast", "offer_id": 45678, "machine_id": 77,
           "host_id": 88, "gpu_name": "RTX 5090", "gpu_count": 1,
           "max_hourly_usd": 0.45, "max_total_usd": 3.0,
           "max_minutes": 300, "projected_net_usd": 0.25,
           "quote_observed_at": (NOW-timedelta(seconds=10)).isoformat()}
    row.update(changes)
    return row


def callback(data, *, update_id=1, user=USER, chat=CHAT, chat_type="private"):
    return {"update_id": update_id, "callback_query": {
        "id": "q1", "data": data, "from": {"id": user},
        "message": {"chat": {"id": chat, "type": chat_type}}}}


class FakeTelegram:
    def __init__(self):
        self.calls = []
        self.incoming = []
        self.fail_send = False

    def __call__(self, url, data):
        method = url.rsplit("/", 1)[-1]
        self.calls.append((method, data))
        if method == "sendMessage":
            if self.fail_send:
                return {"ok": False}
            return {"ok": True, "result": {"message_id": 12}}
        if method == "getUpdates":
            return {"ok": True, "result": self.incoming}
        if method == "answerCallbackQuery":
            return {"ok": True, "result": True}
        raise AssertionError("unexpected Telegram operation")


class ProposalTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.store = tp.ProposalStore(str(Path(self.work.name)/"approvals.db"))

    def tearDown(self):
        self.store.close()
        self.work.cleanup()

    def ready(self):
        p = self.store.prepare(offer(), now=NOW)
        self.assertFalse(p["rental_permitted"])
        self.assertTrue(self.store.mark_notified(p["proposal_id"], 123,
                                                 int(NOW.timestamp())))
        return p["proposal_id"]

    def test_prepare_immutable_offer_and_single_active(self):
        p = self.store.prepare(offer(), now=NOW)
        self.assertEqual(len(p["proposal_id"]), 32)
        self.assertEqual(p["digest"], tp.digest(offer()))
        with self.assertRaisesRegex(tp.ProposalError, "duplicate_active_offer"):
            self.store.prepare(offer(), now=NOW)
        self.assertEqual(self.store.status(p["proposal_id"])["state"], "pending")

    def test_owner_acknowledgement_one_use(self):
        nonce = self.ready()
        action = callback("approve:" + nonce)
        result = self.store.process_update(action, CHAT, USER, int(NOW.timestamp()))
        self.assertEqual(result["state"], "acknowledged")
        self.assertFalse(result["rental_permitted"])
        self.assertEqual(self.store.status(nonce)["state"], "acknowledged")
        self.assertEqual(self.store.process_update(action, CHAT, USER)["state"], "ignored")
        self.assertEqual(self.store.process_update(callback("reject:"+nonce,update_id=2),
                                                    CHAT, USER)["state"], "ignored")
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM audit WHERE event='acknowledged'").fetchone()[0], 1)

    def test_expiry_fails_closed(self):
        nonce = self.ready()
        result = self.store.process_update(callback("approve:"+nonce), CHAT, USER,
                                           int((NOW+timedelta(seconds=301)).timestamp()))
        self.assertEqual(result["state"], "expired")
        self.assertNotEqual(self.store.status(nonce)["state"], "acknowledged")

    def test_wrong_chat_cannot_approve(self):
        nonce = self.ready()
        result = self.store.process_update(callback("approve:"+nonce,chat=9999),
                                           CHAT, USER, int(NOW.timestamp()))
        self.assertEqual(result["state"], "ignored")
        self.assertEqual(self.store.status(nonce)["state"], "notified")

    def test_wrong_user_cannot_approve(self):
        nonce = self.ready()
        result = self.store.process_update(callback("approve:"+nonce,user=9999),
                                           CHAT, USER, int(NOW.timestamp()))
        self.assertEqual(result["state"], "ignored")

    def test_group_callback_cannot_approve(self):
        nonce = self.ready()
        self.assertEqual(self.store.process_update(
            callback("approve:"+nonce,chat_type="supergroup"), CHAT, USER,
            int(NOW.timestamp()))["state"], "ignored")

    def test_no_direct_text_command(self):
        nonce = self.ready()
        self.assertEqual(self.store.process_update(
            {"update_id":1,"message":{"text":"/rent 45678"}}, CHAT, USER)["state"], "ignored")
        self.assertEqual(self.store.status(nonce)["state"], "notified")

    def test_unknown_nonce_and_invalid_callbacks(self):
        nonce = self.ready()
        unknown = "0"*32
        self.assertEqual(self.store.process_update(callback("approve:"+unknown),
                                    CHAT, USER,int(NOW.timestamp()))["state"],"ignored")
        self.assertEqual(self.store.process_update(
            callback("approve:"+nonce+";rent",update_id=2),
            CHAT, USER,int(NOW.timestamp()))["state"],"ignored")

    def test_tampered_payload_rejected(self):
        nonce = self.ready()
        self.store.db.execute("UPDATE proposals SET payload=? WHERE nonce=?",
                              ('{"changed":1}', nonce))
        self.assertEqual(self.store.process_update(callback("approve:"+nonce),
                          CHAT, USER,int(NOW.timestamp()))["state"],"invalid")

    def test_sending_proposal_does_not_rent(self):
        self.store.prepare(offer(), now=NOW)
        transport=FakeTelegram()
        api=tp.TelegramAPI("1234567:"+"a"*35,transport=transport)
        channel=tp.TelegramChannel(self.store,api,CHAT,USER)
        self.assertEqual(channel.send_pending(int(NOW.timestamp())),1)
        self.assertEqual(channel.send_pending(int(NOW.timestamp())),0)
        methods=[m for m,_ in transport.calls]
        self.assertEqual(methods,["sendMessage"])
        self.assertIn("no habilita rentas",transport.calls[0][1]["text"])
        self.assertNotIn("token",transport.calls[0][1]["text"])
        self.assertEqual(self.store.db.execute("SELECT state FROM proposals").fetchone()[0],"notified")

    def test_send_fails_closed(self):
        self.store.prepare(offer(),now=NOW)
        transport=FakeTelegram()
        transport.fail_send=True
        channel=tp.TelegramChannel(self.store,tp.TelegramAPI("1234567:"+"a"*35,transport),CHAT,USER)
        with self.assertRaisesRegex(tp.ProposalError,"telegram_unavailable"):
            channel.send_pending(int(NOW.timestamp()))
        self.assertEqual(self.store.db.execute("SELECT state FROM proposals").fetchone()[0],"pending")

    def test_poll_telegram_authenticated_callback(self):
        nonce=self.ready()
        transport=FakeTelegram()
        transport.incoming=[callback("approve:"+nonce)]
        api=tp.TelegramAPI("1234567:"+"a"*35,transport)
        channel=tp.TelegramChannel(self.store,api,CHAT,USER)
        result=channel.poll_once(int(NOW.timestamp()))
        self.assertEqual(result[0]["state"],"acknowledged")
        self.assertEqual([x[0] for x in transport.calls],["getUpdates","answerCallbackQuery"])
        self.assertEqual(transport.calls[1][1]["text"],"Registrado sin rentar")
        self.assertFalse(self.store.status(nonce)["rental_permitted"])

    def test_stale_or_future_quote_rejected(self):
        for shift in (-1000, 10):
            with self.subTest(shift=shift):
                with self.assertRaisesRegex(tp.ProposalError,"quote_not_fresh"):
                    self.store.prepare(offer(quote_observed_at=(
                        NOW+timedelta(seconds=shift)).isoformat()), now=NOW)

    def test_missing_identity_and_bad_prices_rejected(self):
        cases=[{"gpu_count":True},{"provider":"clore"},{"max_hourly_usd":float("nan")},
               {"max_total_usd":0},{"max_minutes":0},{"gpu_name":"RTX5090;rm"},
               {"max_total_usd":0.1}]
        for changes in cases:
            with self.subTest(changes=changes):
                with self.assertRaises(tp.ProposalError):
                    self.store.prepare(offer(**changes),now=NOW)

    def test_no_implicit_rental_by_approval(self):
        nonce=self.ready()
        self.store.process_update(callback("approve:"+nonce),CHAT,USER,int(NOW.timestamp()))
        row=self.store.db.execute("SELECT state FROM proposals WHERE nonce=?",(nonce,)).fetchone()
        self.assertEqual(row,("acknowledged",))
        self.assertFalse(self.store.status(nonce)["rental_permitted"])

    def test_replay_cannot_reject_after_acknowledgement(self):
        nonce=self.ready()
        self.store.process_update(callback("approve:"+nonce,update_id=100),CHAT,USER,int(NOW.timestamp()))
        self.store.process_update(callback("reject:"+nonce,update_id=99),CHAT,USER,int(NOW.timestamp()))
        self.assertEqual(self.store.status(nonce)["state"],"acknowledged")


if __name__=="__main__":
    unittest.main()
