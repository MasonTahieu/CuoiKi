import pytest
from src.config import ConfigurationError
from src.ssi_api.connections import connection_plan, fcdata_rest_base, FC_REST, FC_STREAM
from src.ssi_api.rest import SSIClient
from src.ssi_api.settings import SSISettings


def test_profiles_keep_auth_and_protocols_separate():
    plan=connection_plan()
    assert plan["network_called"] is False and plan["live_verified"] is False
    fc=plan["profiles"]["fcdata_v2"]
    v3=plan["profiles"]["fastconnect_v3"]
    assert fc["auth_url"]==FC_REST+"AccessToken"
    assert fc["stream_url"]==FC_STREAM
    assert fc["stream_transport"]=="signalr" and v3["stream_transport"]=="websocket"
    # FCData v2 keeps only REST; FastConnect V3 streams through the official ssi-sdk adapter.
    assert fc["stream_implemented"] is False and v3["stream_implemented"] is True
    assert set(connection_plan("fcdata_v2")["profiles"])=={"fcdata_v2"}


@pytest.mark.parametrize("url",["http://fc-data.ssi.com.vn/api/v2/Market/",
    "https://example.com/api/v2/Market/","https://fc-data.ssi.com.vn/api/v2/Market/?token=x",
    "https://user@fc-data.ssi.com.vn/api/v2/Market/", "https://fc-data.ssi.com.vn/v2.0/Market/",
    "https://api.ssi.com.vn/api/v3/"])
def test_fcdata_does_not_send_credentials_to_wrong_contract(url):
    with pytest.raises(ConfigurationError):fcdata_rest_base(url)
    with pytest.raises(ConfigurationError):
        SSIClient(SSISettings(profile="fcdata_v2",consumer_id="id",consumer_secret="secret",rest_base=url))


def test_official_rest_address_normalizes_only_trailing_slash():
    assert fcdata_rest_base()==FC_REST
    assert fcdata_rest_base(FC_REST.rstrip("/"))==FC_REST
