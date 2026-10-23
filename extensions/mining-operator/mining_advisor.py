#!/usr/bin/env python3
"""Fail-closed, read-only PRL offer evaluation backed by empirical production.

No LLM, provider mutation, API key, SSH, credential, or Telegram command path lives here.
AI recommendations may later explain these calculations but cannot override gates.
"""
import argparse
from datetime import datetime, timezone, timedelta
import json
import math
from pathlib import Path
import re
import sqlite3
import sys

MAX_BYTES = 131072
MAX_OFFERS = 100
MAX_AGE = timedelta(days=14)


def fail(reason):
    raise ValueError(reason)


def number(value, name, *, minimum=0, maximum=1e9, allow_zero=False):
    if type(value) not in (float, int) or not math.isfinite(value) or not (minimum <= value <= maximum) or (value == 0 and not allow_zero):
        fail('invalid_' + name)
    return float(value)


def utc(value):
    if not isinstance(value, str) or len(value) > 35:
        fail('invalid_timestamp')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        fail('invalid_timestamp')
    if result.tzinfo is None or result.utcoffset() is None:
        fail('timezone_required')
    return result.astimezone(timezone.utc)


def gpu_key(value, variant):
    if variant not in ('desktop', 'laptop'):
        fail('gpu_variant_unverified')
    if not isinstance(value, str) or len(value) > 100:
        fail('invalid_gpu_name')
    name = ' '.join(value.upper().replace('-', ' ').split())
    match = re.search(r'\bRTX\s*(20|30|40|50)\d{2}\b', name)
    if not match:
        fail('unsupported_gpu')
    if ('LAPTOP' in name or 'MOBILE' in name) != (variant == 'laptop') and ('LAPTOP' in name or 'MOBILE' in name):
        fail('gpu_variant_conflict')
    # Keep exact family and TI/SUPER suffix to avoid cross-GPU leakage.
    model = match.group(0).replace(' ', '')
    tail = name[match.end():]
    qualifiers = []
    for word in ('TI', 'SUPER'):
        if re.search(r'\b' + word + r'\b', tail):
            qualifiers.append(word)
    return 'RTX' + model[3:] + ''.join(qualifiers) + ':' + variant


def read_json(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        fail('missing_or_oversized_input')
    return json.loads(path.read_text(encoding='utf-8'))


class Memory:
    """Small local SQLite model: user-provided measurements, never fabricated yield."""
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.execute('''CREATE TABLE IF NOT EXISTS prl_observations(
          evidence_id TEXT PRIMARY KEY, provider TEXT NOT NULL,
          gpu_model TEXT NOT NULL, observed_at TEXT NOT NULL,
          gpu_count INTEGER NOT NULL, billed_hours REAL NOT NULL,
          prl_mined REAL NOT NULL, setup_minutes REAL NOT NULL,
          accepted_shares INTEGER NOT NULL)''')
        self.db.execute('CREATE INDEX IF NOT EXISTS prl_observations_lookup ON prl_observations(provider,gpu_model,observed_at)')
        self.db.commit()

    def record(self, item):
        if type(item) is not dict or set(item) != {'evidence_id','provider','gpu_name','variant','observed_at','gpu_count','billed_hours','prl_mined','setup_minutes','accepted_shares'}:
            fail('invalid_observation_fields')
        evidence = item['evidence_id']
        if not isinstance(evidence,str) or not re.fullmatch('[A-Za-z0-9_:-]{8,100}', evidence):
            fail('invalid_evidence_id')
        provider = item['provider']
        if provider not in ('vast','clore'):
            fail('unsupported_provider')
        key = gpu_key(item['gpu_name'], item['variant'])
        count = item['gpu_count']
        if type(count) is not int or not 1 <= count <= 16:
            fail('invalid_gpu_count')
        hours = number(item['billed_hours'], 'billed_hours', minimum=0.25, maximum=168)
        mined = number(item['prl_mined'], 'prl_mined', minimum=0, maximum=100000, allow_zero=True)
        setup = number(item['setup_minutes'], 'setup_minutes', minimum=0, maximum=1440, allow_zero=True)
        shares = item['accepted_shares']
        if type(shares) is not int or not 0 <= shares <= 100000000:
            fail('invalid_accepted_shares')
        stamp = utc(item['observed_at'])
        if stamp > datetime.now(timezone.utc) + timedelta(minutes=5):
            fail('future_measurement')
        # Idempotent import: conflicts must not overwrite evidence.
        values = (evidence, provider, key, stamp.isoformat(), count, hours, mined, setup, shares)
        old = self.db.execute('SELECT * FROM prl_observations WHERE evidence_id=?', (evidence,)).fetchone()
        if old is not None and tuple(old) != values:
            fail('evidence_id_conflict')
        if old is None:
            self.db.execute('INSERT INTO prl_observations VALUES(?,?,?,?,?,?,?,?,?)', values)
            self.db.commit()

    def summary(self, provider, key, now):
        # Query only empirical measured PRL, not projected shares/TH/s.
        earliest = (now - MAX_AGE).isoformat()
        rows = self.db.execute('''SELECT billed_hours,gpu_count,prl_mined,setup_minutes,accepted_shares
             FROM prl_observations WHERE provider=? AND gpu_model=? AND observed_at>=? AND observed_at<=?
             ORDER BY observed_at DESC LIMIT 100''', (provider, key, earliest, now.isoformat())).fetchall()
        valid = [(prl / hours / count, setup, hours) for hours,count,prl,setup,shares in rows if shares > 0 and hours >= 0.25]
        if len(valid) < 3 or sum(row[0] > 0 for row in valid) < 3 or sum(r[2] for r in valid) < 3:
            return None
        yields = sorted(r[0] for r in valid)
        setups = sorted(r[1] for r in valid)
        # Conservative observed floor: lower-quartile; never best-case average.
        lower_index = (len(yields)-1)//4
        return {'observations': len(valid), 'prl_per_gpu_hour_lower': yields[lower_index],
                'startup_minutes_conservative': setups[(len(setups)-1)*3//4]}

    def close(self):
        self.db.close()


def normalized_offers(snapshot):
    """Consume sanitized provider broker output; never parse hidden provider fees."""
    if not isinstance(snapshot, dict):
        fail('invalid_snapshot')
    if 'ok' in snapshot:
        if snapshot.get('ok') is not True:
            fail('provider_query_failed')
        snapshot = snapshot.get('result')
    if not isinstance(snapshot, dict):
        fail('invalid_snapshot')
    if 'prl_gpu' in snapshot:
        # The Clore broker exposes whole-server On-Demand USD and Spot MINIMUM
        # bid floors. Neither proves an executable Spot bid or desktop hardware.
        rows = snapshot.get('prl_gpu')
        spot = snapshot.get('prl_gpu_spot_floor', [])
        special = snapshot.get('prl_gpu_5090', [])
        if not all(type(a) is list and len(a) <= MAX_OFFERS for a in (rows, spot, special)):
            fail('invalid_clore_offers')
        offers, by_id = [], set()
        for row in rows + spot + special:
            if type(row) is not dict:
                continue
            oid = str(row.get('id', ''))
            if oid in by_id:
                continue
            by_id.add(oid)
            offers.append({
                'provider': 'clore', 'offer_id': oid,
                'gpu_name': row.get('gpu'), 'gpu_count': row.get('gpu_count_verified'),
                'gpu_variant_verified': row.get('gpu_variant_verified') is True,
                'on_demand_usd_hour': row.get('on_demand_usd_hour'),
                'spot_floor_usd_hour': row.get('spot_floor_usd_hour'),
                'snapshot_utc': snapshot.get('snapshot_utc')
            })
        return offers[:MAX_OFFERS]
    rows = snapshot.get('offers')
    if type(rows) is not list or len(rows) > MAX_OFFERS:
        fail('invalid_offers')
    return [dict(r, provider='vast') for r in rows if type(r) is dict]


def evaluate(snapshot, memory, *, market, now=None):
    """Only positive measured conservative estimates can become review candidates."""
    now = now or datetime.now(timezone.utc)
    if type(market) is not dict or set(market) != {'price_usd_per_prl','price_observed_at','pool_fee_fraction','exchange_fee_fraction','duration_hours','cost_buffer_fraction','extra_charges_usd','min_net_usd'}:
        fail('invalid_market_fields')
    price = number(market['price_usd_per_prl'], 'price', maximum=1000)
    price_time = utc(market['price_observed_at'])
    if not timedelta(0) <= now - price_time <= timedelta(minutes=60):
        fail('stale_market_price')
    pool_fee = number(market['pool_fee_fraction'], 'pool_fee', maximum=0.5,allow_zero=True)
    exchange_fee = number(market['exchange_fee_fraction'], 'exchange_fee', maximum=0.5,allow_zero=True)
    duration = number(market['duration_hours'], 'duration', minimum=0.25, maximum=24)
    buffer = number(market['cost_buffer_fraction'], 'buffer', maximum=1,allow_zero=True)
    extra = number(market['extra_charges_usd'], 'extra_charges', maximum=1000, allow_zero=True)
    min_net = number(market['min_net_usd'], 'min_net', maximum=1000, allow_zero=True)
    offers = normalized_offers(snapshot)
    results=[]
    seen=set()
    for offer in offers:
        provider=offer.get('provider')
        oid=str(offer.get('id',offer.get('offer_id','')))
        identifier=(provider,oid)
        verdict={'provider':provider, 'offer_id':oid, 'status':'needs_verification', 'reasons':[]}
        results.append(verdict)
        if not re.fullmatch(r'[1-9][0-9]{0,14}', oid) or identifier in seen:
            verdict['reasons'].append('invalid_or_duplicate_offer_id'); continue
        seen.add(identifier)
        if provider == 'clore':
            verdict['rental_mode_prices'] = {}
            for mode, field in (('on_demand', 'on_demand_usd_hour'),
                                ('spot_minimum_floor', 'spot_floor_usd_hour')):
                quoted = offer.get(field)
                if type(quoted) in (int, float) and math.isfinite(quoted) and 0 < quoted <= 100:
                    verdict['rental_mode_prices'][mode] = round(float(quoted), 6)
            count = offer.get('gpu_count')
            if type(count) is int and 1 <= count <= 16:
                verdict['gpu_count'] = count
            else:
                verdict['reasons'].append('gpu_count_and_quote_not_verified')
            name = offer.get('gpu_name')
            if type(name) is str and len(name) <= 100:
                verdict['gpu_name'] = name
            if offer.get('gpu_variant_verified') is not True:
                verdict['reasons'].append('gpu_variant_unverified')
            if 'spot_minimum_floor' in verdict['rental_mode_prices']:
                verdict['reasons'].append('spot_floor_not_executable_bid')
            if 'on_demand' not in verdict['rental_mode_prices']:
                verdict['reasons'].append('on_demand_price_unverified')
            verdict['reasons'].append('clore_market_bid_and_all_in_fees_unverified')
            verdict['reasons'].append('prl_yield_per_instance_unverified')
            # Never label a Spot floor or whole-server quote as a rentable profit.
            continue
        if provider!='vast':
            verdict['reasons'].append('unsupported_provider'); continue
        # Vast's search readout alone does not prove RTX desktop/laptop or full cost.
        variant=offer.get('variant')
        try:
            key=gpu_key(offer.get('gpu_name'),variant)
        except ValueError as e:
            verdict['reasons'].append(str(e));continue
        count=offer.get('num_gpus')
        if type(count) is not int or not 1 <= count <= 16:
            verdict['reasons'].append('gpu_count_unverified');continue
        try:
            hourly=number(offer.get('dph_total'), 'hourly', maximum=100)
        except ValueError:
            verdict['reasons'].append('price_unverified');continue
        reliability=offer.get('reliability2')
        if type(reliability) not in (int,float) or not math.isfinite(reliability) or not 0 <= reliability <= 1:
            verdict['reasons'].append('reliability_unverified'); continue
        if reliability < 0.90:
            verdict['status']='reject';verdict['reasons'].append('reliability_below_90_percent');continue
        summary=memory.summary(provider,key,now)
        if summary is None:
            verdict['reasons'].append('insufficient_recent_prl_measurements');continue
        setup_hours = summary['startup_minutes_conservative'] / 60
        productive_hours = max(0, duration - setup_hours)
        expected_prl = productive_hours * count * summary['prl_per_gpu_hour_lower']
        proceeds = expected_prl * price * (1-pool_fee) * (1-exchange_fee)
        spend = hourly * duration * (1+buffer) + extra
        net = proceeds-spend
        verdict.update(gpu_model=key, gpu_count=count, hourly_usd=round(hourly,6),
                measured_samples=summary['observations'], conservative_prl=round(expected_prl,6),
                projected_proceeds_usd=round(proceeds,4), projected_cost_usd=round(spend,4),
                projected_net_usd=round(net,4), startup_minutes=summary['startup_minutes_conservative'])
        # Assessment remains non-authoritative: neither quote nor all-in limit confirmed.
        if productive_hours <= 0:
            verdict['status']='reject';verdict['reasons'].append('startup_exceeds_campaign')
        elif net < min_net:
            verdict['status']='reject';verdict['reasons'].append('net_below_threshold')
        else:
            verdict['status']='candidate_for_manual_quote';verdict['reasons'].append('requires_fresh_all_in_quote_and_authorization')
    results.sort(key=lambda r:(r['status']!='candidate_for_manual_quote',-r.get('projected_net_usd',-1e9),r['offer_id']))
    return {'mode':'read_only','renting_enabled':False,'evaluated_at':now.isoformat(),
            'price_observed_at':price_time.isoformat(),'offers':results,
            'warning':'Estimates use user-supplied PRL price and measured PRL observations, not TH/s. Unknown post-stop/provider charges remain; NEVER authorize rentals from this output.'}


def evaluate_sources(snapshots, memory, *, market, now=None):
    """One deterministic read-only comparison covering Clore AND Vast."""
    if type(snapshots) is not dict or not snapshots or not set(snapshots) <= {'vast', 'clore'}:
        fail('invalid_sources')
    if 'vast' not in snapshots or 'clore' not in snapshots:
        fail('both_providers_required')
    vast = evaluate(snapshots['vast'], memory, market=market, now=now)
    clore = evaluate(snapshots['clore'], memory, market=market, now=now)
    items = vast['offers'] + clore['offers']
    # Preserve both provider labels; an indicative Spot floor never outranks an
    # offer supported by measured PRL yield, as it lacks a valid net projection.
    items.sort(key=lambda r: (r['status'] != 'candidate_for_manual_quote',
                              -r.get('projected_net_usd', -1e9), r['provider'],
                              r['offer_id']))
    return {
        'mode': 'read_only',
        'renting_enabled': False,
        'providers_checked': ['vast', 'clore'],
        'evaluated_at': vast['evaluated_at'],
        'price_observed_at': vast['price_observed_at'],
        'offers': items,
        'warning': ('Vast uses empirical yield when available; Clore Spot prices '
                    'are minimum bid floors, not winning prices. No BTC-to-USD '
                    'assumptions, no TH/s-to-PRL conversion, no rentals or grants.')
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, help='Local SQLite history; restrict OS permissions in deployment')
    parser.add_argument('--import-measurements',help='JSON list of factual observations with evidence IDs')
    parser.add_argument('--offers', help='Legacy: one sanitized provider broker JSON response')
    parser.add_argument('--offers-vast', help='Sanitized Vast read-only JSON response')
    parser.add_argument('--offers-clore', help='Sanitized Clore read-only JSON response')
    parser.add_argument('--market', help='Explicit fresh market-price and fee assumptions JSON')
    args=parser.parse_args(argv)
    memory=Memory(args.database)
    try:
        if args.import_measurements:
            observations=read_json(args.import_measurements)
            if type(observations) is not list or len(observations)>100:
                fail('invalid_measurements')
            for measurement in observations:
                memory.record(measurement)
        combined = bool(args.offers_vast or args.offers_clore)
        if args.offers and combined:
            fail('choose_single_or_both_sources')
        if combined and not (args.offers_vast and args.offers_clore):
            fail('both_providers_required')
        if bool(args.offers or combined) != bool(args.market):
            fail('offers_and_market_required_together')
        if combined:
            result = evaluate_sources({'vast':read_json(args.offers_vast),
                                       'clore':read_json(args.offers_clore)},
                                      memory,market=read_json(args.market))
        elif args.offers:
            result = evaluate(read_json(args.offers),memory,market=read_json(args.market))
        else:
            result = {'mode':'read_only','measurements_imported':True}
        print(json.dumps(result,sort_keys=True))
    finally:
        memory.close()


if __name__=='__main__':
    try:
        main()
    except (ValueError,sqlite3.Error,OSError,UnicodeError,json.JSONDecodeError) as exc:
        print(json.dumps({'ok':False,'error':str(exc) if isinstance(exc,ValueError) else 'input_or_storage_error'}))
        sys.exit(2)
