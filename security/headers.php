<?php

declare(strict_types=1);

namespace HacheBase\Security;

use InvalidArgumentException;

final class Headers
{
    private const DEFAULT_HSTS_MAX_AGE = 31536000;

    private const DEFAULT_CONFIG = [
        'hsts' => [
            'enabled' => true,
            'max_age' => self::DEFAULT_HSTS_MAX_AGE,
            'include_subdomains' => false,
            'preload' => false,
        ],
        'csp' => [
            'mode' => 'off',
            'directives' => [],
        ],
        'proxy' => [
            'trusted_ips' => [],
            'forwarded_proto_header' => 'HTTP_X_FORWARDED_PROTO',
        ],
        'referrer_policy' => 'strict-origin-when-cross-origin',
        'permissions_policy' => 'geolocation=(), microphone=(), camera=()',
        'x_frame_options' => 'SAMEORIGIN',
    ];

    private const TOP_LEVEL_KEYS = [
        'hsts',
        'csp',
        'proxy',
        'referrer_policy',
        'permissions_policy',
        'x_frame_options',
    ];

    private const HSTS_KEYS = [
        'enabled',
        'max_age',
        'include_subdomains',
        'preload',
    ];

    private const CSP_KEYS = [
        'mode',
        'directives',
    ];

    private const PROXY_KEYS = [
        'trusted_ips',
        'forwarded_proto_header',
    ];

    /**
     * Apply the reusable baseline headers.
     *
     * Existing consumers can continue calling Headers::apply() with no arguments.
     * Project-specific CSP/HSTS/proxy behavior is opt-in through $config.
     */
    public static function apply(array $config = [], ?array $server = null): void
    {
        foreach (self::build($config, $server) as $name => $value) {
            header($name . ': ' . $value, true);
        }
    }

    /**
     * Build headers without emitting them so projects and CI can verify the exact contract.
     *
     * @return array<string, string>
     */
    public static function build(array $config = [], ?array $server = null): array
    {
        self::assertKnownKeys($config, self::TOP_LEVEL_KEYS, 'headers');
        self::assertNestedConfig($config);

        $resolved = array_replace_recursive(self::DEFAULT_CONFIG, $config);
        self::validateResolvedConfig($resolved);

        $headers = [
            'X-Content-Type-Options' => 'nosniff',
            'X-Frame-Options' => $resolved['x_frame_options'],
            'Referrer-Policy' => $resolved['referrer_policy'],
            'Permissions-Policy' => $resolved['permissions_policy'],
        ];

        $csp = $resolved['csp'];
        if ($csp['mode'] !== 'off') {
            $policy = self::buildCspPolicy($csp['directives']);
            $headerName = $csp['mode'] === 'report-only'
                ? 'Content-Security-Policy-Report-Only'
                : 'Content-Security-Policy';
            $headers[$headerName] = $policy;
        }

        $server ??= $_SERVER;
        if ($resolved['hsts']['enabled'] && self::isHttps($server, $resolved['proxy'])) {
            $headers['Strict-Transport-Security'] = self::buildHstsValue($resolved['hsts']);
        }

        return $headers;
    }

    /**
     * @param array<string, string|list<string>|null> $directives
     */
    public static function buildCspPolicy(array $directives): string
    {
        if ($directives === []) {
            throw new InvalidArgumentException('CSP directives cannot be empty when CSP is enabled.');
        }

        $parts = [];
        foreach ($directives as $directive => $sources) {
            if (!is_string($directive) || preg_match('/^[a-z][a-z0-9-]*$/', $directive) !== 1) {
                throw new InvalidArgumentException('Invalid CSP directive name.');
            }

            if ($sources === null) {
                $parts[] = $directive;
                continue;
            }

            if (is_string($sources)) {
                $sources = [$sources];
            }

            if (!is_array($sources)) {
                throw new InvalidArgumentException(sprintf('Invalid CSP sources for %s.', $directive));
            }

            $tokens = [];
            foreach ($sources as $source) {
                if (!is_string($source)) {
                    throw new InvalidArgumentException(sprintf('Invalid CSP source for %s.', $directive));
                }

                $source = trim($source);
                if ($source === '' || preg_match('/[;\r\n\x00]/', $source) === 1) {
                    throw new InvalidArgumentException(sprintf('Unsafe CSP source for %s.', $directive));
                }

                $tokens[] = $source;
            }

            $parts[] = $directive . ($tokens === [] ? '' : ' ' . implode(' ', $tokens));
        }

        return implode('; ', $parts);
    }

    /**
     * @param array<string, mixed> $server
     * @param array{trusted_ips:list<string>, forwarded_proto_header:string} $proxy
     */
    private static function isHttps(array $server, array $proxy): bool
    {
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
        if ($remoteAddress === '' || !in_array($remoteAddress, $proxy['trusted_ips'], true)) {
            return false;
        }

        $header = $proxy['forwarded_proto_header'];
        $forwardedProto = (string)($server[$header] ?? '');
        if ($forwardedProto === '') {
            return false;
        }

        $firstHop = strtolower(trim(explode(',', $forwardedProto, 2)[0]));
        return $firstHop === 'https';
    }

    /**
     * @param array{enabled:bool, max_age:int, include_subdomains:bool, preload:bool} $hsts
     */
    private static function buildHstsValue(array $hsts): string
    {
        $value = 'max-age=' . $hsts['max_age'];

        if ($hsts['include_subdomains']) {
            $value .= '; includeSubDomains';
        }

        if ($hsts['preload']) {
            $value .= '; preload';
        }

        return $value;
    }

    /**
     * @param array<string, mixed> $config
     */
    private static function assertNestedConfig(array $config): void
    {
        foreach ([
            'hsts' => self::HSTS_KEYS,
            'csp' => self::CSP_KEYS,
            'proxy' => self::PROXY_KEYS,
        ] as $key => $allowedKeys) {
            if (!array_key_exists($key, $config)) {
                continue;
            }

            if (!is_array($config[$key])) {
                throw new InvalidArgumentException(sprintf('%s configuration must be an array.', $key));
            }

            self::assertKnownKeys($config[$key], $allowedKeys, $key);
        }
    }

    /**
     * @param array<string, mixed> $resolved
     */
    private static function validateResolvedConfig(array $resolved): void
    {
        $hsts = $resolved['hsts'];
        if (!is_bool($hsts['enabled'])
            || !is_int($hsts['max_age'])
            || $hsts['max_age'] < 0
            || !is_bool($hsts['include_subdomains'])
            || !is_bool($hsts['preload'])) {
            throw new InvalidArgumentException('Invalid HSTS configuration.');
        }

        if ($hsts['preload'] && !$hsts['enabled']) {
            throw new InvalidArgumentException('HSTS preload requires HSTS to be enabled.');
        }

        if ($hsts['preload'] && !$hsts['include_subdomains']) {
            throw new InvalidArgumentException('HSTS preload requires includeSubDomains.');
        }

        if ($hsts['preload'] && $hsts['max_age'] < self::DEFAULT_HSTS_MAX_AGE) {
            throw new InvalidArgumentException('HSTS preload requires max-age of at least one year.');
        }

        $csp = $resolved['csp'];
        if (!is_string($csp['mode']) || !in_array($csp['mode'], ['off', 'report-only', 'enforce'], true)) {
            throw new InvalidArgumentException('CSP mode must be off, report-only, or enforce.');
        }

        if (!is_array($csp['directives'])) {
            throw new InvalidArgumentException('CSP directives must be an array.');
        }

        $proxy = $resolved['proxy'];
        if (!is_array($proxy['trusted_ips']) || !array_is_list($proxy['trusted_ips'])) {
            throw new InvalidArgumentException('proxy.trusted_ips must be a list of IP addresses.');
        }

        foreach ($proxy['trusted_ips'] as $ip) {
            if (!is_string($ip) || filter_var($ip, FILTER_VALIDATE_IP) === false) {
                throw new InvalidArgumentException('proxy.trusted_ips contains an invalid IP address.');
            }
        }

        if (!is_string($proxy['forwarded_proto_header'])
            || preg_match('/^HTTP_[A-Z0-9_]+$/', $proxy['forwarded_proto_header']) !== 1) {
            throw new InvalidArgumentException('Invalid forwarded proto server key.');
        }

        self::assertSafeHeaderValue($resolved['referrer_policy'], 'Referrer-Policy');
        self::assertSafeHeaderValue($resolved['permissions_policy'], 'Permissions-Policy');

        if (!is_string($resolved['x_frame_options'])
            || !in_array(strtoupper($resolved['x_frame_options']), ['DENY', 'SAMEORIGIN'], true)) {
            throw new InvalidArgumentException('X-Frame-Options must be DENY or SAMEORIGIN.');
        }

        $resolved['x_frame_options'] = strtoupper($resolved['x_frame_options']);

        if ($csp['mode'] !== 'off') {
            self::buildCspPolicy($csp['directives']);
        }
    }

    private static function assertSafeHeaderValue(mixed $value, string $name): void
    {
        if (!is_string($value) || trim($value) === '' || preg_match('/[\r\n\x00]/', $value) === 1) {
            throw new InvalidArgumentException(sprintf('Invalid %s value.', $name));
        }
    }

    /**
     * @param array<string, mixed> $config
     * @param list<string> $allowed
     */
    private static function assertKnownKeys(array $config, array $allowed, string $scope): void
    {
        foreach (array_keys($config) as $key) {
            if (!is_string($key) || !in_array($key, $allowed, true)) {
                throw new InvalidArgumentException(sprintf('Unknown %s configuration key: %s', $scope, (string)$key));
            }
        }
    }
}
