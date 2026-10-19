<?php
declare(strict_types=1);
require __DIR__.'/provider.php';
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
echo "PROVIDER_PROJECTION_TESTS_OK\n";
