"""Tests for read-only Spot quote isolation and Telegram selection binding."""
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import clore_spot_quote as spot
import clore_spot_quote_service as service
import telegram_clore_competition as client
import telegram_clore_search as search
import telegram_proposals as tp

USER = CHAT = 8125
KEY = "test-only-auth-credential-not-real-aaaaaaaaaaa"

def provider():
    return {"code":0,"exists":True,"market":{
        "currency_rates_in_usd":{"USD-Blockchain":1,"bitcoin":100000},
        "offers":[{"offer_id":44,"currency":"bitcoin","bid":0.00006,
                   "active":True,"my":False}],
        "server":{"min_pricing":{"USD-Blockchain":5},"online":True,
                  "visibility":"public","mrl":36}}}

def snapshot(now=None):
    return spot.parse_spot(provider(),120989,now=now or datetime.now(timezone.utc))

def listing():
    return {"id":120989,"rented":False,
            "specs":{"gpu":"1x NVIDIA GeForce RTX 5090 Laptop GPU",
                     "net":{"cc":"US"},"gpuram":24},
            "gpu_array":["RTX 5090 Laptop GPU"],
            "price":{"spot":{"USD-Blockchain":5},
                     "on_demand":{"USD-Blockchain":6}}}

class FakeSocket:
    def __init__(self, obj):
        self.raw=(json.dumps(obj)+"\n").encode()
        self.calls=[]
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def settimeout(self,n):self.calls.append(("timeout",n))
    def connect(self,p):self.calls.append(("connect",p))
    def sendall(self,b):self.calls.append(("send",json.loads(b)))
    def makefile(self,_):return BytesIO(self.raw)

class FakeTelegram:
    def __init__(self):
        self.calls=[]
        self.updates=[]
        self.msgid=200
    def __call__(self,url,data):
        name=url.rsplit("/",1)[-1]
        self.calls.append((name,data))
        if name=="getUpdates":
            return {"ok":True,"result":self.updates}
        if name=="sendMessage":
            self.msgid+=1
            return {"ok":True,"result":{"message_id":self.msgid}}
        return {"ok":True,"result":True}

def message(text,update_id):
    return {"update_id":update_id,"message":{"text":text,
        "from":{"id":USER},"chat":{"id":CHAT,"type":"private"}}}

def cb(data,update_id,message_id,*,user=USER):
    return {"update_id":update_id,"callback_query":{"data":data,"id":"q"+str(update_id),
        "from":{"id":user},"message":{"message_id":message_id,
        "chat":{"id":CHAT,"type":"private"}}}}

class CompetitionTests(unittest.TestCase):
    def test_private_quote_client_only_sends_id_to_fixed_socket(self):
        p=snapshot()
        sock=FakeSocket({"ok":True,"result":p})
        got=client.get_quote(120989,connector=lambda:sock)
        self.assertEqual(got["server_id"],120989)
        self.assertEqual(sock.calls[1],("connect",client.SOCKET))
        self.assertEqual(sock.calls[2],("send",{"server_id":120989}))
        self.assertNotIn("auth",json.dumps(sock.calls))
        self.assertNotIn(KEY,json.dumps(sock.calls))

    def test_quote_client_fails_closed_on_unauthenticated_response(self):
        for mutation in ({"rental_permitted":True},
                         {"executable_quote":True},{"net_profit_verified":True},
                         {"server_id":5},{"highest_bid_usd_day":-1},
                         {"observed_at":"2020-01-01T01:01:01+00:00"}):
            with self.subTest(mutation=mutation):
                obj=snapshot()
                obj.update(mutation)
                with self.assertRaises(client.QuoteUnavailable):
                    client.get_quote(120989,connector=lambda:FakeSocket({"ok":True,"result":obj}))
        with self.assertRaises(client.QuoteUnavailable):
            client.get_quote(120989,connector=lambda:FakeSocket({"ok":False,"error":"not_authorized"}))

    def test_no_outbound_write_in_service_process(self):
        def fetcher(ident,key):
            self.assertEqual(ident,120989)
            self.assertEqual(key,KEY)
            return snapshot()
        answer=service.process({"server_id":120989},KEY,fetcher=fetcher)
        self.assertTrue(answer["ok"])
        self.assertFalse(answer["result"]["rental_permitted"])
        self.assertNotIn(KEY,json.dumps(answer))
        for req in ({"server_id":"120989"},{"server_id":120989,"bid":5},
                    {"command":"create_order"},[],None):
            with self.assertRaises(service.ServiceError):
                service.process(req,KEY,fetcher=fetcher)

    def test_telegram_button_after_selection_and_bound_competition(self):
        with tempfile.TemporaryDirectory() as d:
            store=tp.ProposalStore(str(Path(d)/"bot.sqlite"))
            try:
                api=FakeTelegram()
                ch=tp.TelegramChannel(store,tp.TelegramAPI(
                    "1234567:"+("a"*35),transport=api),CHAT,USER)
                now=int(time.time())
                api.updates=[message("/gpu 5090 laptop",1)]
                with patch.object(search,"fetch",return_value=[listing()]):
                    ch.poll_once(now)
                first=[x for name,x in api.calls if name=="sendMessage"][-1]
                pick=first["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
                api.updates=[cb(pick,2,201)]
                ch.poll_once(now)
                selected=[x for name,x in api.calls if name=="sendMessage"][-1]
                quote=selected["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
                self.assertTrue(quote.startswith("gpu-quote:"))
                self.assertTrue(store.db.execute(
                    "SELECT 1 FROM gpu_selection_messages WHERE message_id=202").fetchone())
                api.updates=[cb(quote,3,202)]
                with patch.object(client,"get_quote",return_value=snapshot()) as call:
                    ch.poll_once(now)
                    call.assert_called_once_with(120989)
                result=[x for name,x in api.calls if name=="sendMessage"][-1]
                self.assertIn("Puja competidora máxima",result["text"])
                self.assertIn("NO es una cotización ejecutable",result["text"])
                self.assertFalse(store.db.execute("SELECT COUNT(*) FROM clore_telegram_offers").fetchone()[0])
                methods=[name for name,x in api.calls]
                self.assertTrue(set(methods)<={"getUpdates","sendMessage","answerCallbackQuery"})
            finally:
                store.close()

    def test_forged_telegram_message_cannot_request_authenticated_quote(self):
        with tempfile.TemporaryDirectory() as d:
            store=tp.ProposalStore(str(Path(d)/"bot.sqlite"))
            try:
                api=FakeTelegram()
                ch=tp.TelegramChannel(store,tp.TelegramAPI(
                    "1234567:"+("a"*35),transport=api),CHAT,USER)
                now=int(time.time())
                api.updates=[message("/gpu 5090 laptop",1)]
                with patch.object(search,"fetch",return_value=[listing()]):
                    ch.poll_once(now)
                pick=[x for name,x in api.calls if name=="sendMessage"][-1][
                    "reply_markup"]["inline_keyboard"][0][0]["callback_data"]
                api.updates=[cb(pick,2,201)]
                ch.poll_once(now)
                quote=[x for name,x in api.calls if name=="sendMessage"][-1][
                    "reply_markup"]["inline_keyboard"][0][0]["callback_data"]
                for invalid in [cb(quote,3,201),cb(quote,4,202,user=999)]:
                    api.updates=[invalid]
                    with patch.object(client,"get_quote",side_effect=AssertionError("must not call")):
                        ch.poll_once(now)
                self.assertEqual(store.db.execute("SELECT COUNT(*) FROM menu_outbox").fetchone()[0],0)
            finally:
                store.close()

if __name__=="__main__":
    unittest.main()
