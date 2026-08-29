"""
build_graph.py - PI 레시피 그래프(pi_graph.json) 생성기 (오프라인, 패치 시에만 실행)

데이터 출처
-----------
1. P2/P3/P4 레시피, 제품/구조물 typeID: DalShooth EVE_PI_Templates 저장소의
   'Factory - *.json' 템플릿 라우트를 파싱해서 추출 (권위 있는 실게임 데이터).
2. P0->P1 매핑, P0 typeID/이름: 같은 저장소의 'Miner - *.json' 추출기/공장 핀에서 추출.
3. 행성타입->P0 집합: 정규 테이블(임베드). 템플릿의 'Pln' 필드는 "제작 당시 행성"이라
   실제 자원 가용 행성이 아니므로 신뢰하지 않는다 (예: Silicon 미너가 Temperate로 저장됨).

사용법
------
    python -m pi_optimizer.build_graph <templates_dir> [out_path]

templates_dir 는 DalShooth 저장소의 PlanetaryInteractionTemplates 폴더 경로.
"""
import json
import os
import re
import glob
import sys
from collections import defaultdict

# ---------------------------------------------------------------------------
# 정규 상수 (안정적, 게임 패치로 거의 안 변함)
# ---------------------------------------------------------------------------

# P0 (raw) typeID -> 이름
P0_NAMES = {
    2073: "Microorganisms", 2267: "Base Metals", 2268: "Aqueous Liquids",
    2270: "Noble Metals", 2272: "Heavy Metals", 2286: "Planktic Colonies",
    2287: "Complex Organisms", 2288: "Carbon Compounds", 2305: "Autotrophs",
    2306: "Non-CS Crystals", 2307: "Felsic Magma", 2308: "Suspended Plasma",
    2309: "Ionic Solutions", 2310: "Noble Gas", 2311: "Reactive Gas",
}

# 행성타입 typeID -> 이름
PLANET_TYPE_NAMES = {
    11: "Temperate", 12: "Ice", 13: "Gas", 2014: "Oceanic",
    2015: "Lava", 2016: "Barren", 2017: "Storm", 2063: "Plasma",
}

# 행성타입 이름 -> 추출 가능한 P0 이름 집합 (정규)
PLANET_P0 = {
    "Temperate": ["Aqueous Liquids", "Autotrophs", "Carbon Compounds", "Complex Organisms", "Microorganisms"],
    "Ice":       ["Aqueous Liquids", "Heavy Metals", "Microorganisms", "Noble Gas", "Planktic Colonies"],
    "Gas":       ["Aqueous Liquids", "Base Metals", "Ionic Solutions", "Noble Gas", "Reactive Gas"],
    "Oceanic":   ["Aqueous Liquids", "Carbon Compounds", "Complex Organisms", "Microorganisms", "Planktic Colonies"],
    "Lava":      ["Base Metals", "Felsic Magma", "Heavy Metals", "Non-CS Crystals", "Suspended Plasma"],
    "Barren":    ["Aqueous Liquids", "Base Metals", "Carbon Compounds", "Microorganisms", "Noble Metals"],
    "Storm":     ["Aqueous Liquids", "Base Metals", "Ionic Solutions", "Noble Gas", "Suspended Plasma"],
    "Plasma":    ["Base Metals", "Heavy Metals", "Noble Metals", "Non-CS Crystals", "Suspended Plasma"],
}

# 구조물 typeID (핀 T 값). 파싱 시 공장/추출기 판별에 사용.
STRUCTURE = {
    3063: "Extractor Control Unit", 3064: "Extractor Control Unit",
    3067: "Extractor Control Unit", 3068: "Extractor Control Unit",
    2490: "Basic Industry Facility",       # P1 생산 (Basic)
    2473: "Basic Industry Facility",
    2474: "Advanced Industry Facility",     # P2/P3 생산 (Advanced)
    2475: "High-Tech Production Plant",     # P4 생산 (High-Tech)
}
EXTRACTOR_T = {3063, 3064, 3067, 3068}
FACTORY_T = {2490, 2473, 2474, 2475}

# DalShooth 원본 파일명 오타 보정
P1_NAME_FIX = {"Chiral Stuctures": "Chiral Structures"}


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_miners(tdir):
    """Miner 템플릿에서 P0->P1 매핑과 P1 typeID/이름을 추출."""
    p0_to_p1 = {}
    p1_names = {}
    for f in glob.glob(os.path.join(tdir, "Miner -*.json")):
        d = _load(f)
        name = re.sub(r"^Miner - ", "", os.path.basename(f)).replace(".json", "")
        p1_name = name.split(" - ")[-1].strip()
        p1_name = P1_NAME_FIX.get(p1_name, p1_name)
        pins = d["P"]
        # 추출기: heads>0. 그 S = 추출 대상 P0 typeID.
        ext_p0 = {p["S"] for p in pins if p["H"] > 0 and p["S"] is not None}
        # P1 공장: heads==0 & S 지정 (런치패드/저장고는 S=null이라 자동 제외).
        # 주: 미너 템플릿의 Basic Industry Facility typeID는 버전에 따라 여러 값(2481/2483 등)
        # 이라 T로 필터하지 않고 S 유무로 판별한다.
        p1_ids = {p["S"] for p in pins if p["H"] == 0 and p["S"] is not None}
        for p1 in p1_ids:
            p1_names[p1] = p1_name
        # P0->P1 링크: 한 미너 안의 유일한 P0와 유일한 P1을 연결
        if len(ext_p0) == 1 and len(p1_ids) == 1:
            p0_to_p1[next(iter(ext_p0))] = next(iter(p1_ids))
    return p0_to_p1, p1_names


def parse_factories(tdir):
    """Factory 템플릿 라우트에서 각 제품의 직접 레시피(입력 typeID+수량, 출력 수량) 추출."""
    recipes = {}
    for f in glob.glob(os.path.join(tdir, "Factory -*.json")):
        d = _load(f)
        name = re.sub(r"^Factory - ", "", os.path.basename(f)).replace(".json", "")
        pins = d["P"]
        fac = {i for i, p in enumerate(pins)
               if p["S"] is not None and p["T"] in (2474, 2475, 2490)}
        if not fac:
            continue
        svals = {pins[i]["S"] for i in fac}
        if len(svals) != 1:
            continue  # 한 공장 템플릿은 단일 제품만 생산해야 함
        out = next(iter(svals))
        inputs = defaultdict(int)
        out_qty = None
        for r in d["R"]:
            path_pins, T, Q = r["P"], r["T"], r["Q"]
            src, dst = path_pins[0], path_pins[-1]
            if src in fac and T == out:        # 공장->저장 = 출력
                out_qty = Q
            elif dst in fac and T != out:      # 저장->공장 = 입력
                inputs[T] = Q
        recipes[out] = {"name": name, "out_qty": out_qty, "inputs": dict(inputs)}
    return recipes


def build(tdir):
    p0_to_p1, p1_names = parse_miners(tdir)
    recipes = parse_factories(tdir)

    # 이름 맵
    name_of = {}
    name_of.update(P0_NAMES)
    name_of.update(p1_names)
    for tid, r in recipes.items():
        name_of[tid] = r["name"]

    p1_ids = set(p1_names)
    p0_ids = set(P0_NAMES)

    # 티어 계산: P0=0, P1=1, 그 외 = max(입력 티어)+1
    tier_memo = {}

    def tier(tid):
        if tid in p0_ids:
            return 0
        if tid in p1_ids:
            return 1
        if tid in tier_memo:
            return tier_memo[tid]
        if tid not in recipes:
            return None
        ts = [tier(x) for x in recipes[tid]["inputs"]]
        if any(t is None for t in ts):
            tier_memo[tid] = None
            return None
        tier_memo[tid] = max(ts) + 1
        return tier_memo[tid]

    commodities = {}
    # P1 항목 (레시피는 P0 1종에서 나오지만 여기선 tier/name만 기록)
    for p1, nm in p1_names.items():
        commodities[str(p1)] = {"name": nm, "tier": 1, "out_qty": 20,
                                "inputs": {}}
    # P2+ 항목
    for tid, r in recipes.items():
        t = tier(tid)
        commodities[str(tid)] = {
            "name": r["name"], "tier": t, "out_qty": r["out_qty"],
            "inputs": {str(k): v for k, v in r["inputs"].items()},
        }

    graph = {
        "_meta": {
            "source": "DalShooth/EVE_PI_Templates (parsed) + canonical tables",
            "note": "P0/P1/planet-type tables are canonical; P2+ recipes parsed from templates.",
        },
        "p0_names": {str(k): v for k, v in P0_NAMES.items()},
        "p1_names": {str(k): v for k, v in p1_names.items()},
        "p0_to_p1": {str(k): v for k, v in p0_to_p1.items()},
        "p1_to_p0": {str(v): k for k, v in p0_to_p1.items()},
        "planet_type_names": {str(k): v for k, v in PLANET_TYPE_NAMES.items()},
        "planet_p0": PLANET_P0,
        "structure": {str(k): v for k, v in STRUCTURE.items()},
        "commodities": commodities,
    }
    return graph


def main():
    if len(sys.argv) < 2:
        print("usage: python -m pi_optimizer.build_graph <templates_dir> [out_path]")
        sys.exit(1)
    tdir = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(__file__), "data", "pi_graph.json")
    graph = build(tdir)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    n = len(graph["commodities"])
    tiers = defaultdict(int)
    for c in graph["commodities"].values():
        tiers[c["tier"]] += 1
    print(f"wrote {out}: {n} commodities  tiers={dict(sorted(tiers.items(), key=lambda x:(x[0] is None,x[0])))}")


if __name__ == "__main__":
    main()
