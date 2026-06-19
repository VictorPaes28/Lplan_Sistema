"""Backends de e-mail para desenvolvimento."""
from __future__ import annotations

import re
import sys

from django.core.mail.backends.console import EmailBackend as DjangoConsoleEmailBackend

_PORTAL_LINK_RE = re.compile(r'(https?://[^\s]+/rh/portal/[^\s/]+/)', re.IGNORECASE)
_PORTAL_PIN_RE = re.compile(r'Código de acesso ao portal:\s*(\d{6})', re.IGNORECASE)


class ReadableConsoleEmailBackend(DjangoConsoleEmailBackend):
    """
    Imprime e-mails no terminal de forma legível (texto plano + resumo).
    Evita despejar HTML e imagens inline em base64 no console.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('stream', sys.stdout)
        super().__init__(*args, **kwargs)

    def write_message(self, message):
        stream = self.stream
        body = (message.body or '').strip()
        destino = ', '.join(message.to or [])
        separador = '=' * 72

        stream.write('\n')
        stream.write(f'{separador}\n')
        stream.write(' E-MAIL (desenvolvimento)\n')
        stream.write(f'{separador}\n')
        stream.write(f'Para:    {destino}\n')
        stream.write(f'De:      {message.from_email}\n')
        stream.write(f'Assunto: {message.subject}\n')
        stream.write(f'{"-" * 72}\n')
        if body:
            stream.write(f'{body}\n')

        link_match = _PORTAL_LINK_RE.search(body)
        pin_match = _PORTAL_PIN_RE.search(body)
        if link_match or pin_match:
            stream.write(f'{"-" * 72}\n')
            stream.write(' PORTAL — copie para testar\n')
            if link_match:
                stream.write(f' Link: {link_match.group(1)}\n')
            if pin_match:
                stream.write(f' PIN:  {pin_match.group(1)}\n')

        if message.alternatives:
            stream.write(f'{"-" * 72}\n')
            stream.write(f' (+ versão HTML omitida — {len(message.alternatives)} parte(s))\n')
        if message.attachments:
            nomes = []
            for anexo in message.attachments:
                if isinstance(anexo, tuple) and anexo:
                    nomes.append(str(anexo[0]))
                else:
                    nomes.append('anexo')
            stream.write(f' (+ anexos omitidos: {", ".join(nomes)})\n')

        stream.write(f'{separador}\n\n')
        stream.flush()
