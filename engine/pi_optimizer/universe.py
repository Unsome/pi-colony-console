"""
universe.py - 성계 -> 행성 타입 조회.

우선순위: 로컬 픽스처(data/systems/{id}.json) -> ESI.
정적 웹 배포 시엔 오프라인 배치로 전 성계 픽스처를 미리 굽는 것을 권장
(행성 구성은 SDE 패치 때만 바뀜).
"""
import json
import os
import urllib.request

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_SYS_DIR = os.path.join(_DATA_DIR, "systems")
_ESI = "https://esi.evetech.net/latest"

# ESI planet type_id -> 행성타입 이름
_ESI_PLANET_TYPE = {
    11: "Temperate", 12: "Ice", 13: "Gas", 2014: "Oceanic",
    2015: "Lava", 2016: "Barren", 2017: "Storm", 2063: "Plasma",
}


def _fixture_path(system_id):
    return os.path.join(_SYS_DIR, f"{system_id}.json")


def _from_fixture(system_id):
    p = _fixture_path(system_id)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def _esi_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "pi-optimizer/0.1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _from_esi(system_id):
    sysdata = _esi_get(f"{_ESI}/universe/systems/{system_id}/")
    # 리전 이름 (성계 -> 컨스텔레이션 -> 리전)
    region_name = None
    try:
        con = _esi_get(f"{_ESI}/universe/constellations/{sysdata['constellation_id']}/")
        reg = _esi_get(f"{_ESI}/universe/regions/{con['region_id']}/")
        region_name = reg.get("name")
    except Exception:  # noqa - 리전 조회 실패는 치명적 아님
        pass
    planets = []
    for pl in sysdata.get("planets", []):
        pid = pl["planet_id"]
        pdata = _esi_get(f"{_ESI}/universe/planets/{pid}/")
        ptype = _ESI_PLANET_TYPE.get(pdata.get("type_id"))
        if ptype:
            planets.append({"name": pdata.get("name", str(pid)), "type": ptype})
    return {
        "system_id": system_id,
        "name": sysdata.get("name", str(system_id)),
        "region": region_name,
        "security": sysdata.get("security_status"),
        "source": "ESI",
        "planets": planets,
    }


def get_system(system_id, allow_esi=True, cache_esi=True):
    """성계 정보 dict 반환. 픽스처 우선, 없으면 ESI.
    cache_esi=True면 ESI 조회 결과를 data/systems/{id}.json 에 저장해 다음부턴 재사용."""
    data = _from_fixture(system_id)
    if data is not None:
        return data
    if allow_esi:
        data = _from_esi(system_id)
        if cache_esi:
            try:
                os.makedirs(_SYS_DIR, exist_ok=True)
                with open(_fixture_path(system_id), "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception:  # noqa - 캐시 실패는 치명적 아님
                pass
        return data
    raise FileNotFoundError(
        f"성계 {system_id} 픽스처 없음. ESI 접근 불가 환경이면 오프라인 픽스처를 먼저 생성하세요."
    )


def planet_types(system_id, **kw):
    return [p["type"] for p in get_system(system_id, **kw)["planets"]]
