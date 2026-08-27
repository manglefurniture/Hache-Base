<?php

declare(strict_types=1);

require_once __DIR__ . '/../../integrations/email/TransactionalMailer.php';
require_once __DIR__ . '/../../integrations/email/ResendMailer.php';

use HacheBase\Integrations\Email\ResendMailer;

$thrown = false;
try {
    new ResendMailer('', 'sender@example.com');
} catch (InvalidArgumentException) {
    $thrown = true;
}
assert($thrown === true);

$thrown = false;
try {
    new ResendMailer('test-key', 'not-an-email');
} catch (InvalidArgumentException) {
    $thrown = true;
}
assert($thrown === true);

$thrown = false;
try {
    new ResendMailer('test-key', 'sender@example.com', '', 'http://api.resend.com/emails');
} catch (InvalidArgumentException) {
    $thrown = true;
}
assert($thrown === true);

$thrown = false;
try {
    new ResendMailer('test-key', 'sender@example.com', '', 'not-a-url');
} catch (InvalidArgumentException) {
    $thrown = true;
}
assert($thrown === true);

$mailer = new ResendMailer('test-key', 'sender@example.com', 'Example App');
$thrown = false;
try {
    $mailer->sendText('invalid-recipient', 'Subject', 'Body');
} catch (InvalidArgumentException) {
    $thrown = true;
}
assert($thrown === true);

echo "ResendMailerTest OK\n";
