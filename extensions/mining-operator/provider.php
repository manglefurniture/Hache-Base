<?php
declare(strict_types=1);
/** CLI only, service identity only. Never return provider bodies, logs or credentials. */
final class OperatorRejected extends RuntimeException {}
require_once __DIR__.'/clore_market.php';
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
    return op_vast_inspect($id);
}
function op_vast_inspect(string $id): array {
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
function op_vast_complete_inventory(callable $fetchPage): array {
    $rows=[];$ids=[];$tokens=[];$cursor=null;$total=null;$pages=0;
    do {
        if(++$pages>40)op_fail('inventory_incomplete');
        $page=$fetchPage($cursor);
        if(!is_array($page)||($page['success']??null)!==true||
           !is_int($page['total_instances']??null)||$page['total_instances']<0)
            op_fail('inventory_incomplete');
        if($total===null)$total=$page['total_instances'];
        elseif($total!==$page['total_instances'])op_fail('inventory_incomplete');
        $items=op_rows($page,'instances');
        if(count($items)>25||count($rows)+count($items)>1000)op_fail('inventory_incomplete');
        foreach($items as $row){
            if(!isset($row['id'])||!is_int($row['id'])||$row['id']<=0||isset($ids[$row['id']]))
                op_fail('inventory_incomplete');
            $ids[$row['id']]=true;
            $rows[]=op_pick($row,['id','machine_id','host_id','actual_status','intended_status',
                'gpu_name','num_gpus','dph_total']);
        }
        $next=$page['next_token']??null;
        if($next!==null&&(!is_string($next)||$next===''||isset($tokens[$next])))
            op_fail('inventory_incomplete');
        if($next!==null)$tokens[$next]=true;
        $cursor=$next;
    } while($cursor!==null);
    if($total!==count($rows))op_fail('inventory_incomplete');
    return ['instances'=>$rows,'total_instances'=>$total,'complete'=>true,'pages'=>$pages];
}

function op_vast_list_result(array $inventory, int $displayLimit=1000): array {
    $rows=$inventory['instances']??null;
    $total=$inventory['total_instances']??null;
    if(!is_array($rows)||!is_int($total)||$total!==count($rows)||
       $displayLimit<1||$displayLimit>1000)op_fail('inventory_incomplete');
    $shown=[];
    foreach(array_slice($rows,0,$displayLimit) as $row){
        $shown[]=$row;
        $candidate=['instances'=>$shown,'partial'=>count($shown)<$total,
            'complete'=>count($shown)===$total,'inventory_complete'=>true,
            'total_instances'=>$total,'pages'=>$inventory['pages']??null];
        if(strlen(json_encode($candidate,JSON_THROW_ON_ERROR))>110000){
            array_pop($shown);
            break;
        }
    }
    $complete=count($shown)===$total;
    return ['instances'=>$shown,'partial'=>!$complete,'complete'=>$complete,
            'inventory_complete'=>true,'total_instances'=>$total,
            'pages'=>$inventory['pages']??null];
}

function op_vast_inventory(): array {
    return op_vast_complete_inventory(static function(?string $cursor):array {
        $columns=['id','machine_id','host_id','actual_status','intended_status',
                  'gpu_name','num_gpus','dph_total'];
        $path='/api/v1/instances/?limit=25&select_cols='.rawurlencode(json_encode($columns,JSON_THROW_ON_ERROR));
        if($cursor!==null){
            // Vast documents a 1.0 request threshold for this endpoint; pace
            // keyset pages so a large account inventory does not hit 429.
            usleep(1100000);
            $path.='&after_token='.rawurlencode($cursor);
        }
        return op_vast($path)['data'];
    });
}

function op_rental_candidate(array $rows,array $operation): array {
    $baseline=$operation['baseline_instance_ids']??null;
    if(!is_array($baseline)||count($baseline)>1000)op_fail('missing_rental_baseline');
    $existing=[];
    foreach($baseline as $id){
        if((!is_int($id)&&!is_string($id))||!ctype_digit((string)$id)||
           (int)$id<=0)op_fail('invalid_rental_baseline');
        $existing[(string)$id]=true;
    }

    $matches=[];
    foreach($rows as $row){
        if(!is_array($row))op_fail('provider_unavailable');
        if((string)($row['machine_id']??'')!==(string)$operation['machine_id']||
           (string)($row['host_id']??'')!==(string)$operation['host_id']||
           (string)($row['gpu_name']??'')!==$operation['gpu_name']||
           (int)($row['num_gpus']??0)!==$operation['gpu_count'])continue;
        if(isset($row['id']) && isset($existing[(string)$row['id']]))continue;
        if(!isset($row['id']))op_fail('matching_instance_price_or_identity_invalid');
        $matches[]=op_pick($row,['id','machine_id','host_id','gpu_name','num_gpus',
                                  'dph_total','actual_status','intended_status']);
    }
    if(count($matches)!==1)op_fail(count($matches)===0?'rental_not_confirmed':'ambiguous_rental_identity');
    return $matches[0];
}
function op_query(array $operation): array {
    $action=$operation['action'];
    if($action==='clore.marketplace')return op_clore_marketplace();
    if($action==='vast.rent.reconcile'){
        $inventory=op_vast_inventory();
        $rows=$inventory['instances'];
        $candidate=op_rental_candidate($rows,$operation);
        return ['candidate'=>$candidate,'inventory_complete'=>true,
                'total_instances'=>$inventory['total_instances'],'provider_confirmed'=>true,
                'lease_bound'=>false,'rent_executed'=>false,
                'warning'=>'Candidate only; independent pre-rental inventory comparison and armed lease binding required'];
    }
    if($action==='vast.list'){
        return op_vast_list_result(op_vast_inventory());
    }
    if($action==='vast.status')return op_vast_status($operation['instance_id']);
    if($action==='vast.inspect')return op_vast_inspect($operation['instance_id']);
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
    if($action==='vast.rent.quote'){
        $q=['verified'=>['eq'=>true],'rentable'=>['eq'=>true],'rented'=>['eq'=>false],
            'gpu_name'=>['eq'=>$operation['gpu_name']],
            'num_gpus'=>['eq'=>$operation['gpu_count']],
            'dph_total'=>['lte'=>$operation['max_hourly_usd']],
            'type'=>'on-demand','limit'=>10,'order'=>[['dph_total','asc']],'allocated_storage'=>5];
        $r=op_vast('/api/v0/bundles/?q='.rawurlencode(json_encode($q,JSON_THROW_ON_ERROR)));
        $rows=op_rows($r['data'],'offers');
        foreach($rows as $row){
            if((string)($row['id']??'')!==(string)$operation['offer_id'])continue;
            foreach(['machine_id','host_id'] as $key){
                if((string)($row[$key]??'')!==(string)$operation[$key])op_fail('target_state_changed');
            }
            if((string)($row['gpu_name']??'')!==$operation['gpu_name']||
               (int)($row['num_gpus']??0)!==$operation['gpu_count']||
               !is_numeric($row['dph_total']??null)||
               (float)$row['dph_total']<=0||
               (float)$row['dph_total']>(float)$operation['max_hourly_usd'])op_fail('price_limit_exceeded');
            $hourly=(float)$row['dph_total'];
            $durationHours=(float)$operation['max_minutes']/60;
            if($hourly*$durationHours>(float)$operation['max_total_usd'])op_fail('estimated_budget_exceeded');
            return ['offer'=>op_pick($row,['id','machine_id','host_id','gpu_name','num_gpus','gpu_ram','dph_total','reliability2']),
                'estimated_duration_usd'=>round($hourly*$durationHours,4),
                'max_total_usd'=>(float)$operation['max_total_usd'],
                'max_minutes'=>$operation['max_minutes'],
                'rent_authorized'=>false,'rental_enabled'=>false,
                'warning'=>'Read-only offer revalidation, not a rental. 5 GiB storage quote may omit charges; financial supervisor and explicit owner approval required.'];
        }
        op_fail('resource_not_found');
    }
    if($action==='vast.analyze'){
        $q=['verified'=>['eq'=>true],'rentable'=>['eq'=>true],'rented'=>['eq'=>false],
            'gpu_name'=>['eq'=>$operation['gpu_name']],'num_gpus'=>['eq'=>$operation['gpu_count']],
            'dph_total'=>['lte'=>$operation['max_hourly_usd']],'type'=>'on-demand',
            'limit'=>10,'order'=>[['dph_total','asc']],'allocated_storage'=>5];
        $r=op_vast('/api/v0/bundles/?q='.rawurlencode(json_encode($q,JSON_THROW_ON_ERROR)));
        $rows=op_rows($r['data'],'offers');
        $analyzed=[];
        foreach(array_slice($rows,0,10) as $row){
            $safe=op_pick($row,['id','machine_id','host_id','gpu_name','num_gpus','gpu_ram','dph_total','reliability2']);
            if(!is_numeric($safe['dph_total'])||(float)$safe['dph_total']<=0)continue;
            $economics=op_profit_scenarios($safe,(float)$operation['assumed_prl_per_day']);
            $analyzed[]=['offer'=>$safe,'economics'=>$economics];
        }
        usort($analyzed,static fn(array $a,array $b):int=>
            ($b['economics']['scenarios'][2]['daily_net_usd']<=>$a['economics']['scenarios'][2]['daily_net_usd']));
        return ['offers'=>$analyzed,'assumption'=>'User-supplied PRL/day for comparable GPU; not measured for these offers',
            'ranking'=>'estimated daily net at PRL sale price 1.90 USD; ties are not a reliability ranking',
            'pricing_note'=>'Quoted with 5 GiB storage; confirm all charges before rental',
            'rental_authorized'=>false];
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

// Decision support only: never extrapolate PRL production from TH/s without measured yield.
function op_profit_scenarios(array $offer, float $prl_per_day, array $sale_prices=[1.30,1.60,1.90,2.00], float $pool_fee=0.02): array {
    $hourly=$offer['dph_total']??null;
    if(!is_numeric($hourly)||!is_finite((float)$hourly)||(float)$hourly<=0||
       !is_finite($prl_per_day)||$prl_per_day<0||
       !is_finite($pool_fee)||$pool_fee<0||$pool_fee>=1)op_fail('invalid_profit_inputs');
    $dailyCost=round((float)$hourly*24,4);
    $cases=[];
    foreach($sale_prices as $price){
        if(!is_numeric($price)||!is_finite((float)$price)||(float)$price<=0)op_fail('invalid_profit_inputs');
        $revenue=round($prl_per_day*(1-$pool_fee)*(float)$price,4);
        $cases[]=['prl_sale_usd'=>(float)$price,'daily_revenue_usd'=>$revenue,
                  'daily_cost_usd'=>$dailyCost,'daily_net_usd'=>round($revenue-$dailyCost,4)];
    }
    return ['offer_id'=>$offer['id']??null,'hourly_usd'=>(float)$hourly,
        'estimated_daily_cost_usd'=>$dailyCost,'assumed_prl_per_day'=>$prl_per_day,
        'assumed_pool_fee'=>$pool_fee,'break_even_prl_usd'=>$prl_per_day>0?
            round($dailyCost/($prl_per_day*(1-$pool_fee)),4):null,
        'scenarios'=>$cases,
        'warning'=>'Scenario only: PRL/day must come from dated measurements on comparable hardware; quote may omit storage and other charges. No rental authorized.'];
}

function op_start_quote(array $row,array $operation): array {
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

function op_prepare(array $operation): array {
    if($operation['action']==='vast.register'){
        $live=op_vast_inspect($operation['instance_id']);
        require_once '/srv/hache-miner/current/app/vast-enrollment.php';
        try{miner_vast_enrollment_from_provider($live);}
        catch(DomainException){op_fail('target_not_ready');}
        return $live;
    }
    if($operation['action']==='vast.start'){
        $row=op_vast_status($operation['instance_id']);
        return op_start_quote($row,$operation);
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
    try{$r=op_vast('/api/v0/instances/'.rawurlencode($id).'/?owner=me');}
    catch(OperatorRejected $e){
        if($e->getMessage()==='resource_not_found'&&($operation['rental_cleanup']??false)===true)
            return ['status'=>'destroyed','provider_mutation_sent'=>false,
                    'provider_absence_confirmed'=>true];
        throw $e;
    }
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
    if($operation['action']==='vast.register'){
        require_once '/srv/hache-miner/current/app/vast-enrollment.php';
        try{
            $exact=miner_vast_enrollment_from_provider($now);
            return miner_vast_enrollment_write(miner_db(),$exact);
        }catch(DomainException){op_fail('target_state_changed');}
    }
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
        $raw=stream_get_contents(STDIN,32769);if(strlen($raw)>32768)op_fail('invalid_request');
        $request=json_decode($raw,true,16,JSON_THROW_ON_ERROR);
        $mode=$request['mode']??'';$operation=$request['operation']??null;
        if(!is_array($operation)||!isset($operation['action']))op_fail('invalid_request');
        $reads=['vast.list','vast.status','vast.inspect','vast.search','vast.analyze','vast.rent.quote','vast.rent.reconcile','salad.targets','salad.groups','salad.instances','salad.instance','telemetry','clore.marketplace'];
        $writes=['vast.stop','vast.start','vast.register','salad.stop','salad.reallocate'];
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