"""drf-spectacular rozsirenia, aby OpenAPI schema spravne popisala nase
vlastne autentifikacie (inak spectacular hlasi 'could not resolve authenticator')."""
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class RfidSessionAuthScheme(OpenApiAuthenticationExtension):
    target_class = 'rfid_auth.authentication.RfidSessionAuthentication'
    name = 'RfidSessionAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
            'description': 'RFID session token vydany cez POST /api/auth/rfid-login/.',
        }


class KioskDeviceAuthScheme(OpenApiAuthenticationExtension):
    target_class = 'rfid_auth.authentication.KioskDeviceAuthentication'
    name = 'KioskDeviceAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'X-Device-Token',
            'description': 'Tajny token kiosku (z manage.py create_kiosk_device).',
        }
