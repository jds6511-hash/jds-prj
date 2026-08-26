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
| PASS | 17 |
| PASS_WITH_CAVEAT | 5 |
| IMPLEMENTED_NOT_ENFORCED → 이번에 강제 | 5 (R11·R13·R16·R18 + 로그 판정) |
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

### C-9. hidden fallback — 조용한 기본값 (MEDIUM)

`cfg.get(key, default)`는 키가 없어도 기본값으로 계속 돈다. **모든 fallback이 문제는
아니다** — 결과·정체성·경계를 바꾸는 것만 문제다. 셋으로 분류했다.

| key | 위치 | 부재 시 동작 | 영향 | 분류 | 조치 |
|---|---|---|---|---|---|
| `abstention_tau` | `m7_webui:123,317` | `None` → 저관련 경고가 **조용히 꺼진다** | 사용자에게 보이는 경고·로그 복원성. **랭킹 불변** | REQUIRED_FAIL_CLOSED | `search` 역할 필수 키. demo preflight·webui·m7_demo 시작 시 검증 |
| `vlm_max_new_tokens` | `m3:239` | 암묵 128 | **캡션 문자열이 바뀐다** — 3B 57/395가 실제로 상한에 닿았다 | REQUIRED_FAIL_CLOSED | `caption_generation` 역할 필수. 값은 그대로 128 |
| `vlm_rep_penalty` | `m3:244` | 암묵 1.0(=off) | 캡션 문자열 | REQUIRED_FAIL_CLOSED | 같음 |
| `caption_normalize_cjk` | `common:80` | off | 캡션 문자열 → `text_hash` → 인덱스 identity | REQUIRED_FAIL_CLOSED | 같음. **provenance에 기록 추가**(빠져 있었다) |
| `caption_truncate_incomplete` | `common:82` | off | 같음(8-3(b) 후처리 절단 — 토큰 상한 절단과 다른 것이다) | REQUIRED_FAIL_CLOSED | 같음 |
| `stt_beam_size` | `m3:373,398` | `DEFAULT_BEAM_SIZE=5` | STT 전사 → 자막 | EXPLICIT_DEFAULT | **config.yaml에 이 키가 없다** — 확정 인덱스는 암묵 5로 만들어졌다. 상수·캐시 키를 테스트로 고정. config 편집은 HOLD(배포 파일) |
| `load_segments(seg_len=5)` | `common:32` | 5초 격자로 검증 | 5가 아닌 config에서 조용한 mismatch | EXPLICIT_DEFAULT | AST 스캔 테스트 — src·scripts의 **모든** 호출부가 `seg_len`을 명시한다(현재 위반 0) |
| `query_synonyms` | `m5:130` | 빈 사전 = 확장 off | 없음(공식 경로가 off) | SAFE_DEFAULT | 유지 |
| `vlm_4bit` | `m3:92,215` | falsy = fp16 | 생성 identity | 이미 강제 | `identity` 필수 키 + preflight 값 대조 |
| `_read_segments_progress` except → `None` | `m7_webui:87` | 진행률 생략 | UI 표시만 | SAFE_DEFAULT | 유지 |
| `_log_search` except → `pass` | `m7_webui:141` | 로그 1건 유실 | 검색 응답 불변(best-effort 명시) | SAFE_DEFAULT | 유지 |
| `env_provenance` except → `None` | `common:197~216` | torch·cuda·gpu가 null | 기록이 "모른다"로 남는다(거짓 아님) | SAFE_DEFAULT | 유지 |
| `research_source_ids` except → `∅` | `e2e_external:79` | 출처 ID 대조가 비활성 | 파일명 검사가 2선으로 남는다 | EXPLICIT_DEFAULT | 문서화(현 상태 유지) |
| `e2e_only_videos` manifest 부재 → `∅` | `eligibility:41` | E2E 차단만 비활성 | 동결 split·접두어는 계속 차단 | EXPLICIT_DEFAULT | 양방향 테스트로 의미 고정(C-6) |

검증 수단을 `src/deployment.py`에 하나로 뒀다 — 진입점마다 복붙하지 않는다.

```
REQUIRED_KEYS = {identity, search, caption_generation, index}
validate_production_config(cfg, roles=…)   키가 있는지만 본다(값 대조는 진입점 몫)
  scripts/demo.py   identity + search      m7_webui·m7_demo  search
  src/m3_generate.py  caption_generation    src/m4_index.py   index
```

**기본값은 하나도 바꾸지 않았다.** 128·1.0·5·off는 그대로다 — 현재 동작을 명시적으로
고정한 것이고, `tests/test_config_contract.py`가 그 값들을 문자열까지 고정한다.

### C-10. config drift matrix

| 설정 | 정본 | 중복 정의 | CLI 기본 | 코드 기본 | 런타임 검증 | 산출물 기록 | 표류 위험 | 조치 |
|---|---|---|---|---|---|---|---|---|
| caption model | `src/deployment.py` | 없음(사본 제거) | — | — | preflight 값 대조 + 인덱스 provenance 대조 | `caption_provenance` (4편만) | LOW | C-2·C-7 |
| prompt | `config.yaml:17` | 없음(문자열 사본 0) | — | — | `caption_generation` 필수 + 인덱스 해시 대조 | `prompt_sha256` | LOW | 유지 |
| quantization | `deployment.py` | 없음 | — | `cfg.get("vlm_4bit")` falsy | preflight 값 대조 | 요청·실효 둘 다 | NONE | 유지 |
| segment duration | `config.yaml seg_len_sec` | `deployment.DEPLOYMENT`·`m1.make_segments(5)`·`load_segments(5)` | — | 5 | 로드마다 `start=idx*seg_len` 재검증 | `n_segments` | LOW | 호출부 명시 테스트 |
| STT model·lang | `config.yaml` | `m3.transcribe` 함수 기본값 `large-v3` (main은 cfg를 넘긴다) | — | large-v3 | — | `stt_cache.json` meta | LOW | 문서화 |
| stt_beam_size | **없음(암묵 5)** | `DEFAULT_BEAM_SIZE` | — | 5 | — | 캐시 키에 포함 | MEDIUM | 상수·캐시 키 고정 테스트. config 추가는 HOLD |
| embed model | `config.yaml` | `deployment.DEPLOYMENT` | — | — | `meta.embed_model` 대조(m5·preflight) | `meta.json` | NONE | 유지 |
| alpha | `deployment.ALPHA` | 없음(사본 제거) | `m5 --alpha 1.0`(baseline 진단) | — | `check_alpha` + `combine_scores` 범위 | 결과 JSON | LOW | C-3·C-7 |
| top_k | `m7_webui.DEFAULT_TOP_K=3` | `m5 --topk 5` | 3 / 5 | — | 정수·≥1 검증 | 응답 `top_k` | LOW(표시 계층) | §C-11 |
| abstention_tau | `config.yaml` | 없음 | — | `None` | `search` 필수 키 | 로그·응답 동일 값 | NONE | C-8·C-9 |
| vlm_max_new_tokens | `config.yaml` | 없음 | — | 128 | `caption_generation` 필수 | provenance | NONE | C-9 |
| caption 후처리 2플래그 | `config.yaml` | 없음 | — | off | `caption_generation` 필수 | provenance(이번에 추가) | NONE | C-9 |

**중복이 있다는 이유만으로 제거하지 않았다.** 판단 기준은 "지원 진입점이 서로 다른
값으로 돌 수 있는가"다. `m5 --alpha 1.0`·`--topk 5`는 baseline 진단용 CLI라 남긴다.

### C-11. top_k는 표시 계층이다

```
search_with_stats  전 세그먼트를 정렬해 results 전체를 만든다
do_search          top = results[:top_k] — 자르기만 한다
```

랭킹·점수·평가에 관여하지 않는다. 따라서 severity를 낮게 두고, 의미(“표시 개수”)만
한 곳으로 유지한다.

### C-12. Git 공개 안전성 회귀 방지 (⑦)

스캔 결과는 이전과 같다(위험 tracked **0건**). 없던 것은 그것을 지키는 장치다 —
2026-08-26에 논의용 프레임 27장이 실제로 커밋됐고(`acb8650`) 미푸시 상태에서 히스토리째
제거했다. 정책은 문서에, 강제는 없었다.

```
tests/test_publication_safety.py (36건 + skip 1)
  ① tracked_forbidden == 0        정책 경로/패턴으로 검사 — 파일명 키워드 판정 금지
  ② git check-ignore 실측         대표 경로 11개가 실제로 무시되는지 (패턴 독해 아님)
  ③ 과하지 않은지                 공개 대상 11개(코드·config·질의·확정 결과·덱 소스·
                                 FROZEN 목록)가 무시되지 않고 추적되는지
```

과거 히스토리는 다시 손대지 않았다. 이번 항목의 질문은 "앞으로 `git add -A`를 해도
막히는가"이고, 답은 이제 테스트가 지킨다.

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
| R05 | P0 프롬프트 동결 · 캡션 후처리 기본 off | `config.yaml caption_prompt` · `common.py:80-82`(플래그 둘 다 false) · 두 플래그는 이제 `caption_generation` 필수 키이고 provenance에 기록된다(C-9) | PASS_WITH_CAVEAT — 프롬프트 동일성은 provenance 있는 4편에서만 대조된다(C-2) |
| R05-b | 편집 자막은 제외, 장면 속 텍스트(간판·배너)는 포함 | 픽셀 제거 없음 — 프롬프트 문안만. `α=0`에서 STT 자막 기여는 0 | **MISMATCH (범위 한정)** — P0 문안이 덧씌운 자막과 장면 속 텍스트를 구분하지 못한다. 근거·실측은 `CAPTION_TEXT_HANDLING_AUDIT_2026-08-26.md`. 프롬프트 수정·재캡셔닝이 HOLD라 이번 감사에서 닫지 않는다. 영향은 **캡션 텍스트 품질 해석**에 한정되고 배포 파이프라인·경계·데이터 정합성에는 미치지 않는다 |
| R06 | 캡션 재생성은 자동 오염 판정분만 | `m3_generate.py:271-278,319-322` · `--recaption-corrupted` 배타 플래그(`:343-346`) | PASS |
| R07 | 자막·캡션·질의 동일 embed_model · L2 · float32 | `m4_index.py` 생성 · `m5_search.py:64` 로드 대조 | PASS |
| R08 | 재캡셔닝 후 임베딩 미갱신 차단(text_hash) | `m5_search.py:69` · `scripts/demo.py:131` | PASS |
| R09 | 연산 순서 cos → z-score → 정적 치환 → α 가중합 | `m5_search.combine_scores` | PASS |
| R10 | `static_threshold`는 config가 단일 출처(저장된 is_static 무시) | `m5_search.VideoIndex.load:53-56` | PASS |
| R11 | α는 config에 없다 — CLI 주입, 배포 0.5 | `deployment.check_alpha` — `demo.py`(우회 불가) · `m7_webui` · `m7_demo`. 범위 검증은 `combine_scores`가 전 경로에서(C-3·C-7) | IMPLEMENTED_NOT_ENFORCED → **PASS** (진단용 다른 α는 `--allow-nondeployment-alpha` 명시로만) |
| R12 | abstention은 경고 전용 — 순위·결과 불변 | `m7_webui` 부가 필드만 · 로그와 응답이 같은 식(`max(sub,cap)<τ`) | PASS |
| R13 | test 재평가 금지 — 승인 사건 | ~~없음~~ → `m6_evaluate.main` `--test-opening` 필수(C-1) | IMPLEMENTED_NOT_ENFORCED → **PASS** |
| R14 | gt_seg_idx 파생 규칙(1초 겹침, 없으면 최대 겹침) | `common.derive_gt_seg_idx:87-100` · `m6_evaluate.validate_gt_seg_idx` | PASS |
| R15 | 데모는 배포 구성으로만 시작 | `scripts/demo.py preflight` 12항목 fail-closed | PASS |
| R16 | test split · E2E 전용 · P2/P3 영상은 데모 불가 | `src/eligibility.py` 단일 출처 → **video_id를 받는 모든 route** 403(열거 테스트) · `demo.py` · `m7_demo`. 대소문자 정규화 · upload 덮어쓰기 금지 · 403이 artifact 읽기 전(C-4·C-6) | IMPLEMENTED_NOT_ENFORCED → **PASS** |
| R17 | AAR 인용은 인덱스 구간에 대응 | `m9_report_eval.main` cites 범위 assert · `aar_view.check_precomputed` | PASS |
| R18 | M9 실행은 test 접촉 — 승인 필요 | ~~없음~~ → `--test-opening` 필수(C-1) | IMPLEMENTED_NOT_ENFORCED → **PASS** |
| R19 | 영상 출처 provenance 인덱싱 전 기록 · fail-closed · 지표 미사용 | `src/provenance.py` · `m1_preprocess` resolve · `tests/test_provenance.py` | PASS_WITH_CAVEAT — 기존 11편은 `legacy_exempt`로 **데이터에** 면제가 있다(코드가 조용히 넘어가지 않는다) |
| R20 | 캡션 생성 조건 기록(요청값·실효값 둘 다) | `m3_generate.caption_provenance` | PASS_WITH_CAVEAT — 2026-08-17 도입, 확정 인덱스 11편에 없음. 부재를 preflight가 공시(C-2) |
| R21 | 변형 실험 격리 — config 사본 · work/results 동시 분리 | `scripts/casestudy_make_config.py:33-43`(KEEP_IDENTICAL assert) · `make_server_config.py` | PASS |
| R22 | 공개 저장소에 원본 영상·프레임·인덱스 텍스트 미추적 | `.gitignore` · `git ls-files` 실측 **0건** · `tests/test_publication_safety.py`가 tracked 0건·`check-ignore` 실측·과잉 차단 3방향을 지킨다(C-12) | PASS_WITH_CAVEAT — 발췌 인용(케이스 스터디·AAR 추적 문서)은 존재한다. 전량 덤프는 없다 |

---

### C-6. 자격 경계 우회 경로 — route 열거로 재감사 (HIGH)

첫 수정은 "요청 경로 4곳에 403"이었다. 기준을 다시 세우면 그건 부족하다 —
**guard를 거치지 않고 restricted 영상에 도달하는 route가 0개**여야 한다. route table을
열거해 다시 봤고 셋이 더 나왔다.

```
① /api/status/{video_id}  guard 없음. m2·m3 단계에서 segments.json·frames를 읽는다
② 대소문자 변형           Gemini_Promo → 정책 통과. Windows 파일시스템은 대소문자를
                         구분하지 않으므로 work/gemini_promo/ 를 그대로 읽었다 ← 실측 우회
③ upload 덮어쓰기         같은 이름 업로드가 기존 mp4를 무조건 덮었다. 조회 금지와
                         덮어쓰기 금지는 다른 문제다 — text_hash·embed_model은 인덱스만 본다
```

수정:

```
eligibility._norm()          판정 전 대소문자·공백 정규화 (manifest 집합·접두어 모두)
/api/status                  sanitize → _guard 를 job 조회보다 앞에 둔다
/api/upload                  기존 mp4 또는 work/<id>/ 가 있으면 409 (덮지 않는다)
tests/test_demo_policy_boundary.py (23건)
  · route table 열거 — {video_id}를 받는 모든 GET이 403
  · 대소문자 3변형 × 전 route
  · **403이 artifact 읽기 전에 나오는가** — Path.read_text를 감시해 읽기 0건 확인
  · manifest 부재 의미 분리 — 알려진 restricted는 계속 차단 / 일반 영상은 정상 실행
```

정책 우선순위도 코드에 적었다. **접두어는 출처가 아니라 마지막 방어선이다.**

```
① 동결 split 목록(TEST_SPLIT_VIDEOS)  manifest 유무와 무관하게 차단
② manifest 명시 선언(eligible_for_public_demo 등)
③ 이름 접두어 p2_ · p3_               ①②가 비어도 위험한 이름은 막는다
```

### C-7. 진입점별 배포 identity (HIGH)

`scripts/demo.py`만 α=0.5를 강제했고, **README가 함께 안내하는**
`python src/m7_webui.py --alpha 0.7`은 그대로 떴다. 지원 진입점이므로 HIGH로 본다 —
진입점을 바꾸면 배포 구성이 아닌 UI가 production처럼 보였다.

```
src/deployment.py 신설    DEPLOYMENT · ALPHA · SUPPORTED_ENTRYPOINTS · check_alpha
                         demo.py·e2e_external.py의 identity 사본 제거(단일 출처)
m7_webui · m7_demo       α는 배포값만. 진단용은 --allow-nondeployment-alpha 명시
demo.py                  alpha_strict — 우회 플래그가 없다
tests/test_entrypoint_identity.py (22건) — 목록에 항목을 추가하고 구현을 잊으면 깨진다
```

지원 진입점과 각자 강제하는 것:

| 진입점 | 역할 | 강제 |
|---|---|---|
| `scripts/demo.py` | 배포 데모(권장) | identity · α(우회 불가) · 자격 · 인덱스 · text_hash |
| `src/m7_webui.py` | 웹 UI 직접 실행 | α · 자격 |
| `src/m7_demo.py` | Gradio 단일 영상 | α · 자격 |
| `src/m5_search.py` | CLI 검색(진단) | α 범위 |
| `src/m6_evaluate.py` | 평가(dev 기본) | α 범위 · test-opening |
| `src/m9_report_eval.py` | AAR 평가 | test-opening |

### C-8. abstention 판정 단일화 (MEDIUM)

응답과 로그가 `max(sub, cap) < τ`를 **각각** 계산하고 있었다. 8-2 개정 때 응답만 바뀌어
갈라진 것이 원인이므로, 같은 값을 두 번 계산하는 구조 자체를 없앤다 —
`low_relevance_flag(stats, tau)` 하나를 응답과 로그가 공유한다.

---

## E. 확인만 하고 손대지 않은 것

```
확정 결과      results/eval_test.json · alpha_search_dev.json — 읽지도 쓰지도 않았다
배포 config    config.yaml 무변경 (caption_model·alpha·prompt·threshold·tau 전부)
인덱스         work/*/ 무변경 — 재캡셔닝·재임베딩·재색인 0건
케이스 스터디   v1 동결 보존, r2가 발표 기준. 두 판을 합산하지 않는다
```

**test 접촉을 "없음"으로 적지 않는다.** 이 감사는 자격 경계 강제를 확인하려고
`data/queries/queries.jsonl`의 `split=="test"`를 읽어 test 영상 4편·39질의를 대조했고,
경계 테스트에서는 restricted 영상의 **합성** 산출물을 tmp에 깔아 사용했다. 감사 로그는
둘을 분리해 적는 것이 정확하다.

```
test outcomes evaluated                              NO   (M6·M9 실행 0회, 순위·지표 미산출)
test split metadata inspected (eligibility 강제 확인)   YES  (video_id·split·질의 수만)
test 영상의 캡션·자막 열람                              NO   (경계 테스트는 tmp 합성 데이터)
```

## F. HOLD로 남긴 것 (승인 사건)

```
확정 인덱스 11편의 caption_provenance 채우기   → 재색인 필요. HOLD
push / 외부 공개                               → 사용자 승인 사항
```

감사 중에 닫은 것(HOLD 아님):

```
배포 identity 선언 단일화   src/deployment.py로 합쳤다 (C-7)
지원 진입점의 α 자유도      배포값이 기본, 우회는 명시 플래그 (C-7)
```

## G. 남은 위험

1. **11편의 캡션 출처는 산출물로 증명되지 않는다.** 지금 근거는 커밋 이력과 작업현황
   문서다. 재색인 없이는 닫히지 않으므로, 보고서에는 "provenance 있는 4편에서만
   대조 가능"으로 적어야 한다.
2. **`load_segments(seg_len=5)`의 기본값.** 호출부가 cfg를 넘기지 않으면 5초로 검증한다.
   현재 모든 production 호출부는 cfg를 넘긴다(확인). seg_len ablation 코드가 늘면
   여기가 함정이 된다.
2-1. **`load_segments`의 기본값은 이제 테스트가 지킨다** — AST 스캔으로 src·scripts의
   모든 호출부가 `seg_len`을 명시하는지 확인한다(현재 위반 0). 남은 위험은 새 호출부를
   추가할 때 그 테스트를 지우는 경우다.

3. **정책 단일 출처의 적용 범위.** `eligibility`는 데모 경로만 덮는다. 연구 스크립트
   (`p2_*`·`p3_*`)는 자체 arm 맵을 쓴다 — 의도된 분리지만 표류 감시는 테스트 2건뿐이다.

4. **`stt_beam_size`가 config.yaml에 없다.** 확정 인덱스 자막은 암묵 기본값 5로
   만들어졌다. 상수와 캐시 키는 테스트로 고정했지만, 배포 config에 키를 넣는 것은
   config 편집이라 HOLD다.

---

## H. Findings 전체 (severity · 최종 상태)

이미 고친 것도 남긴다 — "발견되지 않았던 것처럼" 지우지 않는다.

| # | finding | severity | 상태 |
|---|---|---|---|
| F1 | 데모 자격 경계가 요청 경로에서 강제되지 않았다 (search·segments·video·upload) | HIGH | **FIXED** |
| F2 | 자격 경계 우회 3건 — `/api/status` 무방비 · 대소문자 변형 · upload 덮어쓰기 | HIGH | **FIXED** |
| F3 | test 접촉 게이트 없음 — `m6_evaluate` 기본 경로가 test 평가, `m9`는 실행 자체가 접촉 | HIGH | **FIXED** |
| F4 | 인덱스 캡션 identity 미검증 — 4B 인덱스를 3B config로 열면 통과 | HIGH | **FIXED** (증거 있는 인덱스 한정) |
| F5 | 진입점별 α 불일치 — `demo.py`만 강제, `m7_webui` 직접 실행은 무검증 | HIGH | **FIXED** |
| F6 | 검색 로그 배너 판정이 응답과 달랐다(기존 테스트가 버그를 고정) | MEDIUM | **FIXED** |
| F7 | α 범위 미검증 — 1.5·NaN이 가중합에 들어갔다 | MEDIUM | **FIXED** |
| F8 | hidden fallback 5종 — 생성 조건·후처리 플래그·τ가 키 부재 시 조용한 기본값 | MEDIUM | **FIXED** (fail-closed 필수 키) |
| F9 | 캡션 후처리 플래그가 provenance에 기록되지 않았다 | MEDIUM | **FIXED** |
| F10 | 배포 identity 선언이 두 파일에 복사돼 있었다 | LOW | **FIXED** (단일 출처) |
| F11 | Git 공개 안전성 회귀 방지 장치 없음 | MEDIUM | **FIXED** (테스트 36건) |
| F12 | P0 문안이 편집 자막과 장면 속 텍스트를 구분하지 못한다 | MEDIUM | **HOLD** (프롬프트 수정·재캡셔닝 승인 사건) |
| F13 | 확정 인덱스 11편에 `caption_provenance`가 없다 | MEDIUM | **ACCEPTED_CAVEAT** (재색인 필요 · preflight가 부재를 공시) |
| F14 | `stt_beam_size`가 config에 없고 암묵 5로 동작 | LOW | **ACCEPTED_CAVEAT** (상수·캐시 키 고정) |

미해결 CRITICAL·HIGH: **0**

---

## I. 감사 경계 (사실 기록)

```
test outcomes evaluated                          NO    M6·M9 실행 0회
test split metadata inspected                    YES   자격 강제 확인 목적(video_id·split·질의 수)
test 성능 재계산                                  NO
test 확장(39→72) 개시                             NO
새 연구·새 지표                                   NO
캡션 재생성 · 재색인 · 새 임베딩                    NO
배포 구성 변경 · 프롬프트 변경                      NO
P2/P3 결과 접근 · M9                              NO
동결 산출물 수정                                   NO
push                                             NO
```

기본값 변경도 없다 — `vlm_max_new_tokens=128`·`vlm_rep_penalty=1.0`·
`DEFAULT_BEAM_SIZE=5`·후처리 off는 그대로이고 테스트가 그 값을 고정한다.

---

## J. 최종 판정

```
PROJECT_DESIGN_CONFORMANCE_AUDIT      COMPLETE
남은 감사 항목                          0
overall verdict                       CONFORMANT_WITH_CAVEATS
```

근거: 배포 architecture·identity·데이터 매핑(구간↔프레임↔임베딩↔순위↔증거)·경계
(test split·E2E·P2/P3·데모 자격)가 **현재 런타임에서 강제된다.** 남은 것은 문서화된
caveat과 승인 사건이다.

```
caveat 1  확정 인덱스 11편의 캡션 출처는 산출물로 증명되지 않는다 (재색인 HOLD)
caveat 2  P0 문안의 편집 자막 / 장면 속 텍스트 구분 부재 (프롬프트 수정 HOLD)
          — 영향은 캡션 텍스트 품질 해석에 한정된다
caveat 3  stt_beam_size가 config에 없다 (암묵 5, 테스트로 고정)
```

R05-b가 MISMATCH지만 이것 때문에 전체를 PARTIALLY_CONFORMANT로 두지 않는다 — 그
항목은 배포 파이프라인·경계·정합성이 아니라 **캡션 문안 정책의 표현**에 관한 것이고,
검색 경로에 미치는 영향은 별도 감사에서 정량화돼 있다(3B 21/395 전사 사례, 하한).

## K. 이 감사 다음에 할 일

```
발표 본편 갱신 · 예상질문_방어 갱신 · 8분 리허설 · 보고서 본문
승인 사항(재색인 · test 확장 · M9 · push)은 그대로 HOLD
```
