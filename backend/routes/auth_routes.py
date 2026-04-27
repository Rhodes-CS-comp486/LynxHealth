"""
SAML-based authentication routes for the LynxHealth backend.


To get started with Single Sign On (SSO), contact Douglas Walker or Mark Miller for
any questions about set up, implementation, or permissions.

Exposes both ``/saml/*`` and ``/sso/*`` aliases so the service can be wired up
to identity providers that use either naming convention. After a successful
SAML assertion the user's email, name, and inferred role are encoded into the
redirect URL so the Angular frontend can initialize its session.
"""

import json
import logging
import os
from urllib.parse import urlsplit
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
from onelogin.saml2.auth import OneLogin_Saml2_Auth

router = APIRouter(tags=['auth'])
logger = logging.getLogger(__name__)


def get_user_role_from_email(email: str | None) -> str:
    """Return ``'admin'`` for ``@admin.edu`` addresses and ``'user'`` otherwise."""
    if email and email.endswith('@admin.edu'):
        return 'admin'
    return 'user'


def get_saml_settings():
    """Load the SAML service-provider settings from ``backend/saml/settings.json``."""
    settings_path = os.path.join(os.path.dirname(__file__), '..', 'saml', 'settings.json')
    with open(settings_path) as f:
        return json.load(f)


async def prepare_saml_request(request: Request):
    """Assemble the request dict expected by ``OneLogin_Saml2_Auth``.

    Normalizes host, scheme, and port using ``X-Forwarded-*`` headers so the
    SAML assertion consumer URL matches what the identity provider sees when
    the app is deployed behind a reverse proxy.
    """
    form_data = await request.form()
    host = request.headers.get('x-forwarded-host') or request.headers.get('host', 'localhost:8000')
    forwarded_proto = request.headers.get('x-forwarded-proto')
    proto = forwarded_proto.split(',')[0].strip() if forwarded_proto else request.url.scheme
    if proto not in {'http', 'https'}:
        proto = 'http'

    forwarded_port = request.headers.get('x-forwarded-port')
    host_port = urlsplit(f'//{host}').port
    server_port = forwarded_port or (str(host_port) if host_port else ('443' if proto == 'https' else '80'))

    return {
        'https': 'on' if proto == 'https' else 'off',
        'http_host': host,
        'server_port': server_port,
        'script_name': request.url.path,
        'get_data': dict(request.query_params),
        'post_data': dict(form_data)
    }


@router.get('/saml/login')
async def saml_login(request: Request):
    """Kick off the SAML SSO flow by redirecting to the identity provider's login URL."""
    req = await prepare_saml_request(request)
    auth = OneLogin_Saml2_Auth(req, get_saml_settings())
    login_url = auth.login()
    return RedirectResponse(url=login_url)


@router.get('/sso/login')
async def sso_login(request: Request):
    """Alias for ``/saml/login`` to support identity providers that post to ``/sso/*``."""
    return await saml_login(request)


@router.post('/saml/callback')
async def saml_callback(request: Request):
    """Assertion Consumer Service endpoint.

    Validates the SAML response, extracts the user's email/name attributes,
    derives the role, and redirects the browser to ``/home`` with the
    session payload embedded in the query string.
    """
    req = await prepare_saml_request(request)
    auth = OneLogin_Saml2_Auth(req, get_saml_settings())
    try:
        auth.process_response()
    except Exception as exc:
        logger.exception('SAML response processing failed')
        return JSONResponse({'error': 'SAML response could not be processed', 'detail': str(exc)}, status_code=400)

    errors = auth.get_errors()

    if errors:
        return JSONResponse({'error': errors}, status_code=400)

    if not auth.is_authenticated():
        return JSONResponse({'error': 'Not authenticated'}, status_code=401)

    attributes = auth.get_attributes()
    email = attributes.get('Email', [None])[0]
    first_name = attributes.get('FirstName', [None])[0]
    last_name = attributes.get('LastName', [None])[0]
    role = get_user_role_from_email(email)

    session = json.dumps({'email': email, 'role': role, 'firstName': first_name, 'lastName': last_name})
    encoded = session.replace('"', '%22').replace(' ', '%20')

    return RedirectResponse(url=f'https://lynxhc.com/home?session={encoded}', status_code=302)


@router.post('/sso/acs')
async def sso_acs(request: Request):
    """Alias for ``/saml/callback`` used by providers that post to ``/sso/acs``."""
    return await saml_callback(request)
