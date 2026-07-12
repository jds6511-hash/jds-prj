---
name: m7-e2e
description: M7 웹UI를 실브라우저(Playwright)로 검증하는 12체크 E2E. 웹UI·검색·abstention 배너 변경 후, 또는 시연 전 점검에 사용.
---

# M7 브라우저 E2E

## 실행 (한 줄)

```bash
python3 .claude/skills/webapp-testing/scripts/with_server.py \
  --server "python3 src/m7_webui.py --alpha 0.5 --port 7860" --port 7860 --timeout 60 \
  -- python3 scripts/m7_browser_e2e.py
```

- `--alpha`는 results/alpha_search_dev.json의 alpha_star.
- 스크린샷은 results/e2e/에 저장. 마지막 줄 "결과: 전부 통과" 확인.

## 검증 항목 (scripts/m7_browser_e2e.py)

업로드 전 채팅 비활성 / 세그먼트 395개 렌더링(pland_costco_hosting) / (무발화) 표기 /
검색 카드 3개 / top1 시간·캡션 / 유관 질의 배너 없음 / 하이라이트 3개 / 카드 클릭 시
플레이어 시킹 / 무관 질의 low_relevance 배너 / 배너와 함께 결과 유지(은폐 금지) /
JS 콘솔 에러 0.

## 주의

- 웹UI의 영상 선택은 세션 내 업로드 기반(jobs 인메모리) — E2E는 `videoId 주입 + onReady()`로
  실제 초기화 경로를 재사용한다. 시연 때는 mp4 업로드(산출물 존재 시 resume으로 수 초).
- 첫 검색은 KURE 로드 ~1분 — 대기 타임아웃 180초 유지.
- 인덱스 기준값(395세그, 13:45 등)은 데모 영상 고정값 — 다른 영상으로 바꾸면 스크립트의
  기대값도 함께 갱신.
