<?php

declare(strict_types=1);

namespace HacheBase\Security;

final class Authorization
{
    public static function hasPermission(array $user, string $permission): bool
    {
        $permissions = $user['permissions'] ?? [];
        return is_array($permissions) && in_array($permission, $permissions, true);
    }

    public static function requirePermission(array $user, string $permission): void
    {
        if (!self::hasPermission($user, $permission)) {
            http_response_code(403);
            exit('Forbidden');
        }
    }

    public static function canAccessSite(array $user, int|string $siteId): bool
    {
        if (!empty($user['is_global_admin'])) {
            return true;
        }

        $siteIds = $user['site_ids'] ?? [];
        if (!is_array($siteIds)) {
            return false;
        }

        return in_array((string)$siteId, array_map('strval', $siteIds), true);
    }

    public static function requireSite(array $user, int|string $siteId): void
    {
        if (!self::canAccessSite($user, $siteId)) {
            http_response_code(403);
            exit('Forbidden');
        }
    }
}
