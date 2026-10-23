<?php
declare(strict_types=1);
/**
 * Unprivileged GPU label normalizer shared by Vast and Clore offer projections.
 *
 * The name is only a provider-advertised claim. "unverified" is the default:
 * absence of "Laptop" is not positive desktop evidence. Hardware attestation
 * is a separate requirement before any profit/rental decision.
 */
function op_gpu_variant_hint(mixed $model): array {
    $name=is_string($model)?substr($model,0,120):'';
    $laptop=(bool)preg_match('/\b(?:laptop|mobile|notebook|max[\s-]?q)\b/i',$name);
    // An exact letter M immediately after RTX/GTX/RX model number (4090M)
    // is a mobile hint; don't confuse RTX 5090 D / 4090 Ti or vendor suffixes.
    $laptop=$laptop||(bool)preg_match('/\b(?:RTX|GTX|RX)\s*[0-9]{3,4}M\b/i',$name);
    $desktop=(bool)preg_match('/\bdesktop(?:[\s-]+(?:gpu|graphics|edition|class))?\b/i',$name);
    if($laptop&&$desktop)return ['gpu_variant'=>'unverified',
        'gpu_variant_evidence'=>'conflicting_provider_labels',
        'gpu_variant_verified'=>false];
    if($laptop)return ['gpu_variant'=>'laptop','gpu_variant_evidence'=>'provider_label',
        'gpu_variant_verified'=>false];
    if($desktop)return ['gpu_variant'=>'desktop','gpu_variant_evidence'=>'provider_label',
        'gpu_variant_verified'=>false];
    return ['gpu_variant'=>'unverified','gpu_variant_evidence'=>'missing_provider_label',
        'gpu_variant_verified'=>false];
}

/** Group all named GPU models, keeping laptop/desktop in distinct buckets. */
function op_gpu_family_key(mixed $name): ?string {
    if(!is_string($name)||trim($name)==='')return null;
    $text=trim(substr(preg_replace('/[\x00-\x1f\x7f]/','',$name)??'',0,120));
    $text=preg_replace('/^\s*[1-9][0-9]{0,2}x\s+/i','',$text)??$text;
    $text=preg_replace('/\b(?:NVIDIA|GEFORCE|LAPTOP|NOTEBOOK|MOBILE|DESKTOP|GPU|MAX[\s-]?Q)\b/i','',$text)??$text;
    $text=strtoupper(trim(preg_replace('/\s+/',' ',$text)??''));
    if(strlen($text)>85)$text=substr($text,0,85);
    return $text===''?null:$text;
}
