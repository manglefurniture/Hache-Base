<?php

declare(strict_types=1);

$root = dirname(__DIR__, 2);
$router = file_get_contents($root . '/tests/form-b/fixture-router.php');
$doc = file_get_contents($root . '/docs/production-readiness/FORM-B-FIXTURE.md');
$test = file_get_contents($root . '/tests/form-b/ProductionReadinessFormBTest.sh');

assert(is_string($router));
assert(is_string($doc));
assert(is_string($test));

$require = static function (string $haystack, string $fragment): void {
    assert(str_contains($haystack, $fragment), 'missing P1-07 fragment: ' . $fragment);
};

foreach ([
    'Csrf::validate',
    "'data-form-state=\"'",
    "'loading'",
    "'success'",
    "'error'",
    'company_website',
    'Retry-After:',
    'X-Hache-Fixture-Deduplicated: true',
    '_p1_07_seen_submission_ids',
    'filter_var($email, FILTER_VALIDATE_EMAIL)',
] as $fragment) {
    $require($router, $fragment);
}

foreach (['FORM-001', 'FORM-002', 'FORM-003', 'FORM-004', 'FORM-005', 'FORM-006', 'FORM-007'] as $control) {
    $require($doc, $control);
}

$require($doc, 'no convierte FORM-001…FORM-007');
$require($doc, 'dedupe del fixture vive en sesión');
$require($doc, 'CAPTCHA no es un requisito de Hache Base');
$require($test, 'csrf_missing_status');
$require($test, 'validation_status');
$require($test, 'honeypot_status');
$require($test, 'duplicate_status');
$require($test, 'rate_blocked_status');

assert(!preg_match('/https?:\/\/[^\s\"\']*(?:recaptcha|hcaptcha|turnstile)/i', $router));

print "FORM_B_FIXTURE_CONTRACT_OK\n";
