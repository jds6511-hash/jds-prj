# F4 문서 정합성 감사 (2026-08-26)

**목적.** 처음 보는 사람이 README와 아키텍처 문서를 믿고 따라 했을 때 현재 실제
production path와 충돌하지 않게 만든다. **새 연구·새 기능을 추가하지 않는다** —
문서와 코드의 불일치, stale wording, 잘못된 실행 명령만 정리한다.

---

## A. README 감사

### 발견·수정

| # | 문제 | 조치 |
|---|---|---|
| 1 | 테스트 수·소요가 `약 4초, 180건` (실제 1,725건 · 약 1분) | 실측값으로 교체 |
| 2 | `--check-only`가 `11항목` (실제 12항목이 됨) | 12항목으로 교체 |
| 3 | 디렉터리 설명의 `단위테스트 180건` | 1,719 → 최종 1,725건 반영 |
| 4 | preflight 거부 목록에 external E2E 전용 영상이 빠짐 | 추가 |
| 5 | 구현 상태표가 `M8~M9 구현·실행 완료`로만 적혀 현재 HOLD·로컬 불가가 안 보임 | 로컬 6GB 불가 + M8 research evaluation HOLD 명시 |
| 6 | **"전부 로컬 실행이다"** — AAR(7B)는 로컬 6GB에서 안 돈다 | 검색·재생은 로컬 / AAR 생성은 서버 GPU로 분리 서술 + runbook 링크 |
| 7 | 튜닝 항목에 `abstention 임계값`이 사용자 대면 표현처럼 노출 | 내부 키 이름임을 밝히고 **"배너 경고뿐, 순위·결과 불변"** 병기 |
| 8 | 현재 연구 상태(4B·P2·P3·test/M9·E2E·케이스 스터디)가 README에 전혀 없음 | **§현재 연구 상태** 신설 |
| 9 | 문서 링크에 `docs/finalization/`이 없음 | 추가 |

### 남은 것

README의 **핵심 결과 표는 공식 test 결과 그대로 둔다** — 확정 배포 구성으로 끝난
결과이고 frozen artifact다. 그 아래 §현재 연구 상태에서 이후 진행분과 경계를 구분한다.

### 명령 smoke (실제 실행)

| command | exit | 기대 | 실제 |
|---|---|---|---|
| `scripts/demo.py --help` | 0 | usage 출력 | PASS |
| `scripts/demo.py --list` | 0 | 인덱스 완성 영상 + 부적격 표기 | PASS |
| `scripts/demo.py --video-id gwaktube_soviet_apartment --check-only` | 0 | preflight PASS 12항목 | PASS |
| `scripts/demo.py --video-id panibottle_vietnam1 --check-only` | 1 | test split 거부 | PASS |
| `scripts/demo.py --video-id e2e_scene_fast --check-only` | 1 | **E2E 전용 거부** | 수정 전 FAIL(통과함) → 수정 후 PASS |
| `src/m5_search.py --help` | 0 | usage | PASS |
| `src/m7_webui.py --help` | 0 | usage | PASS |
| `src/m1_preprocess.py --help` | 0 | usage | PASS |
| `scripts/aar_view.py --help` | 0 | usage | PASS |

GPU 장시간 작업은 하지 않았다. 기존 인덱스만 사용했다.

---

## B. 실제 기능 결함 1건 (F4 범위에서 수정)

**`scripts/demo.py`가 external E2E 전용 영상을 데모로 통과시켰다.**

```
증상   demo.py --list 에 e2e_scene_fast · e2e_speech_medium · e2e_cooking_1 ·
      e2e_interview 가 데모 후보로 표시됐고, --check-only도 PASS했다
문제   이 영상들은 manifest에 eligible_for_public_demo: false · e2e_only: true로
      **이미 선언돼 있다.** 선언만 있고 진입점이 강제하지 않으면 선언이 아무 일도 안 한다
조치   demo_ineligible() 추가 — manifest를 읽어 e2e_only 또는
      eligible_for_public_demo=false면 preflight가 거부하고 --list에 표기한다
      (manifest가 없으면 막지 않는다 — 배포본에 planning/이 없을 수 있다)
결과   preflight 확인 항목 11 → 12. 테스트 6건 추가
```

**배포 config·모델·α·인덱스를 바꾸지 않았다.** 이미 선언된 경계를 코드가 강제하게 한 것뿐이다.

---

## C. 아키텍처 감사

원래도 production path만 그리고 있었고 제외 목록이 있었다. 보강한 것:

```
1  AAR 행을 생성/렌더로 분리 — 생성은 서버 GPU 전용, 렌더는 로컬 가능
2  저관련도 경고 행 — 내부 키가 abstention_tau지만 실제 동작은 배너뿐,
   랭킹·결과 불변, 결과 숨김·거부 없음을 명시
3  '연구·검증 곁길' 절 신설 — 3B↔4B 비교 · P2 · P3 · external E2E ·
   운영비 프로파일 · M8/M9 research를 production과 시각적으로 분리
4  'production path에 없는 것'에 external E2E · 캡션 케이스 스터디 ·
   M8 research evaluation 추가
```

**production path와 실제 모듈명 일치 확인:**
`m1_preprocess → m2_keyframe → m3_generate(Whisper large-v3 + Qwen2.5-VL-3B/P0/4bit)
→ m4_index(KURE-v1) → m5_search(z-score + α=0.5) → m7_webui` — 문서와 코드가 일치한다.

---

## D. 상태 표현 감사

활성 문서 전수 스윕 결과 — **금지 표현이 실제로 쓰인 사례는 없었다.**

| 검색어 | 결과 |
|---|---|
| `3B가 이겼` · `4B 기각` · `4B가 더 좋` | 전부 **금지 목록·부정문 안**에서만 등장 ("~라고 쓰지 않는다") |
| `abstention` | 4곳 — 전부 **내부 config 키임을 밝히고 사용자 대면 문구는 저관련도 경고**라고 구분한 문맥 |
| `cheaper` · `저렴` | 활성 문서에 없음 |
| `contamination 0` · `오염 0` | 앞선 커밋에서 `현행 detector 기준 flag 0`으로 이미 정정 |
| `미탐률` | `현행 규칙이 flag하지 않은 추가 foreign-script candidate`로 이미 정정 |

현재 상태 표기는 다음으로 통일돼 있다.

```
3B    incumbent / current deployment / retained
4B    viable candidate · not adopted · superiority unresolved · operationally feasible
P2    annotation-cost-driven HOLD (20/175, retrieval 미실행, 부분 20건 미분석)
P3    설계 동결 · 실행 HOLD · 1,500은 가정 위의 설계 목표이지 검출 보장 수치 아님
test  HOLD · 이번 기간 접촉 0회 · 39→72 확장 미개방
M9    HOLD
M8    research evaluation HOLD / AAR demo generation은 functional run
E2E   functional validation COMPLETE (벤치마크·정확도 아님)
사례연구 qualitative only · 채택 근거 아님
```

---

## E. 링크·경로 무결성

```
활성 문서 51개 링크 검사 → 깨진 링크 0개
검사 대상: README · CLAUDE.md · docs/README.md · docs/finalization/*.md ·
          docs/tutor/ 최근 문서
```

---

## F. 테스트

`tests/test_demo_preflight.py`에 6건 추가:

```
demo_ineligible이 E2E 전용 영상을 막는가
preflight가 E2E 전용 영상에서 예외를 던지는가
README·최종화 문서의 preflight 항목 수가 실제와 같은가
README의 python 진입점이 실제로 존재하는가
README가 4B를 배포처럼 쓰지 않는가 (주변에 candidate/채택 아님 표기)
아키텍처가 production과 research를 분리하고 있는가
```

전체 **1,725건 통과**(기존 1,719 + 6).

---

## G. 남은 항목 (사용자가 해야 하는 것)

```
1  AAR artifact 1회 확보 — 서버 GPU 필요. runbook은 준비됨
   docs/finalization/AAR_SERVER_RUNBOOK_2026-08-26.md
2  발표 슬라이드·8분 리허설 — 지시 대기 상태로 남아 있다
```

**F4에서 하지 않은 것:** 배포 config 변경 · α 변경 · 모델 변경 · frozen QC 규칙 변경 ·
P2/P3/test/M9 접근 · 인덱스 재생성 · 공식 결과 재계산 · push. frozen historical
artifact는 덮어쓰지 않고 상위 문서에서 현재 상태를 설명하는 방식으로 처리했다.
