"""Safety and margin ranking tests for Telegram PRL-only offer comparison."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import telegram_clore_search as search
import telegram_prl_scenario as roi
import telegram_proposals as tp
from test_telegram_clore_competition import FakeTelegram, message, cb, listing

USER = CHAT = 8125
MARKET = {"prl_per_ph_day": "12.3", "otc_usd_per_prl": "1.7537",
          "market_sale_verified": False, "source": roi.TRACK_SOURCE,
          "price_reference_type": "implied_from_rounded_24h_display"}

def make_offer(offer_id, price, model="NVIDIA GeForce RTX 5090 Laptop GPU",
               variant="laptop"):
    return {"id":offer_id, "gpu":model, "gpu_count":1,
            "variant":variant,"floor_usd_hour":price}

def listing_for(offer_id, spot_hour):
    data=listing()
    data["id"]=offer_id
    data["price"]["spot"]["USD-Blockchain"]=spot_hour*24
    data["price"]["on_demand"]["USD-Blockchain"]=(spot_hour+.1)*24
    return data

class ScenarioRankingTest(unittest.TestCase):
    def test_sorted_by_stress_not_floor_arbitrary_or_positive_base(self):
        rows=[make_offer(110,.230),make_offer(111,.110),
              make_offer(112,.160)]
        ranked=roi.rank_offers(rows,MARKET)
        self.assertEqual([x["offer_id"] for x in ranked["ranked"]],
                         [111,112,110])
        self.assertEqual(ranked["evaluated"],3)
        self.assertEqual(ranked["unverified"],0)
        self.assertEqual(ranked["positive_stress"],1)
        self.assertLess(ranked["ranked"][-1]["base_margin_usd_day"],0)
        out=roi.format_ranking(ranked)
        self.assertIn("Descartar: pérdida incluso en escenario base",out)
        self.assertIn("Positivo bajo supuestos (NO verificado)",out)
        self.assertIn("NO al precio de la puja ganadora",out)

    def test_unknown_gpu_not_treated_as_zero_or_profitable(self):
        offers=[make_offer(122,.1,model="RTX 5080",variant="desktop_label"),
                make_offer(123,.16)]
        ranked=roi.rank_offers(offers,MARKET)
        self.assertEqual(ranked["evaluated"],1)
        self.assertEqual(ranked["unverified"],1)
        self.assertEqual([x["offer_id"] for x in ranked["ranked"]],[123])
        self.assertIn("sin referencia GPU: 1",roi.format_ranking(ranked))

    def test_duplicate_or_invalid_data_rejected(self):
        with self.assertRaisesRegex(roi.ProfitError,"duplicate_rank_offer"):
            roi.rank_offers([make_offer(5,.1),make_offer(5,.2)],MARKET)
        for invalid in ([make_offer(22,-1)], [None], [make_offer(3,0)],
                        [make_offer(6,float("nan"))]):
            with self.subTest(invalid=str(invalid)):
                with self.assertRaises(roi.ProfitError):
                    roi.rank_offers(invalid,MARKET)
        with self.assertRaises(roi.ProfitError):
            roi.rank_offers([make_offer(i+1,.11) for i in range(101)],MARKET)

class OwnerRankingFlow(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=tp.ProposalStore(str(Path(self.tmp.name)/"bot.sqlite"))
        self.api=FakeTelegram()
        self.bot=tp.TelegramChannel(self.store,tp.TelegramAPI(
            "1234567:"+("a"*35),transport=self.api),CHAT,USER)
        self.now=int(time.time())
        self.listings=[listing_for(120989,.229167),
                       listing_for(119661,.2375),
                       listing_for(103367,2.0)]
    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()
    def search(self):
        self.api.updates=[message("/gpu 5090 laptop",1)]
        with patch.object(search,"fetch",return_value=self.listings):
            self.bot.poll_once(self.now)
        payload=[x for m,x in self.api.calls if m=="sendMessage"][-1]
        rank=payload["reply_markup"]["inline_keyboard"][-1][0]
        self.assertEqual(rank["text"],"Comparar escenarios PRL")
        return rank["callback_data"]
    def test_owner_gets_margin_rank_without_writes(self):
        callback=self.search()
        self.api.updates=[cb(callback,2,201)]
        with patch.object(roi,"get_pool_snapshot",return_value=MARKET) as fetch:
            self.bot.poll_once(self.now)
            fetch.assert_called_once()
        payload=[x for m,x in self.api.calls if m=="sendMessage"][-1]
        self.assertIn("comparación histórica PRL",payload["text"])
        self.assertIn("#120989",payload["text"])
        self.assertIn("#119661",payload["text"])
        self.assertIn("Descartar: pérdida incluso en escenario base",payload["text"])
        self.assertIn("No autoriza pujas",payload["text"])
        self.assertFalse(self.store.db.execute(
            "SELECT COUNT(*) FROM clore_telegram_offers").fetchone()[0])
        self.assertEqual(
            set(m for m,_ in self.api.calls),
            {"getUpdates","sendMessage","answerCallbackQuery"})
    def test_wrong_chat_or_message_cannot_fetch_market(self):
        callback=self.search()
        for bad in [cb(callback,2,202), cb(callback,3,201,user=100)]:
            self.api.updates=[bad]
            with patch.object(roi,"get_pool_snapshot",
                              side_effect=AssertionError("blocked")):
                self.bot.poll_once(self.now)
    def test_upstream_unavailable_does_not_claim_profit(self):
        callback=self.search()
        self.api.updates=[cb(callback,2,201)]
        with patch.object(roi,"get_pool_snapshot",
                          side_effect=roi.ProfitError("pool_sources_unavailable")):
            self.bot.poll_once(self.now)
        payload=[x for m,x in self.api.calls if m=="sendMessage"][-1]
        self.assertIn("No se pudo comparar",payload["text"])
        self.assertNotIn("US$ +",payload["text"])
    def test_expired_results_rejected(self):
        callback=self.search()
        nonce=callback.split(":")[1]
        self.store.db.execute("UPDATE gpu_search_snapshots SET expires_at=1 WHERE nonce=?",
                              (nonce,))
        self.api.updates=[cb(callback,2,201)]
        with patch.object(roi,"get_pool_snapshot",
                          side_effect=AssertionError("should not fetch")):
            self.bot.poll_once(self.now)

if __name__ == "__main__":
    unittest.main()
