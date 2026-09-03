# B2 orchestrator 구현 · dry-run 결과 (2026-09-03)

```
구현        scripts/v2_1_b2_orchestrate.py          신규
증거        tests/test_v2_1_b2_orchestrator.py      17건 (O 7 · R 8 · 계약 2)
사전등록     V2_1_B2_ORCHESTRATOR_PREREG_2026-09-03.md
서버 실행    아직 하지 않았다 — 4090 41-episode run은 별도 승인 사건이다
```

## 1. gate 결과

```
O1  정상 다구간            PASS   S0~S7 전부 생성 · LLM 호출 = episode 수 · MODEL_ABSTRACTIVE
O2  sparse eligible == 1   PASS   정본·HWPX에 발명 0 · raw에는 발명 보존
O3a eligible == 0          PASS   LLM 호출 0 · EMPTY 보존 · 구조 유지
O3b parse 실패             PASS   raw 원문 보존 · PARSE_CONTRACT_FAILURE · 다음 구간 진행

R1  완전 재사용            PASS   전 stage reused · 생성기 호출 0
R2  부분 stage             PASS   `_SUCCESS` 없으면 재사용 금지 · downstream 전부 재생성
R3  산출물 변조            PASS   hash 불일치 stage만 재생성 · 앞 stage 재사용 · 뒤 stale
R4  provenance 변경        PASS   model id 변경 · config 변경 각각 전 stage 무효
R5  S2 hard failure        PASS   ENVIRONMENT_BLOCKED · S2 미완료 · 일부 raw 보존 · downstream 0
R6  S7 실패                PASS   canonical 보존 · S7 미완료 · A1(COM) 호출 0

전체 suite   3,883 passed / 1 skipped / 0 xfailed
production fallback   0 (아래 §4)
```

## 2. 계약이 코드에서 어떻게 성립하는가

```
stage manifest   `_SUCCESS.json`
    fingerprint             config_hash · code_revision · prompt_version · prompt_hash · model_id
    upstream_artifact_hash  직전 stage 산출물 hash 집합의 지문
    outputs                 {상대경로: sha256} — 선언한 것 전부
    stage_complete          true. **모든 산출물 검증 뒤 마지막에** 기록한다
```

```
재사용 = 지문 5종 일치 AND upstream 일치 AND 산출물 존재 AND hash 일치 AND complete
무효 전파 = stage N 재생성 → N+1 ~ S7 디렉터리 폐기 (단방향)
소유 경로 = S0은 raw/asr·raw/vlm · S2는 raw/llm — 재생성 시 함께 버린다
```

`reusable()`이 다섯 조건을 모두 확인하고, 하나라도 어긋나면 그 stage부터 다시 만든다.
부분 stage는 **재사용하지 않는다** — R5의 두 번째 arm이 그것을 잰다(죽은 실행의 raw 1건이
남아 있어도 재실행은 전건 재생성이고 호출 수가 2로 돌아온다).

## 3. 실패 semantics 분리

```
hard stage failure (StageError)
    모델 로드 불가            ENVIRONMENT_FAILURE
    CUDA out of memory       ENVIRONMENT_BLOCKED
    canonical 무효            INVALID_CANONICAL
    HWPX 실패                HWPX_FAILED
    → 그 stage 미완료 · downstream 미실행

episode content failure (구조는 살아 있다)
    PromptError(eligible 0)  raw 없음 · EMPTY · no_usable_evidence
    parse 실패                raw 보존 · PARSE_CONTRACT_FAILURE
    grounding 실패            dialogue만 제거 · 상태 보존
    → 다음 episode를 계속 처리한다
```

`PromptError`를 orchestrator 실패로 올리지 않는다 — 올리면 ERR-009 의미가 깨진다.

## 4. 대체 경로가 없다는 것을 기계로 확인한다

```
test_the_orchestrator_has_no_fallback_paths
    pyhwpx · v2_1_hwpx_via_hangul · render_hwpx · load_in_4bit · "3B"/"1.5B" 문자열
    → 소스에 0건
transformers_provider
    llm_4bit=true를 받으면 즉시 StageError (서버 계약은 false)
    모델 로드 실패 시 더 작은 모델로 넘어가지 않는다
S7
    A2'(순수 Python)만 부른다. 실패하면 StageError — A1은 별도 명령으로만 쓴다
```

## 5. dry-run이 실물 경로를 탔다는 근거

fake 생성기는 **프롬프트를 받아 문자열을 돌려주는 자리**에만 있다. 그 뒤는 전부 실물이다.

```
raw 저장(store_then_parse) → 실제 parser → merge_content → bind_cites
→ validate_grounding → apply_sparse_summary → build_aar_canonical(validate_aar)
→ presentation_input → highlight · lineage · synthesis · presentation
→ A2' HWPX (구조 validator PASS)
```

O2가 TRI-005 end-to-end containment의 가장 강한 증거다.

```
raw store   "남성이 문을 열고 건물에 들어가 물건을 훔친 뒤 달아난다."   남아 있다
canonical   "남성이 문을 연다."   summary_mode = SPARSE_EVIDENCE_DETERMINISTIC
HWPX 본문    건물 · 훔친 · 달아난다  0건
```

## 6. 남은 것 — 서버 실행 전에 확인할 것

```
아직 안 한 것    4090 41-episode 실제 실행
                실제 HWPX의 한글 Open()·PDF export (소형 fixture와 별도 증거다)
                episode별 wall time · VRAM peak (측정 항목으로 잡혀 있다)
기록 예정        HF 해석된 snapshot revision · tokenizer revision
                (dry-run에서는 모델이 없어 unavailable로 남는다 — 추정해 적지 않는다)
```

## 7. 이 결과가 주장하지 않는 것

```
B2 operational COMPLETE      아니다 — 서버 실행과 실제 HWPX 열림 확인이 남았다
7B 출력 품질                  측정하지 않았다 (fake 생성기다)
matrix 재판정                 없다 — baseline 6e79ac3 판정은 그대로다
M9 · official test           그대로 HOLD
```
