import asyncio
import importlib
import json
import sys
import types
from types import SimpleNamespace
from urllib.parse import unquote


def _load_auth_routes_module():
    # Stub the onelogin import chain so test imports do not require xmlsec.
    onelogin_module = types.ModuleType('onelogin')
    saml2_module = types.ModuleType('onelogin.saml2')
    auth_module = types.ModuleType('onelogin.saml2.auth')
    auth_module.OneLogin_Saml2_Auth = object
    saml2_module.auth = auth_module
    onelogin_module.saml2 = saml2_module
    sys.modules['onelogin'] = onelogin_module
    sys.modules['onelogin.saml2'] = saml2_module
    sys.modules['onelogin.saml2.auth'] = auth_module
    return importlib.import_module('backend.routes.auth_routes')


auth_routes = _load_auth_routes_module()


class _FakeRequest:
    def __init__(self, *, path: str, host: str = 'localhost:8000', query_params=None, form_data=None):
        self.headers = {'host': host}
        self.url = SimpleNamespace(path=path)
        self.query_params = query_params or {}
        self._form_data = form_data or {}

    async def form(self):
        return self._form_data


def _decode_session_value_from_redirect(location: str) -> str:
    return unquote(location.split('session=', 1)[1])


def test_prepare_saml_request_builds_expected_payload() -> None:
    request = _FakeRequest(path='/saml/callback', query_params={'relay': 'abc'}, form_data={'SAMLResponse': 'xyz'})

    payload = asyncio.run(auth_routes.prepare_saml_request(request))

    assert payload == {
        'https': 'off',
        'http_host': 'localhost:8000',
        'server_port': '8000',
        'script_name': '/saml/callback',
        'get_data': {'relay': 'abc'},
        'post_data': {'SAMLResponse': 'xyz'},
    }


def test_saml_login_redirects_to_identity_provider(monkeypatch) -> None:
    class FakeSamlAuth:
        def __init__(self, _req, _settings):
            pass

        def login(self):
            return 'https://idp.example.com/login'

    monkeypatch.setattr(auth_routes, 'OneLogin_Saml2_Auth', FakeSamlAuth)
    monkeypatch.setattr(auth_routes, 'get_saml_settings', lambda: {})

    response = asyncio.run(auth_routes.saml_login(_FakeRequest(path='/saml/login')))

    assert response.status_code == 307
    assert response.headers['location'] == 'https://idp.example.com/login'


def test_saml_callback_returns_admin_role_for_admin_domain(monkeypatch) -> None:
    class FakeSamlAuth:
        def __init__(self, _req, _settings):
            pass

        def process_response(self):
            return None

        def get_errors(self):
            return []

        def is_authenticated(self):
            return True

        def get_attributes(self):
            return {'Email': ['nurse@admin.edu'], 'FirstName': ['Nurse'], 'LastName': ['Admin']}

    monkeypatch.setattr(auth_routes, 'OneLogin_Saml2_Auth', FakeSamlAuth)
    monkeypatch.setattr(auth_routes, 'get_saml_settings', lambda: {})

    response = asyncio.run(auth_routes.saml_callback(_FakeRequest(path='/saml/callback')))
    decoded_session = _decode_session_value_from_redirect(response.headers['location'])

    assert response.status_code == 302
    assert '"role": "admin"' in decoded_session


def test_saml_callback_returns_user_role_for_non_admin_domain(monkeypatch) -> None:
    class FakeSamlAuth:
        def __init__(self, _req, _settings):
            pass

        def process_response(self):
            return None

        def get_errors(self):
            return []

        def is_authenticated(self):
            return True

        def get_attributes(self):
            return {'Email': ['student@example.edu'], 'FirstName': ['Student'], 'LastName': ['User']}

    monkeypatch.setattr(auth_routes, 'OneLogin_Saml2_Auth', FakeSamlAuth)
    monkeypatch.setattr(auth_routes, 'get_saml_settings', lambda: {})

    response = asyncio.run(auth_routes.saml_callback(_FakeRequest(path='/saml/callback')))
    decoded_session = _decode_session_value_from_redirect(response.headers['location'])

    assert response.status_code == 302
    assert '"role": "user"' in decoded_session


def test_saml_callback_returns_400_when_saml_errors_exist(monkeypatch) -> None:
    class FakeSamlAuth:
        def __init__(self, _req, _settings):
            pass

        def process_response(self):
            return None

        def get_errors(self):
            return ['invalid_response']

        def is_authenticated(self):
            return False

        def get_attributes(self):
            return {}

    monkeypatch.setattr(auth_routes, 'OneLogin_Saml2_Auth', FakeSamlAuth)
    monkeypatch.setattr(auth_routes, 'get_saml_settings', lambda: {})

    response = asyncio.run(auth_routes.saml_callback(_FakeRequest(path='/saml/callback')))

    assert response.status_code == 400
    assert json.loads(response.body) == {'error': ['invalid_response']}


def test_saml_callback_returns_401_for_unauthenticated_response(monkeypatch) -> None:
    class FakeSamlAuth:
        def __init__(self, _req, _settings):
            pass

        def process_response(self):
            return None

        def get_errors(self):
            return []

        def is_authenticated(self):
            return False

        def get_attributes(self):
            return {}

    monkeypatch.setattr(auth_routes, 'OneLogin_Saml2_Auth', FakeSamlAuth)
    monkeypatch.setattr(auth_routes, 'get_saml_settings', lambda: {})

    response = asyncio.run(auth_routes.saml_callback(_FakeRequest(path='/saml/callback')))

    assert response.status_code == 401
    assert json.loads(response.body) == {'error': 'Not authenticated'}
