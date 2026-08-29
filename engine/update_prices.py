"""
update_prices.py - 지타(더 포지) 7일 평균을 ESI에서 긁어 data/prices.json 갱신.

GitHub Action이 하루 1회 실행. P2+P3 전부 긁는다(보조 계산·확장 대비).
ESI 실패/거래일 부족 품목은 건너뛰고, 기존 값이 있으면 유지(직전 good 보존).
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pi_optimizer import pi_data

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "prices.json")
ESI = "https://esi.evetech.net/latest"
THE_FORGE = 10000002
WINDOW_DAYS = 7
MIN_TRADE_DAYS = 4


def esi_history(type_id, region=THE_FORGE):
    url = f"{ESI}/markets/{region}/history/?type_id={type_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "pi-colony-console/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def seven_day_avg(type_id):
    hist = esi_history(type_id)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)).date().isoformat()
    recent = [h for h in hist if h["date"] >= cutoff]
    if len(recent) < MIN_TRADE_DAYS:
        return None
    return sum(h["average"] for h in recent) / len(recent)


def main():
    g = pi_data.load_graph()
    ids = g.items_of_tier(2) + g.items_of_tier(3)

    # 기존 값(직전 good) 로드
    prev = {}
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as f:
                prev = json.load(f).get("prices", {})
        except Exception:
            prev = {}

    prices = dict(prev)
    ok = 0
    for tid in ids:
        try:
            v = seven_day_avg(tid)
            if v is not None:
                prices[str(tid)] = round(v, 2)
                ok += 1
        except Exception as e:  # noqa
            print(f"  skip {tid}: {e}")
        time.sleep(0.1)

    out = {"_meta": {"source": "ESI history 7d avg", "region": THE_FORGE,
                     "updated": datetime.now(timezone.utc).isoformat()},
           "prices": prices}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"updated {ok}/{len(ids)} (총 {len(prices)}종 보유) -> {OUT}")


if __name__ == "__main__":
    main()
