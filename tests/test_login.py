import requests
import pytest
from dotenv import dotenv_values
from src.neo_api.login import AUTH_URL, obtain_token, save_token
from src.neo_api.rest import AuthError


class FakeSession:
    def __init__(self, status=200, data=None, fail=False):
        self.status_code, self.data, self.fail = status,data,fail
    def post(self,url,**kwargs):
        assert url == AUTH_URL
        assert kwargs["allow_redirects"] is False
        self.sent = kwargs
        if self.fail:
            raise requests.Timeout("PRIVATE_PASSWORD")
        return self
    def json(self):
        return self.data


def test_login_and_save_preserve_config_without_password(tmp_path):
    session = FakeSession(data={"status":1,"data":{"access_token":"test.jwt.token","expires_in":10800,
        "refresh_token":"PRIVATE_REFRESH","token_type":"Bearer"}})
    token, expires = obtain_token("user", "PRIVATE_PASSWORD", session)
    path = tmp_path/".env"
    path.write_text("APP_MODE=replay\nCUSTOM_VALUE=keep\n",encoding="utf-8")
    save_token(path,token,"test-device",expires)
    values = dotenv_values(path)
    assert values["NEO_ACCESS_TOKEN"] == "test.jwt.token"
    assert values["APP_MODE"] == "replay" and values["CUSTOM_VALUE"] == "keep"
    assert values["NEO_TOKEN_EXPIRES_AT"]
    assert "PRIVATE_" not in path.read_text()


@pytest.mark.parametrize("session", [FakeSession(302),FakeSession(401),FakeSession(data={"status":0}),
    FakeSession(data={"status":1,"data":{"access_token":"bad\ntoken"}}),FakeSession(fail=True)])
def test_login_rejects_errors_without_echoing_credentials(session):
    with pytest.raises(AuthError) as error:
        obtain_token("user","PRIVATE_PASSWORD",session)
    assert "PRIVATE_PASSWORD" not in str(error.value)
