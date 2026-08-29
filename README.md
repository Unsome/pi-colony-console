# PI Colony Console

EVE PI 디커플드 콜로니(미너 4 + 생산 1) 설계 도구. 성계를 고르면 생산 가능한 P3를
일일 생산가치 순으로 보여주고, 행성별 템플릿을 **클립보드 복사 버튼**으로 제공한다.
게임 내 Open Templates → Import & Export → Load from Clipboard 로 바로 임포트.

정적 사이트(GitHub Pages) + 가격만 하루 1회 갱신(GitHub Actions). 요청 시점 서버 로직 없음.

## 구조

```
index.html  app.js  styles.css      정적 프론트 (Pages 루트)
.nojekyll                            Jekyll 우회
data/
  systems.json                       드롭다운용 성계 목록
  feasible/<id>.json                 성계별 생산가능 P3 + 템플릿 매핑 (가격 독립, 오프라인 생성)
  prices.json                        지타 7일평균 (Action이 매일 갱신)
templates/
  miners/<P1>.json                   MattFalahe CCU IV 미너 15종 (고정)
  production/<id>/<P3>.json          P3별 P2+P3 조합 생산 템플릿 (배정 행성 Pln 반영)
engine/                              오프라인 스크립트 (사이트가 서빙하진 않음)
  build_feasible.py  update_prices.py  add_system.py  gen_production.py
  pi_optimizer/  pi_graph.json  skeleton_factory.json
.github/workflows/daily.yml          매일 가격 갱신 cron
```

가격이 바뀌면 **순위만** 바뀌고 생산 가능여부는 안 바뀐다. 그래서 feasible은 고정이고
클라이언트가 prices.json으로 정렬만 한다 - 매일 엔진을 돌릴 필요가 없다.

## 로컬 미리보기

```bash
python -m http.server 8099      # 저장소 루트에서
# http://localhost:8099  (비밀번호: soju9512)
```

클립보드 복사는 HTTPS 또는 localhost 에서만 동작(브라우저 정책).

## GitHub Pages 배포

1. 이 폴더를 GitHub 저장소로 push (private 권장 - 비번은 장식일 뿐이라 소스에 노출됨).
2. Settings → Pages → Source: **Deploy from a branch**, Branch: `main` / `/ (root)`.
3. 몇 분 뒤 `https://<user>.github.io/<repo>/` 로 접속. 비번 soju9512.

### 매일 가격 갱신 (GitHub Actions)

`.github/workflows/daily.yml` 이 매일 11:20 UTC 에 ESI에서 지타 7일평균을 긁어
`data/prices.json` 을 커밋한다. 저장소 Settings → Actions → General →
Workflow permissions 를 **Read and write** 로 설정해야 봇이 커밋할 수 있다.
수동 실행은 Actions 탭 → daily-prices → Run workflow.

> 최초 배포 시 `data/prices.json` 은 플레이스홀더다. Action을 한 번 수동 실행하거나
> 로컬에서 `python engine/update_prices.py` 를 돌려 실값으로 채운 뒤 push 하라.

## 성계 추가

```bash
python engine/add_system.py <system_id>     # 예: 30002813
git add . && git commit -m "add system" && git push
```

ESI로 행성 구성을 조회해 feasible + 생산 템플릿을 생성하고 목록에 추가한다.
생산 템플릿은 배정된 생산 행성 타입의 Pln으로 생성된다(PG 여유 전제, 수동검증 불요).
성계 ID는 DOTLAN(evemaps.dotlan.net) 에서 확인.

## 게임 쪽 준비

- EVE 설정 → Feature Previews → "Planetary Industry Templates" 활성화.
- 각 행성에 커맨드 센터(CCU4)를 세우고 해당 행성 타입에 맞는 템플릿을 클립보드로 임포트.
- 미너 4개의 P1을 생산 행성 런치패드로 하울링(같은 성계 내 커스텀 오피스 경유).

## 한계 / 주의

- **비밀번호는 장식이다.** 정적 사이트라 app.js에 평문으로 있다. 진짜 가림이 필요하면
  Cloudflare Access(무료)를 Pages 앞에 둘 것.
- 산출은 표준 농도·44433 스킬 명목값(144/일 = 2라인). POCO 수출세·마켓 뎁스·잉여 P1 미반영.
- 3입력 P3 6종은 미너 4개로 P1 6종을 못 대 배제(구조적).
- 생산 템플릿 PG는 행성 지름 의존. 현재 인프라 여유 전제로 배정 타입 Pln만 맞춰 생성.
