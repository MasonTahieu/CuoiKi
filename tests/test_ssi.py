import pytest
import pandas as pd
from src.config import ConfigurationError
from src.ssi_api.settings import SSISettings, load_ssi_settings
from src.ssi_api.rest import SSIClient
from src.ssi_api.collector import canonical_daily
from src.neo_api.rest import NeoError
from src.data.normalize import state_at
from src.data.synthetic import demo_groups
from src.ranking.engine import rank_groups, rank_snapshot
from src.data.store import EventStore, read_events
from streamlit.testing.v1 import AppTest
from src.config import PROJECT_ROOT


class FakeSession:
    def __init__(self,responses):
        self.responses=iter(responses)
        self.calls=[]
    def post(self,*args,**kwargs):
        self.calls.append((args,kwargs))
        return next(self.responses)
    get=post
    def close(self):pass


class Response:
    status_code=200
    def __init__(self,data):self.data=data
    def json(self):return self.data


def test_ssi_configuration_never_uses_neo_token(tmp_path):
    path=tmp_path/".env"
    path.write_text('NEO_ACCESS_TOKEN=private\nNEO_SEMANTICS_VERIFIED=true\n',encoding='utf-8')
    config=load_ssi_settings(path)
    assert config.profile=="unselected" and config.missing()==["SSI_API_PROFILE"]
    assert not config.semantics_verified
    with pytest.raises(ConfigurationError):config.validate_v2()


def test_vn30_group_ranks_consistently_and_mixed_groups_are_refused():
    frame=state_at(demo_groups())
    assert len(frame)==12 and set(frame.index_group)=={"VN30"}
    ranked=rank_groups(frame)
    for group in ("VN30",):
        subset=ranked.loc[ranked.index_group.eq(group)]
        assert subset["rank"].notna().sum()==12
        assert subset["rank"].min()==1
        assert subset["cohort_size"].eq(12).all()
        expected=rank_snapshot(frame.loc[frame.index_group.eq(group)])
        pd.testing.assert_series_equal(subset.total_score,expected.total_score)
    mixed=frame.copy()
    mixed.loc[mixed.index[:6],"index_group"]="OTHER"
    with pytest.raises(ValueError):rank_snapshot(mixed)


def test_ssi_scores_remain_locked_and_sources_not_mixed(tmp_path):
    frame=state_at(demo_groups())
    frame["source"]="ssi"
    assert rank_groups(frame)["rank"].isna().all()
    store=EventStore(tmp_path/"data.sqlite")
    store.append("ssi","run","2026-11-04T10:00:00+07:00","ssiRaw",{"apiKey":"private","consumerID":"private","data":{"x":1}})
    store.close()
    assert "private" not in str(read_events(tmp_path/"data.sqlite"))


def test_ssi_v2_auth_and_nested_index_contract():
    session=FakeSession([Response({"status":200,"data":{"accessToken":"mock-token"}}),
        Response({"status":"Success","totalRecord":1,"data":[{"IndexCode":"VN30","Exchange":"HOSE","TotalSymbolNo":"2", "IndexComponent":[{"StockSymbol":"A"},{"StockSymbol":"B"}]}]})])
    settings=SSISettings(profile="fcdata_v2",consumer_id="id",consumer_secret="SECRET")
    client=SSIClient(settings,session=session,sleep=lambda _:None,clock=lambda:0)
    client.authenticate()
    members=client.components("VN30")
    assert [m["symbol"] for m in members]==["A","B"]
    assert all(m["marketCode"]=="HOSE" for m in members)
    with pytest.raises(NeoError):client.components("HNX30")  # outside the VN30-only scope
    assert session.calls[0][1]["json"]=={"consumerID":"id","consumerSecret":"SECRET"}
    assert all(call[1]["allow_redirects"] is False for call in session.calls)
    assert "SECRET" not in repr(settings)
    with pytest.raises(NeoError):client.request("PlaceOrder")


def test_ssi_missing_key_stops_before_network():
    with pytest.raises(ConfigurationError):SSIClient(SSISettings(profile="fcdata_v2"))


def test_daily_data_never_invents_intraday_book_or_session():
    row=canonical_daily({"Symbol":"AAA","Tradingdate":"04/11/2026","Closeprice":"20000","Totalmatchval":"1000000"})
    assert row["closePrice"]=="20000"
    assert "bidPrice1" not in row and "tradingSession" not in row and "tradingStatus" not in row
    with pytest.raises(ValueError):canonical_daily({"Foreignsellvaltotal":1,"Toreignsellvaltotal":2})


def test_ui_offers_only_the_vn30_group(monkeypatch):
    monkeypatch.setenv("APP_MODE","demo")
    monkeypatch.setenv("DATA_PROVIDER","ssi")
    app=AppTest.from_file(str(PROJECT_ROOT/"app.py"),default_timeout=30).run()
    chooser=next(s for s in app.selectbox if s.label=="Nhóm so sánh")
    assert list(chooser.options)==["VN30"]
    assert not app.exception
    assert len(app.dataframe[0].value)==12
    assert all(s.startswith("DEMO") for s in app.dataframe[0].value["Mã"])
