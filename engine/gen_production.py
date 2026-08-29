"""
gen_production.py - 임의 2입력 P3용 P2+P3 조합 생산 행성 템플릿(CCU4) 생성기.

MattFalahe "Factory - Smartfab Units" 순수 P3 템플릿을 물리 스켈레톤(핀 좌표·링크 트리)으로
재사용한다. 팩토리 행성은 추출 핫스팟 의존이 없어 좌표·링크가 P3 종류와 무관하게 통용된다.
leaf 2개를 지워 10 AIF로 만들고(CCU4), 스키매틱·라우트만 대상 P3에 맞게 재작성한다.

배분(비율 1:2:2, 10 AIF = 2 라인):
  - P3   × 2 : 각 10 P2a + 10 P2b 소비 -> 3 P3 생산 (60분)
  - P2a  × 4 : 각 40 P1 + 40 P1 소비 -> 5 P2a
  - P2b  × 4 : 동일
  => 산출 6 P3/시 = 144/일. P2a 20/시 = P2b 20/시 = P3 소비량과 정확히 균형.

Pln 은 배정된 생산 행성 타입으로 설정(게임이 구조물 자동 변환하지만 명시).
"""
import json
import os
import copy

_SKELETON = os.path.join(os.path.dirname(__file__), "skeleton_factory.json")

PLANET_PLN = {"Temperate": 11, "Ice": 12, "Gas": 13, "Oceanic": 2014,
              "Lava": 2015, "Barren": 2016, "Storm": 2017, "Plasma": 2063}

_AIF = 2474
_LPAD = 2552
_DROP_LEAVES = {9, 13}  # 원본(13핀) 1-indexed leaf 2개 삭제 -> 10 AIF


def _load_skeleton():
    with open(_SKELETON, encoding="utf-8") as f:
        return json.load(f)


def build_production_template(graph, p3_id, production_planet_type):
    """graph(PiGraph), P3 typeID, 생산 행성 타입 이름 -> 조합 템플릿 dict 반환."""
    p2a, p2b = graph.p3_p2_inputs(p3_id)          # 2 P2 typeID
    p2a_p1 = list(graph.commodities[p2a]["inputs"].keys())  # 2 P1
    p2b_p1 = list(graph.commodities[p2b]["inputs"].keys())

    d = _load_skeleton()
    pins = d["P"]
    lp1 = [i for i, p in enumerate(pins) if p["T"] == _LPAD][0] + 1  # 1-idx launchpad

    keep_old1 = [i + 1 for i in range(len(pins)) if (i + 1) not in _DROP_LEAVES]
    old2new = {o: n for n, o in enumerate(keep_old1, start=1)}

    newpins = [copy.deepcopy(pins[o - 1]) for o in keep_old1]

    aif_old = [o for o in keep_old1 if pins[o - 1]["T"] == _AIF]
    # 배정: 2 P3, 4 P2a, 4 P2b
    role = {}
    for i, o in enumerate(aif_old):
        role[o] = "P3" if i < 2 else ("P2A" if i < 6 else "P2B")

    for o in aif_old:
        n = old2new[o]
        newpins[n - 1]["S"] = {"P3": p3_id, "P2A": p2a, "P2B": p2b}[role[o]]

    # 원본 각 AIF의 입력/출력 경로 추출
    in_paths, out_path = {}, {}
    for r in d["R"]:
        p = r["P"]; src, dst = p[0], p[-1]
        if src == lp1 and dst != lp1:
            in_paths.setdefault(dst, []).append(p)
        elif dst == lp1 and src != lp1:
            out_path[src] = p

    def remap(path):
        return [old2new[x] for x in path]

    INPUTS = {
        "P2A": [(p2a_p1[0], 40), (p2a_p1[1], 40)],
        "P2B": [(p2b_p1[0], 40), (p2b_p1[1], 40)],
        "P3":  [(p2a, 10), (p2b, 10)],
    }
    OUTPUT = {"P2A": (p2a, 5), "P2B": (p2b, 5), "P3": (p3_id, 3)}

    newR = []
    for o in aif_old:
        base_in = in_paths[o][0]
        for (T, Q) in INPUTS[role[o]]:
            newR.append({"P": remap(base_in), "Q": Q, "T": T})
        T, Q = OUTPUT[role[o]]
        newR.append({"P": remap(out_path[o]), "Q": Q, "T": T})

    newL = []
    for l in d["L"]:
        if l["S"] in _DROP_LEAVES or l["D"] in _DROP_LEAVES:
            continue
        nl = copy.deepcopy(l); nl["S"] = old2new[l["S"]]; nl["D"] = old2new[l["D"]]
        newL.append(nl)

    p3name = graph.name(p3_id)
    out = {
        "CmdCtrLv": 4,
        "Cmt": f"Factory - {production_planet_type} - {p3name} (P2+P3 combined, CCU IV) "
               f"[2 P3 + 4 {graph.name(p2a)} + 4 {graph.name(p2b)}]",
        "Diam": d["Diam"],
        "L": newL,
        "P": newpins,
        "Pln": PLANET_PLN.get(production_planet_type, d["Pln"]),
        "R": newR,
    }
    # 검증
    nP = len(newpins)
    assert all(1 <= x <= nP for r in newR for x in r["P"])
    assert all(1 <= l["S"] <= nP and 1 <= l["D"] <= nP for l in newL)
    return out
