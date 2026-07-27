from django.apps import AppConfig


class RfidAuthConfig(AppConfig):
    name = 'rfid_auth'

    def ready(self):
        # zaregistruje OpenApiAuthenticationExtension pre drf-spectacular
        from rfid_auth import schema  # noqa: F401
