from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import math
from pathlib import Path
import re
import struct
from typing import Any


CN_TZ = timezone(timedelta(hours=8))

_FILE_NAME_RE = re.compile(r"^(?P<code>\d{6})_(?P<dataset>\d+)\.dat$", re.IGNORECASE)
_SH_PREFIXES = ("5", "6", "9")
_SZ_PREFIXES = ("0", "1", "2", "3")


@dataclass(frozen=True)
class FinanceDatRecord:
    ts_code: str
    market: str
    dataset_id: int
    record_no: int
    announce_date: date | None
    report_date: date | None
    value_1: float | None
    value_2: float | None
    value_3: float | None
    value_4: float | None
    value_5: float | None
    value_6: float | None
    flag_1: int | None
    flag_2: int | None
    file_name: str
    file_size: int
    raw_json: dict[str, Any]


@dataclass(frozen=True)
class FinanceDatFile:
    path: Path
    code: str
    market: str
    dataset_id: int
    record_size: int
    records: list[FinanceDatRecord]


def _infer_market(code: str, path: Path) -> str:
    parts = {part.upper() for part in path.parts}
    if "SH" in parts:
        return "SH"
    if "SZ" in parts:
        return "SZ"
    if code.startswith(_SH_PREFIXES):
        return "SH"
    if code.startswith(_SZ_PREFIXES):
        return "SZ"
    return ""


def _to_cn_date(value: int) -> date | None:
    if not value:
        return None
    return datetime.fromtimestamp(value / 1000.0, tz=CN_TZ).date()


def _normalize_float(value: float) -> float | None:
    if math.isnan(value):
        return None
    if abs(value) >= 1.79e308:
        return None
    return value


def _build_numeric_record(
    *,
    ts_code: str,
    market: str,
    dataset_id: int,
    record_no: int,
    file_name: str,
    file_size: int,
    announce_ms: int,
    report_ms: int,
    values: list[float],
    extra: dict[str, Any] | None = None,
) -> FinanceDatRecord:
    normalized = [_normalize_float(value) for value in values]
    raw_json: dict[str, Any] = {
        "announce_ms": announce_ms,
        "report_ms": report_ms,
        "value_count": len(values),
    }
    if extra:
        raw_json.update(extra)
    return FinanceDatRecord(
        ts_code=ts_code,
        market=market,
        dataset_id=dataset_id,
        record_no=record_no,
        announce_date=_to_cn_date(announce_ms),
        report_date=_to_cn_date(report_ms),
        value_1=normalized[0] if len(normalized) > 0 else None,
        value_2=normalized[1] if len(normalized) > 1 else None,
        value_3=normalized[2] if len(normalized) > 2 else None,
        value_4=normalized[3] if len(normalized) > 3 else None,
        value_5=normalized[4] if len(normalized) > 4 else None,
        value_6=normalized[5] if len(normalized) > 5 else None,
        flag_1=None,
        flag_2=None,
        file_name=file_name,
        file_size=file_size,
        raw_json=raw_json,
    )


def _parse_numeric_dataset(
    payload: bytes,
    *,
    ts_code: str,
    market: str,
    dataset_id: int,
    record_no: int,
    file_name: str,
    file_size: int,
    date_count: int,
    double_count: int,
    keep_all_values: bool = False,
) -> FinanceDatRecord:
    prefix = "<" + ("Q" * date_count) + ("d" * double_count)
    values = struct.unpack(prefix, payload)
    date_values = list(values[:date_count])
    numeric_values = list(values[date_count:])
    extra: dict[str, Any] = {}
    if date_count >= 3:
        extra["extra_date_ms"] = date_values[2]
    if keep_all_values:
        extra["values"] = [_normalize_float(value) for value in numeric_values]
    return _build_numeric_record(
        ts_code=ts_code,
        market=market,
        dataset_id=dataset_id,
        record_no=record_no,
        file_name=file_name,
        file_size=file_size,
        announce_ms=date_values[0],
        report_ms=date_values[1],
        values=numeric_values,
        extra=extra,
    )


def _parse_text_dataset(
    payload: bytes,
    *,
    ts_code: str,
    market: str,
    dataset_id: int,
    record_no: int,
    file_name: str,
    file_size: int,
) -> FinanceDatRecord:
    announce_ms, report_ms = struct.unpack("<QQ", payload[:16])
    text = payload[16:].split(b"\x00", 1)[0].decode("gbk", errors="ignore").strip()
    return FinanceDatRecord(
        ts_code=ts_code,
        market=market,
        dataset_id=dataset_id,
        record_no=record_no,
        announce_date=_to_cn_date(announce_ms),
        report_date=_to_cn_date(report_ms),
        value_1=None,
        value_2=None,
        value_3=None,
        value_4=None,
        value_5=None,
        value_6=None,
        flag_1=None,
        flag_2=None,
        file_name=file_name,
        file_size=file_size,
        raw_json={
            "announce_ms": announce_ms,
            "report_ms": report_ms,
            "text": text,
        },
    )


def _parse_7004_record(
    payload: bytes,
    *,
    ts_code: str,
    market: str,
    record_no: int,
    file_name: str,
    file_size: int,
) -> FinanceDatRecord:
    announce_ms, report_ms, value_1, value_2, value_3, value_4, flag_1, flag_2 = struct.unpack("<QQddddII", payload)
    raw_json = {
        "announce_ms": announce_ms,
        "report_ms": report_ms,
        "value_count": 4,
        "flag_1": flag_1,
        "flag_2": flag_2,
    }
    return FinanceDatRecord(
        ts_code=ts_code,
        market=market,
        dataset_id=7004,
        record_no=record_no,
        announce_date=_to_cn_date(announce_ms),
        report_date=_to_cn_date(report_ms),
        value_1=_normalize_float(value_1),
        value_2=_normalize_float(value_2),
        value_3=_normalize_float(value_3),
        value_4=_normalize_float(value_4),
        value_5=None,
        value_6=None,
        flag_1=flag_1,
        flag_2=flag_2,
        file_name=file_name,
        file_size=file_size,
        raw_json=raw_json,
    )


def _parse_7005_record(
    payload: bytes,
    *,
    ts_code: str,
    market: str,
    record_no: int,
    file_name: str,
    file_size: int,
) -> FinanceDatRecord:
    announce_ms, report_ms, value_1, value_2, value_3, value_4, value_5, value_6 = struct.unpack("<QQdddddd", payload)
    raw_json = {
        "announce_ms": announce_ms,
        "report_ms": report_ms,
        "value_count": 6,
    }
    return FinanceDatRecord(
        ts_code=ts_code,
        market=market,
        dataset_id=7005,
        record_no=record_no,
        announce_date=_to_cn_date(announce_ms),
        report_date=_to_cn_date(report_ms),
        value_1=_normalize_float(value_1),
        value_2=_normalize_float(value_2),
        value_3=_normalize_float(value_3),
        value_4=_normalize_float(value_4),
        value_5=_normalize_float(value_5),
        value_6=_normalize_float(value_6),
        flag_1=None,
        flag_2=None,
        file_name=file_name,
        file_size=file_size,
        raw_json=raw_json,
    )


def parse_finance_dat(path_like: str | Path) -> FinanceDatFile:
    path = Path(path_like)
    match = _FILE_NAME_RE.match(path.name)
    if not match:
        raise ValueError(f"unsupported finance dat filename: {path.name}")
    code = match.group("code")
    dataset_id = int(match.group("dataset"))
    market = _infer_market(code, path)
    ts_code = f"{code}.{market}" if market else code
    payload = path.read_bytes()

    if dataset_id == 7001:
        record_size = 1264
        parser = lambda data, **kwargs: _parse_numeric_dataset(  # noqa: E731
            data, dataset_id=7001, date_count=2, double_count=156, keep_all_values=True, **kwargs
        )
    elif dataset_id == 7002:
        record_size = 664
        parser = lambda data, **kwargs: _parse_numeric_dataset(  # noqa: E731
            data, dataset_id=7002, date_count=3, double_count=80, keep_all_values=True, **kwargs
        )
    elif dataset_id == 7003:
        record_size = 920
        parser = lambda data, **kwargs: _parse_numeric_dataset(  # noqa: E731
            data, dataset_id=7003, date_count=3, double_count=112, keep_all_values=True, **kwargs
        )
    elif dataset_id == 7004:
        record_size = 56
        parser = _parse_7004_record
    elif dataset_id == 7005:
        record_size = 64
        parser = _parse_7005_record
    elif dataset_id == 7006:
        record_size = 416
        parser = lambda data, **kwargs: _parse_text_dataset(data, dataset_id=7006, **kwargs)  # noqa: E731
    elif dataset_id == 7007:
        record_size = 416
        parser = lambda data, **kwargs: _parse_text_dataset(data, dataset_id=7007, **kwargs)  # noqa: E731
    elif dataset_id == 7008:
        record_size = 344
        parser = lambda data, **kwargs: _parse_numeric_dataset(  # noqa: E731
            data, dataset_id=7008, date_count=2, double_count=41, keep_all_values=True, **kwargs
        )
    else:
        raise ValueError(f"unsupported finance dataset id: {dataset_id}")

    if len(payload) % record_size != 0:
        raise ValueError(
            f"file size {len(payload)} is not aligned to dataset {dataset_id} record size {record_size}: {path.name}"
        )

    records: list[FinanceDatRecord] = []
    for record_no, offset in enumerate(range(0, len(payload), record_size)):
        record_payload = payload[offset : offset + record_size]
        records.append(
            parser(
                record_payload,
                ts_code=ts_code,
                market=market,
                record_no=record_no,
                file_name=path.name,
                file_size=len(payload),
            )
        )

    return FinanceDatFile(
        path=path,
        code=code,
        market=market,
        dataset_id=dataset_id,
        record_size=record_size,
        records=records,
    )
