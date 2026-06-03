"""Context processors do app accounts."""


def modulos_integrados_manutencao(request):
    from accounts.modulos_integrados import load_modulos_status_map

    return {'modulos_manutencao': load_modulos_status_map()}
