<?php
declare(strict_types=1);
/** CLI only, service identity only. Never return provider bodies, logs or credentials. */
final class OperatorRejected extends RuntimeException {}
function op_fail(string $code): never { throw new OperatorRejected($code); }
function op_http(string $url, array $headers, string $method='GET', ?array $body=null): array {
    $buffer=''; $ch=curl_init($url);
    curl_setopt_array($ch,[CURLOPT_RETURNTRANSFER=>false,CURLOPT_FOLLOWLOCATION=>false,
        CURLOPT_CONNECTTIMEOUT=>5,CURLOPT_TIMEOUT=>12,CURLOPT_SSL_VERIFYPEER=>true,
        CURLOPT_SSL_VERIFYHOST=>2,CURLOPT_PROTOCOLS=>CURLPROTO_HTTPS,
        CURLOPT_HTTPHEADER=>$headers,CURLOPT_CUSTOMREQUEST=>$method,
        CURLOPT_WRITEFUNCTION=>static function($handle,string $chunk)use(&$buffer):int {
            if(strlen($buffer)+strlen($chunk)>524288)return 0;
            $buffer.=$chunk;return strlen($chunk);
        }]);
    if($body!==null)curl_setopt($ch,CURLOPT_POSTFIELDS,json_encode($body,JSON_THROW_ON_ERROR));
    $ok=curl_exec($ch);$status=(int)curl_getinfo($ch,CURLINFO_HTTP_CODE);curl_close($ch);
    if($ok===false)op_fail($method==='GET'?'provider_unavailable':'provider_outcome_unknown');
    if($status===401)op_fail('credential_unavailable');
    if($status===403)op_fail('provider_forbidden');
    if($status===404)op_fail('resource_not_found');
    if($status===429)op_fail('provider_rate_limited');
    if($status<200||$status>=300)op_fail($method==='GET'?'provider_unavailable':'provider_outcome_unknown');
    $data=$buffer===''?[]:json_decode($buffer,true,32,JSON_THROW_ON_ERROR);
    if(!is_array($data))op_fail('provider_unavailable');
    return ['http_status'=>$status,'data'=>$data];
}
function op_pick(array $data,array $fields): array {
    $out=[];foreach($fields as $field){$v=$data[$field]??null;
        if(is_string($v))$v=substr(preg_replace('/[\x00-\x1f\x7f]/','',$v)??'',0,120);
        $out[$field]=is_scalar($v)||$v===null?$v:null;
    }return $out;
}
function op_rows(array $data,string $key): array {
    if(!isset($data[$key])||!is_array($data[$key])||!array_is_list($data[$key]))op_fail('provider_unavailable');
    foreach($data[$key] as $row)if(!is_array($row))op_fail('provider_unavailable');
    return $data[$key];
}
function op_vast_key(): string {
    $file='/etc/hache-miner/vast-stop-api-key';
    if(!is_file($file)||is_link($file)||!is_readable($file))op_fail('credential_unavailable');
    $key=trim((string)file_get_contents($file));
    if(strlen($key)<20||preg_match('/\s/',$key))op_fail('credential_unavailable');
    return $key;
}
function op_vast(string $path,string $method='GET',?array $body=null): array {
    return op_http('https://console.vast.ai'.$path,
        ['Authorization: Bearer '.op_vast_key(),'Content-Type: application/json'],$method,$body);
}
function op_vast_registered(string $id): void {
    $q=miner_db()->prepare('SELECT COUNT(*) FROM vast_instances WHERE instance_id=? AND enabled=1');
    $q->execute([$id]);if((int)$q->fetchColumn()!==1)op_fail('target_not_enabled');
}
function op_vast_status(string $id): array {
    op_vast_registered($id);
    $r=op_vast('/api/v0/instances/'.rawurlencode($id).'/?owner=me');
    $row=$r['data']['instances']??null;
    if(!is_array($row)||!isset($row['id'])||(string)$row['id']!==$id)op_fail('resource_not_found');
    $safe=op_pick($row,['id','machine_id','host_id','actual_status','intended_status','gpu_name','num_gpus','dph_total','ssh_host','ssh_port']);
    foreach(['actual_status','intended_status'] as $field)$safe[$field]=strtolower(trim((string)$safe[$field]));
    return $safe;
}
function op_target(array $operation): array {
    $q=miner_db()->prepare('SELECT organization_slug,project_slug FROM salad_targets WHERE enabled=1 AND organization_slug=? AND project_slug=? LIMIT 1');
    $q->execute([$operation['organization'],$operation['project']]);
    if(!$q->fetch())op_fail('target_not_enabled');
    $key=miner_salad_api_key_for_org($operation['organization']);
    if(!is_string($key)||strlen($key)<12)op_fail('credential_unavailable');
    $url='https://api.salad.com/api/public/organizations/'.rawurlencode($operation['organization'])
       .'/projects/'.rawurlencode($operation['project']).'/containers';
    if(isset($operation['group']))$url.='/'.rawurlencode($operation['group']);
    return [$url,['Salad-Api-Key: '.$key,'Accept: application/json','Content-Type: application/json']];
}
function op_group(array $row): array {
    return ['name'=>(string)($row['name']??''),'replicas'=>(int)($row['replicas']??0),
        'status'=>strtolower((string)($row['current_state']['status']??$row['state']??'unknown'))];
}
function op_instance(array $row): array {
    $out=op_pick($row,['instance_id','id','ready','started','state']);
    $out['state']=miner_instance_state($row);return $out;
}
function op_query(array $operation): array {
    $action=$operation['action'];
    if($action==='vast.list'){
        $r=op_vast('/api/v1/instances/?limit=25');$rows=op_rows($r['data'],'instances');
        if(count($rows)>25)op_fail('provider_unavailable');
        return ['instances'=>array_map(static fn(array $r):array=>op_pick($r,
            ['id','machine_id','host_id','actual_status','intended_status','gpu_name','num_gpus','dph_total']),$rows),
            'partial'=>!empty($r['data']['next_token']),'total_instances'=>$r['data']['total_instances']??null];
    }
    if($action==='vast.status')return op_vast_status($operation['instance_id']);
    if($action==='vast.search'){
        $q=['verified'=>['eq'=>true],'rentable'=>['eq'=>true],'rented'=>['eq'=>false],
            'gpu_name'=>['eq'=>$operation['gpu_name']],'num_gpus'=>['eq'=>$operation['gpu_count']],
            'dph_total'=>['lte'=>$operation['max_hourly_usd']],'type'=>'on-demand',
            'limit'=>10,'order'=>[['dph_total','asc']],'allocated_storage'=>5];
        $r=op_vast('/api/v0/bundles/?q='.rawurlencode(json_encode($q,JSON_THROW_ON_ERROR)));
        $rows=op_rows($r['data'],'offers');
        return ['offers'=>array_map(static fn(array $r):array=>op_pick($r,
            ['id','machine_id','host_id','gpu_name','num_gpus','gpu_ram','dph_total','reliability2']),array_slice($rows,0,10)),
            'pricing_note'=>'offer quote for 5 GiB storage; verify final rental and additional charges before creating resources'];
    }
    if($action==='salad.targets')return ['targets'=>miner_db()->query(
        'SELECT organization_slug,project_slug,enabled FROM salad_targets ORDER BY id LIMIT 100')->fetchAll()];
    if($action==='telemetry'){
        return ['vast'=>miner_db()->query('SELECT v.instance_id,v.enabled,v.gpu_count,s.total_ths,s.observed_at,s.received_at FROM vast_instances v LEFT JOIN vast_samples s ON s.id=(SELECT MAX(z.id) FROM vast_samples z WHERE z.instance_id=v.instance_id) ORDER BY v.instance_id LIMIT 100')->fetchAll(),
                'salad_sync'=>miner_db()->query("SELECT r.source_name,r.observed_at,r.status FROM sync_runs r JOIN (SELECT x.source_name,MAX(x.id) id FROM sync_runs x JOIN salad_targets t ON t.enabled=1 AND x.source_name=CONCAT('salad:',t.organization_slug,'/',t.project_slug) GROUP BY x.source_name) latest ON latest.id=r.id LIMIT 100")->fetchAll()];
    }
    [$url,$headers]=op_target($operation);
    if($action==='salad.groups'){
        $r=op_http($url,$headers);$rows=op_rows($r['data'],array_key_exists('items',$r['data'])?'items':'container_groups');
        return ['groups'=>array_map('op_group',array_slice($rows,0,100)),'partial'=>count($rows)>100];
    }
    if($action==='salad.instances'){
        $r=op_http($url.'/instances',$headers);$rows=op_rows($r['data'],'instances');
        return ['instances'=>array_map('op_instance',array_slice($rows,0,100)),'partial'=>count($rows)>100];
    }
    if($action==='salad.instance'){
        $r=op_http($url.'/instances/'.rawurlencode($operation['instance_id']),$headers);
        return op_instance($r['data']);
    }
    op_fail('unsupported_action');
}
function op_prepare(array $operation): array {
    if($operation['action']==='vast.start'){
        $row=op_vast_status($operation['instance_id']);
        if($row['actual_status']!=='exited'||$row['intended_status']!=='stopped')
            op_fail('target_not_ready');
        if(!is_numeric($row['dph_total'])||!is_finite((float)$row['dph_total'])||
           (float)$row['dph_total']<=0||(float)$row['dph_total']>(float)$operation['max_hourly_usd'])
            op_fail('price_limit_exceeded');
        if(!is_int($row['num_gpus'])||$row['num_gpus']<1||$row['num_gpus']>16||
           !is_int($row['machine_id'])||!is_int($row['host_id'])||
           !is_string($row['ssh_host'])||$row['ssh_host']===''||
           !is_int($row['ssh_port'])||$row['ssh_port']<1)
            op_fail('target_not_ready');
        // Charge estimate is NOT a provider-enforced financial cap.
        $estimate=(int)ceil((float)$row['dph_total']*$operation['max_minutes']/60*100);
        if($estimate>(int)floor($operation['max_total_usd']*100+0.00001))
            op_fail('estimated_budget_exceeded');
        return $row+['estimated_cost_cents'=>$estimate];
    }
    if($operation['action']==='vast.stop'){
        $row=op_vast_status($operation['instance_id']);
        return ['id'=>(string)$row['id'],'machine_id'=>(string)$row['machine_id'],
            'host_id'=>(string)$row['host_id'],'actual_status'=>(string)$row['actual_status'],
            'intended_status'=>(string)$row['intended_status']];
    }
    [$url,$headers]=op_target($operation);
    if($operation['action']==='salad.stop'){
        $r=op_http($url,$headers);$g=op_group($r['data']);
        if($g['name']!==$operation['group'])op_fail('target_state_changed');
        return $g;
    }
    if($operation['action']==='salad.reallocate'){
        $q=miner_db()->prepare('SELECT id FROM group_state WHERE organization=? AND project_name=? AND group_name=? LIMIT 1');
        $q->execute([$operation['organization'],$operation['project'],$operation['group']]);
        $gid=$q->fetchColumn();if(!$gid)op_fail('target_not_ready');
        try{$target=miner_reallocation_target((int)$gid,$operation['instance_id']);}
        catch(DomainException $e){op_fail('target_not_ready');}
        if(miner_reallocation_cooldown_seconds($target,$operation['instance_id'])>0)op_fail('cooldown_active');
        $r=op_http($url.'/instances/'.rawurlencode($operation['instance_id']),$headers);
        if(!miner_reallocation_live_matches($r['data'],$operation['instance_id']))op_fail('target_state_changed');
        return ['group_id'=>(int)$gid,'instance_id'=>$operation['instance_id'],'ready'=>true,'started'=>true,'state'=>'running'];
    }
    op_fail('unsupported_action');
}
function op_snapshot_equal(array $left,array $right): bool {
    // Python stores canonical JSON with sorted keys. Preserve strict types, not insertion order.
    ksort($left);ksort($right);return $left===$right;
}
function op_guard_stop(array $operation,array $snapshot): array {
    if($operation['action']!=='vast.start')op_fail('unsupported_action');
    // The independent lease supervisor verifies the deadline and uses this
    // helper only on its own durable, grant-bound leases.
    $id=$operation['instance_id'];
    if(!isset($snapshot['machine_id'],$snapshot['host_id'])||
       !is_int($snapshot['machine_id'])||!is_int($snapshot['host_id']))
        op_fail('target_state_changed');
    $r=op_vast('/api/v0/instances/'.rawurlencode($id).'/?owner=me');
    $row=$r['data']['instances']??null;
    if(!is_array($row)||(string)($row['id']??'')!==$id||
       (int)($row['machine_id']??-1)!==$snapshot['machine_id']||
       (int)($row['host_id']??-1)!==$snapshot['host_id'])
        op_fail('target_state_changed');
    $actual=strtolower((string)($row['actual_status']??''));
    $intended=strtolower((string)($row['intended_status']??''));
    if(in_array($actual,['stopped','exited'],true)&&
       in_array($intended,['stopped','exited'],true))
        return ['status'=>'already_stopped','provider_mutation_sent'=>false];
    $r=op_vast('/api/v0/instances/'.rawurlencode($id).'/','PUT',['state'=>'stopped']);
    if(($r['data']['success']??null)!==true)op_fail('provider_outcome_unknown');
    return ['status'=>'accepted','provider_mutation_sent'=>true,'verification_required'=>true];
}

function op_execute(array $operation,array $snapshot): array {
    $now=op_prepare($operation);
    if(!op_snapshot_equal($now,$snapshot))op_fail('target_state_changed');
    if($operation['action']==='vast.start'){
        // Only after the broker has durably armed a deadline in its private DB.
        $r=op_vast('/api/v0/instances/'.rawurlencode($operation['instance_id']).'/',
                   'PUT',['state'=>'running']);
        if(($r['data']['success']??null)!==true)op_fail('provider_outcome_unknown');
        return ['status'=>'accepted','provider_mutation_sent'=>true,
                'verification_required'=>true];
    }
    if($operation['action']==='vast.stop'){
        if(in_array($now['intended_status'],['stopped','exited'],true)
            &&in_array($now['actual_status'],['stopped','exited'],true))return ['status'=>'already_stopped','provider_mutation_sent'=>false];
        $r=op_vast('/api/v0/instances/'.rawurlencode($operation['instance_id']).'/','PUT',['state'=>'stopped']);
        if(($r['data']['success']??null)!==true)op_fail('provider_outcome_unknown');
        return ['status'=>'accepted','provider_mutation_sent'=>true,'verification_required'=>true];
    }
    [$url,$headers]=op_target($operation);
    if($operation['action']==='salad.stop'){
        if($now['status']==='stopped')return ['status'=>'already_stopped','provider_mutation_sent'=>false];
        $r=op_http($url.'/stop',$headers,'POST');
        return ['status'=>'accepted','http_status'=>$r['http_status'],'verification_required'=>true];
    }
    if($operation['action']==='salad.reallocate'){
        $target=miner_reallocation_target($now['group_id'],$operation['instance_id']);
        $fingerprint=miner_reallocation_fingerprint($target,$operation['instance_id']);
        $db=miner_db();$lock='hmr:'.substr($fingerprint,0,60);
        $st=$db->prepare('SELECT GET_LOCK(?,2)');$st->execute([$lock]);
        if((int)$st->fetchColumn()!==1)op_fail('cooldown_active');
        try{
            // Share the EXISTING lock, cooldown and intent audit with UI/auto-reallocation.
            op_prepare($operation);
            miner_audit(null,'manual_reallocate_intent',$fingerprint);
            $r=op_http($url.'/instances/'.rawurlencode($operation['instance_id']).'/reallocate',$headers,'POST');
            if($r['http_status']!==202)op_fail('provider_outcome_unknown');
            miner_audit(null,'manual_reallocate_accepted',$fingerprint);
            return ['status'=>'accepted','verification_required'=>true];
        }finally{$st=$db->prepare('SELECT RELEASE_LOCK(?)');$st->execute([$lock]);}
    }
    op_fail('unsupported_action');
}

if(realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    try{
        if(PHP_SAPI!=='cli'||!function_exists('posix_geteuid')||posix_geteuid()!==posix_getpwnam('hache-miner')['uid'])op_fail('service_identity_required');
        require_once '/srv/hache-miner/current/app/core.php';
        require_once '/srv/hache-miner/current/app/reallocate.php';
        $raw=stream_get_contents(STDIN,8193);if(strlen($raw)>8192)op_fail('invalid_request');
        $request=json_decode($raw,true,16,JSON_THROW_ON_ERROR);
        $mode=$request['mode']??'';$operation=$request['operation']??null;
        if(!is_array($operation)||!isset($operation['action']))op_fail('invalid_request');
        $reads=['vast.list','vast.status','vast.search','salad.targets','salad.groups','salad.instances','salad.instance','telemetry'];
        $writes=['vast.stop','vast.start','salad.stop','salad.reallocate'];
        if($mode==='query'&&in_array($operation['action'],$reads,true))$result=op_query($operation);
        elseif($mode==='prepare'&&in_array($operation['action'],$writes,true))$result=op_prepare($operation);
        elseif($mode==='execute'&&in_array($operation['action'],$writes,true)&&is_array($request['snapshot']??null))$result=op_execute($operation,$request['snapshot']);
        elseif($mode==='guard_stop'&&$operation['action']==='vast.start'&&is_array($request['snapshot']??null))$result=op_guard_stop($operation,$request['snapshot']);
        else op_fail('unsupported_action');
        echo json_encode(['ok'=>true,'result'=>$result],JSON_THROW_ON_ERROR).PHP_EOL;
    }catch(Throwable $e){
        $error=$e instanceof OperatorRejected?$e->getMessage():'provider_unavailable';
        echo json_encode(['ok'=>false,'error'=>$error],JSON_THROW_ON_ERROR).PHP_EOL;exit(1);
    }
}
