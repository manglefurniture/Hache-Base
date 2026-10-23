<?php
declare(strict_types=1);
require_once __DIR__.'/provider.php';
function testClore(bool $condition,string $message):void {
    if(!$condition)throw new RuntimeException($message);
}
$base=[
    'price'=>['on_demand'=>['USD-Blockchain'=>2.4],
              'usd'=>['on_demand_btc'=>2.2,'on_demand_usd'=>2.4,'spot'=>0],
              'spot'=>['USD-Blockchain'=>0.72]],
    'rented'=>false,
    'gpu_array'=>[['name'=>'RTX 5060 Ti']],
    'specs'=>['cpu'=>'AMD Ryzen 9 9950X 16-Core Processor','cpus'=>'14/28','ram'=>16,
              'gpu'=>'1x NVIDIA GeForce RTX 5060 Ti','gpuram'=>16,
              'net'=>['cc'=>'US']],
    'init_token'=>'NEVER_EXPOSE_THIS_SECRET',
    'background_job'=>['env'=>['WALLET_KEY'=>'NEVER_EXPOSE_THIS_SECRET']]
];
$combo=$base;$combo['id']=15;
$cpu=$base;$cpu['id']=10;
$cpu['specs']['gpu']='1x NVIDIA GTX 745';
$cpu['price']['usd']=['on_demand_usd'=>1.2];
$gpu=$base;$gpu['id']=20;
$gpu['specs']['cpu']='Intel i5-6500T';
$gpu['price']['usd']=['on_demand_usd'=>1.8];
$rented=$base;$rented['id']=4;$rented['rented']=true;
$noPrice=$base;$noPrice['id']=5;$noPrice['price']=['on_demand'=>['bitcoin'=>0.01]];
$tooSmall=$base;$tooSmall['id']=6;$tooSmall['specs']['ram']=4;
$out=op_clore_marketplace_projection(['code'=>0,'servers'=>[
    $rented,$combo,$cpu,$gpu,$noPrice,$tooSmall]]);
testClore($out['total_servers']===6&&$out['eligible_servers']===3,'Eligibility filtering');
testClore(array_column($out['xmr_cpu'],'id')===[10,15],'XMR pricing order');
testClore(array_column($out['prl_gpu'],'id')===[20,15],'PRL pricing order');
testClore(array_column($out['xmr_prl_combined'],'id')===[15],'Combined classifier');
testClore($out['xmr_cpu'][0]['on_demand_usd_hour']===0.05,'Correct daily to hourly price');
testClore($out['rental_authorized']===false,'Read-only guarantee');
testClore(!str_contains(json_encode($out,JSON_THROW_ON_ERROR),'NEVER_EXPOSE_THIS_SECRET'),'No sensitive provider fields leaked');
testClore(op_clore_hourly_usd($noPrice)===null,'Do not equate BTC to USD');
testClore(abs((float)op_clore_hourly_usd(['price'=>['on_demand'=>['USD-Blockchain'=>2.4]]])-0.1)<0.0000001,'Native USD fallback');
foreach ([['code'=>5,'servers'=>[]],['code'=>0,'servers'=>'bad'],['code'=>0,'servers'=>[['id'=>'bad']]]] as $bad) {
    try {
        $badResult=op_clore_marketplace_projection($bad);
        if(is_string($bad['servers']??null)||($bad['code']??0)!==0)
            throw new LogicException('Malformed API response accepted');
        testClore($badResult['eligible_servers']===0,'Invalid server must be filtered');
    } catch(OperatorRejected $e) {
        testClore($e->getMessage()==='provider_unavailable','Unexpected error mapping');
    }
}
testClore($out['prl_gpu'][0]['gpu_count_verified']===1,'Count must match array and specs');
testClore($out['prl_gpu'][0]['gpu_variant_verified']===false,'Never infer desktop from RTX name');
testClore($out['prl_gpu'][0]['spot_floor_usd_hour']===0.03,'Spot USD day to hour');
testClore(array_column($out['prl_gpu_spot_floor'],'id')===[15,20],'Spot floor ranking with stable id tie-break');
testClore(!array_key_exists('background_job',$out['prl_gpu'][0]),'Never expose provider secrets');
testClore(op_clore_spot_floor_hourly_usd(['price'=>['spot'=>['bitcoin'=>0.00001]]])===null,
    'No BTC to USD conversion');
testClore(op_clore_spot_floor_hourly_usd(['price'=>['spot'=>['USD-Blockchain'=>0],'usd'=>['spot'=>0]]])===null,
    'Spot zero is unavailable');
testClore(abs((float)op_clore_spot_floor_hourly_usd([
   'price'=>['spot'=>['USD-Blockchain'=>2.40], 'usd'=>['spot'=>1.20]]])-0.05)<0.000001,
   'Use the cheapest trusted USD spot value across denominations');
testClore(abs((float)op_clore_spot_floor_hourly_usd([
   'price'=>['spot'=>['USD-Blockchain'=>1.20], 'usd'=>['spot'=>2.40]]])-0.05)<0.000001,
   'Native USD spot may itself be cheapest');

testClore(abs((float)op_clore_spot_floor_hourly_usd(['price'=>['usd'=>['spot'=>1.20]]])-0.05)<0.000001,
    'Provider USD equivalent permitted');
$multi=$base;$multi['id']=500;$multi['specs']['gpu']='2x NVIDIA GeForce RTX 5090';
$multi['gpu_array']=[['index'=>0],['index'=>1]];
$multi['price']['spot']['USD-Blockchain']=2.4;
$mismatch=$multi;$mismatch['id']=501;$mismatch['gpu_array']=[['index'=>0]];
$laptop=$multi;$laptop['id']=502;$laptop['specs']['gpu']='1x NVIDIA GeForce RTX 5090 Laptop GPU';
$laptop['gpu_array']=[['index'=>0]];
$multiProjection=op_clore_marketplace_projection(['code'=>0,'servers'=>[$multi,$mismatch,$laptop]]);
testClore($multiProjection['prl_gpu_5090'][0]['id']===500,'Dedicated 5090 slice');
testClore($multiProjection['prl_gpu_5090'][0]['gpu_count_verified']===2,'Multi GPU match');
testClore($multiProjection['prl_gpu_5090'][1]['gpu_count_verified']===null,
    'Mismatched GPU inventory must not pass');
testClore(!in_array(502,array_column($multiProjection['prl_gpu_5090'],'id'),true),
    'RTX 5090 Laptop cannot masquerade as desktop shortlist');
testClore($multiProjection['prl_gpu_spot_floor'][0]['spot_floor_usd_hour']===0.1,
    'Spot quote remains preliminary floor');
echo "CLORE_MARKETPLACE_READONLY_TESTS_OK\n";
