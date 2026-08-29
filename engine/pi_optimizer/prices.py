"""
prices.py - 지타(더 포지) 7일 평균 가격.

프로덕션 파이프라인 (사용자 확정)
--------------------------------
- 일 1회 cron 으로 ESI 마켓 히스토리에서 최근 7일 daily `average` 를 평균 -> data/prices.json.
- 프론트/엔진은 캐시된 prices.json 만 읽는다 (정적 배포 친화적).

주의
----
- 이것은 히스토리 daily average 의 7일 평균이다. "지타 스플릿"(최우선 매수/매도 중간)은
  실시간 오더북이라 별도 소스가 필요 - v1은 히스토리 평균으로 간다.
- 히스토리는 배열 위치가 아니라 ISO 날짜로 필터하고 거래일수로 게이팅해야 얕은 품목이
  왜곡되지 않는다 (사용자 생산 스캐너 교훈과 동일).
"""
import json
import os
import time
import urllib.request
from datetime import datetime, timezone, timedelta

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_CACHE = os.path.join(_DATA_DIR, "prices.json")
_FIXTURE = os.path.join(_DATA_DIR, "prices_fixture.json")
_ESI = "https://esi.evetech.net/latest"
THE_FORGE = 10000002  # 지타가 속한 리전

WINDOW_DAYS = 7
MIN_TRADE_DAYS = 4  # 최근 창 안에서 거래일이 이보다 적으면 신뢰도 낮음 -> None 처리


def load_prices():
    """캐시(prices.json) 우선, 없으면 플레이스홀더 픽스처. {typeID(int): price} 반환."""
    for path in (_CACHE, _FIXTURE):
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            prices = {int(k): v for k, v in raw.get("prices", {}).items()}
            prices["_meta"] = raw.get("_meta", {})
            return prices
    return {"_meta": {"source": "none"}}


def _esi_history(type_id, region=THE_FORGE):
    url = f"{_ESI}/markets/{region}/history/?type_id={type_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "pi-optimizer/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def seven_day_avg(type_id, region=THE_FORGE, window=WINDOW_DAYS):
    """최근 window 일(캘린더 기준) daily average 의 평균. 거래일 부족 시 None."""
    hist = _esi_history(type_id, region)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window)).date().isoformat()
    recent = [h for h in hist if h["date"] >= cutoff]
    if len(recent) < MIN_TRADE_DAYS:
        return None
    return sum(h["average"] for h in recent) / len(recent)


def update_cache(type_ids, region=THE_FORGE, sleep=0.1):
    """cron 용: 주어진 typeID 들의 7일 평균을 계산해 prices.json 에 저장."""
    prices = {}
    for tid in type_ids:
        try:
            v = seven_day_avg(tid, region)
            if v is not None:
                prices[str(tid)] = round(v, 2)
        except Exception as e:  # noqa
            print(f"  price fetch failed {tid}: {e}")
        time.sleep(sleep)
    out = {"_meta": {"source": "ESI history 7d avg", "region": region,
                     "updated": datetime.now(timezone.utc).isoformat()},
           "prices": prices}
    with open(_CACHE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return len(prices)
