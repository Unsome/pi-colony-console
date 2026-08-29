"""
build_feasible.py - 성계별 생산 가능 P3 목록(가격 독립)과 생산 템플릿을 오프라인 생성.

산출물:
  data/feasible/{system_id}.json   - 생산 가능 P3 + 미너4·생산1 템플릿 매핑
  templates/production/{system_id}/{P3}.json - P3별 조합 생산 템플릿(CCU4)

가격은 여기서 다루지 않는다(클라이언트가 prices.json 으로 정렬). 성계 추가 시 이 스크립트만
다시 돌리면 된다: python engine/build_feasible.py <system_id>
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pi_optimizer import pi_data, universe, recommend
import gen_production

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY_P3 = recommend.DAILY_P3_PER_LINE * 2   # CCU4 조합 생산 행성 = 2 라인 = 144/일

# P0 이름 -> P1 이름은 그래프로, 미너 템플릿 파일명은 P1 이름 그대로 사용
MINER_DIR = os.path.join(ROOT, "templates", "miners")


def build(system_id):
    g = pi_data.load_graph()
    sysinfo = universe.get_system(system_id, allow_esi=True)
    ptypes = [p["type"] for p in sysinfo["planets"]]

    plans = recommend.recommend(g, ptypes, {}, daily_p3=DAILY_P3)

    prod_dir = os.path.join(ROOT, "templates", "production", str(system_id))
    os.makedirs(prod_dir, exist_ok=True)

    p3_entries = []
    for p in plans:
        p3_id = p["id"]
        p3_name = p["name"]
        prod_type = p["production_planet_type"]

        # 생산 템플릿 생성
        tmpl = gen_production.build_production_template(g, p3_id, prod_type)
        prod_file = f"{p3_name}.json"
        with open(os.path.join(prod_dir, prod_file), "w", encoding="utf-8") as f:
            json.dump(tmpl, f, ensure_ascii=False, indent=2)

        # 미너 카드 정보
        miners = []
        for m in p["miners"]:
            p1_name = m["p1"]
            # P0 이름
            p1_id = g.name_to_id[p1_name]
            p0_id = g.p1_to_p0[p1_id]
            p0_name = g.p0_names[p0_id]
            miner_file = f"{p1_name}.json"
            miner_exists = os.path.exists(os.path.join(MINER_DIR, miner_file))
            miners.append({
                "p1": p1_name, "p0": p0_name, "planet_type": m["planet_type"],
                "template": f"templates/miners/{miner_file}" if miner_exists else None,
            })

        # 생산 P2 배분 정보
        p2a, p2b = g.p3_p2_inputs(p3_id)
        p3_entries.append({
            "id": p3_id, "name": p3_name,
            "daily_units": int(DAILY_P3),
            "production": {
                "planet_type": prod_type,
                "template": f"templates/production/{system_id}/{prod_file}",
                "p2_split": [{"p2": g.name(p2a), "aif": 4}, {"p2": g.name(p2b), "aif": 4}],
                "p3_aif": 2,
            },
            "miners": miners,
        })

    out = {
        "system": {
            "id": system_id, "name": sysinfo.get("name"),
            "region": sysinfo.get("region"), "security": sysinfo.get("security"),
            "planets": ptypes,
        },
        "colony": {"miners": 4, "production": 1, "skill": "44433 (CCU4/IC4)",
                   "lines": 2, "daily_p3": int(DAILY_P3)},
        "p3s": p3_entries,
    }
    os.makedirs(os.path.join(ROOT, "data", "feasible"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "feasible", f"{system_id}.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"{sysinfo.get('name')} (#{system_id}): 생산 가능 P3 {len(p3_entries)}종, "
          f"생산 템플릿 {len(p3_entries)}개 생성")
    _update_systems_index()


def _update_systems_index():
    """data/systems.json - 드롭다운용 성계 목록 갱신."""
    feas_dir = os.path.join(ROOT, "data", "feasible")
    systems = []
    for fn in sorted(os.listdir(feas_dir)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(feas_dir, fn), encoding="utf-8") as f:
            d = json.load(f)
        s = d["system"]
        systems.append({"id": s["id"], "name": s["name"], "region": s.get("region")})
    with open(os.path.join(ROOT, "data", "systems.json"), "w", encoding="utf-8") as f:
        json.dump({"systems": systems}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    sid = int(sys.argv[1]) if len(sys.argv) > 1 else 30045351
    build(sid)
