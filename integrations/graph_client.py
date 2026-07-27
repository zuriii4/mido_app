import logging

import msal
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_BASE_URL = 'https://graph.microsoft.com/v1.0'
GRAPH_SCOPE = 'https://graph.microsoft.com/.default'


class GraphAuthError(Exception):
    pass


class GraphClient:
    """Drzi MSAL app a poskytuje get_json/get_bytes s automatickym tokenom.

    MSAL si token interne cachuje a obnovuje sam (in-memory cache), takze
    staci vzdy zavolat acquire_token_for_client - ak je platny, vrati ho z cache.
    """

    def __init__(self):
        self._app = msal.ConfidentialClientApplication(
            settings.AZURE_CLIENT_ID,
            authority=f'https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}',
            client_credential=settings.AZURE_CLIENT_SECRET,
        )

    def _token(self):
        result = self._app.acquire_token_for_client(scopes=[GRAPH_SCOPE])
        if 'access_token' not in result:
            raise GraphAuthError(
                f"Nepodarilo sa ziskat Graph token: {result.get('error')} - {result.get('error_description')}"
            )
        return result['access_token']

    def _headers(self):
        return {'Authorization': f'Bearer {self._token()}'}

    def get_json(self, url, params=None):
        if not url.startswith('http'):
            url = f'{GRAPH_BASE_URL}/{url.lstrip("/")}'
        response = requests.get(url, headers=self._headers(), params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_json_paged(self, url, params=None):
        """Generator - vracia postupne kazdu stranku ('value' zoznam), sleduje @odata.nextLink."""
        next_url = url
        next_params = params
        while next_url:
            data = self.get_json(next_url, params=next_params)
            yield data.get('value', [])
            next_url = data.get('@odata.nextLink')
            next_params = None  # nextLink uz obsahuje vsetky query parametre

    def get_bytes(self, url, params=None):
        if not url.startswith('http'):
            url = f'{GRAPH_BASE_URL}/{url.lstrip("/")}'
        response = requests.get(url, headers=self._headers(), params=params, timeout=120)
        response.raise_for_status()
        return response.content
