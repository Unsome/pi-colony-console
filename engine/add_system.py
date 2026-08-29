"""
add_system.py - 성계 추가 (개인용, 파일 단계).

성계 ID 입력 -> ESI로 행성 종류 스캔 -> 성계별 행성정보/생산가능 P3/생산 템플릿 생성
-> 드롭다운 목록 갱신 -> git 자동 커밋·푸시.

사용:
    python engine/add_system.py <system_id>              # 스캔+생성+커밋+푸시
    python engine/add_system.py <system_id> --no-commit  # 생성만(커밋 안 함)

성계 ID는 DOTLAN(evemaps.dotlan.net/system/<이름>) 이나 게임 지도에서 확인.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import build_feasible

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True,
                          capture_output=True, text=True)


def _commit_push(sid):
    try:
        _git("add", "data", "templates", "engine/pi_optimizer/data/systems")
        status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                capture_output=True, text=True).stdout.strip()
        if not status:
            print("변경 사항 없음 (이미 추가된 성계).")
            return
        _git("commit", "-m", f"add system {sid}")
        print("커밋 완료.")
        try:
            _git("push")
            print("푸시 완료 - 몇 분 뒤 사이트에 반영됩니다.")
        except subprocess.CalledProcessError as e:
            print("푸시 실패(원격/인증 확인). 수동으로: git push")
            print((e.stderr or "").strip()[:300])
    except subprocess.CalledProcessError as e:
        print("git 자동 처리 실패. 수동으로: git add . && git commit -m 'add system' && git push")
        print((e.stderr or "").strip()[:300])
    except FileNotFoundError:
        print("git 을 찾을 수 없습니다. 수동으로 커밋하세요.")


def main():
    argv = list(sys.argv[1:])
    if not argv or argv[0].startswith("-"):
        print("사용: python engine/add_system.py <system_id> [--no-commit]")
        sys.exit(1)
    sid = int(argv[0])
    no_commit = "--no-commit" in argv

    build_feasible.build(sid)  # ESI 스캔 + feasible/템플릿/목록 생성

    if no_commit:
        print("생성 완료(커밋 안 함). 반영하려면: git add . && git commit && git push")
    else:
        _commit_push(sid)


if __name__ == "__main__":
    main()
