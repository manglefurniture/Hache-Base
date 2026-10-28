#!/usr/bin/env python3
"""Fail-closed illustrative PRL mining unit economics. Never authorizes a bid."""
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from http.client import HTTPException
import math
import re
import ssl
import urllib.error
import urllib.request

SOURCE = "https://www.pearlsonar.com/pools"
# Historical observations from the user's GPU trials, not verified per-host.
# Never extrapolate without exact family, variant, count, and a real share audit.
CALIBRATIONS = {
    ("RTX 5090", "laptop"): ("330", "Salad 5090 Laptop, historical"),
    ("RTX 5090", "desktop_label"): ("380", "Vast 5090 desktop, historical"),
    ("RTX 4070 TI SUPER", "desktop_label"): ("155", "Salad/Clore 4070 Ti SUPER, historical"),
    ("RTX 4090", "desktop_label"): ("300", "Salad 4090, historical"),
}
UPTIME = Decimal("0.85")  # scenario allowance; not actual uptime
PRICE_HAIRCUT = Decimal("0.90")  # sale slippage/market liquidity reserve
RENTAL_BUFFER = Decimal("1.05")  # approximate Clore rental/fee overhead, not provider quote

class ProfitError(ValueError):
    pass

class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts=[]
        self.suppress=0
    def handle_starttag(self, tag, attrs):
        if tag in ("script","style"):
            self.suppress += 1
    def handle_endtag(self, tag):
        if tag in ("script","style") and self.suppress:
            self.suppress -= 1
    def handle_data(self, data):
        if not self.suppress:
            self.parts.append(data)

def amount(raw, low, high):
    if type(raw) not in (str,int,float) or isinstance(raw,bool):
        raise ProfitError("invalid_input_amount")
    try:
        d=Decimal(str(raw))
    except (ValueError,InvalidOperation):
        raise ProfitError("invalid_input_amount") from None
    if not d.is_finite() or not Decimal(str(low)) < d < Decimal(str(high)):
        raise ProfitError("invalid_input_amount")
    return d

def parse_pool_html(page):
    """Parse only visible provider cards, never next.js hydration scripts."""
    if not isinstance(page,(str,bytes)):
        raise ProfitError("invalid_pool_page")
    if isinstance(page,bytes):
        try: page=page.decode("utf-8")
        except UnicodeError: raise ProfitError("invalid_pool_page") from None
    if not 3000 <= len(page) <= 400000:
        raise ProfitError("pool_page_size_untrusted")
    p=Parser()
    try:
        p.feed(page)
    except Exception:
        raise ProfitError("invalid_pool_page") from None
    text=" ".join(" ".join(p.parts).split())
    # Bound the source card so another pool's yield cannot be substituted.
    k=re.search(r"\bKryptex\b",text)
    end=re.search(r"\b(?:PearlHash|LuckyPool|Hero Miners)\b",text[k.end():]) if k else None
    if not k or not end:
        raise ProfitError("kryptex_pool_card_missing")
    card=text[k.start():k.end()+end.start()]
    found=re.search(r"\bNet yield\s+(\d{1,2}(?:\.\d{1,3})?)\s+PRL per PH/s",card)
    price=re.search(r"\bOTC\s+\$\s*(\d{1,2}(?:\.\d{1,5})?)\b",text[:k.start()])
    if not found or not price:
        raise ProfitError("pool_yield_or_otc_missing")
    return {"prl_per_ph_day":str(amount(found[1],1,45)),
            "otc_usd_per_prl":str(amount(price[1],0.1,20)),
            "source":SOURCE, "market_sale_verified":False,
            "yield_historical_24h":True}

def get_pool_snapshot(*,transport=None):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,url):return None
    opener=urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),NoRedirect())
    transport=transport or opener.open
    request=urllib.request.Request(SOURCE,method="GET",
         headers={"Accept":"text/html","User-Agent":"Hache-PRL-Scenario/1"})
    try:
        with transport(request,timeout=12) as response:
            if getattr(response,"status",200)!=200:
                raise ProfitError("pool_unavailable")
            html=response.read(400001)
    except (OSError,urllib.error.URLError,TimeoutError,HTTPException):
        raise ProfitError("pool_unavailable") from None
    return parse_pool_html(html)

def normalized_model(gpu):
    if type(gpu) is not str or len(gpu)>125:
        raise ProfitError("gpu_model_unknown")
    name=re.sub(r"\s+"," ",gpu.upper().replace("-"," ")).strip()
    name=re.sub(r"^(?:(?:NVIDIA|GEFORCE)\s+)+","",name)
    name=re.sub(r"\s+(?:LAPTOP|MOBILE)(?:\s+GPU)?$","",name)
    name=re.sub(r"\s+GPU$","",name)
    return name

def compute(offer, market):
    """Estimate one listed whole-rig at Spot host *floor*, NOT an executable bid."""
    if type(offer) is not dict or type(market) is not dict:
        raise ProfitError("invalid_roi_input")
    if type(offer.get("id")) is not int or not 0<offer["id"]<10**15:
        raise ProfitError("invalid_offer")
    count=offer.get("gpu_count")
    variant=offer.get("variant")
    if type(count) is not int or not 1<=count<=16 or variant not in ("laptop","desktop_label"):
        raise ProfitError("invalid_gpu_configuration")
    model=normalized_model(offer.get("gpu"))
    ref=CALIBRATIONS.get((model,variant))
    if not ref:
        raise ProfitError("gpu_hashrate_unverified")
    ths=amount(ref[0],1,1000)*count
    floor_hour=amount(offer.get("floor_usd_hour"),0,100)
    yield_ph=amount(market.get("prl_per_ph_day"),1,45)
    prl_price=amount(market.get("otc_usd_per_prl"),.1,20)
    if market.get("market_sale_verified") is not False:
        raise ProfitError("untrusted_market_claim")
    prl_per_day=ths/Decimal("1000")*yield_ph*UPTIME
    sale_revenue=prl_per_day*prl_price*PRICE_HAIRCUT
    rent_cost=floor_hour*24*RENTAL_BUFFER
    base_margin=sale_revenue-rent_cost
    # Stress: network difficulty +30% (yield /1.3), price -20%.
    stress_revenue=sale_revenue / Decimal("1.3") * Decimal("0.8")
    stress_margin=stress_revenue-rent_cost
    maximum_floor_hour=(stress_revenue/24/RENTAL_BUFFER)
    round4=lambda x:float(x.quantize(Decimal("0.0001")))
    return {
        "offer_id":offer["id"],"assumed_total_ths":float(ths),
        "gpu_reference":ref[1], "gpu_model":model, "gpu_count":count,
        "spot_floor_usd_hour":round4(floor_hour),
        "prl_yield_per_ph_day":float(yield_ph),
        "otc_reference_usd_prl":float(prl_price),
        "prl_per_day_scenario":round4(prl_per_day),
        "estimated_usd_day_after_sale_reserve":round4(sale_revenue),
        "estimated_rent_usd_day_including_buffer":round4(rent_cost),
        "base_margin_usd_day":round4(base_margin),
        "stress_margin_usd_day":round4(stress_margin),
        "stress_break_even_spot_floor_usd_hour":round4(maximum_floor_hour),
        "hashrate_verified_on_selected_host":False,
        "executed_bid_verified":False, "sale_price_verified":False,
        "net_profit_verified":False, "rental_permitted":False,
        "source":market.get("source")
    }

def format_scenario(result):
    r=result
    return (
        f"<b>Escenario PRL · Clore #{r['offer_id']}</b>\n"
        f"GPU: {r['gpu_count']} × {r['gpu_model']}\n"
        f"TH/s históricos supuestos: {r['assumed_total_ths']:.0f}\n"
        f"Referencia histórica: {r['gpu_reference']}\n"
        f"Yield Kryptex (24 h): {r['prl_yield_per_ph_day']:.2f} PRL/PH/día\n"
        f"Precio OTC indicativo: US$ {r['otc_reference_usd_prl']:.4f}/PRL\n"
        f"Piso Spot anunciado: US$ {r['spot_floor_usd_hour']:.4f}/hora\n"
        f"Producción ilustrativa: {r['prl_per_day_scenario']:.3f} PRL/día\n"
        f"Ingreso tras reserva de venta: US$ {r['estimated_usd_day_after_sale_reserve']:.2f}/día\n"
        f"Renta con reserva de costos: US$ {r['estimated_rent_usd_day_including_buffer']:.2f}/día\n"
        f"Margen ilustrativo: US$ {r['base_margin_usd_day']:+.2f}/día\n"
        f"Margen adverso (+30% dificultad, -20% precio): US$ {r['stress_margin_usd_day']:+.2f}/día\n"
        f"Piso máximo para equilibrar en adverso: US$ "
        f"{r['stress_break_even_spot_floor_usd_hour']:.4f}/hora\n\n"
        "<b>No es rentabilidad verificada.</b> Se supone 85% de tiempo "
        "efectivo, reserva 10% para venta y 5% para renta. El yield es "
        "histórico de 24h, el precio OTC no es una orden ejecutable y "
        "la GPU alquilada podría rendir distinto. Una puja ganadora "
        "puede costar más que el piso. Sin pujas ni gasto."
    )
