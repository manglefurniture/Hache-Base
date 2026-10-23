<?php
declare(strict_types=1);
/** Public Clore marketplace reader. Never reads tokens and never sends mutations. */
function op_clore_marketplace_fetch(): array {
    $url='https://api.clore.ai/v1/marketplace';
    $body='';
    $ch=curl_init($url);
    if($ch===false)op_fail('provider_unavailable');
    curl_setopt_array($ch,[
        CURLOPT_RETURNTRANSFER=>false,
        CURLOPT_FOLLOWLOCATION=>false,
        CURLOPT_CONNECTTIMEOUT=>5,
        CURLOPT_TIMEOUT=>20,
        CURLOPT_SSL_VERIFYPEER=>true,
        CURLOPT_SSL_VERIFYHOST=>2,
        CURLOPT_PROTOCOLS=>CURLPROTO_HTTPS,
        CURLOPT_HTTPGET=>true,
        CURLOPT_HTTPHEADER=>['Accept: application/json'],
        CURLOPT_USERAGENT=>'curl/8.0',
        CURLOPT_WRITEFUNCTION=>static function($handle,string $chunk)use(&$body):int {
            // The full marketplace is several MB, but the broker only emits a small projection.
            if(strlen($body)+strlen($chunk)>16777216)return 0;
            $body.=$chunk;
            return strlen($chunk);
        },
    ]);
    $ok=curl_exec($ch);
    $status=(int)curl_getinfo($ch,CURLINFO_HTTP_CODE);
    curl_close($ch);
    if($status===429)op_fail('provider_rate_limited');
    if($ok===false||$status!==200)op_fail('provider_unavailable');
    try{$data=json_decode($body,true,32,JSON_THROW_ON_ERROR);}
    catch(JsonException){op_fail('provider_unavailable');}
    if(!is_array($data))op_fail('provider_unavailable');
    return $data;
}
/** The API provides USD-equivalent on-demand day prices; never equate BTC to USD. */
function op_clore_hourly_usd(array $server): ?float {
    $price=$server['price']??null;
    if(!is_array($price))return null;
    $usd=$price['usd']??null;
    $days=[];
    if(is_array($usd)){
        foreach(['on_demand_usd','on_demand_btc','on_demand_clore'] as $name){
            $v=$usd[$name]??null;
            if(is_numeric($v)&&is_finite((float)$v)&&(float)$v>0)$days[]=(float)$v;
        }
    }
    // Native USD rental prices are usable even when converted USD fields are absent.
    $native=$price['on_demand']['USD-Blockchain']??null;
    if(is_numeric($native)&&is_finite((float)$native)&&(float)$native>0)$days[]=(float)$native;
    if(!$days)return null;
    return min($days)/24;
}
/** Spot is only the host's minimum USD/day bid, NEVER the winning bid or final price. */
function op_clore_spot_floor_hourly_usd(array $server): ?float {
    $price=$server['price']??null;
    if(!is_array($price))return null;
    // Native USD-Blockchain price is the only unambiguous currency-backed price.
    $native=$price['spot']['USD-Blockchain']??null;
    if(is_numeric($native)&&is_finite((float)$native)&&(float)$native>0)
        return (float)$native/24;
    // Provider-supplied USD equivalent is usable only when present and positive.
    $equivalent=$price['usd']['spot']??null;
    if(is_numeric($equivalent)&&is_finite((float)$equivalent)&&(float)$equivalent>0)
        return (float)$equivalent/24;
    return null; // Never reinterpret BTC or CLORE tokens as dollars.
}
/** Require a matching, whole-rig GPU count in both public hardware descriptions. */
function op_clore_verified_gpu_count(array $server): ?int {
    $name=$server['specs']['gpu']??null;
    $gpuArray=$server['gpu_array']??null;
    if(!is_string($name)||!preg_match('/^([1-9][0-9]?)x\s+/i',$name,$match))
        return null;
    $count=(int)$match[1];
    if($count>16||!is_array($gpuArray)||!array_is_list($gpuArray)||
        count($gpuArray)!==$count)return null;
    return $count;
}
function op_clore_marketplace_projection(array $data): array {
    if(($data['code']??null)!==0)op_fail('provider_unavailable');
    $servers=$data['servers']??null;
    if(!is_array($servers)||!array_is_list($servers)||count($servers)>10000)op_fail('provider_unavailable');
    $xmr=[];$prl=[];$combo=[];$prlSpot=[];$prl5090=[];$eligible=0;
    foreach($servers as $server){
        if(!is_array($server)||($server['rented']??false)!==false)continue;
        $specs=$server['specs']??null;
        if(!is_array($specs)||!is_int($server['id']??null)||$server['id']<=0)continue;
        $ram=$specs['ram']??null;
        $hourly=op_clore_hourly_usd($server);
        $spotHourly=op_clore_spot_floor_hourly_usd($server);
        if(!is_numeric($ram)||(float)$ram<8||$hourly===null)continue;
        $cpu=(string)($specs['cpu']??'');
        $gpu=(string)($specs['gpu']??'');
        $isCpu=(bool)preg_match('/Ryzen|EPYC|Threadripper/i',$cpu);
        $isGpu=(bool)preg_match('/RTX (?:20|30|40|50)[0-9]{2}/i',$gpu)
            &&is_numeric($specs['gpuram']??null)&&(float)$specs['gpuram']>=8;
        if(!$isCpu&&!$isGpu)continue;
        $eligible++;
        $net=$specs['net']??[];
        $safe=[
            'id'=>$server['id'],
            'cpu'=>substr(preg_replace('/[\x00-\x1f\x7f]/','',$cpu)??'',0,110),
            'cpus'=>substr((string)($specs['cpus']??''),0,20),
            'ram_gb'=>round((float)$ram,2),
            'gpu'=>substr(preg_replace('/[\x00-\x1f\x7f]/','',$gpu)??'',0,110),
            'gpu_ram_gb'=>is_numeric($specs['gpuram']??null)?(float)$specs['gpuram']:null,
            'country'=>is_array($net)?substr((string)($net['cc']??''),0,35):'',
            'on_demand_usd_hour'=>round($hourly,5),
            'on_demand_usd_day'=>round($hourly*24,4),
            'gpu_count_verified'=>op_clore_verified_gpu_count($server),
            'gpu_variant_verified'=>false, // Laptop/desktop never inferred by absence of 'Laptop'.
            'spot_floor_usd_hour'=>$spotHourly===null?null:round($spotHourly,5),
            'spot_floor_usd_day'=>$spotHourly===null?null:round($spotHourly*24,4),
        ];
        if($isCpu)$xmr[]=$safe;
        if($isGpu){
            $prl[]=$safe;
            if($spotHourly!==null)$prlSpot[]=$safe;
            if(preg_match('/\\bRTX\\s*5090\\b/i',$gpu))$prl5090[]=$safe;
        }
        if($isCpu&&$isGpu)$combo[]=$safe;
    }
    $sort=static function(array &$offers):void {
        usort($offers,static fn(array $a,array $b):int=>
            ($a['on_demand_usd_hour']<=>$b['on_demand_usd_hour'])?:($a['id']<=>$b['id']));
        $offers=array_slice($offers,0,10);
    };
    $spotSort=static function(array &$offers):void {
        usort($offers,static fn(array $a,array $b):int=>
            ($a['spot_floor_usd_hour']<=>$b['spot_floor_usd_hour'])?:($a['id']<=>$b['id']));
        $offers=array_slice($offers,0,10);
    };
    $sort($xmr);$sort($prl);$sort($combo);
    $spotSort($prlSpot);
    $sort($prl5090);
    return [
        'source'=>'clore_public_marketplace',
        'snapshot_utc'=>gmdate('Y-m-d\TH:i:s\Z'),
        'total_servers'=>count($servers),
        'eligible_servers'=>$eligible,
        'xmr_cpu'=>$xmr,
        'prl_gpu'=>$prl,
        'prl_gpu_spot_floor'=>$prlSpot,
        'prl_gpu_5090'=>$prl5090,
        'xmr_prl_combined'=>$combo,
        'rental_authorized'=>false,
        'warning'=>'READ ONLY. On-demand prices and Spot MINIMUM floors are whole-server USD/hour, not current winning bids or executable quotes. GPU count requires matching specs and gpu_array; desktop/laptop and PRL yield unverified. Spot competition, storage, fees, taxes, post-stop costs and net profitability must be checked. No rentals or mining performed.',
    ];
}
function op_clore_marketplace(): array {
    return op_clore_marketplace_projection(op_clore_marketplace_fetch());
}
