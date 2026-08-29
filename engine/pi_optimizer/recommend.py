"""
recommend.py - 디커플드 5행성 콜로니 추천 엔진 (순수 함수, I/O 없음).

콜로니 구조 (사용자 확정, 개정판)
--------------------------------
- 미너 행성 4개: 각 행성이 P0 1종 추출 -> P1 1종 생산 (MattFalahe "Miners CCU IV" 템플릿 사용).
  P2를 한 행성에서 만들려면 추출기 2개를 서로 다른 핫스팟에 박아야 해서 규격화 불가 ->
  P1만 뽑는 단일-추출 미너로 분리.
- 생산 행성 1개: 미너에서 온 P1 4종을 받아 P2 2종 + P3 1종 생산. Gas 배제(반경 커서 링크 과부하).
- 스킬 44433 (IC4=5행성/캐릭, CCU4).

구조적 귀결
-----------
- 미너 4개 = P1 4종 -> P2 2종 -> P3 1종. 따라서 **단일 P3 제품**. (커플드의 Config 1/2/S 구분 소멸)
- 2입력 P3 15종은 전부 P1 정확히 4종 -> 후보. 3입력 P3 6종은 P1 5~6종 -> 미너 4개로 불가, 배제.

산출량
------
- MattFalahe CCU IV 미너 = ECU 1(헤드 10) + BIF 8 -> P1 320/시(7,680/일). P3 라인 하나가
  입력당 필요로 하는 건 80/시뿐 -> 미너가 약 4배 과잉공급. 즉 병목은 미너가 아니라 생산 행성.
- 생산 행성이 돌리는 P3 라인 수(CCU4 피팅 한계)가 산출을 결정. 1라인=72/일.
  실제 라인 수는 생산 행성 템플릿 확정 시 고정 -> daily_p3 파라미터로 노출.
- 미너 과잉공급분(잉여 P1)은 판매 여지가 있으나 v1 미반영(마켓 뎁스/물류 별도).

주의: 산출은 표준 농도·44433 스킬 가정의 명목값. 실제 행성 스캔 시 달라짐.
POCO 수출세·마켓 뎁스·잉여 P1 판매 미반영.
"""

# 산출 상수
DAILY_P3_PER_LINE = 72.0   # P3 라인 1개 완전가동 = 3/시 × 24 (생산 행성 템플릿 확정 시 조정)
MAX_MINERS = 4             # 미너 행성 수 = 확보 가능한 서로 다른 P1 종류 상한


# ---------------------------------------------------------------------------
# 이분 매칭 (Kuhn): P1 슬롯 -> 물리 행성
# ---------------------------------------------------------------------------
def _augment(s, allowed, planet_types, match_r, visited):
    for pj, pt in enumerate(planet_types):
        if pt in allowed[s] and not visited[pj]:
            visited[pj] = True
            if match_r[pj] == -1 or _augment(match_r[pj], allowed, planet_types, match_r, visited):
                match_r[pj] = s
                return True
    return False


def _max_matching(allowed, planet_types):
    match_r = [-1] * len(planet_types)
    cnt = 0
    for s in range(len(allowed)):
        visited = [False] * len(planet_types)
        if _augment(s, allowed, planet_types, match_r, visited):
            cnt += 1
    return cnt, match_r


def _feasible(slots, planet_types, capable_fn):
    """slots(P1 typeID 리스트, 서로 다른 종류)를 서로 다른 미너 행성에 배치하고,
    비-Gas 생산 행성 1개를 남길 수 있으면 (True, production_type, assignment, remaining) 반환.
    assignment = 슬롯 순서대로 [(p1_id, 미너 행성타입), ...].
    remaining = 미너/생산에 안 쓰인 남은 물리 행성 타입 리스트."""
    allowed = [capable_fn(p1) for p1 in slots]
    for fi, ft in enumerate(planet_types):
        if ft == "Gas":
            continue  # 생산 행성은 Gas 배제
        rest = planet_types[:fi] + planet_types[fi + 1:]
        cnt, match_r = _max_matching(allowed, rest)
        if cnt == len(slots):
            slot_to_type = {}
            used = set()
            for pj, s in enumerate(match_r):
                if s != -1:
                    slot_to_type[s] = rest[pj]
                    used.add(pj)
            assignment = [(slots[s], slot_to_type[s]) for s in range(len(slots))]
            remaining = [rest[pj] for pj in range(len(rest)) if pj not in used]
            return True, ft, assignment, remaining
    return False, None, None, None


def _price(prices, tid):
    return prices.get(tid, 0.0)


# ---------------------------------------------------------------------------
# 메인 추천 (디커플드 단일 P3)
# ---------------------------------------------------------------------------
def recommend(graph, planet_types, prices, daily_p3=DAILY_P3_PER_LINE):
    """
    planet_types: 성계 행성 타입 이름 리스트.
    prices: {typeID: jita_price}. 없으면 0.
    daily_p3: 생산 행성이 만드는 P3 일산출(라인 수 반영). 기본 1라인=72.
    반환: 플랜 dict 리스트 (일일 생산가치 내림차순). 각 플랜 = 단일 P3.
    """
    cap = graph.p1_capable_planet_types
    plans = []
    for p3 in graph.items_of_tier(3):
        p1_distinct = graph.p3_p1_distinct(p3)
        if len(p1_distinct) > MAX_MINERS:
            continue  # 3입력 P3 등 (P1 5~6종) -> 미너 4개로 불가
        ok, prod_type, assign, remaining = _feasible(p1_distinct, planet_types, cap)
        if not ok:
            continue
        price = _price(prices, p3)
        val = daily_p3 * price
        plans.append({
            "id": p3, "name": graph.name(p3),
            "daily_units": daily_p3, "unit_price": price, "daily_value": val,
            "n_inputs": len(graph.p3_p2_inputs(p3)),
            "p2_inputs": [graph.name(p2) for p2 in graph.p3_p2_inputs(p3)],
            "miners": [{"p1": graph.name(p1), "planet_type": t} for p1, t in assign],
            "production_planet_type": prod_type,
            "spare_planet_types": remaining,
            "planets_used": len(assign) + 1,
        })
    plans.sort(key=lambda p: p["daily_value"], reverse=True)
    return plans
