"""Non-mutating service hardening and installation contract regression tests."""
from pathlib import Path
import subprocess
import unittest

SRC = Path(__file__).resolve().parent
DEPLOY = SRC / "deploy"


class MarketServiceTests(unittest.TestCase):
    def test_installer_syntax_and_release_pinning(self):
        installer=(DEPLOY/"install-market-scout.sh").read_text()
        r=subprocess.run(["bash","-n",str(DEPLOY/"install-market-scout.sh")],
                         capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("both_releases_must_be_current",installer)
        self.assertIn("nonclean_release",installer)
        self.assertIn("test_mining_market_scout.py",installer)
        self.assertIn("first_dual_api_scan_failed_timer_disabled",installer)
        self.assertIn("first_telegram_notification_failed_timer_disabled",installer)
        for forbidden in ('vast.rent','clore.create_order','salad.reallocate',
                          '"method":"execute"','systemctl stop hache-miner-vast'):
            self.assertNotIn(forbidden,installer)

    def test_token_not_exposed_to_broker_scout(self):
        scout=(DEPLOY/"hache-mining-market-scout.service").read_text()
        notifier=(DEPLOY/"hache-mining-market-notifier.service").read_text()
        self.assertIn("User=gpt-agent",scout)
        self.assertIn("Group=hache-telegram",scout)
        self.assertIn("SupplementaryGroups=gpt-agent",scout)
        self.assertIn("RestrictAddressFamilies=AF_UNIX",scout)
        self.assertIn("StateDirectoryMode=0750",scout)
        self.assertIn("OnSuccess=hache-mining-market-notifier.service",scout)
        self.assertNotIn("LoadCredential=",scout)
        self.assertNotIn("EnvironmentFile=",scout)
        self.assertIn("User=hache-telegram",notifier)
        self.assertIn("LoadCredential=telegram_token:",notifier)
        self.assertIn("EnvironmentFile=/etc/hache-mining-agent/telegram-recipient.env",notifier)
        self.assertIn("ReadOnlyPaths=/var/lib/hache-mining-market",notifier)
        self.assertIn("StateDirectory=hache-mining-telegram",notifier)
        self.assertNotIn("SupplementaryGroups=gpt-agent",notifier)

    def test_timer_is_hourly_not_high_frequency(self):
        timer=(DEPLOY/"hache-mining-market-scout.timer").read_text()
        self.assertIn("OnCalendar=hourly",timer)
        self.assertIn("Unit=hache-mining-market-scout.service",timer)
        self.assertIn("Persistent=true",timer)

    def test_scanner_can_only_read_fixed_actions(self):
        script=(SRC/"mining_market_scout.py").read_text()
        self.assertIn('SOURCE_ACTIONS = ("vast.marketplace", "clore.marketplace")',script)
        self.assertIn('"method": "query"',script)
        self.assertNotIn('"method": "execute"',script)
        self.assertNotIn('"action":"vast.rent"',script)
        self.assertNotIn("telegram_token",script)
        notifier=(SRC/"mining_market_notifier.py").read_text()
        self.assertIn('api.call("sendMessage"',notifier)
        self.assertNotIn("query_broker",notifier)
        self.assertNotIn("vast.start",notifier)


if __name__=="__main__":
    unittest.main()
