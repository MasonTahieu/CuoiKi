"""Only selected provider configuration is loaded; NEO secrets cannot authenticate SSI."""
from src.neo_api.settings import load_neo_settings
from src.ssi_api.settings import load_ssi_settings


def load_provider_settings(provider):
    return load_ssi_settings() if provider=="ssi" else load_neo_settings()
