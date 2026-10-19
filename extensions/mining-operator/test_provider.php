<?php
declare(strict_types=1);
require __DIR__.'/provider.php';
$input=['id'=>123,'actual_status'=>'running','onstart'=>'PRIVATE_COMMAND',
        'jupyter_token'=>'PRIVATE_TOKEN','extra_env'=>['API_KEY'=>'PRIVATE_KEY']];
$safe=op_pick($input,['id','actual_status']);
if($safe!==['id'=>123,'actual_status'=>'running']||str_contains(json_encode($safe),'PRIVATE'))throw new RuntimeException('Unsafe projection');
if(op_group(['name'=>'fixture','replicas'=>2,'current_state'=>['status'=>'Running']])!==
   ['name'=>'fixture','replicas'=>2,'status'=>'running'])throw new RuntimeException('State mapping');
echo "PROVIDER_PROJECTION_TESTS_OK\n";
