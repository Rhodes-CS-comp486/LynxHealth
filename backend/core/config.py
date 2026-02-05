import os



def _get_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

APP_ENV = os.getenv("APP_ENV", "development")


SAML_STRICT = _get_bool(os.getenv("SAML_STRICT"), default=True)
SAML_DEBUG = _get_bool(os.getenv("SAML_DEBUG"), default=False)

SAML_SP_BASE_URL = os.getenv("SAML_SP_BASE_URL", "https://localhost:8000")
SAML_SP_ENTITY_ID = os.getenv("SAML_SP_ENTITY_ID", f"{SAML_SP_BASE_URL}/auth/sso/metadata")
SAML_SP_ACS_URL = os.getenv("SAML_SP_ACS_URL", f"{SAML_SP_BASE_URL}/auth/sso/acs")
SAML_SP_X509CERT = os.getenv("SAML_SP_X509CERT", "")
SAML_SP_PRIVATE_KEY = os.getenv("SAML_SP_PRIVATE_KEY", "")
SAML_SP_NAMEID_FORMAT = os.getenv(
    "SAML_SP_NAMEID_FORMAT",
    "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
)

SAML_IDP_ENTITY_ID = os.getenv("SAML_IDP_ENTITY_ID", "")
SAML_IDP_SSO_URL = os.getenv("SAML_IDP_SSO_URL", "")
SAML_IDP_SLO_URL = os.getenv("SAML_IDP_SLO_URL", "")
SAML_IDP_X509CERT = os.getenv("SAML_IDP_X509CERT", "")
SAML_IDP_METADATA_PATH = os.getenv(
    "SAML_IDP_METADATA_PATH",
    "https://rhodes.onelogin.com/saml/metadata/784e58e9-c3fe-4e8f-8bbf-e9a11c3f1dd4",
)

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRES_MINUTES = int(os.getenv("JWT_EXPIRES_MINUTES", "60"))

FRONTEND_SSO_REDIRECT_URL = os.getenv("FRONTEND_SSO_REDIRECT_URL", "")

def validate_runtime_config() -> None:
    if APP_ENV.lower() == "production" and JWT_SECRET_KEY == "change-me":
        raise RuntimeError("JWT_SECRET_KEY must be set in production.")

