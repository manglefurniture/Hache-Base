"""Market scanner and notifier regression tests. No network, wallet or spend."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest

import mining_market_scout as scout
import mining_market_notifier as notify

NOW = datetime.now(timezone.utc).replace(microsecond=0)


def vast(name="RTX 4070 Laptop GPU", price=0.3, suffix=1):
    return {
        "source": "vast_on_demand_public_offers",
        "snapshot_utc": NOW.isoformat(), "rental_authorized": False,
        "model_variants_partial": False, "offers": [
            {"id": 1000+suffix, "gpu_name": name, "num_gpus": 1,
             "hourly_usd": price, "gpu_variant": "laptop",
             "gpu_variant_verified": False, "reliability2": 0.95}]
    }


def clore(name="1x NVIDIA GeForce RTX 5090", price=0.5):
    return {
        "source": "clore_public_marketplace",
        "snapshot_utc": NOW.isoformat(), "rental_authorized": False,
        "prl_gpu_models_partial": False, "prl_gpu_models": [
            {"id": 2001, "gpu": name, "gpu_count_verified": 1,
             "on_demand_usd_hour": price,
             "spot_floor_usd_hour": 0.35, "gpu_variant": "unverified",
             "gpu_variant_verified": False}]
    }


class FakeApi:
    def __init__(self):
        self.sent = []

    def call(self, method, data):
        assert method == "sendMessage"
        self.sent.append(data)
        return {"message_id": 123 + len(self.sent)}


class MarketScanTests(unittest.TestCase):
    def test_provider_inputs_immutable_and_no_net_claims(self):
        report = scout.make_report(vast(), clore(), NOW, (NOW.isoformat(), True))
        self.assertEqual(len(report["offers"]), 2)
        self.assertFalse(report["net_profit_verified"])
        self.assertFalse(report["prl_market_price_verified"])
        self.assertFalse(report["per_gpu_prl_verified"])
        self.assertFalse(report["rental_permitted"])
        self.assertEqual({x["provider"] for x in report["offers"]}, {"vast", "clore"})
        self.assertEqual(report["offers"][0]["gpu_variant"], "laptop")
        self.assertEqual(report["offers"][1]["gpu_variant"], "unverified")
        self.assertEqual(report["offers"][1]["spot_floor_usd_hour"], 0.35)
        self.assertTrue(all(o["net_verified"] is False for o in report["offers"]))

    def test_only_broker_read_queries(self):
        for forbidden in ("vast.rent", "clore.create_order", "vast.start", "salad.stop"):
            with self.subTest(forbidden=forbidden):
                with self.assertRaisesRegex(scout.ScanError, "not_a_readonly_marketplace"):
                    scout.query_broker(forbidden)

    def test_fails_closed_stale_and_unsafe_sources(self):
        outdated=vast()
        outdated["snapshot_utc"]=(NOW-timedelta(minutes=8)).isoformat()
        with self.assertRaisesRegex(scout.ScanError, "stale_provider_quotes"):
            scout.make_report(outdated, clore(), NOW)
        illegal=clore()
        illegal["rental_authorized"]=True
        with self.assertRaisesRegex(scout.ScanError, "unsafe_provider_response"):
            scout.make_report(vast(), illegal, NOW)

    def test_no_provider_secret_or_unknown_gpu_with_invalid_count(self):
        v=vast()
        v["offers"][0]["ssh_private_key"]="DO_NOT_LEAK_SECRET"
        v["offers"].append({**v["offers"][0], "id":1002, "num_gpus":None})
        report=scout.make_report(v,clore(),NOW)
        self.assertEqual(len(report["offers"]),2)
        self.assertNotIn("DO_NOT_LEAK_SECRET",json.dumps(report))

    def test_report_safe_permissions_and_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"report.json"
            report=scout.make_report(vast(),clore(),NOW)
            scout.save_report(report,p,uid=os.geteuid(),gid=os.getegid())
            self.assertEqual(p.stat().st_mode & 0o777, 0o640)
            loaded=notify.load_report(p,NOW,source_uid=os.geteuid(),source_gid=os.getegid())
            self.assertEqual(loaded["offers"],report["offers"])
            p.chmod(0o666)
            with self.assertRaisesRegex(notify.NotifyError,"untrusted_report"):
                notify.load_report(p,NOW)

    def test_spoofed_net_or_stale_report_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"report.json"
            report=scout.make_report(vast(),clore(),NOW)
            scout.save_report(report,p)
            with self.assertRaisesRegex(notify.NotifyError,"stale_report"):
                notify.load_report(p,NOW+timedelta(minutes=11))
            report["net_profit_verified"]=True
            scout.save_report(report,p)
            with self.assertRaisesRegex(notify.NotifyError,"unexpected_scout_claim"):
                notify.load_report(p,NOW)


class MarketNotificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.state=notify.NotificationState(Path(self.tmp.name)/"alerts.sqlite")
        self.report=scout.make_report(vast(),clore(),NOW)
        self.api=FakeApi()

    def tearDown(self):
        self.state.close()
        self.tmp.cleanup()

    def test_initial_digest_no_rent_language_and_spot_warning(self):
        result=notify.send_report(self.api,123,self.report,self.state,NOW)
        self.assertEqual(result,"initial")
        self.assertEqual(len(self.api.sent),1)
        text=self.api.sent[0]["text"]
        self.assertIn("SIN renta, puja ni gasto",text)
        self.assertIn("Spot mínimo",text)
        self.assertIn("Rentabilidad neta: NO verificada",text)
        self.assertEqual(self.api.sent[0]["chat_id"],123)
        self.assertEqual(self.state.current()[2],1)

    def test_hourly_dedupe_and_six_hour_cooldown(self):
        notify.send_report(self.api,123,self.report,self.state,NOW)
        self.assertEqual(notify.send_report(self.api,123,self.report,self.state,
                                            NOW+timedelta(minutes=58)),"unchanged")
        self.assertEqual(len(self.api.sent),1)
        # No announcement on a trivial or model-incomparable price change.
        other=scout.make_report(vast(name="RTX 3060 Laptop GPU"),clore(),NOW)
        self.assertEqual(notify.send_report(self.api,123,other,self.state,
                                            NOW+timedelta(hours=7)),"unchanged")
        improved=scout.make_report(vast(price=0.25),clore(),NOW)
        self.assertEqual(notify.send_report(self.api,123,improved,self.state,
                                            NOW+timedelta(hours=7)),"improved_advertised_quote")
        self.assertEqual(self.state.current()[2],2)
        self.assertEqual(notify.send_report(self.api,123,improved,self.state,
                                            NOW+timedelta(hours=23)),"unchanged")
        self.assertEqual(len(self.api.sent),2)

    def test_does_not_alert_for_spot_floor_only(self):
        notify.send_report(self.api,123,self.report,self.state,NOW)
        altered=scout.make_report(vast(),clore(),NOW)
        altered["offers"][1]["spot_floor_usd_hour"]=0.01
        self.assertEqual(notify.send_report(self.api,123,altered,self.state,
                                            NOW+timedelta(hours=7)),"unchanged")

    def test_daily_digest_next_day_with_timestamps(self):
        notify.send_report(self.api,123,self.report,self.state,NOW)
        outcome=notify.send_report(self.api,123,self.report,self.state,
                                   NOW+timedelta(days=1,hours=1))
        self.assertEqual(outcome,"daily_digest")
        self.assertEqual(self.state.current()[2],1)
        self.assertEqual(len(self.api.sent),2)

    def test_failed_delivery_does_not_mark_sent(self):
        class Unavailable:
            def call(self, *_):
                raise notify.ProposalError("telegram_unavailable")
        with self.assertRaises(notify.ProposalError):
            notify.send_report(Unavailable(),123,self.report,self.state,NOW)
        self.assertIsNone(self.state.current()[0])

if __name__ == "__main__":
    unittest.main()
