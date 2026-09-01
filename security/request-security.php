<?php

declare(strict_types=1);

namespace HacheBase\Security;

use InvalidArgumentException;

/**
 * Minimal transport-security resolver shared by headers and session cookies.
 *
 * This class deliberately resolves only whether the current request is HTTPS.
 * It does not derive the client IP, trust arbitrary forwarding chains, or replace
 * project-specific reverse-proxy configuration.
 */
final class RequestSecurity
{
    private const DEFAULT_PROXY = [
        'trusted_ips' => [],
        'forwarded_proto_header' => 'HTTP_X_FORWARDED_PROTO',
    ];

    private const PROXY_KEYS = [
        'trusted_ips',
        'forwarded_proto_header',
    ];

    /**
     * @param array<string, mixed> $server
     * @param array<string, mixed> $proxy
     */
    public static function isHttps(array $server, array $proxy = []): bool
    {
        $resolvedProxy = self::resolveProxyConfig($proxy);

        $https = strtolower(trim((string)($server['HTTPS'] ?? '')));
        if ($https !== '' && $https !== 'off' && $https !== '0') {
            return true;
        }

        if (strtolower(trim((string)($server['REQUEST_SCHEME'] ?? ''))) === 'https') {
            return true;
        }

        if ((string)($server['SERVER_PORT'] ?? '') === '443') {
            return true;
        }

        $remoteAddress = (string)($server['REMOTE_ADDR'] ?? '');
        if ($remoteAddress === '' || !in_array($remoteAddress, $resolvedProxy['trusted_ips'], true)) {
            return false;
        }

        $header = $resolvedProxy['forwarded_proto_header'];
        $forwardedProto = strtolower(trim((string)($server[$header] ?? '')));

        // Reject comma-separated/multi-hop values. The trusted proxy must overwrite or
        // normalize the header to one authoritative token before it reaches PHP.
        return $forwardedProto === 'https';
    }

    /**
     * @param array<string, mixed> $proxy
     * @return array{trusted_ips:list<string>, forwarded_proto_header:string}
     */
    public static function resolveProxyConfig(array $proxy = []): array
    {
        self::assertKnownKeys($proxy, self::PROXY_KEYS);
        $resolved = array_replace(self::DEFAULT_PROXY, $proxy);

        if (!is_array($resolved['trusted_ips']) || !array_is_list($resolved['trusted_ips'])) {
            throw new InvalidArgumentException('proxy.trusted_ips must be a list of IP addresses.');
        }

        foreach ($resolved['trusted_ips'] as $ip) {
            if (!is_string($ip) || filter_var($ip, FILTER_VALIDATE_IP) === false) {
                throw new InvalidArgumentException('proxy.trusted_ips contains an invalid IP address.');
            }
        }

        if (!is_string($resolved['forwarded_proto_header'])
            || preg_match('/^HTTP_[A-Z0-9_]+$/', $resolved['forwarded_proto_header']) !== 1) {
            throw new InvalidArgumentException('Invalid forwarded proto server key.');
        }

        /** @var array{trusted_ips:list<string>, forwarded_proto_header:string} $resolved */
        return $resolved;
    }

    /**
     * @param array<string, mixed> $config
     * @param list<string> $allowed
     */
    private static function assertKnownKeys(array $config, array $allowed): void
    {
        foreach (array_keys($config) as $key) {
            if (!is_string($key) || !in_array($key, $allowed, true)) {
                throw new InvalidArgumentException(sprintf('Unknown proxy configuration key: %s', (string)$key));
            }
        }
    }
}
