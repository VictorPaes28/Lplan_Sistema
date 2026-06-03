"""Context processors do app accounts."""


def modulos_integrados_manutencao(request):
    try:
        from accounts.modulos_integrados import load_modulos_status_map

        return {'modulos_manutencao': load_modulos_status_map()}
    except Exception:
        from accounts.modulos_integrados import default_modulos_status_map

        return {'modulos_manutencao': default_modulos_status_map()}
