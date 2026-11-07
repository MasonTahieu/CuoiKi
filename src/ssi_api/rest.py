"""FCData v2 only. Version-specific contract from guide.ssi.com.vn, pending real validation."""
import time
import requests
from src.neo_api.rest import AuthError, NeoError
from src.ssi_api.connections import FC_REST, fcdata_rest_base

BASE = FC_REST
READ_ENDPOINTS = {"Securities","SecuritiesDetails","IndexList","IndexComponents","DailyOhlc","IntradayOhlc","DailyIndex","DailyStockPrice"}


class SSIClient:
    def __init__(self,settings,session=None,sleep=time.sleep,clock=time.monotonic):
        settings.validate_v2()
        self.base=fcdata_rest_base(settings.rest_base)
        self.settings,self.session=settings,session or requests.Session()
        self.sleep,self.clock,self.last=sleep,clock,None
        self._token=""

    def close(self):
        self.session.close()

    def request(self,endpoint,params=None,login=False):
        if (login and endpoint!="AccessToken") or (not login and endpoint not in READ_ENDPOINTS):
            raise NeoError("Chỉ cho phép xác thực FCData và các endpoint dữ liệu thị trường SSI đã khai báo.")
        if not login and not self._token:
            raise AuthError("Chưa đăng nhập SSI.")
        if self.last is not None:
            self.sleep(max(0,1-(self.clock()-self.last)))  # conservative single-process budget; not an SSI quota claim
        self.last=self.clock()
        try:
            if login:
                response=self.session.post(self.base+endpoint,json={"consumerID":self.settings.consumer_id,
                    "consumerSecret":self.settings.consumer_secret},timeout=(5,20),allow_redirects=False)
            else:
                response=self.session.get(self.base+endpoint,params=params,headers={"Authorization":"Bearer "+self._token},
                    timeout=(5,20),allow_redirects=False)
        except requests.RequestException:
            raise NeoError("Không nhận được phản hồi SSI; đã dừng, không tự thử lại đăng nhập.") from None
        if response.status_code == 401:
            self._token = ""
            raise AuthError("SSI trả HTTP 401. Phiên xác thực bị từ chối hoặc hết hạn. Cần xác thực lại.")
        if response.status_code == 429:
            raise NeoError("SSI trả HTTP 429 do giới hạn tần suất. Đã dừng lần đọc.")
        if response.status_code!=200:
            raise NeoError(f"SSI trả HTTP {response.status_code}; kiểm tra quyền, cấu hình và phiên bản được cấp.")
        try:
            body=response.json()
        except ValueError:
            raise NeoError("SSI không trả JSON hợp lệ.") from None
        if not isinstance(body,dict) or body.get("status") not in (200,"Success") or "data" not in body:
            raise NeoError("SSI báo lỗi hoặc schema khác hợp đồng FCData v2; cần đối chiếu mẫu thực.")
        return body

    def authenticate(self):
        self._token = ""
        data=self.request("AccessToken",login=True)["data"]
        token=data.get("accessToken") if isinstance(data,dict) else None
        if not isinstance(token,str) or not token or any(c.isspace() for c in token):
            raise NeoError("SSI thiếu accessToken hợp lệ.")
        self._token=token

    def list_all(self,endpoint,**params):
        rows,total=[],None
        for page in range(1,11):
            body=self.request(endpoint,{**params,"pageIndex":page,"pageSize":1000})
            data,count=body["data"],body.get("totalRecord")
            if not isinstance(data,list) or type(count) is not int or count<0:
                raise NeoError("SSI thiếu thông tin phân trang hợp lệ.")
            if any(not isinstance(record, dict) for record in data):
                raise NeoError("SSI trả bản ghi phân trang sai kiểu. Cần kiểm tra hợp đồng dữ liệu.")
            if total is not None and count!=total:
                raise NeoError("Dữ liệu SSI thay đổi trong lúc phân trang; cần lấy lại.")
            total=count
            rows.extend(data)
            if len(rows)==total:
                return rows
            if not data or len(rows)>total:
                break
        raise NeoError("Chưa lấy đủ trang SSI; không sử dụng kết quả thiếu.")

    def components(self,index):
        if index not in {"VN30","HNX30"}:
            raise NeoError("Nhóm ngoài phạm vi VN30/HNX30.")
        records=self.list_all("IndexComponents",indexCode=index)
        if len(records)!=1 or records[0].get("IndexCode")!=index:
            raise NeoError("SSI trả nhóm chỉ số khác yêu cầu.")
        record=records[0]
        members=record.get("IndexComponent")
        if not isinstance(members,list):
            raise NeoError("Thiếu IndexComponent.")
        symbols=[m.get("StockSymbol") for m in members if isinstance(m,dict)]
        if (len(symbols)!=len(members) or not all(isinstance(s,str) and s for s in symbols)
                or len(set(symbols))!=len(symbols) or str(record.get("TotalSymbolNo"))!=str(len(symbols))):
            raise NeoError("Danh sách thành phần thiếu/trùng hoặc không khớp tổng.")
        exchange={"VN30":"HOSE","HNX30":"HNX"}[index]
        if record.get("Exchange")!=exchange:
            raise NeoError("Sàn SSI không khớp nhóm chỉ số.")
        return [dict(symbol=s,index_group=index,marketCode=exchange,stockType="ST") for s in symbols]
