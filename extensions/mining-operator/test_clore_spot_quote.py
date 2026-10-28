"""Offline safety tests: Clore Spot quote may only perform a fixed GET."""
from datetime import datetime, timezone
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from http.client import IncompleteRead
from pathlib import Path

import clore_spot_quote as spot

NOW = datetime(2026, 10, 28, 21, 0, tzinfo=timezone.utc)
KEY = "test-only-auth-credential-not-real-aaaaaaaaaaa"

def snapshot(*, bids=None, floor=4.7, online=True, visibility="public",
             min_pricing=None, rates=None):
    return {"code":0,"exists":True,
            "market":{
                "currency_rates_in_usd": rates if rates is not None else {
                    "USD-Blockchain":1, "bitcoin":100000, "CLORE-Blockchain":0.20},
                "offers": bids if bids is not None else [
                    {"offer_id":70,"bid":0.000055,"currency":"bitcoin","active":True,"my":False},
                    {"offer_id":71,"bid":6,"currency":"USD-Blockchain","active":False,"my":False},
                    {"offer_id":72,"bid":32,"currency":"CLORE-Blockchain","active":False,"my":True},
                ],
                "server":{
                    "min_pricing": (min_pricing if min_pricing is not None else {"USD-Blockchain":floor}),
                    "visibility": visibility,"online":online, "mrl":72}
            }}

class SpotQuoteTests(unittest.TestCase):
    def test_cross_currency_bid_ranking_in_usd(self):
        p=spot.parse_spot(snapshot(),120989,now=NOW)
        self.assertEqual(p["server_id"],120989)
        self.assertEqual(p["minimum_usd_day"],4.7)
        self.assertEqual(p["highest_bid_usd_day"],6.4)
        self.assertEqual(p["illustrative_1pct_usd_day"],6.464)
        self.assertEqual(p["active_bids"],1)
        self.assertEqual(p["own_bids"],1)
        self.assertEqual(p["bid_count"],3)
        self.assertFalse(p["rental_permitted"])
        self.assertFalse(p["executable_quote"])
        self.assertFalse(p["net_profit_verified"])
        self.assertNotIn(KEY,json.dumps(p))

    def test_empty_market_only_floor_shown(self):
        p=spot.parse_spot(snapshot(bids=[]),120989,now=NOW)
        self.assertEqual(p["highest_bid_usd_day"],0)
        self.assertEqual(p["illustrative_1pct_usd_day"],4.7)

    def test_offline_private_and_missing_usd_floor_fail_closed(self):
        for sample in (snapshot(online=False), snapshot(visibility="private"),
                       snapshot(min_pricing={"bitcoin":0.000001}),{"code":1},
                       {"code":0,"exists":False},snapshot(rates={"bitcoin":0.0001})):
            with self.subTest(sample=sample):
                with self.assertRaises(spot.SpotError):
                    spot.parse_spot(sample,120989,now=NOW)

    def test_bad_competing_currency_or_exchange_rate_fail_closed(self):
        p=snapshot()
        p["market"]["offers"][1]["currency"]="unknownCoin"
        with self.assertRaisesRegex(spot.SpotError,"unknown_spot_currency"):
            spot.parse_spot(p,123,now=NOW)
        p=snapshot()
        del p["market"]["currency_rates_in_usd"]["bitcoin"]
        with self.assertRaisesRegex(spot.SpotError,"missing_competing_currency_rate"):
            spot.parse_spot(p,123,now=NOW)
        p=snapshot()
        p["market"]["offers"][0]["bid"]="Infinity"
        with self.assertRaises(spot.SpotError):
            spot.parse_spot(p,123,now=NOW)

    def test_unverified_market_response_shapes_rejected(self):
        for bad in ({"offers":None}, {"offers":[{"offer_id":3}]},
                    {"offers":[{"offer_id":4,"bid":0,"currency":"bitcoin","my":False,"active":True}]},
                    {"offers":[{"offer_id":4,"bid":1,"currency":"bitcoin","my":None,"active":True}]}):
            p=snapshot(bids=[])
            p["market"].update(bad)
            with self.subTest(bad=bad):
                with self.assertRaises(spot.SpotError):
                    spot.parse_spot(p,120989,now=NOW)

    def test_only_https_get_fixed_server_and_header_private(self):
        seen=[]
        class FakeResponse:
            status=200
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,n):return json.dumps(snapshot()).encode()
        def transport(request,timeout):
            seen.append({"url":request.full_url,"method":request.get_method(),
                         "headers":dict(request.header_items()),"timeout":timeout})
            return FakeResponse()
        p=spot.fetch_spot(120989,KEY,transport=transport,now=NOW)
        self.assertFalse(p["rental_permitted"])
        self.assertEqual(seen[0]["url"],spot.BASE+"120989")
        self.assertEqual(seen[0]["method"],"GET")
        self.assertEqual(seen[0]["timeout"],12)
        self.assertIn("Auth",seen[0]["headers"])
        self.assertEqual(seen[0]["headers"]["Auth"],KEY)
        self.assertNotIn(KEY,json.dumps(p))
        self.assertNotIn("create_order",json.dumps(p))

    def test_http_protocol_failure_and_oversize_do_not_leak(self):
        class Broken:
            status=200
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,n):raise IncompleteRead(b"{", 10)
        with self.assertRaisesRegex(spot.SpotError,"spot_unavailable"):
            spot.fetch_spot(5,KEY,transport=lambda request,timeout:Broken(),now=NOW)
        class Big:
            status=200
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,n):return b"x"*(n)
        with self.assertRaisesRegex(spot.SpotError,"spot_response_too_large"):
            spot.fetch_spot(5,KEY,transport=lambda request,timeout:Big(),now=NOW)

    def test_public_telegram_cannot_supply_credential_or_server_url(self):
        for value in (0,-1,True,1.2,10**18,"1","https://evil"):
            with self.subTest(value=value):
                with self.assertRaises(spot.SpotError):
                    spot.fetch_spot(value,KEY,transport=lambda *_:self.fail("network request"),now=NOW)
        with patch.dict(os.environ,{"CREDENTIALS_DIRECTORY":""}):
            with self.assertRaisesRegex(spot.SpotError,"systemd_credential_required"):
                spot.credential()
        with tempfile.TemporaryDirectory() as d:
            Path(d,"clore_key").write_text(KEY)
            with patch.dict(os.environ,{"CREDENTIALS_DIRECTORY":d}):
                self.assertEqual(spot.credential(),KEY)

if __name__ == "__main__":
    unittest.main()
