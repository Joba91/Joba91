"""Explicit vision targets; model selection never establishes compatibility."""
TARGETS = {
    'Mini 4 Pro': {'firmware_declared': '01.00.1100', 'native_reference': 'wa140',
                   'native_reference_scope': 'Pareja inferior; sin cobertura delantera acreditada',
                   'calibration_enabled': False, 'usb_profile_observed': True},
    'Air 3': {'firmware_declared': '01.00.1600', 'native_reference': None,
              'native_reference_scope': 'Identificador interno y perfil USB pendientes de contraste',
              'calibration_enabled': False, 'usb_profile_observed': False},
}
MINI4_ACTIVE_ACTIONS = ('Capturar USB pasivo', 'Consultar SN visión (prueba)',
                       'Diagnóstico visión (HMS)', 'Recibir imágenes (prueba)')


def target_info(model):
    if model not in TARGETS:
        raise ValueError('Selecciona Mini 4 Pro o Air 3 para el proyecto de visión.')
    return dict(TARGETS[model])


def require_active_profile(model):
    info = target_info(model)
    if model != 'Mini 4 Pro' or not info['usb_profile_observed']:
        raise ValueError('Air 3: aún falta contrastar su perfil USB y protocolo. Usa Recopilar perfil USB; no se aplicarán peticiones de Mini 4 Pro.')
    return info
