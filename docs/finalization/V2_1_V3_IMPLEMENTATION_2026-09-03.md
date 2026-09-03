# summary-only v3 — 승인 조건 · 구현 · mutation 결과 (2026-09-03)

사전등록 본문은 고치지 않는다(`V2_1_V3_SUMMARY_ONLY_PREREG_2026-09-03.md`).
이 문서는 그 위에 얹힌 **승인 조건과 구현 실측**이다.

```
1  v2/v3 병행 계약                  APPROVED
2  R0/R1 동일조건 서버 비교 1회       APPROVED
3  primary metric = eligible / 41    APPROVED
4  서버 실행 전 합성 테스트           APPROVED

v2 frozen contract 수정            NOT AUTHORIZED
OPEN-12 완화                       NOT AUTHORIZED
summary 재grounding                NOT AUTHORIZED
GRD-004 상태 변경                  NOT AUTHORIZED
```

## 1. 성공을 두 층으로 나눈다

승인 조건에 따라 회수율과 mechanism을 **분리해서** 판정한다.

```
mechanism closure    dialogue_note·stt_cites 생성 = 0
                     dialogue 때문에 표현에서 빠진 구간 = 0
                     OPEN-12 무변경 · GEO 회귀 0 · TRI-005 회귀 0
                     → "선택적 dialogue field 때문에 표현 자격이 붕괴하는 결합이 제거됐다"

product outcome      eligible / 41 을 실측 그대로 적는다
                     2/41에서 늘지 않으면 H-R2는 지지되지 않은 것이다
                     늘어도 "요약이 사실이다"·"grounding이 해결됐다"로 쓰지 않는다
```

성공 시 쓸 수 있는 문장은 하나뿐이다.

```
The optional-dialogue failure path no longer suppresses otherwise present
canonical summaries.
```

## 2. 구현 — v2를 건드리지 않았다는 기계 증거

```
src/v2_1_prompt.py
    CONTRACT           그대로. 사전 내용 변경 0
    CONTRACT_V3        신규 (required ["summary"] · optional [] · omit_when_absent [])
    _TAIL              출력 지시문을 계약 밖 사전으로 분리
                       (계약 사전에 넣으면 v2의 prompt_hash가 바뀐다)
    CONTRACTS          {"v2", "v3"} — resolve_contract가 모르는 이름을 거부한다
    build_episode_prompt(..., *, contract=CONTRACT)     기본값 v2

scripts/v2_1_b2_orchestrate.py
    orchestrate(..., contract_name="v2")   기본값 v2
    fingerprint / S2 / S5가 선택된 계약의 version·hash를 기록한다
    --contract {v2,v3}                     CLI에서만 v3를 고른다
```

v2 계약 지문이 R0 실행 기록과 **같다**.

```
contract_hash(CONTRACT)                          beaa322ea0200d3d1f6cdccc2da7421f7bb79c2024186e3df1b8c918e12d2725
runs/b2_full_4090/aar_canonical.json  prompt_hash beaa322ea0200d3d1f6cdccc2da7421f7bb79c2024186e3df1b8c918e12d2725
contract_hash(CONTRACT_V3)                       a08e3c3c4988daa6639cf0316f8b5d81f466685590fb54400eeda7d6ab6610d7
```

이 값을 테스트가 상수로 못 박는다(`test_c_v2_contract_hash_is_the_one_already_recorded`).
v2 프롬프트 꼬리 5줄도 문자열로 고정했다.

## 3. mechanism metric — 지표를 먼저 검증했다

`distributions.presentation`을 orchestrator가 매 실행 기록한다.

```
episodes                            표현 입력에 들어온 구간 수
eligible                            primary metric (summary_eligible_for_presentation)
excluded_by_dialogue_grounding      정본에 요약이 있는데 grounding FAIL로 빠진 구간 수
excluded_episode_ids                그 구간 번호
dialogue_note_present               정본에 dialogue_note가 남은 구간 수
```

자격 판정은 `summary_eligible_for_presentation` **하나만** 쓴다 — 조건식을 다시 쓰면
OPEN-12가 생긴 방식으로 정의가 갈라진다.

지표가 공허하지 않다는 것을 두 방향으로 확인했다.

```
R0 정본 재계산      eligible 2 / 41 · excluded_by_dialogue_grounding 38    ← 실측 재현
합성 v2 arm        근거 없는 수량을 dialogue에 넣으면 excluded 1로 센다
합성 v3 arm        excluded 0 · dialogue_note_present 0
```

## 4. 합성 게이트 (서버 없이) — 23건 PASS

`tests/test_v2_1_prompt_v3.py`. orchestrator 실경로로 돈다(raw 저장 → 실제 parser →
binding → grounding → sparse → AAR → presentation → A2' HWPX).

```
normal            VALID_PARSE · summary 존재 · dialogue_note None
                  grounding NOT_APPLICABLE · eligible 2/2 · HWPX 본문에 요약 존재
                  **모델에 실제로 보낸 문자열**에 dialogue_note·stt_cites 0건
rich-STT          자격 발화가 근거 블록에 도달한다("seg#6 발화:") · source stt   (GEO-001)
dialogue-heavy    12구간 전부 발화 · 처리 성공 · source stt 유지               (GEO-004)
sparse            eligible == 1 → 정본 = 근거 원문 · SPARSE_EVIDENCE_DETERMINISTIC
                  발명 문장은 raw에만 남고 HWPX 본문에 0건
no-evidence       PromptError · LLM 호출 0 · EMPTY · 구조 유지 · eligible 0
parse 실패         raw 원문 보존 · PARSE_CONTRACT_FAILURE · 다음 구간 진행
계약 외 키          v3에서 모델이 dialogue를 내도 **판정을 거친다**(무검증 통과 없음)
v2 회귀            계약 미지정 = v2 · dialogue 생성·판정 그대로 · hash 동일
```

전체 suite `3,904 passed / 1 skipped / 0 xfailed` (REG-004는 커밋 전 dirty tree 항목).

## 5. mutation — 4개 전부 RED

```
M1  v3에 dialogue_note 재추가     RED   3건
      test_c_v3_requires_summary_and_declares_no_optional_field
      test_c_v3_prompt_never_names_the_dialogue_fields
      test_s_normal_the_prompt_sent_to_the_model_is_summary_only
M2  v3에 stt_cites 재요구         RED   같은 3건
M3  기본 계약을 v3로 바꿈          RED   2건
      test_c_the_default_call_is_v2
      test_c_v2_prompt_text_is_byte_for_byte_the_v2_tail
M4  sparse 권한 상실              RED   1건
      test_s_sparse_safe_mode_still_owns_the_sentence_under_v3
```

M3가 이번 건의 governance를 코드로 증명한다 — v2 수정이 아니라 **병행 계약 도입**이고,
v2 호출자가 모르는 채로 v3를 쓰는 경로는 없다.

## 6. 서버 비교 — 고정 조건

`scripts/v2_1_v3_paired_run.sh`. 계약만 바꿔 두 arm을 **연속으로** 돌린다.

```
바뀌는 것    prompt contract · output schema · PROMPT_VERSION

고정하는 것  B1 segments.json (같은 파일 · 같은 sha256)
            fixed_window_v1 · window_sec 60 → canonical episode 41
            Qwen2.5-7B-Instruct · bf16 · llm_4bit false
            do_sample false · max_new_tokens 512
            grounding 규칙 · OPEN-12 표현 자격 · presentation builder · A2' 렌더러
            같은 commit · 같은 config_server.yaml
```

```
R0를 보고 v3 프롬프트를 고쳐 R1을 돌리지 않는다. 한 번의 고정 비교로 끝낸다.
순서: 합성 게이트 → v3 계약 freeze(커밋) → R0 → R1 → 분석
```

## 7. 이 문서가 주장하지 않는 것

```
회수율이 개선됐다        아직 서버 비교를 돌리지 않았다
보고서가 제출 가능하다    SUBMISSION_READY = NO 그대로
GRD-004가 해제됐다      아니다 — P1 WAIVED 그대로
v2.1 판정이 바뀌었다     아니다 — baseline 6e79ac3 그대로 · M9 HOLD · official test UNOPENED
```
