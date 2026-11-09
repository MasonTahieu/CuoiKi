# Smoke test FastConnect V3

Bắt đầu 2026-11-09T13:15:35.095424+07:00 · kết thúc 2026-11-09T13:16:54.281261+07:00 · đăng nhập `none`.

| Bước | Kết quả |
|---|---|
| Thành phần nhóm | VN30 30 mã |
| securitiesSummary chỉ số hôm nay | 0 dòng |
| Stream | dừng vì `duration_limit` · nhận 1612 · ghép 1004 · lỗi giải mã 0 |
| Ack đăng ký | {'ok': 1, 'error': 0} |
| Loại thông điệp | {'QUOTE': 1032, 'TRADE': 550, 'ROOM': 30} |
| Mẫu thời gian nguồn | {'QUOTE': {'9999/99/99 99:99:99': 1032}, 'TRADE': {'9999/99/99 99:99:99.999': 550}, 'ROOM': {'9999/99/99 99:99:99': 30}} |
| Số mức sổ lệnh | {'bids=10/asks=10': 1032} |
| Trung vị giá khớp | None |

## Chất lượng sau phát lại

```json
{
  "group_coverage": {
    "VN30": {
      "members": 30,
      "fields_complete": 0,
      "data_usable": 0,
      "data_usable_percent": 0.0
    }
  },
  "reasons": {
    "CONNECTION_NOT_ACTIVE": 30,
    "MISSING_FIELDS": 30,
    "EXCESS_RECORDED_LAG": 22
  },
  "warnings": {
    "SESSION_FROM_SCHEDULE": 30,
    "SYMBOL_STATUS_NOT_PROVIDED": 30,
    "SOURCE_CLOCK_AHEAD_OF_RECEIVE": 6
  }
}
```

## Đối chiếu stream với REST cùng ngày

```json
{
  "totalTradingVolume": {
    "symbols": 0,
    "median_ratio": null,
    "min_ratio": null,
    "max_ratio": null
  },
  "totalTradingValue": {
    "symbols": 0,
    "median_ratio": null,
    "min_ratio": null,
    "max_ratio": null
  },
  "foreignBuyValue": {
    "symbols": 0,
    "median_ratio": null,
    "min_ratio": null,
    "max_ratio": null
  },
  "foreignSellValue": {
    "symbols": 0,
    "median_ratio": null,
    "min_ratio": null,
    "max_ratio": null
  },
  "openPrice": {
    "symbols": 0,
    "median_ratio": null,
    "min_ratio": null,
    "max_ratio": null
  }
}
```

Không bật `SSI_SEMANTICS_VERIFIED=true` chỉ dựa trên một lần smoke test.
