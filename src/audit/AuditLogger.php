<?php

declare(strict_types=1);

namespace HacheBase\Audit;

use PDO;
use Throwable;

final class AuditLogger
{
    public const DOMAIN_CHANGE = 'domain_change';
    public const TECHNICAL_RESULT = 'technical_result';

    public function __construct(private PDO $db)
    {
    }

    /**
     * Records a relevant mutation. Audit failure is returned to the caller so
     * each project can decide whether its operation must fail closed.
     */
    public function record(array $event): bool
    {
        $event = self::prepareForRecord($event);
        if ($event === null) {
            return false;
        }

        $sql = <<<'SQL'
INSERT INTO audit_events (
    actor_type, actor_id, actor_role, organization_id, site_id,
    action, entity_type, entity_id, source, request_id, ip_address,
    before_data, after_data, metadata
) VALUES (
    :actor_type, :actor_id, :actor_role, :organization_id, :site_id,
    :action, :entity_type, :entity_id, :source, :request_id, :ip_address,
    :before_data, :after_data, :metadata
)
SQL;

        try {
            $stmt = $this->db->prepare($sql);
            return $stmt->execute([
                ':actor_type' => $event['actor_type'],
                ':actor_id' => $event['actor_id'] ?? null,
                ':actor_role' => $event['actor_role'] ?? null,
                ':organization_id' => $event['organization_id'] ?? null,
                ':site_id' => $event['site_id'] ?? null,
                ':action' => $event['action'],
                ':entity_type' => $event['entity_type'],
                ':entity_id' => $event['entity_id'] ?? null,
                ':source' => $event['source'] ?? null,
                ':request_id' => $event['request_id'] ?? null,
                ':ip_address' => $event['ip_address'] ?? null,
                ':before_data' => $this->jsonOrNull($event['before']),
                ':after_data' => $this->jsonOrNull($event['after']),
                ':metadata' => $this->jsonOrNull($event['metadata']),
            ]);
        } catch (Throwable) {
            return false;
        }
    }

    /**
     * Rejects events that do not belong in the administrative audit trail and
     * normalizes snapshots before persistence. Projects should call this after
     * confirming the domain mutation, not after merely accepting an HTTP call.
     *
     * `domain_change` is the backwards-compatible default. A technical result
     * is allowed as a separate, snapshot-free event so a 2xx cannot be read as
     * proof that the domain changed.
     *
     * @param array<string, mixed> $event
     * @return array<string, mixed>|null null means that no audit event may be recorded
     */
    public static function prepareForRecord(array $event): ?array
    {
        $scope = trim((string) ($event['audit_scope'] ?? 'administrative'));
        if (
            $scope !== 'administrative'
            || ($event['read_only'] ?? false) === true
            || ($event['diagnostic'] ?? false) === true
            || ($event['telemetry'] ?? false) === true
        ) {
            return null;
        }

        $kind = trim((string) ($event['event_kind'] ?? self::DOMAIN_CHANGE));
        if (!in_array($kind, [self::DOMAIN_CHANGE, self::TECHNICAL_RESULT], true)) {
            return null;
        }

        $action = trim((string) ($event['action'] ?? ''));
        $entityType = trim((string) ($event['entity_type'] ?? ''));
        if ($action === '' || $entityType === '') {
            return null;
        }

        $before = $event['before'] ?? null;
        $after = $event['after'] ?? null;

        if ($kind === self::TECHNICAL_RESULT && ($before !== null || $after !== null)) {
            return null;
        }

        if ($kind === self::DOMAIN_CHANGE) {
            if (($before !== null && !is_array($before)) || ($after !== null && !is_array($after))) {
                return null;
            }

            if (is_array($before) && is_array($after) && self::snapshotsEquivalent($before, $after)) {
                return null;
            }
        }

        $metadata = $event['metadata'] ?? [];
        if (!is_array($metadata)) {
            $metadata = ['value' => $metadata];
        }
        $metadata['_audit'] = [
            'event_kind' => $kind,
            'audit_scope' => $scope,
        ];

        return [
            'actor_type' => $event['actor_type'] ?? 'user',
            'actor_id' => $event['actor_id'] ?? null,
            'actor_role' => $event['actor_role'] ?? null,
            'organization_id' => $event['organization_id'] ?? null,
            'site_id' => $event['site_id'] ?? null,
            'action' => $action,
            'entity_type' => $entityType,
            'entity_id' => $event['entity_id'] ?? null,
            'source' => $event['source'] ?? null,
            'request_id' => $event['request_id'] ?? null,
            'ip_address' => $event['ip_address'] ?? null,
            'before' => is_array($before) ? AuditSanitizer::sanitize($before) : null,
            'after' => is_array($after) ? AuditSanitizer::sanitize($after) : null,
            'metadata' => AuditSanitizer::sanitize($metadata),
        ];
    }

    private function jsonOrNull(mixed $value): ?string
    {
        if ($value === null) {
            return null;
        }

        $json = json_encode($value, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        return $json === false ? null : $json;
    }

    /** @param array<string|int, mixed> $before @param array<string|int, mixed> $after */
    private static function snapshotsEquivalent(array $before, array $after): bool
    {
        return self::canonicalize($before) === self::canonicalize($after);
    }

    private static function canonicalize(mixed $value): mixed
    {
        if (!is_array($value)) {
            return $value;
        }

        if (self::isList($value)) {
            return array_map(static fn (mixed $item): mixed => self::canonicalize($item), $value);
        }

        ksort($value, SORT_STRING);
        foreach ($value as $key => $item) {
            $value[$key] = self::canonicalize($item);
        }

        return $value;
    }

    /** @param array<string|int, mixed> $value */
    private static function isList(array $value): bool
    {
        $expected = 0;
        foreach (array_keys($value) as $key) {
            if ($key !== $expected) {
                return false;
            }
            $expected++;
        }

        return true;
    }
}
