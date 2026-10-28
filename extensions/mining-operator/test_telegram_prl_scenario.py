"""Read-only PRL scenario tests; no provider mutation or real rental."""
from decimal import Decimal
from html import escape
import json
import unittest

import telegram_prl_scenario as roi

def fixture():
    return ("<html><body>OTC $ 1.8936 Pools Net yield explains units "
            "<b>Kryptex</b> Fee 1% Workers 112000 "
            "Net yield 14.37 PRL per PH/s · day "
            "PearlHash Fee 1% Net yield 11.83 PRL per PH/s · day"
            + " filler " * 600 + "</body></html>")

def offer(model="NVIDIA GeForce RTX 5090 Laptop GPU",count=1,
          variant="laptop",price=.229167):
    return {"id":120989,"gpu":model,"gpu_count":count,"variant":variant,
            "floor_usd_hour":price}

class ROI(unittest.TestCase):
    def setUp(self):self.pool=roi.parse_pool_html(fixture())

    def test_kryptex_card_and_otc_only(self):
        self.assertEqual(self.pool["prl_per_ph_day"],"14.37")
        self.assertEqual(self.pool["otc_usd_per_prl"],"1.8936")
        self.assertFalse(self.pool["market_sale_verified"])
        malicious=fixture().replace("Net yield 14.37", "Net yield 144.37")
        with self.assertRaises(roi.ProfitError):roi.parse_pool_html(malicious)
        bad=fixture().replace("OTC $ 1.8936","OTC $ 0")
        with self.assertRaises(roi.ProfitError):roi.parse_pool_html(bad)

    def test_otc_price_full_precision_or_reject_no_truncation(self):
        full=fixture().replace("OTC $ 1.8936","OTC $ 1.893678")
        self.assertEqual(roi.parse_pool_html(full)["otc_usd_per_prl"],"1.893678")
        for raw in ("1.893678901", "1.8936.5", "1.8936extra"):
            modified=fixture().replace("OTC $ 1.8936", "OTC $ "+raw)
            with self.subTest(raw=raw), self.assertRaises(roi.ProfitError):
                roi.parse_pool_html(modified)
        wrong=fixture().replace("Net yield 14.37", "Net yield 14.371234567")
        with self.assertRaises(roi.ProfitError):
            roi.parse_pool_html(wrong)

    def test_pearltrack_24h_visible_kryptex_card_and_implied_price(self):
        track=(
            "<html><body>Network hashrate 75 EH/s Largest pool 50.0% Kryptex "
            "Nakamoto coeff 2 "
            "Kryptex ↗ uv0gqv Fee 1% · 7m ago Consistent Proven 37 EH/s "
            "24H blocks 216 Profit / PH·day 12.5 PEARL $23.12 · net of 1% "
            "Wallet balance 123,456 PEARL "
            "PearlHash ↗ 50ltku Fee 1% Profit / PH·day 12.2 PEARL $22.65 · net of 1% "
            + " filler " * 700 + "</body></html>"
        )
        p=roi.parse_track_html(track)
        self.assertEqual(p["prl_per_ph_day"],"12.5")
        self.assertEqual(p["otc_usd_per_prl"],"1.849600")
        self.assertEqual(p["source"],roi.TRACK_SOURCE)
        self.assertFalse(p["market_sale_verified"])
        self.assertEqual(p["price_reference_type"],"implied_from_rounded_24h_display")
        r=roi.compute(offer(),p)
        self.assertIn("implícita, aproximada",roi.format_scenario(r))

    def test_pearltrack_rejects_wrong_source_card_and_bad_precision(self):
        t=(
            "<html><body>Kryptex Nakamoto coeff 2 "
            "Kryptex ↗ uv0gqv Fee 1% Profit / PH·day 12.5 PEARL $23.12 · net of 1% "
            "PearlHash ↗ abc Fee 1% "
            + " filler " * 700 + "</body></html>"
        )
        for altered in (
            t.replace("12.5 PEARL","12.51234567 PEARL"),
            t.replace("$23.12","$23.123456789"),
            t.replace("Kryptex ↗","Kryptex (not a card)"),
            t.replace("PearlHash ↗",""),
        ):
            with self.subTest(altered=altered[:160]):
                with self.assertRaises(roi.ProfitError):
                    roi.parse_track_html(altered)

    def test_two_source_fallback_prefers_track_and_recovers_to_sonar(self):
        track=(
            "<html><body>Kryptex ↗ uv Fee 1% Profit / PH·day 12.5 PEARL "
            "$23.12 · net of 1% Wallet 123 PearlHash ↗ abc "
            + " filler " * 700 + "</body></html>"
        )
        class Response:
            status=200
            def __init__(self,raw):self.raw=raw
            def __enter__(self):return self
            def __exit__(self,*a):return None
            def read(self,n):return self.raw.encode()
        seen=[]
        def primary(req,timeout):
            seen.append((req.full_url,req.get_method(),timeout))
            return Response(track)
        p=roi.get_pool_snapshot(transport=primary)
        self.assertEqual(p["source"],roi.TRACK_SOURCE)
        self.assertEqual(seen,[(roi.TRACK_SOURCE,"GET",6)])
        seen.clear()
        def fallback(req,timeout):
            seen.append((req.full_url,req.get_method(),timeout))
            if req.full_url==roi.TRACK_SOURCE:
                raise TimeoutError("simulated")
            return Response(fixture())
        p=roi.get_pool_snapshot(transport=fallback)
        self.assertEqual(p["source"],roi.SOURCE)
        self.assertEqual(seen,[(roi.TRACK_SOURCE,"GET",6),(roi.SOURCE,"GET",7)])

    def test_5090_laptop_break_even_and_stress(self):
        out=roi.compute(offer(),self.pool)
        self.assertEqual(out["assumed_total_ths"],330)
        self.assertAlmostEqual(out["prl_per_day_scenario"],4.0308,places=3)
        self.assertGreater(out["base_margin_usd_day"],0)
        self.assertLess(out["stress_margin_usd_day"],out["base_margin_usd_day"])
        self.assertFalse(out["net_profit_verified"])
        self.assertFalse(out["executed_bid_verified"])
        self.assertFalse(out["hashrate_verified_on_selected_host"])
        self.assertFalse(out["rental_permitted"])
        text=roi.format_scenario(out)
        self.assertIn("No es rentabilidad verificada",text)
        self.assertIn("Sin pujas ni gasto",text)

    def test_multi_gpu_distinct_variant_and_unknown_gpu_fail_closed(self):
        d=roi.compute(offer(model="NVIDIA GeForce RTX 5090",count=2,
                            variant="desktop_label"),self.pool)
        self.assertEqual(d["assumed_total_ths"],760)
        with self.assertRaisesRegex(roi.ProfitError,"gpu_hashrate_unverified"):
            roi.compute(offer(model="RTX 5080"),self.pool)
        with self.assertRaisesRegex(roi.ProfitError,"gpu_hashrate_unverified"):
            roi.compute(offer(model="RTX 4070 Ti SUPER",variant="laptop"),self.pool)
        with self.assertRaisesRegex(roi.ProfitError,"invalid_gpu_configuration"):
            roi.compute(offer(count=17),self.pool)

    def test_script_injection_cannot_spoof_page_price(self):
        malicious=fixture().replace("<body>","<body><script>OTC $ 15 Kryptex Net yield 30 PRL per PH/s PearlHash</script>")
        self.assertEqual(roi.parse_pool_html(malicious)["prl_per_ph_day"],"14.37")

    def test_otc_price_cannot_be_presented_as_sale_verified(self):
        bad=dict(self.pool,market_sale_verified=True)
        with self.assertRaisesRegex(roi.ProfitError,"untrusted_market_claim"):
            roi.compute(offer(),bad)
        for bogus in ("Infinity",float("nan"),-1,0,True,"100000000000000000"):
            with self.subTest(bogus=str(bogus)):
                with self.assertRaises(roi.ProfitError):
                    roi.compute(offer(price=bogus),self.pool)

    def test_public_http_get_only_and_no_credentials(self):
        seen=[]
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*x):pass
            def read(self,n):return fixture().encode()
        def transport(req,timeout):
            seen.append((req.full_url,req.get_method(),timeout,dict(req.header_items())))
            return Response()
        p=roi.get_pool_snapshot(transport=transport)
        self.assertEqual(p["source"],roi.SOURCE)
        self.assertEqual([x[0] for x in seen],[roi.TRACK_SOURCE,roi.SOURCE])
        self.assertTrue(all(x[1]=="GET" for x in seen))
        self.assertEqual([x[2] for x in seen],[6,7])
        self.assertTrue(all(not any("Auth" in key for key in x[3]) for x in seen))


class TelegramScenarioFlow(unittest.TestCase):
    def setUp(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        import telegram_proposals as tp
        from test_telegram_clore_competition import FakeTelegram
        self.temp=TemporaryDirectory()
        self.store=tp.ProposalStore(str(Path(self.temp.name)/"bot.sqlite"))
        self.api=FakeTelegram()
        self.chat=tp.TelegramChannel(self.store,tp.TelegramAPI(
             "1234567:"+("a"*35),transport=self.api),8125,8125)
        self.now=int(__import__("time").time())
    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def make_selection(self):
        from unittest.mock import patch
        from test_telegram_clore_competition import message,cb,listing
        import telegram_clore_search as search
        self.api.updates=[message("/gpu 5090 laptop",1)]
        with patch.object(search,"fetch",return_value=[listing()]):
            self.chat.poll_once(self.now)
        pick=[x for m,x in self.api.calls if m=="sendMessage"][-1][
              "reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        self.api.updates=[cb(pick,2,201)]
        self.chat.poll_once(self.now)
        selection=[x for m,x in self.api.calls if m=="sendMessage"][-1]
        return selection["reply_markup"]["inline_keyboard"][1][0]["callback_data"]

    def test_owner_can_request_scenario_without_rental(self):
        from unittest.mock import patch
        from test_telegram_clore_competition import cb
        button=self.make_selection()
        self.assertTrue(button.startswith("gpu-roi:"))
        self.api.updates=[cb(button,3,202)]
        with patch.object(roi,"get_pool_snapshot",return_value=roi.parse_pool_html(fixture())):
            self.chat.poll_once(self.now)
        payload=[x for m,x in self.api.calls if m=="sendMessage"][-1]
        self.assertIn("Escenario PRL",payload["text"])
        self.assertIn("No es rentabilidad verificada",payload["text"])
        self.assertFalse(self.store.db.execute(
            "SELECT COUNT(*) FROM clore_telegram_offers").fetchone()[0])
        self.assertEqual(set(m for m,_ in self.api.calls),
            {"getUpdates","sendMessage","answerCallbackQuery"})

    def test_forged_callback_cannot_fetch_pool(self):
        from unittest.mock import patch
        from test_telegram_clore_competition import cb
        button=self.make_selection()
        for update in (cb(button,3,201),cb(button,4,202,user=7777)):
            self.api.updates=[update]
            with patch.object(roi,"get_pool_snapshot",side_effect=AssertionError("network forbidden")):
                self.chat.poll_once(self.now)

    def test_upstream_missing_rate_does_not_fake_profit(self):
        from unittest.mock import patch
        from test_telegram_clore_competition import cb
        button=self.make_selection()
        self.api.updates=[cb(button,3,202)]
        with patch.object(roi,"get_pool_snapshot",side_effect=roi.ProfitError("pool_unavailable")):
            self.chat.poll_once(self.now)
        payload=[x for m,x in self.api.calls if m=="sendMessage"][-1]
        self.assertIn("No puedo verificar",payload["text"])

if __name__=="__main__":
    unittest.main()
