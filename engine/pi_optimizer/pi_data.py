"""
pi_data.py - PI 레시피 그래프 로더 및 조회 헬퍼.

pi_graph.json (build_graph.py 생성물)을 로드하고, 추천 엔진이 쓰는
파생 조회들을 제공한다. 순수 데이터 계층 - 네트워크 I/O 없음.
"""
import json
import os
from functools import lru_cache

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_GRAPH_PATH = os.path.join(_DATA_DIR, "pi_graph.json")


class PiGraph:
    """PI 레시피 그래프 래퍼. 모든 typeID는 int로 정규화."""

    def __init__(self, raw):
        self.p0_names = {int(k): v for k, v in raw["p0_names"].items()}
        self.p1_names = {int(k): v for k, v in raw["p1_names"].items()}
        self.p0_to_p1 = {int(k): int(v) for k, v in raw["p0_to_p1"].items()}
        self.p1_to_p0 = {int(k): int(v) for k, v in raw["p1_to_p0"].items()}
        self.planet_type_names = {int(k): v for k, v in raw["planet_type_names"].items()}
        self.planet_p0 = raw["planet_p0"]  # name -> [P0 name,...]
        self.commodities = {}
        for k, v in raw["commodities"].items():
            self.commodities[int(k)] = {
                "name": v["name"], "tier": v["tier"], "out_qty": v["out_qty"],
                "inputs": {int(ik): iv for ik, iv in v["inputs"].items()},
            }
        self.name_to_id = {}
        for tid in self.commodities:
            self.name_to_id[self.commodities[tid]["name"]] = tid
        for tid, nm in {**self.p0_names, **self.p1_names}.items():
            self.name_to_id.setdefault(nm, tid)

    # --- 기본 조회 ---
    def name(self, tid):
        if tid in self.commodities:
            return self.commodities[tid]["name"]
        return self.p0_names.get(tid) or self.p1_names.get(tid) or f"type#{tid}"

    def tier(self, tid):
        if tid in self.commodities:
            return self.commodities[tid]["tier"]
        if tid in self.p0_names:
            return 0
        if tid in self.p1_names:
            return 1
        return None

    def items_of_tier(self, t):
        return [tid for tid, c in self.commodities.items() if c["tier"] == t]

    # --- 커플드 모델 전용 파생 조회 ---
    @lru_cache(maxsize=None)
    def p2_required_p0(self, p2_id):
        """P2를 만드는 데 필요한 P0 이름 집합 (P2 -> 2 P1 -> 2 P0)."""
        p1s = tuple(self.commodities[p2_id]["inputs"].keys())
        p0names = []
        for p1 in p1s:
            p0 = self.p1_to_p0.get(p1)
            if p0 is None:
                return None  # 이 P2는 P1이 아닌 입력을 가짐(비정상) -> 커플드 불가
            p0names.append(self.p0_names[p0])
        return frozenset(p0names)

    @lru_cache(maxsize=None)
    def p2_capable_planet_types(self, p2_id):
        """이 P2를 단일 행성에서 자급(2 P0 추출->2 P1->P2)할 수 있는 행성타입 집합.
        두 P0가 모두 그 행성타입에서 추출 가능해야 한다. (커플드 모델용)"""
        req = self.p2_required_p0(p2_id)
        if req is None:
            return frozenset()
        out = set()
        for ptype, p0list in self.planet_p0.items():
            if req <= set(p0list):
                out.add(ptype)
        return frozenset(out)

    def p3_p2_inputs(self, p3_id):
        """P3의 입력 P2 typeID 리스트 (2개 또는 3개)."""
        return list(self.commodities[p3_id]["inputs"].keys())

    # --- 디커플드 모델(미너 4 + 생산 1) 전용 파생 조회 ---
    @lru_cache(maxsize=None)
    def p1_capable_planet_types(self, p1_id):
        """이 P1을 추출·생산할 수 있는 행성타입 집합 (P1 -> P0 1종 -> 그 P0를 가진 행성).
        미너 행성은 P0 1종만 추출하므로 커플드보다 훨씬 느슨하다."""
        p0 = self.p1_to_p0.get(p1_id)
        if p0 is None:
            return frozenset()
        p0name = self.p0_names[p0]
        return frozenset(pt for pt, p0list in self.planet_p0.items() if p0name in p0list)

    def p3_p1_multiset(self, p3_id):
        """P3의 모든 P1 입력 (P3 -> P2들 -> P1들). 2입력 P3=4개, 3입력=6개 (공유 시 중복)."""
        out = []
        for p2 in self.p3_p2_inputs(p3_id):
            out += list(self.commodities[p2]["inputs"].keys())
        return out

    def p3_p1_distinct(self, p3_id):
        """P3가 요구하는 서로 다른 P1 종류 리스트. 디커플드 미너 수 제약(<=4)에 사용."""
        return list(dict.fromkeys(self.p3_p1_multiset(p3_id)))


@lru_cache(maxsize=1)
def load_graph(path=_GRAPH_PATH):
    with open(path, encoding="utf-8") as f:
        return PiGraph(json.load(f))
