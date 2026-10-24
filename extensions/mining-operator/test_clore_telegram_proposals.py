"""Exact-offer Clore Telegram decisions are NOT spend authorization."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

import telegram_proposals as tp

NOW = datetime.fromtimestamp(1800000000, timezone.utc)
CHAT = USER = 76543
IMAGE = "ghcr.io/manglefurniture/prl-miner@sha256:"+"a"*64


def terms(**replace):
    values = {
        "server_id": 456, "currency": "USD-Blockchain",
        "gpu_descriptor": "1x NVIDIA GeForce RTX 5090",
        "gpu_variant": "desktop", "gpu_variant_verified": True,
        "image": IMAGE, "daily_bid_usd": "12", "max_total_usd": "1",
        "creation_fee_usd": "0.10", "max_minutes": 60,
        "quote_observed_at": (NOW-timedelta(seconds=10)).isoformat(),
    }
    values.update(replace)
    return values


def callback(nonce, *, action="accept", user=USER, chat=CHAT, kind="private",
             message_id=12, update_id=1):
    return {"update_id": update_id, "callback_query": {
        "id": "clore-query-1", "data": f"clore-{action}:{nonce}",
        "from": {"id": user}, "message": {
            "message_id": message_id,
            "chat": {"id":chat, "type":kind}
        }
    }}


class Stub:
    def __init__(self):
        self.incoming=[]
        self.fail=False
        self.calls=[]
    def __call__(self,url,data):
        method=url.rsplit("/",1)[-1]
        self.calls.append((method,data))
        if method=="getUpdates":
            return {"ok":True,"result":self.incoming}
        if method=="sendMessage" and self.fail:
            return {"ok":False}
        return {"ok":True,"result":{"message_id":12} if method=="sendMessage" else True}


class CloreTelegramTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.store=tp.ProposalStore(str(Path(self.directory.name)/"telegram.sqlite"))
        self.api_transport=Stub()
        self.channel=tp.TelegramChannel(self.store,tp.TelegramAPI(
            "1234567:"+"a"*35,transport=self.api_transport),CHAT,USER)
        self.tick=int(NOW.timestamp())
    def tearDown(self):
        self.store.close()
        self.directory.cleanup()
    def ready(self):
        proposal=self.store.prepare_clore(terms(),now=NOW)
        self.assertTrue(self.store.mark_clore_notified(proposal["proposal_id"],12,self.tick))
        return proposal

    def test_exact_terms_and_hash_are_immutable(self):
        proposal=self.store.prepare_clore(terms(),now=NOW)
        self.assertEqual(proposal["decision_only"],True)
        self.assertEqual(proposal["rental_permitted"],False)
        self.assertEqual(proposal["digest"], tp.digest(terms()))
        self.assertEqual(self.store.clore_status(proposal["proposal_id"])["state"],"pending")
        with self.assertRaisesRegex(tp.ProposalError,"existing_clore_offer"):
            self.store.prepare_clore(terms(server_id=457),now=NOW)
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM clore_cancel_leases").fetchone()[0] if
            self.store.db.execute("SELECT 1 FROM sqlite_master WHERE name='clore_cancel_leases'").fetchone()
            else 0,0)

    def test_callback_owner_and_message_binding(self):
        nonce=self.ready()["proposal_id"]
        cases=[
            {"user":999,"update_id":1},
            {"chat":999,"update_id":2},
            {"kind":"group","update_id":3},
            {"message_id":13,"update_id":4},
            {"message_id":None,"update_id":5},
        ]
        for entry in cases:
            with self.subTest(entry=entry):
                result=self.store.process_update(callback(nonce,**entry),CHAT,USER,self.tick)
                self.assertEqual(result["state"],"ignored")
        self.assertEqual(self.store.clore_status(nonce)["state"],"notified")
        success=self.store.process_update(callback(nonce,update_id=6),CHAT,USER,self.tick)
        self.assertEqual(success["state"],"clore_acknowledged")
        self.assertFalse(success["rental_permitted"])
        self.assertEqual(success["digest"],tp.digest(terms()))
        self.assertEqual(self.store.clore_status(nonce)["state"],"acknowledged")
        self.assertEqual(self.store.process_update(
            callback(nonce,action="reject",update_id=7),CHAT,USER,self.tick)["state"],
            "already_clore_acknowledged")
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM audit WHERE event='clore_acknowledged'").fetchone()[0],1)

    def test_rejection_expiry_and_tampering(self):
        nonce=self.ready()["proposal_id"]
        reject=self.store.process_update(callback(nonce,action="reject"),CHAT,USER,self.tick)
        self.assertEqual(reject["state"],"clore_rejected")
        self.assertEqual(self.store.clore_status(nonce)["state"],"rejected")
        self.store.db.execute("UPDATE clore_telegram_offers SET state='notified'")
        expired=self.store.process_update(callback(nonce,update_id=2),CHAT,USER,self.tick+200)
        self.assertEqual(expired["state"],"clore_expired")
        self.store.db.execute("UPDATE clore_telegram_offers SET state='notified',payload='{}'")
        invalid=self.store.process_update(callback(nonce,update_id=3),CHAT,USER,self.tick)
        self.assertEqual(invalid["state"],"clore_invalid")

    def test_replay_duplicate_nonce_cross_provider_is_inert(self):
        nonce=self.ready()["proposal_id"]
        self.store.process_update(callback(nonce,update_id=20),CHAT,USER,self.tick)
        self.assertEqual(self.store.process_update(
            callback(nonce,update_id=20),CHAT,USER,self.tick)["state"],"ignored")
        self.assertEqual(self.store.process_update({
            **callback(nonce,update_id=21),
            "callback_query": {**callback(nonce)["callback_query"],
                "data":"approve:"+nonce}},CHAT,USER,self.tick)["state"],"ignored")
        self.assertEqual(self.store.clore_status(nonce)["state"],"acknowledged")

    def test_quote_image_gpu_and_budget_rejected(self):
        examples=[
            terms(currency="usdt"),terms(currency="bitcoin"),
            terms(gpu_variant_verified=False),
            terms(gpu_variant="unverified"),
            terms(image="ghcr.io/manglefurniture/prl-miner:latest"),
            terms(max_total_usd="0.1"),
            terms(quote_observed_at=(NOW-timedelta(seconds=90)).isoformat()),
            terms(server_id=True),
        ]
        for candidate in examples:
            with self.subTest(candidate=candidate),self.assertRaises(tp.ProposalError):
                self.store.prepare_clore(candidate,now=NOW)

    def test_send_reply_receipt_and_no_commercial_api(self):
        receipt=self.store.prepare_clore(terms(),now=NOW)
        self.assertEqual(self.channel.send_clore_pending(self.tick),1)
        self.assertEqual(self.channel.send_clore_pending(self.tick),0)
        posted=self.api_transport.calls[0][1]
        self.assertIn(receipt["digest"],posted["text"])
        self.assertIn(IMAGE,posted["text"])
        self.assertIn("SIN alquilar",posted["reply_markup"]["inline_keyboard"][0][0]["text"])
        self.assertEqual(self.api_transport.calls[0][0],"sendMessage")
        self.api_transport.incoming=[callback(receipt["proposal_id"],update_id=1)]
        self.channel.poll_once(self.tick)
        self.assertEqual(self.store.clore_status(receipt["proposal_id"])["state"],"acknowledged")
        self.assertEqual([x[0] for x in self.api_transport.calls],
            ["sendMessage","getUpdates","answerCallbackQuery"])
        self.assertIn("SIN alquilar",self.api_transport.calls[-1][1]["text"])

    def test_failed_send_retries_without_notifying_or_spending(self):
        p=self.store.prepare_clore(terms(),now=NOW)
        self.api_transport.fail=True
        with self.assertRaisesRegex(tp.ProposalError,"telegram_unavailable"):
            self.channel.send_clore_pending(self.tick)
        self.assertEqual(self.store.clore_status(p["proposal_id"])["state"],"pending")
        self.api_transport.fail=False
        self.assertEqual(self.channel.send_clore_pending(self.tick),1)
        self.assertEqual(self.store.clore_status(p["proposal_id"])["state"],"notified")

    def test_tampered_message_id_and_future_quote_cannot_accept(self):
        p=self.ready()
        nonce=p["proposal_id"]
        self.store.db.execute(
            "UPDATE clore_telegram_offers SET message_id=? WHERE nonce=?",
            (33,nonce))
        self.assertEqual(self.store.process_update(
            callback(nonce),CHAT,USER,self.tick)["state"],"ignored")
        with self.assertRaises(tp.ProposalError):
            self.store.prepare_clore(terms(quote_observed_at=(
                NOW+timedelta(seconds=10)).isoformat()),now=NOW)

    def test_expired_proposal_slot_can_be_reused_without_reviving_previous(self):
        old = self.store.prepare_clore(terms(),now=NOW)
        fresh_now = NOW + timedelta(seconds=130)
        fresh = terms(quote_observed_at=(fresh_now-timedelta(seconds=5)).isoformat())
        new = self.store.prepare_clore(fresh,now=fresh_now)
        self.assertNotEqual(old["proposal_id"],new["proposal_id"])
        self.assertEqual(self.store.clore_status(old["proposal_id"])["state"],"expired")
        self.assertEqual(self.store.clore_status(new["proposal_id"])["state"],"pending")
        self.assertEqual(self.store.process_update(
            callback(old["proposal_id"]),CHAT,USER,int(fresh_now.timestamp()))["state"],"ignored")

    def test_no_text_rent_command(self):
        self.ready()
        update={"update_id":1,"message":{"text":"/rent 456",
          "chat":{"id":CHAT,"type":"private"},"from":{"id":USER}}}
        self.assertEqual(self.store.process_update(update,CHAT,USER,self.tick)["state"],"ignored")
        self.assertEqual(self.api_transport.calls,[])

if __name__=="__main__":
    unittest.main()
