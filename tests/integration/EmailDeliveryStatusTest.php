<?php

declare(strict_types=1);

require_once __DIR__ . '/../../integrations/email/EmailDeliveryStatus.php';

use HacheBase\Integrations\Email\EmailDeliveryStatus;

$statuses = [
    EmailDeliveryStatus::REQUESTED,
    EmailDeliveryStatus::ACCEPTED,
    EmailDeliveryStatus::DELAYED,
    EmailDeliveryStatus::DELIVERED,
    EmailDeliveryStatus::BOUNCED,
    EmailDeliveryStatus::FAILED,
    EmailDeliveryStatus::SUPPRESSED,
];
foreach ($statuses as $status) {
    EmailDeliveryStatus::assertValid($status);
}
assert(EmailDeliveryStatus::isTerminal(EmailDeliveryStatus::DELIVERED) === true);
assert(EmailDeliveryStatus::isTerminal(EmailDeliveryStatus::BOUNCED) === true);
assert(EmailDeliveryStatus::isTerminal(EmailDeliveryStatus::FAILED) === true);
assert(EmailDeliveryStatus::isTerminal(EmailDeliveryStatus::SUPPRESSED) === true);
assert(EmailDeliveryStatus::isTerminal(EmailDeliveryStatus::DELAYED) === false);

$thrown = false;
try {
    EmailDeliveryStatus::assertValid('opened');
} catch (InvalidArgumentException) {
    $thrown = true;
}
assert($thrown === true);

$accepted = EmailDeliveryStatus::apply(
    EmailDeliveryStatus::REQUESTED,
    '2026-09-04T11:59:00.000000Z',
    EmailDeliveryStatus::ACCEPTED,
    '2026-09-04T12:00:00.000000Z',
);
assert($accepted['status'] === EmailDeliveryStatus::ACCEPTED);
assert($accepted['applied'] === true);

$delayed = EmailDeliveryStatus::apply(
    EmailDeliveryStatus::ACCEPTED,
    '2026-09-04T12:00:00.000000Z',
    EmailDeliveryStatus::DELAYED,
    '2026-09-04T12:01:00.000000Z',
);
assert($delayed['status'] === EmailDeliveryStatus::DELAYED);
assert($delayed['applied'] === true);

$newer = EmailDeliveryStatus::apply(
    EmailDeliveryStatus::DELAYED,
    '2026-09-04T12:01:00.000000Z',
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

$regression = EmailDeliveryStatus::apply(
    EmailDeliveryStatus::DELAYED,
    '2026-09-04T12:01:00.000000Z',
    EmailDeliveryStatus::ACCEPTED,
    '2026-09-04T12:03:00.000000Z',
);
assert($regression['status'] === EmailDeliveryStatus::DELAYED);
assert($regression['applied'] === false);
assert($regression['reason'] === 'state_regression');

$duplicate = EmailDeliveryStatus::apply(
    EmailDeliveryStatus::BOUNCED,
    '2026-09-04T12:03:00.123456Z',
    EmailDeliveryStatus::BOUNCED,
    '2026-09-04T12:04:00.123456Z',
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
assert($terminalLater['status'] === EmailDeliveryStatus::DELIVERED);
assert($terminalLater['applied'] === false);
assert($terminalLater['reason'] === 'terminal_conflict');

$suppressed = EmailDeliveryStatus::apply(
    EmailDeliveryStatus::REQUESTED,
    '2026-09-04T12:00:00.000000Z',
    EmailDeliveryStatus::SUPPRESSED,
    '2026-09-04T12:00:01.000000Z',
);
assert($suppressed['status'] === EmailDeliveryStatus::SUPPRESSED);
assert($suppressed['applied'] === true);
assert(EmailDeliveryStatus::isTerminal($suppressed['status']) === true);

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
