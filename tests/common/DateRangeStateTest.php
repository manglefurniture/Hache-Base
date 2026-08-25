<?php

declare(strict_types=1);

require_once __DIR__ . '/../../src/common/DateRangeState.php';

use HacheBase\Common\DateRangeState;

$tz = 'America/Cancun';

assert(DateRangeState::classify('2026-08-26', '2026-09-13', new \DateTimeImmutable('2026-08-25 12:00:00-05:00'), $tz) === DateRangeState::FUTURE);
assert(DateRangeState::classify('2026-08-25', '2026-09-12', new \DateTimeImmutable('2026-08-25 12:00:00-05:00'), $tz) === DateRangeState::ACTIVE);
assert(DateRangeState::classify('2026-08-01', '2026-08-25', new \DateTimeImmutable('2026-08-25 23:59:59-05:00'), $tz) === DateRangeState::ACTIVE);
assert(DateRangeState::classify('2026-08-01', '2026-08-24', new \DateTimeImmutable('2026-08-25 00:00:00-05:00'), $tz) === DateRangeState::ENDED);

$utcInstant = new \DateTimeImmutable('2026-08-26 02:30:00+00:00');
assert(DateRangeState::operationalToday($tz, $utcInstant)->format('Y-m-d') === '2026-08-25');
assert(DateRangeState::classify('2026-08-25', '2026-08-25', $utcInstant, $tz) === DateRangeState::ACTIVE);

putenv('APP_TIMEZONE=America/Cancun');
assert(DateRangeState::operationalToday(null, $utcInstant)->format('Y-m-d') === '2026-08-25');
putenv('APP_TIMEZONE');

$invalidRange = false;
try {
    DateRangeState::classify('2026-08-26', '2026-08-25', null, $tz);
} catch (\InvalidArgumentException) {
    $invalidRange = true;
}
assert($invalidRange === true);

$invalidDate = false;
try {
    DateRangeState::classify('2026-02-30', '2026-03-01', null, $tz);
} catch (\InvalidArgumentException) {
    $invalidDate = true;
}
assert($invalidDate === true);

$invalidTimezone = false;
try {
    DateRangeState::operationalToday('Not/A_Timezone');
} catch (\InvalidArgumentException) {
    $invalidTimezone = true;
}
assert($invalidTimezone === true);

echo "DateRangeStateTest OK\n";
