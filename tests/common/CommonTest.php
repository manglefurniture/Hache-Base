<?php

declare(strict_types=1);

require_once __DIR__ . '/../../src/common/PhoneNormalizer.php';
require_once __DIR__ . '/../../src/common/Input.php';
require_once __DIR__ . '/../../src/common/Money.php';

use HacheBase\Common\PhoneNormalizer;
use HacheBase\Common\Input;
use HacheBase\Common\Money;

assert(PhoneNormalizer::toE164('998 123 4567', '52') === '+529981234567');
assert(PhoneNormalizer::toE164('+52 998 123 4567', '52') === '+529981234567');
assert(PhoneNormalizer::toE164('+5219981234567', '52') === '+529981234567');
assert(Input::email('test@example.com') === 'test@example.com');
assert(Input::email('not-an-email') === null);
assert(Input::positiveId('42') === 42);
assert(Input::positiveId('0') === null);
assert(Money::toCents('1200.50') === 120050);
assert(Money::decimal(120050) === '1200.50');

echo "CommonTest OK\n";
