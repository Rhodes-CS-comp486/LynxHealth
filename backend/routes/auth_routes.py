from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse, Response


from backend.auth import jwt_handler, saml
from backend.auth.dependencies import get_current_user

from backend.core import config
from backend.database import SessionLocal
from backend.models.user import User

router = APIRouter()


@router.post("/login")
def login():
    return {"message": "Login endpoint working"}

@router.get("/sso/login")
async def sso_login(request: Request):
    form_data = await request.form()
    request_data = saml.build_request_data(
        url=str(request.url),
        host=request.headers.get("host", ""),
        query_params=dict(request.query_params),
        form_data=dict(form_data),
    )
    auth = saml.init_saml_auth(request_data)
    redirect_url = auth.login()
    return RedirectResponse(url=redirect_url)



@router.post("/sso/acs")
async def sso_acs(request: Request):
    form_data = await request.form()
    request_data = saml.build_request_data(
        url=str(request.url),
        host=request.headers.get("host", ""),
        query_params=dict(request.query_params),
        form_data=dict(form_data),
    )
    auth = saml.init_saml_auth(request_data)
    auth.process_response()
    errors = auth.get_errors()
    if errors:
        raise HTTPException(status_code=400, detail={"saml_errors": errors})
    if not auth.is_authenticated():
        raise HTTPException(status_code=401, detail="SAML authentication failed")

    attributes = auth.get_attributes()
    name_id = auth.get_nameid()
    email_candidates = (
        attributes.get("email")
        or attributes.get("Email")
        or attributes.get("mail")
        or []
    )
    email = email_candidates[0] if email_candidates else name_id
    if not email:
        raise HTTPException(status_code=400, detail="Email not found in SAML response")

    db = SessionLocal()
    try:
        user = (
            db.query(User)
            .filter(
                (User.sso_subject == name_id)
                | (User.email == email)
            )
            .first()
        )
        if user is None:
            user = User(
                email=email,
                hashed_password="",
                role="student",
                sso_provider="onelogin",
                sso_subject=name_id,
            )
            db.add(user)
        else:
            user.sso_provider = user.sso_provider or "onelogin"
            user.sso_subject = user.sso_subject or name_id
        db.commit()
    finally:
        db.close()

    token = jwt_handler.create_access_token(subject=email)
    if config.FRONTEND_SSO_REDIRECT_URL:
        parsed = urlparse(config.FRONTEND_SSO_REDIRECT_URL)
        query = dict(parse_qsl(parsed.query))
        query.update({"access_token": token, "token_type": "bearer"})
        redirect_url = urlunparse(parsed._replace(query=urlencode(query)))
        return RedirectResponse(url=redirect_url)
    return {"access_token": token, "token_type": "bearer"}



@router.get("/sso/metadata")
def sso_metadata():
    metadata, errors = saml.generate_sp_metadata()
    if errors:
        raise HTTPException(status_code=500, detail={"metadata_errors": errors})
    return Response(content=metadata, media_type="application/xml")


@router.get("/sso/logout")
async def sso_logout(request: Request):
    form_data = await request.form()
    request_data = saml.build_request_data(
        url=str(request.url),
        host=request.headers.get("host", ""),
        query_params=dict(request.query_params),
        form_data=dict(form_data),
    )
    auth = saml.init_saml_auth(request_data)
    redirect_url = auth.logout()
    return RedirectResponse(url=redirect_url)

@router.get("me")
def me(current_user: User = Depends(get_current_user)):
    return {"email": current_user.email, "role": current_user.role}

