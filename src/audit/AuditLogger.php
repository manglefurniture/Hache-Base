<?php

declare(strict_types=1);

namespace HacheBase\Audit;

use PDO;
use Throwable;

final class AuditLogger
{
    public function __construct(private PDO $db)
    {
    }

    /**
     * Records a relevant mutation. Audit failure is returned to the caller so
     * each project can decide whether its operation must fail closed.
     */
    public function record(array $event): bool
    {
        $action = trim((string) ($event['action'] ?? ''));
        $entityType = trim((string) ($event['entity_type'] ?? ''));

        if ($action === '' || $entityType === '') {
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
                ':actor_type' => $event['actor_type'] ?? 'user',
                ':actor_id' => $event['actor_id'] ?? null,
                ':actor_role' => $event['actor_role'] ?? null,
                ':organization_id' => $event['organization_id'] ?? null,
                ':site_id' => $event['site_id'] ?? null,
                ':action' => $action,
                ':entity_type' => $entityType,
                ':entity_id' => $event['entity_id'] ?? null,
                ':source' => $event['source'] ?? null,
                ':request_id' => $event['request_id'] ?? null,
                ':ip_address' => $event['ip_address'] ?? null,
                ':before_data' => $this->jsonOrNull($event['before'] ?? null),
                ':after_data' => $this->jsonOrNull($event['after'] ?? null),
                ':metadata' => $this->jsonOrNull($event['metadata'] ?? null),
            ]);
        } catch (Throwable) {
            return false;
        }
    }

    private function jsonOrNull(mixed $value): ?string
    {
        if ($value === null) {
            return null;
        }

        $json = json_encode($value, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        return $json === false ? null : $json;
    }
}
