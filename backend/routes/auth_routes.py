import json
import os
from urllib.parse import urlsplit
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
from onelogin.saml2.auth import OneLogin_Saml2_Auth

router = APIRouter(tags=['auth'])


def get_user_role_from_email(email: str | None) -> str:
    if email and email.endswith('@admin.edu'):
        return 'admin'
    return 'user'


def get_saml_settings():
    settings_path = os.path.join(os.path.dirname(__file__), '..', 'saml', 'settings.json')
    with open(settings_path) as f:
        return json.load(f)


async def prepare_saml_request(request: Request):
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
    req = await prepare_saml_request(request)
    auth = OneLogin_Saml2_Auth(req, get_saml_settings())
    login_url = auth.login()
    return RedirectResponse(url=login_url)


@router.get('/sso/login')
async def sso_login(request: Request):
    return await saml_login(request)


@router.post('/saml/callback')
async def saml_callback(request: Request):
    req = await prepare_saml_request(request)
    auth = OneLogin_Saml2_Auth(req, get_saml_settings())
    auth.process_response()
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
