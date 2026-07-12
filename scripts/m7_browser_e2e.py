# M7 웹UI 브라우저 E2E: 세그먼트 렌더링 → 장면형 검색 카드 → 무관 질의 low_relevance 배너
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
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE)
    page.wait_for_load_state("networkidle")

    # 1) 초기 상태: 채팅 비활성(업로드 전)
    check("초기 chat-input 비활성", page.locator("#chat-input").is_disabled())

    # 2) 인덱싱 완료 영상으로 상태 주입 → 실제 onReady 경로 실행
    page.evaluate("videoId = 'pland_costco_hosting'; onReady();")
    page.wait_for_selector(".seg", timeout=30000)
    n_segs = page.locator(".seg").count()
    check("세그먼트 목록 렌더링", n_segs == 395, f"{n_segs}개 (기대 395)")
    check("onReady 후 chat-input 활성", not page.locator("#chat-input").is_disabled())
    check("무발화 표기 존재", page.locator(".seg", has_text="(무발화)").count() > 0)

    # 3) 장면형 검색: 실제 폼 제출 → /api/search → 카드 렌더링 (첫 검색은 KURE 로드 ~1분)
    page.fill("#chat-input", "새우전을 부치는 장면")
    page.click("#chat-send")
    page.wait_for_selector(".msg.bot .card", timeout=180000)
    cards = page.locator(".msg.bot .card")
    check("검색 카드 3개", cards.count() == 3, f"{cards.count()}개")
    first = cards.first.inner_text()
    check("top1 카드에 시간·캡션 표시", "13:45" in first and "새우" in first, first[:60].replace("\n", " / "))
    check("관련 질의에 배너 없음", page.locator(".low-rel").count() == 0)
    check("세그먼트 하이라이트", page.locator(".seg.hit").count() == 3)
    page.screenshot(path=f"{SHOT}/e2e_search.png", full_page=False)

    # 4) top1 카드 클릭 → 플레이어 시킹
    cards.first.click()
    t = page.evaluate("document.getElementById('player').currentTime")
    check("카드 클릭 시 플레이어 시킹", abs(t - 825) < 6, f"currentTime={t} (기대 825±5)")

    # 5) 무관 질의 → low_relevance 배너 표시 + 결과 은폐 금지(카드는 그대로)
    page.fill("#chat-input", "비트코인 시세 전망")
    page.click("#chat-send")
    page.wait_for_selector(".low-rel", timeout=60000)
    check("무관 질의 배너 표시", page.locator(".low-rel").count() == 1)
    last_bot = page.locator(".msg.bot").last
    check("배너와 함께 결과 카드도 표시(은폐 금지)", last_bot.locator(".card").count() == 3)
    page.screenshot(path=f"{SHOT}/e2e_lowrel.png", full_page=False)

    # 6) JS 콘솔 에러 없음
    check("페이지 JS 에러 0건", not errors, "; ".join(errors[:2]))

    browser.close()

print("결과:", "전부 통과" if not failures else f"실패 {len(failures)}건: {failures}")
sys.exit(1 if failures else 0)
