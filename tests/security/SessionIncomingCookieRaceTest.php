<?php

declare(strict_types=1);

use HacheBase\Security\Auth;

require_once __DIR__ . '/../../security/auth.php';

final class VanishingSessionHandler implements SessionHandlerInterface, SessionUpdateTimestampHandlerInterface
{
    /** @var array<string, string> */
    public array $data = [];
    public bool $deleteOnClose = false;

    public function open(string $path, string $name): bool
    {
        return true;
    }

    public function close(): bool
    {
        if ($this->deleteOnClose) {
            $this->data = [];
            $this->deleteOnClose = false;
        }

        return true;
    }

    public function read(string $id): string|false
    {
        return $this->data[$id] ?? '';
    }

    public function write(string $id, string $data): bool
    {
        $this->data[$id] = $data;
        return true;
    }

    public function destroy(string $id): bool
    {
        unset($this->data[$id]);
        return true;
    }

    public function gc(int $max_lifetime): int|false
    {
        return 0;
    }

    public function validateId(string $id): bool
    {
        return array_key_exists($id, $this->data);
    }

    public function updateTimestamp(string $id, string $data): bool
    {
        if (!array_key_exists($id, $this->data)) {
            return false;
        }

        $this->data[$id] = $data;
        return true;
    }
}

$handler = new VanishingSessionHandler();
assert(session_set_save_handler($handler, true));
session_name('HACHEBASERACE');

$server = [
    'HTTPS' => 'off',
    'SERVER_PORT' => '80',
    'REMOTE_ADDR' => '127.0.0.1',
];
$config = [
    'idle_timeout' => 60,
    'absolute_timeout' => 180,
    'cookie_path' => '/admin',
];

// Seed a normal Hache anonymous session with persisted SEC-007 metadata and cookie tuple.
Auth::startSecureSession($config, $server, 7000);
$incomingId = session_id();
assert($incomingId !== '');
assert(session_write_close());
session_id('');
assert(array_key_exists($incomingId, $handler->data));

// Emulate a new browser request. The first provenance read succeeds, but a concurrent
// logout/GC removes the backing session exactly when that read releases its lock.
$_COOKIE[session_name()] = $incomingId;
$handler->deleteOnClose = true;

$rejected = false;
try {
    Auth::login(
        ['id' => 99, 'role' => 'user'],
        ['idle_timeout' => 60, 'absolute_timeout' => 180, 'cookie_path' => '/'],
        $server,
        7001,
    );
} catch (LogicException $exception) {
    $rejected = str_contains($exception->getMessage(), 'changed during SEC-007 provenance validation');
}

assert($rejected === true);
assert(session_status() === PHP_SESSION_NONE);
assert(session_id() === '');
assert($handler->data === []);
assert((bool)ini_get('session.use_cookies') === true);
assert(!isset($_SESSION['user']));

unset($_COOKIE[session_name()]);

echo "SESSION_INCOMING_COOKIE_RACE_OK\n";
