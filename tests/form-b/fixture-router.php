<?php

declare(strict_types=1);

use HacheBase\Security\Auth;
use HacheBase\Security\Csrf;

require_once dirname(__DIR__, 2) . '/security/auth.php';
require_once dirname(__DIR__, 2) . '/security/csrf.php';

$path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
if (!is_string($path)) {
    $path = '/';
}

if ($path === '/health') {
    header('Content-Type: text/plain; charset=utf-8');
    header('Cache-Control: no-store');
    echo "ok\n";
    return true;
}

if ($path !== '/form-b') {
    http_response_code(404);
    header('Content-Type: text/plain; charset=utf-8');
    header('Cache-Control: no-store');
    echo "Not Found\n";
    return true;
}

Auth::startSecureSession();
header('Cache-Control: no-store');
header('Pragma: no-cache');

$escape = static fn (string $value): string => htmlspecialchars(
    $value,
    ENT_QUOTES | ENT_SUBSTITUTE,
    'UTF-8',
);

$length = static fn (string $value): int => function_exists('mb_strlen')
    ? mb_strlen($value, 'UTF-8')
    : strlen($value);

$readField = static function (array $source, string $key): string {
    $value = $source[$key] ?? '';

    return is_string($value) ? $value : '';
};

$newSubmissionId = static fn (): string => bin2hex(random_bytes(16));

/**
 * This session-local limiter is intentionally fixture-only. It demonstrates the
 * observable 429/Retry-After contract without pretending that an anonymous,
 * cookie-scoped bucket is a production-grade shared limiter.
 */
$consumeRateLimit = static function (int $maxAttempts = 6, int $windowSeconds = 60): ?int {
    $key = '_p1_07_public_form_rate';
    $now = time();
    $bucket = $_SESSION[$key] ?? null;

    if (!is_array($bucket) || (int)($bucket['reset_at'] ?? 0) <= $now) {
        $bucket = [
            'count' => 0,
            'reset_at' => $now + $windowSeconds,
        ];
    }

    $bucket['count'] = (int)($bucket['count'] ?? 0) + 1;
    $_SESSION[$key] = $bucket;

    if ($bucket['count'] <= $maxAttempts) {
        return null;
    }

    return max(1, (int)$bucket['reset_at'] - $now);
};

$render = static function (
    string $state,
    array $values,
    array $errors,
    int $status,
    string $message,
    string $submissionId,
) use ($escape): void {
    http_response_code($status);
    header('Content-Type: text/html; charset=utf-8');
    header('X-Hache-Fixture-Accepted-Count: ' . (int)($_SESSION['_p1_07_accepted_count'] ?? 0));

    $csrf = Csrf::token();
    $name = $escape((string)($values['name'] ?? ''));
    $email = $escape((string)($values['email'] ?? ''));
    $body = $escape((string)($values['message'] ?? ''));
    $csrfEscaped = $escape($csrf);
    $submissionEscaped = $escape($submissionId);
    $stateEscaped = $escape($state);
    $messageEscaped = $escape($message);

    $errorSummary = '';
    if ($errors !== []) {
        $items = '';
        foreach ($errors as $field => $error) {
            $items .= '<li><a href="#' . $escape((string)$field) . '">' . $escape((string)$error) . '</a></li>';
        }
        $errorSummary = '<div id="form-errors" role="alert" tabindex="-1"><h2>Revisa el formulario</h2><ul>' . $items . '</ul></div>';
    }

    $nameError = isset($errors['name'])
        ? '<p id="name-error" class="field-error">' . $escape((string)$errors['name']) . '</p>'
        : '';
    $emailError = isset($errors['email'])
        ? '<p id="email-error" class="field-error">' . $escape((string)$errors['email']) . '</p>'
        : '';
    $messageError = isset($errors['message'])
        ? '<p id="message-error" class="field-error">' . $escape((string)$errors['message']) . '</p>'
        : '';
    $submissionError = isset($errors['submission_id'])
        ? '<p id="submission-error" class="field-error">' . $escape((string)$errors['submission_id']) . '</p>'
        : '';

    $nameAria = isset($errors['name']) ? ' aria-invalid="true" aria-describedby="name-error"' : '';
    $emailAria = isset($errors['email']) ? ' aria-invalid="true" aria-describedby="email-error"' : '';
    $messageAria = isset($errors['message']) ? ' aria-invalid="true" aria-describedby="message-error"' : '';

    echo '<!doctype html>';
    echo '<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">';
    echo '<title>Fixture formulario B</title></head><body>';
    echo '<main><h1>Contacto — fixture nivel B</h1>';
    echo '<p>Ejemplo aislado de P1-07. Los datos solo se usan para demostrar el flujo de prueba y no se persisten como contenido de negocio.</p>';
    echo $errorSummary;
    echo '<p id="form-status" role="status" aria-live="polite">' . $messageEscaped . '</p>';
    echo '<form id="contact-form" method="post" action="/form-b" data-form-state="' . $stateEscaped . '">';
    echo '<input type="hidden" name="_csrf" value="' . $csrfEscaped . '">';
    echo '<input type="hidden" name="submission_id" value="' . $submissionEscaped . '">';
    echo $submissionError;

    echo '<div><label for="name">Nombre</label>';
    echo '<input id="name" name="name" type="text" required minlength="2" maxlength="80" autocomplete="name" value="' . $name . '"' . $nameAria . '>';
    echo $nameError . '</div>';

    echo '<div><label for="email">Correo</label>';
    echo '<input id="email" name="email" type="email" required maxlength="254" autocomplete="email" inputmode="email" value="' . $email . '"' . $emailAria . '>';
    echo $emailError . '</div>';

    echo '<div><label for="message">Mensaje</label>';
    echo '<textarea id="message" name="message" required minlength="10" maxlength="1000"' . $messageAria . '>' . $body . '</textarea>';
    echo $messageError . '</div>';

    echo '<div aria-hidden="true" style="position:absolute;left:-10000px;width:1px;height:1px;overflow:hidden">';
    echo '<label for="company_website">Sitio web de empresa</label>';
    echo '<input id="company_website" name="company_website" type="text" tabindex="-1" autocomplete="off" value="">';
    echo '</div>';

    echo '<p>Finalidad: responder esta solicitud. No incluyas contraseñas, datos de pago ni secretos.</p>';
    echo '<button id="submit-button" type="submit">Enviar</button>';
    echo '</form></main>';
    echo '<script>';
    echo 'const f=document.getElementById("contact-form"),b=document.getElementById("submit-button"),s=document.getElementById("form-status"),e=document.getElementById("form-errors");';
    echo 'if(e){e.focus();}';
    echo 'if(f&&b&&s){let sending=false;f.addEventListener("submit",function(ev){if(sending){ev.preventDefault();return;}sending=true;f.dataset.formState="loading";b.disabled=true;b.setAttribute("aria-disabled","true");s.textContent="Enviando…";});}';
    echo '</script></body></html>';
};

$method = strtoupper((string)($_SERVER['REQUEST_METHOD'] ?? 'GET'));

if ($method === 'GET') {
    $render(
        'idle',
        ['name' => '', 'email' => '', 'message' => ''],
        [],
        200,
        'Completa el formulario.',
        $newSubmissionId(),
    );
    return true;
}

if ($method !== 'POST') {
    header('Allow: GET, POST');
    $render(
        'error',
        ['name' => '', 'email' => '', 'message' => ''],
        [],
        405,
        'Método no permitido.',
        $newSubmissionId(),
    );
    return true;
}

$name = trim($readField($_POST, 'name'));
$email = trim($readField($_POST, 'email'));
$messageBody = trim($readField($_POST, 'message'));
$submissionId = strtolower(trim($readField($_POST, 'submission_id')));
$honeypot = trim($readField($_POST, 'company_website'));
$values = [
    'name' => $name,
    'email' => $email,
    'message' => $messageBody,
];

if (!Csrf::validate($readField($_POST, '_csrf'))) {
    $render(
        'error',
        $values,
        [],
        419,
        'La sesión del formulario expiró. Recarga e inténtalo de nuevo.',
        preg_match('/^[a-f0-9]{32}$/', $submissionId) === 1 ? $submissionId : $newSubmissionId(),
    );
    return true;
}

$retryAfter = $consumeRateLimit();
if ($retryAfter !== null) {
    header('Retry-After: ' . $retryAfter);
    $render(
        'error',
        $values,
        [],
        429,
        'Demasiados intentos. Espera antes de volver a enviar.',
        preg_match('/^[a-f0-9]{32}$/', $submissionId) === 1 ? $submissionId : $newSubmissionId(),
    );
    return true;
}

// Honeypot intentionally returns the same generic success shape without a business effect.
if ($honeypot !== '') {
    $render(
        'success',
        ['name' => '', 'email' => '', 'message' => ''],
        [],
        200,
        'Solicitud recibida.',
        $newSubmissionId(),
    );
    return true;
}

$errors = [];
if ($length($name) < 2 || $length($name) > 80) {
    $errors['name'] = 'Escribe un nombre de 2 a 80 caracteres.';
}
if ($length($email) > 254 || filter_var($email, FILTER_VALIDATE_EMAIL) === false) {
    $errors['email'] = 'Escribe un correo válido.';
}
if ($length($messageBody) < 10 || $length($messageBody) > 1000) {
    $errors['message'] = 'Escribe un mensaje de 10 a 1000 caracteres.';
}
if (preg_match('/^[a-f0-9]{32}$/', $submissionId) !== 1) {
    $errors['submission_id'] = 'El identificador de envío no es válido. Inténtalo de nuevo.';
    $submissionId = $newSubmissionId();
}

if ($errors !== []) {
    $render(
        'error',
        $values,
        $errors,
        422,
        'Hay campos que necesitan corrección.',
        $submissionId,
    );
    return true;
}

$seen = $_SESSION['_p1_07_seen_submission_ids'] ?? [];
if (!is_array($seen)) {
    $seen = [];
}

if (isset($seen[$submissionId])) {
    header('X-Hache-Fixture-Deduplicated: true');
    $render(
        'success',
        ['name' => '', 'email' => '', 'message' => ''],
        [],
        200,
        'Solicitud recibida.',
        $newSubmissionId(),
    );
    return true;
}

$seen[$submissionId] = true;
$_SESSION['_p1_07_seen_submission_ids'] = $seen;
$_SESSION['_p1_07_accepted_count'] = (int)($_SESSION['_p1_07_accepted_count'] ?? 0) + 1;

$render(
    'success',
    ['name' => '', 'email' => '', 'message' => ''],
    [],
    201,
    'Solicitud recibida.',
    $newSubmissionId(),
);

return true;
