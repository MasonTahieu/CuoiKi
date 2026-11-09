# Smoke test FastConnect V3

Bắt đầu 2026-11-09T13:18:20.380084+07:00 · kết thúc 2026-11-09T13:24:04.875382+07:00 · đăng nhập `none`.

| Bước | Kết quả |
|---|---|
| Thành phần nhóm | VN30 30 mã |
| securitiesSummary chỉ số hôm nay | 0 dòng |
| Stream | dừng vì `duration_limit` · nhận 8414 · ghép 8045 · lỗi giải mã 0 |
| Ack đăng ký | {'ok': 1, 'error': 0} |
| Loại thông điệp | {'QUOTE': 5497, 'ROOM': 146, 'TRADE': 2771} |
| Mẫu thời gian nguồn | {'QUOTE': {'9999/99/99 99:99:99': 5497}, 'ROOM': {'9999/99/99 99:99:99': 146}, 'TRADE': {'9999/99/99 99:99:99.999': 2771}} |
| Số mức sổ lệnh | {'bids=10/asks=10': 5497} |
| Trung vị giá khớp | None |

## Chất lượng sau phát lại

```json
{
  "group_coverage": {
    "VN30": {
      "members": 30,
      "fields_complete": 30,
      "data_usable": 0,
      "data_usable_percent": 0.0
    }
  },
  "reasons": {
    "CONNECTION_NOT_ACTIVE": 30,
    "EXCESS_RECORDED_LAG": 22,
    "STALE_FIELDS": 14
  },
  "warnings": {
    "SESSION_FROM_SCHEDULE": 30,
    "SYMBOL_STATUS_NOT_PROVIDED": 30,
    "TOTAL_VALUE_DERIVED": 30,
    "SOURCE_CLOCK_AHEAD_OF_RECEIVE": 30
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
