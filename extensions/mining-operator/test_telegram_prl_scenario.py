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
        self.assertEqual(seen[0][0],roi.SOURCE)
        self.assertEqual(seen[0][1],"GET")
        self.assertEqual(seen[0][2],12)
        self.assertFalse(any("Auth" in key for key in seen[0][3]))

if __name__=="__main__":
    unittest.main()
