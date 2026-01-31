from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser
from onelogin.saml2.settings import OneLogin_Saml2_Settings

from backend.core import config


def build_saml_settings() -> dict:
    base_settings = {
        "strict": config.SAML_STRICT,
        "debug": config.SAML_DEBUG,
        "sp": {
            "entityId": config.SAML_SP_ENTITY_ID,
            "assertionConsumerService": {
                "url": config.SAML_SP_ACS_URL,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "singleLogoutService": {
                "url": config.SAML_SP_SLO_URL,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": config.SAML_SP_X509CERT,
            "privateKey": config.SAML_SP_PRIVATE_KEY,
            "NameIDFormat": config.SAML_SP_NAMEID_FORMAT,
        },
        "idp": {
            "entityId": config.SAML_IDP_ENTITY_ID,
            "singleSignOnService": {
                "url": config.SAML_IDP_SSO_URL,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "singleLogoutService": {
                "url": config.SAML_IDP_SLO_URL,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": config.SAML_IDP_X509CERT,
        },
    }
    if config.SAML_IDP_METADATA_PATH:
        return OneLogin_Saml2_IdPMetadataParser.parse(
            config.SAML_IDP_METADATA_PATH,
            base_settings,
        )
    return base_settings


def init_saml_auth(request_data: dict) -> OneLogin_Saml2_Auth:
    return OneLogin_Saml2_Auth(request_data, build_saml_settings())


def build_request_data(url: str, host: str, query_params: dict, form_data: dict) -> dict:
    scheme = "https" if url.startswith("https") else "http"
    return {
        "https": "on" if scheme == "https" else "off",
        "http_host": host,
        "server_port": "443" if scheme == "https" else "80",
        "script_name": url,
        "get_data": query_params,
        "post_data": form_data,
    }


def generate_sp_metadata() -> tuple[str, list[str]]:
    settings = OneLogin_Saml2_Settings(build_saml_settings(), sp_validation_only=True)
    metadata = settings.get_sp_metadata()
    errors = settings.validate_metadata(metadata)
    return metadata, errors