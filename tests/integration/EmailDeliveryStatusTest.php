<?php

declare(strict_types=1);

require_once __DIR__ . '/../../integrations/email/EmailDeliveryStatus.php';

use HacheBase\Integrations\Email\EmailDeliveryStatus;

$statuses = [
    EmailDeliveryStatus::ACCEPTED,
    EmailDeliveryStatus::DELIVERED,
    EmailDeliveryStatus::DELAYED,
    EmailDeliveryStatus::BOUNCED,
    EmailDeliveryStatus::FAILED,
];
foreach ($statuses as $status) {
    EmailDeliveryStatus::assertValid($status);
}

$thrown = false;
try {
    EmailDeliveryStatus::assertValid('opened');
} catch (InvalidArgumentException) {
    $thrown = true;
}
assert($thrown === true);

$newer = EmailDeliveryStatus::apply(
    EmailDeliveryStatus::ACCEPTED,
    '2026-09-04T12:00:00.000000Z',
    EmailDeliveryStatus::DELIVERED,
    '2026-09-04T12:02:00.000000Z',
);
assert($newer['status'] === EmailDeliveryStatus::DELIVERED);
assert($newer['applied'] === true);
assert($newer['reason'] === 'newer_event');

$stale = EmailDeliveryStatus::apply(
    EmailDeliveryStatus::DELIVERED,
    '2026-09-04T12:02:00.000000Z',
    EmailDeliveryStatus::DELAYED,
    '2026-09-04T12:01:00.000000Z',
);
assert($stale['status'] === EmailDeliveryStatus::DELIVERED);
assert($stale['applied'] === false);
assert($stale['reason'] === 'stale_event');

$duplicate = EmailDeliveryStatus::apply(
    EmailDeliveryStatus::BOUNCED,
    '2026-09-04T12:03:00.123456Z',
    EmailDeliveryStatus::BOUNCED,
    '2026-09-04T12:03:00.123456Z',
);
assert($duplicate['applied'] === false);
assert($duplicate['reason'] === 'duplicate_state');

$conflict = EmailDeliveryStatus::apply(
    EmailDeliveryStatus::DELIVERED,
    '2026-09-04T12:04:00.000000Z',
    EmailDeliveryStatus::BOUNCED,
    '2026-09-04T12:04:00.000000Z',
);
assert($conflict['status'] === EmailDeliveryStatus::DELIVERED);
assert($conflict['applied'] === false);
assert($conflict['reason'] === 'same_timestamp_conflict');

$terminalLater = EmailDeliveryStatus::apply(
    EmailDeliveryStatus::DELIVERED,
    '2026-09-04T12:04:00.000000Z',
    EmailDeliveryStatus::BOUNCED,
    '2026-09-04T12:05:00.000000Z',
);
assert($terminalLater['status'] === EmailDeliveryStatus::BOUNCED);
assert($terminalLater['applied'] === true);

$thrown = false;
try {
    EmailDeliveryStatus::apply(
        EmailDeliveryStatus::ACCEPTED,
        'not-a-date',
        EmailDeliveryStatus::DELIVERED,
        '2026-09-04T12:02:00Z',
    );
} catch (InvalidArgumentException) {
    $thrown = true;
}
assert($thrown === true);

echo "EmailDeliveryStatusTest OK\n";
