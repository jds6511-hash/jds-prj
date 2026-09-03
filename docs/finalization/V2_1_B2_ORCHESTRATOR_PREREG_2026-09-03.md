# B2 사전등록 — v2.1 report orchestrator (2026-09-03)

```
preregistration drafting     APPROVED   ← 이 문서
server reservation prep      APPROVED   §8
orchestrator implementation  HOLD
4090 production run          HOLD
```

**구현하지 않는다.** 이 문서가 고정하는 것은 입력 경계 · provider · stage/hash/resume ·
실패 semantics · HWPX 경로 · 서버 계약 · dry-run fixture다.

승인 이유는 GPU가 아니라 **orchestrator가 새 production execution boundary**라는 것이다.
지금 저장소에서 `segments → … → HWPX`를 실제 영상 하나로 잇는 경로는 **테스트 하네스
`tests/v2_1_gate_b.py` 한 곳뿐**이다(실측: `validate_grounding` 호출부가 그 파일에만
있다). 이것을 script로 옮기는 순간 failure semantics · resume · artifact provenance를
새로 책임진다.

---

## 1. 입력 경계 — B1 산출물을 소비한다

```
B1   ingestion / evidence production      M1~M3          완료(2026-09-03)
B2   v2.1 report production               canonical~HWPX  이 사전등록
```

**B2 안에서 M1~M3를 다시 실행하지 않는다.** 재실행하면 같은 영상의 evidence가 두 벌이
되고 어느 것이 보고서의 근거인지 사후에 갈리지 않는다.

실측 입력(B1 full run).

```
work_full/full_xekZO4n4QuE/segments.json   485구간 · duration 2424.133s
    필드   idx · start · end · is_static · motion_score · rep_frame · subtitle · caption
    caption 비어있지 않음 485/485 · subtitle 296/485
work_full/full_xekZO4n4QuE/frames/         rep_frame 참조 대상
work_full/full_xekZO4n4QuE/audio.wav · stt_cache.json
provenance   videos.json["videos"]["full_xekZO4n4QuE"] · sha256 ea0e9f4866612820…
B1 실행 기록  runs/full/full_probe.json (code HEAD be35249a · config sha 8484cc99b871a2c0)
```

ingest 어댑터는 이미 있다 — `v2_1_segments.legacy_segments_to_canonical`이 `idx/start/end`를
canonical로 바꾸는 **유일한 경계**다. B2는 그 함수만 쓰고 legacy 필드를 뒤로 흘리지 않는다.

raw store 재료도 여기서 만든다.

```
asr  → RawStore.store(source_type="asr", producer="m3_generate", producer_version=<B1 code HEAD>)
vlm  → 같은 방식
근거  v2.1 raw-before-parse는 **LLM 출력**에 대한 계약이고, ASR·caption 원문은
      B1이 만든 것이므로 **생성자를 B1으로 기록**한다. B2가 만든 것처럼 적지 않는다
```

## 2. canonical provider 고정

```
boundary provider   fixed_window_v1   (v2_1_boundary.DEFAULT_PROVIDER_NAME)
window_sec          60.0              (v2_1_fixed_window.WINDOW_SEC 기본값)
실측 결과            485구간 → episode 41개 · 첫 (0,11) · 마지막 (480,484)
기록                provider_name · provider_version · provider_config를 정본에 남긴다
```

```
금지   change-point provider 자동 선택
      C0 boundary signal 사용
      LLM boundary
      fallback provider (provider 실패 시 다른 provider로 넘어가지 않는다)
```

## 3. LLM은 content만

```
episode structure   코드가 만든다   (경계·구간 소속·순서·시간)
episode content     LLM이 만든다   (summary · dialogue_note · stt_cites)
```

Gate B 철학을 B2 때문에 재설계하지 않는다. LLM 호출은 `v2_1_llm_adapter.invoke_episode`
경로만 쓰고, 프롬프트는 `v2_1_prompt.build_episode_prompt`가 만든 것을 그대로 쓴다.

```
prompt_version   episode_content_v2   (변경하지 않는다)
prompt_hash      contract_hash()      정본에 기록
```

## 4. stage artifact — S0 ~ S7

```
S0  ingest validation      segments 계약·provenance·raw store 적재
S1  canonical episodes     fixed_window_v1 · partition 검증
S2  raw LLM outputs        episode별 raw 응답 (parse 이전)
S3  parsed content         parse + merge_content
S4  grounding/sparse-safe  binding → grounding → sparse safe mode
S5  aar                    aar_canonical.json + validate_aar
S6  presentation           highlight · lineage · synthesis · presentation
S7  HWPX                   A2' 산출물 (+ MD)
```

각 stage는 산출물과 함께 **재사용 조건**을 적는다.

```
stage manifest 항목
    input_hash        직전 stage 산출물의 sha256
    config_hash       config_server.yaml sha256
    code_revision     git HEAD
    prompt_version    · prompt_hash
    model_identifier  model_id · do_sample · max_new_tokens · llm_4bit
    started_at · finished_at · wall_seconds
```

**resume는 stage 단위로만 하고, 존재만으로 신뢰하지 않는다.**

```
재사용   위 다섯(input_hash · config_hash · code_revision · prompt version/hash · model id)이
        **전부 일치**할 때만
불일치   그 stage부터 다시 만든다. 부분 병합·수동 보정 금지
기록     재사용했는지 다시 만들었는지를 stage manifest에 남긴다
```

## 5. raw-before-parse 유지

```
LLM 호출 → raw 응답 저장 → parse
```

서버 실행이라고 이 순서를 바꾸지 않는다. `RawStore.store_then_parse`가 그 계약의 주인이고,
orchestrator는 그것을 우회해 파싱하지 않는다. parse가 깨져도 raw는 남는다.

## 6. 실패 semantics — 사전에 고정

```
LLM 모델 사용 불가        explicit FAIL · ENVIRONMENT_FAILURE
                        **더 작은 모델로 자동 하향 금지** (3B 하향은 예시 복사 오염으로 기각됨)
CUDA OOM                explicit FAIL · ENVIRONMENT_BLOCKED · 4bit 자동 전환 금지
서버 예약 실패            실행하지 않는다. 로컬 대체 실행 금지
parse failure           raw 보존 + PARSE_CONTRACT_FAILURE (내용은 비운다)
grounding failure       구조 보존 · dialogue만 제거 · 상태는 FAIL로 남긴다
sparse eligible == 1    SPARSE_EVIDENCE_DETERMINISTIC (TRI-005 C3 그대로)
eligible == 0           프롬프트 거부(PromptError) · summary 없음 (ERR-009)
HWPX 실패               canonical·MD 유지 · **silent renderer fallback 금지**
partition 위반           hard fail (문서를 만들지 않는다)
```

## 7. HWPX 경로

```
primary   scripts/v2_1_hwpx_owpml.py        순수 Python · 3중 검증 통과
oracle    scripts/v2_1_hwpx_via_hangul.py   한글 COM · Windows 전용 · 진단·대조용
금지      src/v2_1_render_hwpx.py           KNOWN OPERATIONAL DEFECT — B2에서 쓰지 않는다
```

```
A2' 실패 시   explicit FAIL
             A1으로 **자동 fallback하지 않는다**. A1은 별도 명령으로만 부른다
대조         두 경로의 semantic text 동일성은 이미 differential test가 잰다
```

## 8. 서버 계약 — 예약 준비

```
GPU        RTX 4090 24GB class
model      Qwen/Qwen2.5-7B-Instruct
llm_4bit   false            (24GB · 기존 실측 20.1GB — headroom 크지 않다)
sampling   do_sample=false  (결정적)
저장        /ssd · HF_HOME=/ssd/$USER/cache  (비대화형 SSH는 .bashrc를 읽지 않으므로 명령마다 명시)
config     scripts/make_server_config.py로 생성한 config_server.yaml — 본 config 편집 금지
접속        `SERVER_LOCAL.md`(추적 안 함)에만 실제 값. 문서·커밋에는 자리표시자만
           `<SERVER_USER>` · `<SERVER_HOST>` · `<LAB_MACHINE>`
전례        docs/finalization/AAR_SERVER_RUNBOOK_2026-08-26.md — 머신 라벨은 호스트명이 아니다
```

실행 중 B1과 같은 형식으로 기록한다.

```
VRAM 폴링(5초)   peak · p95 · median · util
OOM 여부
episode별 wall time   (41 episode 예정)
LLM 실패·재시도 횟수
stage별 wall time · 재사용 여부
```

## 9. dry-run fixture — O1 · O2 · O3

전체 영상 전에 **합성 fixture 3종으로 artifact chain 끝까지** 통과시킨다. 서버 LLM 없이,
모델 출력 자리에 payload를 주입해 orchestrator 자체를 검증한다.

```
O1  normal multi-episode
    입력   S1 시나리오 · 3 episode 이상 · dialogue + 유효 인용
    기대   S0~S7 전부 생성 · grounding PASS/NOT_APPLICABLE
           summary_mode MODEL_ABSTRACTIVE · A2' HWPX 구조 검증 PASS

O2  eligible == 1 sparse
    입력   S4 + 유효 발화 1건 · 모델이 발명 서사를 낸다
    기대   정본 summary = 근거 원문 · summary_mode SPARSE_EVIDENCE_DETERMINISTIC
           발명 문자열이 HWPX 본문에 0건 (TRI-005 회귀가 orchestrator 경로에서도 성립)

O3  no eligible evidence / parse failure
    입력   S5(전 채널 공백) + 깨진 payload 하나
    기대   프롬프트 거부(PromptError)로 기록 · content 실패 상태 보존 · raw 보존
           구조·시간·순서 유지 · 표현에서 NO_RELIABLE_CONTENT
           문서를 "생성 실패" 같은 문구로 메우지 않는다
```

세 개가 통과한 뒤에 40.4분 B1 산출물을 넣는다. **별도 3분 LLM canary는 두지 않는다** —
7B 경로는 Gate B(B-02b)에서 서버 실측된 바 있고, 이번 신규 위험은 모델이 아니라
orchestrator다.

## 10. closure 목표 — 새 acceptance matrix가 아니다

post-v2.1 operational integration으로 기록한다.

```
real B1 artifacts consumed          O
fixed_window canonical produced     O
Qwen 7B content produced            O
raw outputs preserved               O
grounding applied                   O
TRI-005 sparse mode preserved       O
AAR generated (validate_aar ok)     O
presentation generated              O
A2' HWPX opens in Hancom            O
all provenance recorded             O
```

성공해도 다음은 그대로다.

```
M9 opened              NO
official test opened   NO
general entailment     NO   (GRD-004 P1 WAIVED 유지)
BCS generalization     NO
matrix 재판정           없음 — baseline 6e79ac3 판정은 소급 변경하지 않는다
```

## 11. 승인이 필요한 것

```
1  §4 stage/hash/resume 계약
2  §6 실패 semantics (특히 자동 모델 하향·자동 4bit 전환 금지)
3  §7 A2' primary · A1 자동 fallback 금지
4  §8 서버 계약 · 예약
5  §9 O1/O2/O3 통과 후 전체 실행
```

그다음 순서.

```
사전등록 검토 → orchestrator 구현 승인 → O1~O3 dry-run → 서버 예약 → 전체 실행
→ 실행 기록·산출물 보고 → post-v2.1 integration 문서화
```
