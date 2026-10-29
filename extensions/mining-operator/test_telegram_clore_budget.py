"""Offline Clore maximum bid, USDT budget and duration review: NO provider writes."""
from datetime import datetime,timezone
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import telegram_clore_budget as budget
import telegram_clore_search as search
import telegram_prl_scenario as roi
import telegram_clore_competition as quote_client
import telegram_proposals as tp
from test_telegram_clore_competition import FakeTelegram, message, cb, listing

USER=CHAT=8125
MARKET={"prl_per_ph_day":"12.3","otc_usd_per_prl":"1.7537",
        "market_sale_verified":False,"source":roi.TRACK_SOURCE,
        "price_reference_type":"implied_from_rounded_24h_display"}

def quote(server_id, floor=0.50, top=0, now=None):
    return {
        "server_id":server_id,"minimum_usd_day":floor,
        "highest_bid_usd_day":top,
        "illustrative_1pct_usd_day":max(floor,top*1.01),
        "server_mrl_hours":24,
        "rental_permitted":False,"executable_quote":False,
        "observed_at":datetime.fromtimestamp(
            now or int(time.time()),timezone.utc).isoformat()
    }

class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=tp.ProposalStore(str(Path(self.tmp.name)/"bot.sqlite"))
        self.api=FakeTelegram()
        self.channel=tp.TelegramChannel(
            self.store,tp.TelegramAPI("1234567:"+("a"*35),transport=self.api),CHAT,USER)
        self.now=int(time.time())
    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()
    def select(self):
        self.api.updates=[message("/gpu 5090 laptop",1)]
        with patch.object(search,"fetch",return_value=[listing()]):
            self.channel.poll_once(self.now)
        pick=[v for k,v in self.api.calls if k=="sendMessage"][-1][
              "reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        self.api.updates=[cb(pick,2,201)]
        self.channel.poll_once(self.now)
        return [v for k,v in self.api.calls if k=="sendMessage"][-1]
    def prepare(self,command="/puja 120989 1.00 5.00 60",id=3):
        self.api.updates=[message(command,id)]
        with patch.object(quote_client,"get_quote",side_effect=lambda sid:quote(sid,now=self.now)), \
             patch.object(roi,"get_pool_snapshot",return_value=MARKET):
            self.channel.poll_once(self.now)
        return [v for k,v in self.api.calls if k=="sendMessage"][-1]

    def test_strict_command_bounds(self):
        self.assertEqual(budget.parse_command("/puja 120989 1.00 5.00 60"),
                         {"server_id":120989,"day":"1.00","budget":"5.00","minutes":60})
        for command in ["/puja", "/puja 0 1 5 60", "/puja 120989 -1 5 60",
                        "/puja 120989 1e3 5 60",
                        "/puja 120989 1 5 1", "/puja 120989 1 5 1441",
                        "/puja 120989 1000 5 60", "/puja 120989 1 2000 60",
                        "/puja 120989 1.001 5 60", "/puja 120989 1 5;curl 60"]:
            with self.subTest(command=command):
                self.assertEqual(budget.parse_command(command),{"help":True})

    def test_selection_required_and_no_budget_implies_no_spend(self):
        self.api.updates=[message("/puja 120989 1.00 5.00 60",1)]
        with patch.object(quote_client,"get_quote",side_effect=AssertionError("no unselected quote")):
            self.channel.poll_once(self.now)
        msg=[v for k,v in self.api.calls if k=="sendMessage"][-1]["text"]
        self.assertIn("No se realizará ninguna puja",msg)
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM clore_bid_previews").fetchone()[0],0)

    def test_valid_preview_bound_to_exact_private_delivery_and_single_use(self):
        self.select()
        msg=self.prepare()
        self.assertIn("Preautorización de límites",msg["text"])
        self.assertIn("NO CONTRATA",msg["text"])
        token=msg["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        self.assertTrue(token.startswith("bid-review:"))
        self.assertIn("1.00/día",msg["text"])
        self.assertEqual(self.store.db.execute(
            "SELECT state FROM clore_bid_previews").fetchone()[0],"notified")
        self.api.updates=[cb(token,4,203)]
        self.channel.poll_once(self.now)
        self.assertEqual(self.store.db.execute(
            "SELECT state FROM clore_bid_previews").fetchone()[0],"reviewed")
        self.api.updates=[cb(token,5,203)]
        self.channel.poll_once(self.now)
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM clore_create_attempts").fetchone()[0],0) if self.store.db.execute(
                "SELECT name FROM sqlite_master WHERE name='clore_create_attempts'").fetchone() else None
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM clore_telegram_offers").fetchone()[0],0)
        self.assertEqual(set(k for k,_ in self.api.calls),
                         {"getUpdates","sendMessage","answerCallbackQuery"})

    def test_wrong_callback_user_and_message_cannot_approve(self):
        self.select()
        msg=self.prepare()
        token=msg["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        for bad in [cb(token,4,202),cb(token,5,203,user=9999)]:
            self.api.updates=[bad]
            self.channel.poll_once(self.now)
        self.assertEqual(self.store.db.execute(
            "SELECT state FROM clore_bid_previews").fetchone()[0],"notified")

    def test_rejected_preview_not_approvable(self):
        self.select()
        msg=self.prepare()
        cancel=msg["reply_markup"]["inline_keyboard"][0][1]["callback_data"]
        approve=msg["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        self.api.updates=[cb(cancel,4,203)]
        self.channel.poll_once(self.now)
        self.api.updates=[cb(approve,5,203)]
        self.channel.poll_once(self.now)
        self.assertEqual(self.store.db.execute("SELECT state FROM clore_bid_previews").fetchone()[0],"rejected")

    def test_negative_downside_no_confirmation_controls(self):
        self.select()
        payload=self.prepare("/puja 120989 6.00 8.00 60")
        self.assertIn("margen adverso",payload["text"])
        self.assertNotIn("inline_keyboard",payload.get("reply_markup",{}))
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM clore_bid_previews").fetchone()[0],0)

    def test_market_competition_floor_budget_and_duration(self):
        self.select()
        for quote_f,command,error in [
          (lambda sid:quote(sid,floor=5,now=self.now),"/puja 120989 1.00 5.00 60","competition"),
          (lambda sid:quote(sid,top=3,now=self.now),"/puja 120989 1.00 5.00 60","competition"),
          (lambda sid:quote(sid,now=self.now),"/puja 120989 1.00 0.20 60","reserve"),
          (lambda sid:dict(quote(sid,now=self.now),server_mrl_hours=0.5),
            "/puja 120989 1.00 5.00 60","mrl")
        ]:
            with self.subTest(error=error):
                request=budget.parse_command(command)
                with self.assertRaises(budget.BidPreviewError):
                    budget.evaluate(self.store.db,request,self.now,
                                    quote_reader=quote_f,pool_reader=lambda:MARKET)

    def test_old_selection_and_stale_provider_snapshot_block(self):
        self.select()
        self.store.db.execute("UPDATE gpu_search_snapshots SET expires_at=1")
        self.api.updates=[message("/puja 120989 1.00 5.00 60",3)]
        with patch.object(quote_client,"get_quote",side_effect=AssertionError("must not quote")):
            self.channel.poll_once(self.now)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM clore_bid_previews").fetchone()[0],0)

    def test_expired_or_tampered_review_denied(self):
        self.select()
        msg=self.prepare()
        token=msg["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        self.store.db.execute("UPDATE clore_bid_previews SET expires_at=?",(self.now-1,))
        self.api.updates=[cb(token,4,203)]
        self.channel.poll_once(self.now)
        self.assertEqual(self.store.db.execute(
            "SELECT state FROM clore_bid_previews").fetchone()[0],"notified")
        self.store.db.execute("UPDATE clore_bid_previews SET expires_at=?,terms_json=?",
                              (self.now+60,'{"tampered":true}'))
        self.api.updates=[cb(token,5,203)]
        self.channel.poll_once(self.now)
        self.assertEqual(self.store.db.execute("SELECT state FROM clore_bid_previews").fetchone()[0],"notified")

if __name__=="__main__":
    unittest.main()
