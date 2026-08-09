# M7 웹UI 브라우저 E2E: 세그먼트 렌더링 → 검색 결과 → 채널 리본 → low_relevance 배너
# 셀렉터는 UI 계약이다 — index.html을 고치면 여기도 같이 고쳐야 한다.
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:7860"
SHOT = "results/e2e"
import os as _os; _os.makedirs(SHOT, exist_ok=True)
failures = []

def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), "|", name, "|", detail)
    if not cond:
        failures.append(name)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE)
    page.wait_for_load_state("networkidle")

    # 1) 초기 상태: 질의 입력 비활성(업로드 전)
    check("초기 질의 입력 비활성", page.locator("#q").is_disabled())
    # 확정 설정이 헤더에 뜬다 — 발표 중 "α는 얼마냐"에 화면이 답한다
    spec = page.locator("#spec").inner_text()
    check("헤더에 α 표시", "α" in spec and "0.5" in spec, spec)

    # 2) 인덱싱 완료 영상으로 상태 주입 → 실제 ready() 경로 실행
    page.evaluate("videoId = 'pland_costco_hosting'; ready();")
    page.wait_for_selector(".seg", timeout=30000)
    n_segs = page.locator(".seg").count()
    check("세그먼트 목록 렌더링", n_segs == 395, f"{n_segs}개 (기대 395)")
    check("ready 후 질의 입력 활성", not page.locator("#q").is_disabled())
    check("무발화 표기 존재", page.locator(".seg", has_text="발화 없음").count() > 0)
    check("검색 전 리본은 유휴 상태", "idle" in (page.locator("#ribbon").get_attribute("class") or ""))

    # 3) 장면형 검색: 실제 폼 제출 → /api/search → 결과 렌더링 (첫 검색은 KURE 로드 ~1분)
    page.fill("#q", "새우전을 부치는 장면")
    page.click("#go")
    page.wait_for_selector(".hit", timeout=180000)
    hits = page.locator(".hit")
    check("검색 결과 3건", hits.count() == 3, f"{hits.count()}건")
    first = hits.first.inner_text()
    check("top1에 시간·화면 설명 표시", "13:45" in first and "새우" in first,
          first[:70].replace("\n", " / "))
    check("결과에 두 채널이 모두 라벨링됨",
          hits.first.locator(".line.speech").count() == 1
          and hits.first.locator(".line.scene").count() == 1)
    check("관련 질의에 배너 없음", page.locator(".notice").count() == 0)
    check("세그먼트 하이라이트", page.locator(".seg.on").count() == 3)

    # 3-b) 채널 리본이 실제로 그려졌는지 — 픽셀을 본다(요소 존재만으로는 부족)
    check("리본 유휴 해제", "idle" not in (page.locator("#ribbon").get_attribute("class") or ""))
    painted = page.evaluate("""() => {
      const cv = document.getElementById('canvas');
      const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
      let n = 0;
      for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++;
      return n;
    }""")
    check("리본에 픽셀이 그려짐", painted > 1000, f"불투명 픽셀 {painted}개")
    per_seg_len = page.evaluate("lastPerSeg ? lastPerSeg.sub.length : 0")
    check("리본 데이터가 세그먼트 수와 일치", per_seg_len == n_segs, f"{per_seg_len}")
    page.screenshot(path=f"{SHOT}/e2e_search.png", full_page=False)

    # 4) top1 클릭 → 플레이어 시킹
    hits.first.click()
    t = page.evaluate("document.getElementById('player').currentTime")
    check("결과 클릭 시 플레이어 시킹", abs(t - 825) < 6, f"currentTime={t} (기대 825±5)")

    # 5) 리본 클릭 → 해당 시점으로 시킹(시연에서 쓰는 조작)
    box = page.locator("#canvas").bounding_box()
    page.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + box["height"] / 2)
    t2 = page.evaluate("document.getElementById('player').currentTime")
    check("리본 클릭 시 중간 지점으로 시킹", abs(t2 - 395 * 5 * 0.5) < 40, f"currentTime={t2}")

    # 6) 무관 질의 → low_relevance 배너 + 결과 은폐 금지
    page.fill("#q", "비트코인 시세 전망")
    page.click("#go")
    page.wait_for_selector(".notice", timeout=60000)
    check("무관 질의 배너 표시", page.locator(".notice").count() == 1)
    check("배너와 함께 결과도 표시(은폐 금지)", page.locator(".hit").count() == 3)
    page.screenshot(path=f"{SHOT}/e2e_lowrel.png", full_page=False)

    # 7) JS 콘솔 에러 없음
    check("페이지 JS 에러 0건", not errors, "; ".join(errors[:2]))

    browser.close()

print("결과:", "전부 통과" if not failures else f"실패 {len(failures)}건: {failures}")
sys.exit(1 if failures else 0)
