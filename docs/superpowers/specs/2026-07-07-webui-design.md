# 영상 검색 웹 UI (M7-W) 설계

날짜: 2026-07-07
상태: 사용자 승인됨
관련 문서: docs/DESIGN_SPEC.md 4-7 (M7), docs/superpowers/plans/2026-07-07-video-pipeline-m1-m9.md

## 목적

기존 M7 Gradio 데모를 대체하지 않고, 사용자가 보기 쉬운 웹 UI를 추가한다:
영상 업로드 → 자동 인덱싱(진행률 표시) → 좌측 플레이어 + 우측 전사/장면설명
목록 + 채팅형 검색.

## 확정 요구사항 (사용자 응답)

1. **업로드 흐름**: 업로드 시 M1~M4 파이프라인 자동 실행, UI에 단계별 진행률 표시.
2. **채팅 응답**: LLM 없이 검색 결과 카드 — Top-3 구간(시간·자막·캡션 미리보기)이
   채팅 말풍선으로 표시, 클릭 시 플레이어가 해당 초로 점프. 검색 이력이 채팅창에 쌓임.
3. **전사 패널**: 세그먼트 목록 + 클릭 점프만 (재생 위치 자동 동기화는 하지 않음).
   검색 결과 구간은 목록에서 하이라이트.
4. **스택**: FastAPI + 단일 HTML 페이지 (Gradio 확장 대신 — 커스텀 상호작용이
   많아 네이티브 `<video>` API가 안정적).

## 구성 요소

```
src/m7_webui.py          # FastAPI 서버 (API + 정적 파일 서빙)
src/webui/index.html     # 화면 전체 (HTML+CSS+JS 단일 파일, 빌드 도구 없음)
```

- 기존 코드는 수정하지 않는다. `m7_demo.py`(계획 산출물)도 그대로 둔다.
- 서버는 M5의 `search()`/`VideoIndex`를 그대로 import한다 (재구현 금지,
  DESIGN_SPEC 4-7과 동일 계약).
- M1~M4는 서브프로세스로 기존 CLI를 순서대로 실행한다
  (`python src/mN_*.py --config config.yaml --video-id {id}`).
  - 근거: 모듈 간 통신은 파일이라는 프로젝트 원칙 유지, 서버 프로세스가
    GPU 코드를 직접 들지 않음, 각 단계의 멱등성(산출물 있으면 스킵)을
    그대로 상속 — 이미 인덱싱된 영상 재업로드는 즉시 완료 처리.

## API

| 메서드 | 경로 | 역할 |
|---|---|---|
| GET | `/` | index.html 반환 |
| POST | `/api/upload` | multipart mp4 → `data/videos/{stem}.mp4` 저장(파일명 stem을 video_id로 정규화: 허용 문자 `[a-zA-Z0-9_-]`, 그 외는 `_` 치환) → 백그라운드 인덱싱 시작 → `{video_id}` |
| GET | `/api/status/{video_id}` | `{stage, detail}` — stage ∈ m1, m2, m3, m4, done, error. stage가 m2/m3일 때는 조건부로 `progress: {n, total}` 추가(m2: 생성된 프레임 수/총, m3: 캡션 완료 수/총. segments.json 읽기 실패 시 생략). 프런트 1초 폴링, 밴드 내 보간으로 표시 |
| GET | `/api/current` | 마지막으로 시작된 잡의 `{video_id, stage, detail}` 반환(시작 이력이 없으면 `video_id: null`). 페이지 로드 시 재접속 복원용 |
| GET | `/api/segments/{video_id}` | segments.json의 세그먼트 배열 (idx, start, end, subtitle, caption) |
| POST | `/api/search` | `{video_id, query}` → M5 search() Top-3 `[{idx, start, end, score, subtitle, caption}]` |
| GET | `/api/video/{video_id}` | mp4 스트리밍, HTTP Range 요청 지원(시크 필수) |

동시성·자원 규칙:

- 인덱싱은 GPU 자원 때문에 서버 전체에서 동시 1건만. 진행 중 다른 업로드는
  409 + "다른 영상 인덱싱 중" 메시지로 거절.
- `VideoIndex`와 임베딩 모델은 서버 메모리에 캐시. 첫 검색만 모델 로딩으로
  느리고 이후 빠름.
- α는 서버 실행 인자 `--alpha` (기본 0.5). queries.jsonl 라벨링 후 M6 grid
  search로 확정한 값으로 교체하는 임시값임을 help 문구에 명시.

## 화면 레이아웃

```
┌────────────────────────────────────────────────┐
│  [영상 업로드]  진행률: ████░░ 캡션 생성 중(M3)…    │
├──────────────────────────┬─────────────────────┤
│      영상 플레이어         │  세그먼트 목록(스크롤)   │
│                          │  [0:35] 자막 / 설명    │
├──────────────────────────┤  ← 클릭 = 점프        │
│  채팅 검색                 │  (검색 결과 구간        │
│  나: 질의 / 봇: 결과 카드×3 │   하이라이트)          │
│  [입력창________] [검색]   │                     │
└──────────────────────────┴─────────────────────┘
```

- 왼쪽 위 플레이어, 왼쪽 아래 채팅(결과 클릭→점프 동선), 오른쪽 전체 높이
  세그먼트 목록.
- 결과 카드/세그먼트 클릭 → `video.currentTime = start; video.play()`.
- 검색 시 결과 3개 구간을 우측 목록에서 하이라이트하고 1위 구간으로 스크롤.
- 시간 표시는 `m:ss` 형식(내부 값은 기존 계약대로 정수 초).
- 인덱싱 완료(status가 done, 또는 `/api/current`로 복원한 잡이 done)로 새 영상이
  준비되면 채팅창(chat-log)을 초기화한 뒤 안내 메시지를 새로 띄운다 — 이전 영상의
  대화 이력이 남지 않도록 한다.

## 오류 처리

- 파이프라인 단계 실패: status `error` + 실패 단계명 + stderr 마지막 몇 줄을
  UI에 표시.
- mp4 아닌 업로드: 400 거절.
- 인덱싱 완료 전 검색: 409 + "인덱싱이 끝나면 검색할 수 있어요" 안내.

## 테스트

- FastAPI `TestClient` 기반 API 계약 테스트:
  - 업로드 검증(확장자 거부, 파일명 정규화)과 status 상태 전이
  - search 응답 스키마 — M5 `search`는 스텁 주입(기존 M6 테스트 패턴)
  - 인덱싱 중 중복 업로드 409
- 서브프로세스 파이프라인은 테스트에서 모킹 (GPU 불필요).
- 실제 GPU e2e는 spiderman_trailer(기 인덱싱)로 수동 스모크: 업로드 → 즉시
  done → 검색 → 점프 확인.

## 의존성 추가

`fastapi`, `uvicorn`, `python-multipart` (requirements.txt에 추가).
클라우드 API 없음 — 전부 로컬 서빙 (온프레미스 원칙 유지).

## 범위 밖 (명시적 제외)

- LLM 대화형 응답(RAG), 재생 위치 자동 동기화, 다중 사용자/인증,
  업로드 대기열, M8·M9 연동.

## 변경 이력

- 2026-07-09: 정합성 감사 반영 — `/api/current`, status `progress` 필드, 채팅 초기화 동작 문서화.
