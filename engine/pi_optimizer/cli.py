"""
cli.py - 성계 선택 -> 추천 P3 조회 (디커플드 모델: 미너 4 + 생산 1).

사용법:
    python -m pi_optimizer.cli <system_id> [--lines N] [--top N] [--no-esi]

예:
    python -m pi_optimizer.cli 30045351            # Iwisoda
    python -m pi_optimizer.cli 30045351 --lines 2  # 생산 행성이 P3 2라인일 때
"""
import argparse
import sys
from collections import Counter

from . import pi_data, universe, prices, recommend


def _force_utf8_stdout():
    """Windows 콘솔(cp949)에서 한글 출력이 깨지지 않게 stdout/stderr를 UTF-8로."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa
            pass


def _fmt(v):
    return f"{v:,.0f}"


def main(argv=None):
    _force_utf8_stdout()
    ap = argparse.ArgumentParser(description="EVE PI 디커플드 5행성 P3 추천 (미너4+생산1)")
    ap.add_argument("system_id", type=int, help="성계 ID (예: 30045351 = Iwisoda)")
    ap.add_argument("--lines", type=int, default=1,
                    help="생산 행성 P3 라인 수 (기본 1). 산출 = 72 × lines")
    ap.add_argument("--top", type=int, default=15, help="표시할 P3 수 (기본 15)")
    ap.add_argument("--no-esi", action="store_true", help="ESI 폴백 비활성 (픽스처만)")
    args = ap.parse_args(argv)

    g = pi_data.load_graph()
    sysinfo = universe.get_system(args.system_id, allow_esi=not args.no_esi)
    ptypes = [p["type"] for p in sysinfo["planets"]]
    px = prices.load_prices()
    price_meta = px.get("_meta", {})
    daily = recommend.DAILY_P3_PER_LINE * args.lines

    comp = ", ".join(f"{t}×{n}" for t, n in Counter(ptypes).most_common())
    print(f"\n성계: {sysinfo['name']} (#{args.system_id})  "
          f"보안 {sysinfo.get('security')}  {sysinfo.get('region','')}")
    print(f"행성 {len(ptypes)}개: {comp}")
    print(f"생산 행성 후보(비-Gas) {sum(1 for t in ptypes if t!='Gas')}개 / "
          f"Gas {ptypes.count('Gas')}개(미너 가능)")
    print(f"가격 소스: {price_meta.get('source','?')}")

    plans = recommend.recommend(
        g, ptypes, {k: v for k, v in px.items() if isinstance(k, int)}, daily_p3=daily)

    if not plans:
        print("\n이 성계에서 디커플드 콜로니로 만들 수 있는 P3가 없습니다.")
        return

    print(f"\n추천 P3 {min(args.top, len(plans))}/{len(plans)} "
          f"(생산 {args.lines}라인 = {_fmt(daily)}개/일, 일일 생산가치 내림차순):\n")
    print("주의: 산출은 표준 농도·44433 스킬 명목값이며 생산 행성 라인 수에 비례. "
          "가격은 위 소스 기준. POCO 수출세·마켓 뎁스·잉여 P1 판매 미반영.\n")

    for i, p in enumerate(plans[:args.top], 1):
        print(f"[{i}] {p['name']}  일가치 {_fmt(p['daily_value'])} ISK  "
              f"({_fmt(p['daily_units'])}/일 × {_fmt(p['unit_price'])})")
        print(f"     P2 경로: {' + '.join(p['p2_inputs'])}")
        miners = ", ".join(f"{m['planet_type']}→{m['p1']}" for m in p["miners"])
        print(f"     미너 4행성: {miners}")
        print(f"     생산 행성: {p['production_planet_type']} (비-Gas)   "
              f"사용 {p['planets_used']}/5행성")
        print()


if __name__ == "__main__":
    main()
