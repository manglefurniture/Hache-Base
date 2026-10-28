"""Regression: Spot quote must reuse existing root-held Clore key path."""
from pathlib import Path
import unittest

DIR=Path(__file__).resolve().parent/"deploy"
EXPECTED="LoadCredential=clore_key:/etc/hache-miner/secrets/clore_api_key"

class SecretPathTests(unittest.TestCase):
    def test_quote_uses_existing_financial_guard_key(self):
        unit=(DIR/"hache-mining-operator-clore-spot-quote.service.example").read_text()
        install=(DIR/"install-clore-spot-quote.sh").read_text()
        self.assertIn(EXPECTED,unit)
        self.assertIn("/etc/hache-miner/secrets/clore_api_key",install)
        self.assertNotIn("/etc/hache-miner/clore-api-key",unit)
        self.assertNotIn("/etc/hache-miner/clore-api-key",install)
        self.assertIn("LoadCredential=",unit)
        self.assertNotIn("ExecStart=/bin/bash",unit)
        self.assertIn('[[ "$EUID" -eq 0 ]]',install)

if __name__=="__main__":
    unittest.main()
