<?php
declare(strict_types=1);
require __DIR__.'/provider.php';

$scenario=op_profit_scenarios(['id'=>123,'dph_total'=>0.10],2.0);
if($scenario['estimated_daily_cost_usd']!==2.4||
   $scenario['scenarios'][0]['daily_net_usd']!==0.148||
   $scenario['break_even_prl_usd']!==1.2245)
    throw new RuntimeException('Profit scenario arithmetic');
$zero=op_profit_scenarios(['dph_total'=>0.1],0);
if($zero['break_even_prl_usd']!==null||$zero['scenarios'][0]['daily_net_usd']!==-2.4)
    throw new RuntimeException('Unknown yield must not imply profitability');
foreach([-1,INF,NAN] as $invalid){
    try{op_profit_scenarios(['dph_total'=>0.1],$invalid);throw new LogicException('Accepted invalid yield');}
    catch(OperatorRejected $e){if($e->getMessage()!=='invalid_profit_inputs')throw $e;}
}

$input=['id'=>123,'actual_status'=>'running','onstart'=>'PRIVATE_COMMAND',
        'jupyter_token'=>'PRIVATE_TOKEN','extra_env'=>['API_KEY'=>'PRIVATE_KEY']];
$safe=op_pick($input,['id','actual_status']);
if($safe!==['id'=>123,'actual_status'=>'running']||str_contains(json_encode($safe),'PRIVATE'))throw new RuntimeException('Unsafe projection');
if(op_group(['name'=>'fixture','replicas'=>2,'current_state'=>['status'=>'Running']])!==
   ['name'=>'fixture','replicas'=>2,'status'=>'running'])throw new RuntimeException('State mapping');
if(!op_snapshot_equal(['id'=>'123','state'=>'stopped'],['state'=>'stopped','id'=>'123']))throw new RuntimeException('Canonical JSON key order');
if(op_snapshot_equal(['id'=>'123'],['id'=>123]))throw new RuntimeException('Strict target type');
if(op_rows(['instances'=>[]],'instances')!==[])throw new RuntimeException('Valid empty inventory');
foreach([[],['success'=>false],['instances'=>'bad'],['instances'=>['bad']]] as $bad){
    try{op_rows($bad,'instances');throw new LogicException('Invalid provider payload reported as empty success');}
    catch(OperatorRejected $e){if($e->getMessage()!=='provider_unavailable')throw $e;}
}

// Guarded Vast starts are evaluated on fixed metadata, not by a live provider call.
$quoteRow=['id'=>56667162,'machine_id'=>151300,'host_id'=>467312,
    'actual_status'=>'exited','intended_status'=>'stopped',
    'num_gpus'=>8,'dph_total'=>4.29,'ssh_host'=>'ssh8.vast.ai','ssh_port'=>10566];
$limits=['action'=>'vast.start','instance_id'=>'56667162',
    'max_hourly_usd'=>5.0,'max_total_usd'=>2.0,'max_minutes'=>20];
$quote=op_start_quote($quoteRow,$limits);
if($quote['estimated_cost_cents']!==143)
    throw new RuntimeException('Unexpected conservative quote');
foreach([
    ['row'=>array_replace($quoteRow,['actual_status'=>'running']), 'op'=>$limits],
    ['row'=>array_replace($quoteRow,['dph_total'=>6.0]), 'op'=>$limits],
    ['row'=>array_replace($quoteRow,['num_gpus'=>0]), 'op'=>$limits],
    ['row'=>$quoteRow, 'op'=>array_replace($limits,['max_total_usd'=>1.0])]
] as $bad){
    try{
        op_start_quote($bad['row'],$bad['op']);
        throw new LogicException('Unsafe start quote accepted');
    }catch(OperatorRejected $e){ /* expected */ }
}
$safe=op_pick($quoteRow,['id','ssh_host','ssh_port']);
if(count($safe)!==3||isset($safe['api_key']))
    throw new RuntimeException('Unexpected data in SSH projection');
echo "PROVIDER_PROJECTION_TESTS_OK\n";


foreach ([['id'=>1,'dph_total'=>0.1],['id'=>2,'dph_total'=>0.2]] as $candidate) {
    $e=op_profit_scenarios($candidate,2.0);
    if(count($e['scenarios'])!==4)throw new RuntimeException('Scenario coverage');
}

$identity=['machine_id'=>456,'host_id'=>789,'gpu_name'=>'RTX 4070 Ti SUPER',
           'gpu_count'=>1,'max_hourly_usd'=>0.21];
$instance=['id'=>999,'machine_id'=>456,'host_id'=>789,'gpu_name'=>'RTX 4070 Ti SUPER',
           'num_gpus'=>1,'dph_total'=>0.20,'actual_status'=>'running','intended_status'=>'running'];
if(op_rental_candidate([$instance],$identity)['id']!==999)
    throw new RuntimeException('Valid rental identity not found');
foreach([
    [[], 'rental_not_confirmed'],
    [[$instance,$instance], 'ambiguous_rental_identity'],
    [[array_replace($instance,['dph_total'=>0.22])], 'matching_instance_price_or_identity_invalid'],
    [[array_replace($instance,['host_id'=>790])], 'rental_not_confirmed'],
    [[array_replace($instance,['id'=>null])], 'matching_instance_price_or_identity_invalid']
] as [$inventory,$expected]){
    try{
        op_rental_candidate($inventory,$identity);
        throw new LogicException('Unsafe rental identity accepted: '.$expected);
    }catch(OperatorRejected $e){
        if($e->getMessage()!==$expected)throw $e;
    }
}
