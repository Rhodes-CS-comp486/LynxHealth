import json
import os
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
    return {
        'https': 'off',
        'http_host': request.headers.get('host', 'localhost:8000'),
        'server_port': '8000',
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

    return RedirectResponse(url=f'http://localhost:4200/home?session={encoded}', status_code=302)
