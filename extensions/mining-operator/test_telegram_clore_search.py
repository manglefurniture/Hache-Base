"""Live Clore GPU search flow: offline fixtures; no provider bids or spend."""
import json
from http.client import IncompleteRead
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import telegram_clore_search as s
import telegram_proposals as tp

CHAT = USER = 8125

def rig(oid, model="RTX 5090", variant="", count=1, day=5.5, rented=False):
    g = "NVIDIA GeForce " + model + (" Laptop GPU" if variant=="laptop" else "")
    return {"id":oid,"rented":rented,"specs":{
                "gpu":f"{count}x {g}","gpuram":24 if variant=="laptop" else 32,
                "ram":32,"net":{"cc":"US"}},
            "gpu_array":[{"name":g} for _ in range(count)],
            "price":{"spot":{"USD-Blockchain":day},
                     "on_demand":{"USD-Blockchain":day+1}}}

def text_command(value, update_id, *, user=USER, chat=CHAT, kind="private"):
    return {"update_id":update_id, "message":{"text":value,
            "from":{"id":user},"chat":{"id":chat,"type":kind}}}

def callback(data, update_id, message_id, *, user=USER, chat=CHAT, kind="private"):
    return {"update_id":update_id, "callback_query":{
            "id":"q"+str(update_id),"data":data,"from":{"id":user},
            "message":{"message_id":message_id,"chat":{"id":chat,"type":kind}}}}

class Transport:
    def __init__(self):
        self.updates=[]
        self.calls=[]
        self.counter=200
        self.failed=False
    def __call__(self,url,data):
        method=url.rsplit("/",1)[-1]
        self.calls.append((method,data))
        if method=="getUpdates":
            return {"ok":True,"result":self.updates}
        if method=="sendMessage":
            if self.failed:
                return {"ok":False}
            self.counter+=1
            return {"ok":True,"result":{"message_id":self.counter}}
        if method=="answerCallbackQuery":
            return {"ok":True,"result":True}
        raise AssertionError("Unsupported Telegram method")

class CloreSearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=tp.ProposalStore(str(Path(self.tmp.name)/"store.db"))
        self.api=Transport()
        self.channel=tp.TelegramChannel(self.store,tp.TelegramAPI(
            "1234567:"+("a"*35), transport=self.api),CHAT,USER)
        self.tick=int(time.time())
        self.rows=[rig(501),rig(502,day=4.9),rig(503,variant="laptop",day=4),
                   rig(504,model="RTX 4080",day=3),rig(505,count=2,day=2),
                   rig(506,rented=True,day=1),rig(507,day=5.1)]
    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_parse_search_restricts_input(self):
        self.assertEqual(s.parse_command("/gpu 5090 laptop"),{"model":"5090","variant":"laptop","count":1})
        self.assertEqual(s.parse_command("/gpu 4070 ti super escritorio x2"),
                         {"model":"4070 TI SUPER","variant":"desktop","count":2})
        self.assertEqual(s.parse_command("/gpu"),{"help":True})
        self.assertEqual(s.parse_command("/gpu 5090; curl anything"),{"help":True})
        self.assertIsNone(s.parse_command("/rent 5090"))

    def test_sorted_exact_whole_rig_and_no_profit_claim(self):
        q=s.parse_command("/gpu 5090")
        matches,total=s.offers(self.rows,q)
        self.assertEqual([x["id"] for x in matches],[503,502,507,501])
        self.assertEqual(total,4)
        self.assertEqual(matches[0]["floor_usd_hour"],round(4/24,6))
        self.assertTrue(all("profit" not in x and "net" not in x for x in matches))
        q=s.parse_command("/gpu 5090 laptop")
        self.assertEqual([x["id"] for x in s.offers(self.rows,q)[0]],[503])
        q=s.parse_command("/gpu 5090 escritorio x2")
        self.assertEqual([x["id"] for x in s.offers(self.rows,q)[0]],[505])

    def test_exact_gpu_model_does_not_include_ti_or_super_variants(self):
        rows = [rig(1200, model="RTX 4070", day=3),
                rig(1201, model="RTX 4070 Ti", day=2),
                rig(1202, model="RTX 4070 Ti SUPER", day=1),
                rig(1203, model="RTX 5090 D v2", day=1)]
        for command, expected in [
            ("/gpu 4070", [1200]),
            ("/gpu 4070 ti", [1201]),
            ("/gpu 4070 ti super", [1202]),
            ("/gpu 5090", []),
            ("/gpu 5090 d v2", [1203]),
        ]:
            with self.subTest(command=command):
                result,_=s.offers(rows,s.parse_command(command))
                self.assertEqual([x["id"] for x in result], expected)

    def test_malformed_network_metadata_never_breaks_search(self):
        bad = rig(1300)
        bad["specs"]["net"] = ["unexpected", "array"]
        result, n = s.offers([bad],s.parse_command("/gpu 5090"))
        self.assertEqual(n, 1)
        self.assertEqual(result[0]["country"], "??")
        bad["specs"]["net"] = "bad"
        self.assertEqual(s.offers([bad],s.parse_command("/gpu 5090"))[0][0]["country"],"??")

    def test_owner_query_sends_fresh_results_and_binds_selection(self):
        self.api.updates=[text_command("/gpu 5090 laptop",1)]
        with patch.object(s,"fetch",return_value=self.rows):
            self.channel.poll_once(self.tick)
        msgs=[data for method,data in self.api.calls if method=="sendMessage"]
        self.assertEqual(len(msgs),1)
        self.assertIn("#503",msgs[0]["text"])
        self.assertIn("NO por rentabilidad neta",msgs[0]["text"])
        button=msgs[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        self.assertIn("gpu-pick:",button)
        self.api.calls.clear()
        self.api.updates=[callback(button,2,201)]
        self.channel.poll_once(self.tick)
        msgs=[x for name,x in self.api.calls if name=="sendMessage"]
        self.assertEqual(len(msgs),1)
        self.assertIn("Oferta seleccionada #503",msgs[0]["text"])
        self.assertIn("sin puja ni alquiler",msgs[0]["text"])
        self.assertEqual(self.store.db.execute(
            "SELECT selected_id FROM gpu_search_snapshots").fetchone()[0],503)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM clore_telegram_offers").fetchone()[0],0)

    def test_wrong_chat_user_or_message_does_not_select(self):
        self.api.updates=[text_command("/gpu 5090",1,user=100)]
        with patch.object(s,"fetch",side_effect=AssertionError("must not fetch")):
            self.channel.poll_once(self.tick)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM gpu_search_snapshots").fetchone()[0],0)
        self.api.updates=[text_command("/gpu 5090",2)]
        with patch.object(s,"fetch",return_value=self.rows):
            self.channel.poll_once(self.tick)
        button=[data for name,data in self.api.calls if name=="sendMessage"][-1][
            "reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        self.api.updates=[callback(button,3,9999)]
        self.channel.poll_once(self.tick)
        self.assertEqual(self.store.db.execute("SELECT selected_id FROM gpu_search_snapshots").fetchone()[0],None)
        self.api.updates=[callback(button,4,201,user=99)]
        self.channel.poll_once(self.tick)
        self.assertEqual(self.store.db.execute("SELECT selected_id FROM gpu_search_snapshots").fetchone()[0],None)

    def test_button_pagination_and_page_offer_binding(self):
        rows=[rig(1000+i,day=4+i*.01) for i in range(12)]
        self.api.updates=[text_command("/gpu 5090",1)]
        with patch.object(s,"fetch",return_value=rows):
            self.channel.poll_once(self.tick)
        first=[data for method,data in self.api.calls if method=="sendMessage"][-1]
        self.assertIn("Página 1/3", first["text"])
        next_button=first["reply_markup"]["inline_keyboard"][-1][0]["callback_data"]
        self.assertTrue(next_button.startswith("gpu-page:"))
        self.api.updates=[callback(next_button,2,201)]
        self.channel.poll_once(self.tick)
        second=[data for method,data in self.api.calls if method=="sendMessage"][-1]
        self.assertIn("Página 2/3",second["text"])
        self.assertIn("#1005",second["text"])
        # Forging a page-2 choice against the page-1 message is rejected.
        bad=second["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        self.api.updates=[callback(bad,3,201)]
        self.channel.poll_once(self.tick)
        self.assertIsNone(self.store.db.execute(
            "SELECT selected_id FROM gpu_search_snapshots").fetchone()[0])
        self.api.updates=[callback(bad,4,202)]
        self.channel.poll_once(self.tick)
        self.assertEqual(self.store.db.execute(
            "SELECT selected_id FROM gpu_search_snapshots").fetchone()[0],1005)

    def test_no_spend_commands_and_duplicate_selection(self):
        self.api.updates=[text_command("/pujar 5090",1),
                          text_command("/rent 5090",2)]
        with patch.object(s,"fetch",side_effect=AssertionError("no fetch")):
            self.channel.poll_once(self.tick)
        self.assertFalse(any(method=="sendMessage" for method,_ in self.api.calls))

    def test_search_expired_cannot_be_selected(self):
        self.api.updates=[text_command("/gpu 5090",1)]
        with patch.object(s,"fetch",return_value=self.rows):
            self.channel.poll_once(self.tick)
        btn=[data for name,data in self.api.calls if name=="sendMessage"][-1][
            "reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        nonce=btn.split(":")[1]
        self.store.db.execute("UPDATE gpu_search_snapshots SET expires_at=? WHERE nonce=?",
                              (self.tick-1,nonce))
        self.api.updates=[callback(btn,2,201)]
        self.channel.poll_once(self.tick)
        self.assertIsNone(self.store.db.execute(
            "SELECT selected_id FROM gpu_search_snapshots").fetchone()[0])

    def test_truncated_https_response_is_safe_and_does_not_bid(self):
        class Truncated:
            status=200
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,n): raise IncompleteRead(b'{', 3)
        with self.assertRaisesRegex(s.SearchError,"clore_not_available"):
            s.fetch(transport=lambda request, timeout: Truncated())

    def test_failures_do_not_trigger_commercial_mutation(self):
        self.api.updates=[text_command("/gpu 5090",1)]
        with patch.object(s,"fetch",side_effect=s.SearchError("clore_not_available")):
            self.channel.poll_once(self.tick)
        sends=[x for method,x in self.api.calls if method=="sendMessage"]
        self.assertEqual(len(sends),1)
        self.assertIn("No se gastó nada",sends[0]["text"])
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM gpu_search_snapshots").fetchone()[0],0)

    def test_api_only_fixed_public_get(self):
        seen=[]
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,n):return json.dumps({"code":0,"servers":self_rows}).encode()
        self_rows=self.rows
        def probe(req,timeout):
            seen.append((req.full_url,req.get_method(),timeout))
            return Response()
        self.assertEqual(len(s.fetch(transport=probe)),len(self.rows))
        self.assertEqual(seen,[(s.API,"GET",22)])

if __name__=="__main__":
    unittest.main()
