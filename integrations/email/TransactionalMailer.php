<?php

declare(strict_types=1);

namespace HacheBase\Integrations\Email;

interface TransactionalMailer
{
    /**
     * Envía un correo de texto y devuelve el identificador asignado por el proveedor.
     */
    public function sendText(string $to, string $subject, string $text): string;
}
