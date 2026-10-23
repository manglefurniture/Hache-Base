"""Static release safety checks. No service mutations executed in tests."""
from pathlib import Path
import subprocess
import unittest

SOURCE=Path(__file__).resolve().parent
SCRIPT=SOURCE/"deploy"/"deploy-gpu-variants.sh"

class ReleaseTests(unittest.TestCase):
    def test_bash_syntax(self):
        r=subprocess.run(["bash","-n",str(SCRIPT)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)

    def test_stage_nounset_initializes_root_before_dst(self):
        """Exercise the real Bash statements that previously failed at line 46."""
        lines=SCRIPT.read_text().splitlines()
        index=lines.index('stage() {')
        locals_=[]
        for line in lines[index+1:]:
            if line.strip().startswith('local '):
                locals_.append(line)
            elif locals_:
                break
        self.assertGreaterEqual(len(locals_),2)
        script="set -u; SHA=fixedsha; stage() {\n"+ "\n".join(locals_)+"\nprintf '%s' \"$dst\";\n}; stage /tmp/hache-test"
        result=subprocess.run(["bash","-c",script],capture_output=True,text=True,timeout=8)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout,"/tmp/hache-test/releases/fixedsha")

    def test_exact_sha_revert_paths(self):
        s=SCRIPT.read_text()
        self.assertIn('invalid_full_commit',s)
        self.assertIn('git -C "$dst" rev-parse HEAD',s)
        self.assertIn('git -C "$dst" fetch --quiet --no-tags --depth 1 origin "$SHA"',s)
        self.assertIn('modified_or_extra_release_files',s)
        self.assertIn('release_contains_untrusted_owner',s)
        self.assertIn('PYTHONDONTWRITEBYTECODE=1',s)
        self.assertIn('OLD_OS="$(readlink "$OP/current")"',s)
        self.assertIn('OLD_BS="$(readlink "$BOT/current")"',s)
        self.assertIn('mv -Tf "$OP/.rollback.$$" "$OP/current"',s)
        self.assertIn('mv -Tf "$BOT/.rollback.$$" "$BOT/current"',s)
        self.assertIn("trap 'rollback",s)

    def test_lease_check_pre_and_post_freeze(self):
        s=SCRIPT.read_text()
        self.assertGreaterEqual(s.count("check_leases"),3)
        self.assertIn('WHERE phase=?',s)
        self.assertIn('hache-miner-vast-watchdog.timer',s)
        self.assertIn('hache-mining-operator-vast-lease.timer',s)
        self.assertNotIn('systemctl stop hache-miner-vast-watchdog',s)
        self.assertGreaterEqual(s.count("check_clore_leases"), 3)
        self.assertIn("active_or_unreadable_clore_financial_obligation", s)
        self.assertIn("hache-mining-operator-clore-cancel.timer", s)
        self.assertIn("test_clore_cancel_guard.py", s)

    def test_no_spend_smoke_and_unit_tests(self):
        s=SCRIPT.read_text()
        for snippet in ('test_clore_market.php','test_provider.php',
                        'test_mining_advisor.py','test_telegram_proposals.py',
                        '"method":"capabilities"','"action":"clore.marketplace"'):
            self.assertIn(snippet,s)
        for forbidden in ('"method":"execute"','"method":"prepare"',
                          '"action":"vast.rent"','"action":"clore.create_order"',
                          'sudoers','systemctl restart mariadb'):
            self.assertNotIn(forbidden,s)

    def test_bad_sha_aborts_without_touching_services(self):
        r=subprocess.run(["bash",str(SCRIPT),"INVALID"],
            capture_output=True,text=True,timeout=8)
        self.assertNotEqual(r.returncode,0)
        self.assertTrue("root_required" in r.stderr or
                        "invalid_full_commit" in r.stderr,r.stderr)

if __name__=="__main__":
    unittest.main()
