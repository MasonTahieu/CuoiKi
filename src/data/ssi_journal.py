"""Read-only, cursor-ordered access to one collector run; bounded batch writer."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3


class JournalError(ValueError):
    pass


class BufferedSink:
    def __init__(self,store,batch_size=128):
        if type(batch_size) is not int or not 1<=batch_size<=10000:
            raise ValueError("Kích thước lô phải từ 1 đến 10000.")
        self.store,self.batch_size,self.pending=store,batch_size,[]

    def __call__(self,**event):
        self.pending.append(deepcopy(event))
        boundary=event["channel"]=="connection" and event["payload"].get("state") in {
            "connecting","connected","disconnected","auth_failed","adapter_error","stopped"}
        if boundary or len(self.pending)>=self.batch_size:
            self.flush()

    def flush(self):
        if self.pending:
            self.store.append_many(self.pending)
            self.pending.clear()  # preserve pending items if the transaction raises


class SSIJournal:
    def __init__(self,path):
        self.path=Path(path).resolve()
        self.db=None

    def __enter__(self):
        if not self.path.is_file():
            raise JournalError("Chưa có kho SSI collector tại đường dẫn đã chọn.")
        try:
            self.db=sqlite3.connect(self.path.as_uri()+"?mode=ro",uri=True,timeout=10)
            self.db.execute("PRAGMA query_only=ON")
            self.db.execute("BEGIN")  # one consistent read snapshot, even while collector writes
            self.db.execute("SELECT id,source,run,received_at,channel,payload FROM events LIMIT 0")
        except sqlite3.Error:
            if self.db:self.db.close()
            raise JournalError("Không đọc được cấu trúc journal SQLite.") from None
        return self

    def __exit__(self,*_):
        self.db.close()

    def runs(self,limit=50):
        if type(limit) is not int or not 1<=limit<=1000:
            raise JournalError("Giới hạn số run phải từ 1 đến 1000.")
        try:
            cursor=self.db.execute("""SELECT run,COUNT(*),MIN(id),MAX(id) FROM events
                GROUP BY run HAVING SUM(CASE WHEN channel IN ('ssiDecoded','ssiMerged') THEN 1
                WHEN channel IN ('universe','connection') AND payload LIKE '%"connection_epoch"%' THEN 1 ELSE 0 END)>0
                ORDER BY MAX(id) DESC LIMIT ?""",(limit,))
            rows=cursor.fetchall()
            return [self.describe(row[0]) for row in rows]
        except sqlite3.Error:
            raise JournalError("Không liệt kê được run trong journal.") from None

    def describe(self,run):
        rows=self.db.execute("SELECT source,COUNT(*),MIN(id),MAX(id) FROM events WHERE run=? GROUP BY source",(run,)).fetchall()
        if not rows:
            raise JournalError("Không tìm thấy run đã chọn.")
        if len(rows)!=1 or rows[0][0] not in {"ssi","synthetic"}:
            raise JournalError("Run phải có đúng một nguồn SSI hoặc giả lập; không trộn nguồn.")
        source,count,first,last=rows[0]
        times=self.db.execute("SELECT received_at FROM events WHERE id IN (?,?) ORDER BY id",(first,last)).fetchall()
        return dict(run=run,source=source,events=count,first_event_id=first,last_event_id=last,
                    first_received_at=times[0][0],last_received_at=times[-1][0])

    def timeline(self, run, limit=200):
        """Recent replay positions in journal order, excluding raw and cached copies."""
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise JournalError("Giới hạn mốc phát lại phải từ 1 đến 1000.")
        records = self.db.execute(
            "SELECT id,received_at,channel,payload FROM events "
            "WHERE run=? AND channel IN ('connection','ssiDecoded','universe') ORDER BY id DESC LIMIT ?",
            (run, limit),
        ).fetchall()
        points = []
        for ident, received_at, channel, payload in reversed(records):
            state = None
            if channel == "connection":
                try:
                    state = json.loads(payload).get("state")
                except (ValueError, TypeError, AttributeError):
                    raise JournalError("Bản ghi kết nối trong journal không hợp lệ.") from None
            points.append(dict(event_id=ident, received_at=received_at, channel=channel, state=state))
        return points

    def events(self,run,through_event_id=None,batch_size=256):
        if type(batch_size) is not int or batch_size<1:
            raise JournalError("Kích thước trang đọc phải dương.")
        if through_event_id is not None and (type(through_event_id) is not int or through_event_id<1):
            raise JournalError("event_id phải là số nguyên dương.")
        query="SELECT id,source,run,received_at,channel,payload FROM events WHERE run=?"
        args=[run]
        if through_event_id is not None:
            query+=" AND id<=?"
            args.append(through_event_id)
        cursor=self.db.execute(query+" ORDER BY id",args)
        while True:
            rows=cursor.fetchmany(batch_size)
            if not rows:break
            for ident,source,name,at,channel,raw in rows:
                try:
                    payload=json.loads(raw)
                except (ValueError,TypeError):
                    raise JournalError("Journal chứa JSON hỏng; không phát lại kết quả một phần.") from None
                if not isinstance(payload,dict):
                    raise JournalError("Journal chứa payload không đúng kiểu object.")
                yield dict(event_id=ident,source=source,run=name,received_at=at,channel=channel,payload=payload)
