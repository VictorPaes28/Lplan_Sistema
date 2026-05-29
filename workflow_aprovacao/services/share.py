from __future__ import annotations

from urllib.parse import quote

from django.urls import reverse


def build_process_share_payload(*, request, process) -> dict[str, str]:
    """
    Monta URL do processo e mensagem para compartilhar no WhatsApp.
    O acesso à tela continua restrito por user_can_view_process no backend.
    """
    detail_path = reverse('workflow_aprovacao:process_detail', kwargs={'pk': process.pk})
    absolute_url = request.build_absolute_uri(detail_path)
    title = (process.title or '').strip() or f'Processo #{process.pk}'
    status = process.get_status_display()
    message = (
        f'Central de Aprovações — {title}\n'
        f'Obra: {process.project.code} · {process.category.name}\n'
        f'Situação: {status}\n\n'
        f'Acesse com seu login Lplan (somente quem tem acesso ao módulo e '
        f'vínculo com este processo):\n{absolute_url}'
    )
    return {
        'url': absolute_url,
        'message': message,
        'whatsapp_url': f'https://wa.me/?text={quote(message)}',
    }
