# PROJECT_DESIGN_CONFORMANCE_AUDIT — 설계 선언 ↔ 코드·런타임·산출물 전수 대조

작성 2026-08-26 · 범위 FINALIZATION · 대상 commit `6aa7032`(감사 시작) → 이 문서 커밋
검증: `python -m pytest tests/ -q` **1,824 passed · exit 0 · 51초**

---

## A. 이 감사가 답하는 질문

문서에 "이렇게 설계했다"고 적힌 것이 **실제로 강제되는가.**
판정은 두 축을 분리한다.

```
선언돼 있다     문서·주석·config에 규칙이 적혀 있다
강제된다        규칙을 어기는 실행이 코드에서 실패한다
```

둘이 갈리는 지점이 이 감사의 전부다. **테스트 개수는 품질 증거로 세지 않았다** —
요구사항 자체가 테스트에 없으면 1,800건이어도 그 요구사항은 검증되지 않는다.
실제로 아래 R13·R18은 테스트가 1,757건이던 시점에도 **아무 테스트도 그 규칙을 지키지
않았고**, 규칙은 CLAUDE.md 절대규칙 1에만 있었다.

---

## B. 결론 요약

| | 건수 |
|---|---|
| PASS | 15 |
| PASS_WITH_CAVEAT | 5 |
| IMPLEMENTED_NOT_ENFORCED → 이번에 강제 | 4 (R13·R16·R18 + 로그 판정) |
| MISMATCH | 0 |
| NOT_IMPLEMENTED | 0 |

**가장 무거운 발견은 R13·R18이다.** test 39건은 프로젝트가 "비가역 자원"으로 규정한
자원인데, `python src/m6_evaluate.py` 한 줄(플래그 없음)이 **기본 경로로 test를
평가**했고, `src/m9_report_eval.py`는 질의를 `split=="test"`로 하드코딩해 읽으므로
**실행 자체가 test 접촉**인데 게이트가 없었다. 규칙은 문서에만 있었다.

이 감사에서 고친 것은 **없던 강제를 추가한 것**뿐이고, 방법론·배포 구성·수치는
하나도 바꾸지 않았다. 확정 결과 파일(`results/eval_test.json`·`alpha_search_dev.json`)은
읽지도 다시 쓰지도 않았다.

---

## C. 이번에 추가한 강제 (5건)

### C-1. test 접촉 게이트 — M6·M9 (HIGH)

```
DESIGNED     test 재평가는 사용자 승인 사건 (CLAUDE.md 절대규칙 1)
IMPLEMENTED  없음. 문서에만 존재
ACTUAL       m6_evaluate: --dev-only가 opt-in → 인자 없이 실행하면 test 평가가 기본
             m9_report_eval: split=="test" 하드코딩 → 실행 = test 접촉, 게이트 0
FIXED        둘 다 --test-opening '<사유>' 필수. 사유는 결과 JSON에 기록
             (eval_test.json.test_opening · report_eval_*.json.test_opening)
TEST         tests/test_test_opening_gate.py (4건)
```

사유를 **문자열로 요구**하는 이유: 접촉 이력이 산출물에서 재구성돼야 한다.
DESIGN_SPEC 8-6은 공식 평가 7회의 사유 ①~⑦을 문서로 관리하는데, 그 목록의 근거가
지금까지 **사람의 기억과 커밋 로그**였다. 이제 결과 파일 자체가 사유를 들고 있다.

### C-2. 인덱스 ↔ config 캡션 identity (HIGH)

```
DESIGNED     배포는 3B/P0/4bit. 다른 모델·프롬프트 산출물과 섞이지 않는다
IMPLEMENTED  text_hash(캡션↔임베딩 동시성) · embed_model(임베딩 모델) 대조만
ACTUAL       4B로 만든 캡션 인덱스를 3B config로 열면 두 검사가 **모두 통과**한다
             — 어느 모델이 그 캡션을 썼는지 보는 검사가 없었다
FIXED        m5_search._check_caption_identity — segments.json의 caption_provenance와
             cfg의 caption_model·caption_prompt를 대조, 불일치면 로드 실패
CAVEAT       caption_provenance는 2026-08-17 도입이라 **확정 인덱스 11편에는 없다.**
             증거가 없는 인덱스는 통과시키고(재색인은 HOLD), 대신 demo.py preflight가
             "캡션 생성 기록이 없다"를 경고로 **공시**한다
TEST         tests/test_deployment_identity.py (14건) · test_demo_preflight.py (2건)
```

실측(2026-08-26, 확정 인덱스 15편 스캔):

```
caption_provenance 있음   4편 (e2e_cooking_1 · e2e_interview · e2e_scene_fast · e2e_speech_medium)
                          전부 config_caption_model = Qwen/Qwen2.5-VL-3B-Instruct
없음                      11편 (dev 3 · test 4 · 신규 3 · pland_costco_hosting)
```

런타임 확인 — config를 4B로 바꾸고 두 인덱스를 열었다.

```
e2e_cooking_1          차단: 캡션 모델 불일치: index=…3B… config=…4B…
pland_costco_hosting   통과 (증거 없음 — 위 CAVEAT 그대로)
```

### C-3. α 값 범위 (MEDIUM)

`--alpha`에 검증이 없어 `1.5`·`NaN`이 그대로 가중합에 들어갔다. 가중합이라 예외 없이
"동작"하고 랭킹만 조용히 무의미해진다. `combine_scores`에서 한 번 막는다 —
검색·평가 **모든 경로가 이 함수를 지난다**. `scripts/demo.py`의 α=0.5 강제는 그대로다.

### C-4. m7_demo 자격 경계 (MEDIUM)

`scripts/demo.py`를 우회해 `python src/m7_demo.py --video-id <test영상>`을 돌리면
막는 것이 없었다. 같은 정책 함수(`eligibility.demo_block_reason`)를 진입점에서 호출한다.
**이 유형의 결함은 이번 최종화에서 네 번째다**(manifest 선언 미강제 → 웹 API 요청 경로
→ 로그 판정 → 여기). 유형 자체를 기록해 둔다: *정책을 한 곳에서 선언하고 다른 곳에서
쓰지 않는다.*

### C-5. 중복 선언 표류 방지 (LOW)

배포 identity가 `scripts/demo.py`와 `scripts/e2e_external.py` 두 곳에 있고, 연구 영상
이름 집합이 `eligibility`와 `e2e_external`에 각각 있다. 발표 전에 합치는 것은
리팩터링이라 하지 않았다 — 대신 **어긋나면 실패하는 테스트**를 넣었다.

---

## D. 요구사항 추적표 (R01~R22)

`status` 정의: PASS(선언·구현·강제 일치) / PASS_WITH_CAVEAT(강제되나 적용 범위에 한계
있음) / DOC_ONLY(문서에만) / IMPLEMENTED_NOT_ENFORCED(코드에 있으나 우회 가능) /
MISMATCH(문서와 코드가 다름) / NOT_IMPLEMENTED / NOT_APPLICABLE.

| ID | 요구사항 | 강제 지점 | 상태 |
|---|---|---|---|
| R01 | 5초 등간격 분할 · `start = idx*5` 불변식 | `m1_preprocess.py:9-13,59-62` 생성 시 assert + `common.load_segments:44` **로드마다 재검증** | PASS |
| R02 | 구간당 대표 프레임 1장(차분 argmax, 평활) | `m2_keyframe.py:11-21,112,128` | PASS |
| R03 | 오버랩 자막 귀속(겹치는 모든 구간) | `m3_generate.py:176-190` | PASS |
| R04 | 자막 크레딧 환각 제거는 **전체 일치 자동 판정만** | `common.is_subtitle_credit` · `m3_generate.py:183` | PASS |
| R05 | P0 프롬프트 동결 · 캡션 후처리 기본 off | `config.yaml caption_prompt` · `common.py:80-82`(플래그 둘 다 false → 실질 no-op) | PASS_WITH_CAVEAT — 프롬프트 동일성은 provenance 있는 4편에서만 대조된다(C-2) |
| R06 | 캡션 재생성은 자동 오염 판정분만 | `m3_generate.py:271-278,319-322` · `--recaption-corrupted` 배타 플래그(`:343-346`) | PASS |
| R07 | 자막·캡션·질의 동일 embed_model · L2 · float32 | `m4_index.py` 생성 · `m5_search.py:64` 로드 대조 | PASS |
| R08 | 재캡셔닝 후 임베딩 미갱신 차단(text_hash) | `m5_search.py:69` · `scripts/demo.py:131` | PASS |
| R09 | 연산 순서 cos → z-score → 정적 치환 → α 가중합 | `m5_search.combine_scores` | PASS |
| R10 | `static_threshold`는 config가 단일 출처(저장된 is_static 무시) | `m5_search.VideoIndex.load:53-56` | PASS |
| R11 | α는 config에 없다 — CLI 주입, 배포 0.5 | `scripts/demo.py:100` α≠0.5 거부 · `combine_scores` 범위 검증(C-3) | PASS_WITH_CAVEAT — 컴포넌트 진입점(`m5`·`m7_demo`·`m7_webui`)은 dev 용도로 임의 α를 허용한다. 배포 경로는 `demo.py` 하나다 |
| R12 | abstention은 경고 전용 — 순위·결과 불변 | `m7_webui` 부가 필드만 · 로그와 응답이 같은 식(`max(sub,cap)<τ`) | PASS |
| R13 | test 재평가 금지 — 승인 사건 | ~~없음~~ → `m6_evaluate.main` `--test-opening` 필수(C-1) | IMPLEMENTED_NOT_ENFORCED → **PASS** |
| R14 | gt_seg_idx 파생 규칙(1초 겹침, 없으면 최대 겹침) | `common.derive_gt_seg_idx:87-100` · `m6_evaluate.validate_gt_seg_idx` | PASS |
| R15 | 데모는 배포 구성으로만 시작 | `scripts/demo.py preflight` 12항목 fail-closed | PASS |
| R16 | test split · E2E 전용 · P2/P3 영상은 데모 불가 | `src/eligibility.py` 단일 출처 → `m7_webui` 4개 경로 403 · `demo.py` · `m7_demo`(C-4) | IMPLEMENTED_NOT_ENFORCED → **PASS** |
| R17 | AAR 인용은 인덱스 구간에 대응 | `m9_report_eval.main` cites 범위 assert · `aar_view.check_precomputed` | PASS |
| R18 | M9 실행은 test 접촉 — 승인 필요 | ~~없음~~ → `--test-opening` 필수(C-1) | IMPLEMENTED_NOT_ENFORCED → **PASS** |
| R19 | 영상 출처 provenance 인덱싱 전 기록 · fail-closed · 지표 미사용 | `src/provenance.py` · `m1_preprocess` resolve · `tests/test_provenance.py` | PASS_WITH_CAVEAT — 기존 11편은 `legacy_exempt`로 **데이터에** 면제가 있다(코드가 조용히 넘어가지 않는다) |
| R20 | 캡션 생성 조건 기록(요청값·실효값 둘 다) | `m3_generate.caption_provenance` | PASS_WITH_CAVEAT — 2026-08-17 도입, 확정 인덱스 11편에 없음. 부재를 preflight가 공시(C-2) |
| R21 | 변형 실험 격리 — config 사본 · work/results 동시 분리 | `scripts/casestudy_make_config.py:33-43`(KEEP_IDENTICAL assert) · `make_server_config.py` | PASS |
| R22 | 공개 저장소에 원본 영상·프레임·인덱스 텍스트 미추적 | `.gitignore` · `git ls-files` 실측 **0건** | PASS_WITH_CAVEAT — 발췌 인용(케이스 스터디·AAR 추적 문서)은 존재한다. 전량 덤프는 없다 |

---

## E. 확인만 하고 손대지 않은 것

```
확정 결과      results/eval_test.json · alpha_search_dev.json — 읽지도 쓰지도 않았다
배포 config    config.yaml 무변경 (caption_model·alpha·prompt·threshold·tau 전부)
인덱스         work/*/ 무변경 — 재캡셔닝·재임베딩·재색인 0건
케이스 스터디   v1 동결 보존, r2가 발표 기준. 두 판을 합산하지 않는다
```

## F. HOLD로 남긴 것 (승인 사건)

```
확정 인덱스 11편의 caption_provenance 채우기   → 재색인 필요. HOLD
배포 identity 선언 단일화(demo ↔ e2e_external) → 리팩터링. 표류 테스트로 대체
R11 컴포넌트 진입점의 α 자유도 제거            → dev 사용성과 상충. 문서화로 종결
push / 외부 공개                               → 사용자 승인 사항
```

## G. 남은 위험

1. **11편의 캡션 출처는 산출물로 증명되지 않는다.** 지금 근거는 커밋 이력과 작업현황
   문서다. 재색인 없이는 닫히지 않으므로, 보고서에는 "provenance 있는 4편에서만
   대조 가능"으로 적어야 한다.
2. **`load_segments(seg_len=5)`의 기본값.** 호출부가 cfg를 넘기지 않으면 5초로 검증한다.
   현재 모든 production 호출부는 cfg를 넘긴다(확인). seg_len ablation 코드가 늘면
   여기가 함정이 된다.
3. **정책 단일 출처의 적용 범위.** `eligibility`는 데모 경로만 덮는다. 연구 스크립트
   (`p2_*`·`p3_*`)는 자체 arm 맵을 쓴다 — 의도된 분리지만 표류 감시는 테스트 2건뿐이다.
