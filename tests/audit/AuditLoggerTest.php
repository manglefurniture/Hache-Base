<?php

declare(strict_types=1);

require_once __DIR__ . '/../../src/audit/AuditSanitizer.php';
require_once __DIR__ . '/../../src/audit/AuditLogger.php';

use HacheBase\Audit\AuditLogger;

$change = AuditLogger::prepareForRecord([
    'event_kind' => AuditLogger::DOMAIN_CHANGE,
    'actor_type' => 'user',
    'actor_id' => 'operator-7',
    'organization_id' => 'organization-1',
    'action' => 'resource.updated',
    'entity_type' => 'resource',
    'entity_id' => 'resource-4',
    'before' => ['status' => 'pending', 'password' => 'old-secret'],
    'after' => ['status' => 'active', 'password' => 'new-secret'],
]);
assert(is_array($change));
assert($change['before']['password'] === '[REDACTED]');
assert($change['after']['password'] === '[REDACTED]');
assert($change['metadata']['_audit']['event_kind'] === AuditLogger::DOMAIN_CHANGE);

$noOp = AuditLogger::prepareForRecord([
    'action' => 'resource.updated',
    'entity_type' => 'resource',
    'entity_id' => 'resource-4',
    'before' => ['status' => 'active', 'settings' => ['x' => 1, 'y' => 2]],
    'after' => ['settings' => ['y' => 2, 'x' => 1], 'status' => 'active'],
]);
assert($noOp === null);

$diagnostic = AuditLogger::prepareForRecord([
    'audit_scope' => 'diagnostic',
    'action' => 'diagnostic.completed',
    'entity_type' => 'diagnostic',
    'entity_id' => 'run-1',
]);
assert($diagnostic === null);

$readOnly = AuditLogger::prepareForRecord([
    'read_only' => true,
    'action' => 'resource.viewed',
    'entity_type' => 'resource',
    'entity_id' => 'resource-4',
]);
assert($readOnly === null);

$technical = AuditLogger::prepareForRecord([
    'event_kind' => AuditLogger::TECHNICAL_RESULT,
    'action' => 'request.completed',
    'entity_type' => 'request',
    'request_id' => 'request-2',
]);
assert(is_array($technical));
assert($technical['before'] === null);
assert($technical['after'] === null);
assert($technical['metadata']['_audit']['event_kind'] === AuditLogger::TECHNICAL_RESULT);

$technicalWithSnapshots = AuditLogger::prepareForRecord([
    'event_kind' => AuditLogger::TECHNICAL_RESULT,
    'action' => 'request.completed',
    'entity_type' => 'request',
    'before' => ['status' => 'pending'],
]);
assert($technicalWithSnapshots === null);

$collectionChange = AuditLogger::prepareForRecord([
    'action' => 'resource.updated',
    'entity_type' => 'resource',
    'before' => ['status' => 'pending'],
    'after' => ['status' => 'active'],
]);
assert(is_array($collectionChange));

echo "AuditLoggerTest OK\n";
