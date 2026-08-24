# P2 GT 라벨링 프로토콜 amendment — **DRAFT** (2026-08-24)

**확정 문서가 아니다.** 사용자 승인 전이며, 승인 없이 실제 AI 초안 생성을 시작하지
않는다. 사전등록 본문과 보충1~4, `P2_GT_sample_size_amendment_2026-08-24.md`는
**수정하지 않는다.**

human-only 라벨링에서 **AI-first + 사람 심사(human adjudication)**로 바꾸는 안이다.
바꾸는 것은 **초안 작성 노동의 소재**뿐이고, 최종 GT 책임은 사람의 원본 확인에 있다.

## 0. 명칭 — 결과를 뭐라고 부를 수 있는가

```
쓸 수 없는 표현   "human-generated" · "fully human labeled" ·
                "175 real-user queries" · "fully human-generated query set"
정확한 표현      AI-first, human-adjudicated GT
                또는 hybrid human / AI-assisted GT
```

구성:

```
최초 20행    human-only
나머지 155행  AI draft + 필수 사람 심사
             (도구가 AI를 쓸 수 없는 행은 audit에 human-only/manual로 기록)
```

결과는 **"hybrid human / AI-assisted annotation 프로토콜 아래의 fresh P2 benchmark"**로
해석한다. 모든 AI 초안이 사람의 원본 영상 확인을 거쳐 확정됐다는 사실은 명시할 수 있다.

**PRIMARY 분석에서 두 provenance를 구분해 가중·선택·제외하지 않는다.**
`label_origin`은 audit metadata다.

## 1. 변경 시점 — P2-outcome-blind

```
P2 retrieval 실행       없음
P2 arm 산출물 열람       없음
P2 RR·MRR 계산          없음
p2_evaluate 실행         없음
P2 캡션·파이프라인 자막 열람  없음
사람 작성 완료            20 / 175
```

동결 산출물: `docs/probes/_scratch/p2_gt_hybrid_transition_freeze.json`

```
human_only         20건 · query_id 목록만 기록 (내용 미기록)
intake sha256      cefb69bf2e2701f9…
활성 설계            p2_175 · keep_mask f689a023…
시트 manifest        e845b84419c66e01…
archive · audit     315행 원본 · 140행 drop audit 각각 sha256
outcome_access      전부 false
```

**완료 20건의 text·gt_start·gt_end 내용은 동결 파일에 담지 않았다.** 이 파일이 AI
프롬프트·few-shot·품질 튜닝의 입력이 되면 human-only 분량이 초안에 새어 든다.

## 2. 기존 20건 처리

```
label_origin      human_only
분석 대상          그대로 final 175의 일부다
금지              AI 초안을 본 뒤 wording·boundary를 다시 고치는 것
금지              AI 프롬프트 튜닝 · few-shot 예시 · accept/reject 임계값 설정 ·
                 어떤 유형에 AI를 쓸지 결정하는 근거
calibration set   아니다
```

typo 수정 자체를 영원히 금지한다는 뜻은 아니다. **AI 초안을 본 뒤 고치는 것**을 금지한다.

## 3. AI가 볼 수 있는 것 / 못 보는 것

```
허용   query_id · video_id · 동결 query_type · 원본 영상 · 원본 음성 ·
      컨택트시트 · 구간 격자(idx/start/end/rep_frame) ·
      영상 자체에 박힌 자막·그래픽
금지   3B 캡션 · 4B 캡션 · 파이프라인 자막/STT · 임베딩 · 색인 · 검색 결과 ·
      순위 · 점수 · RR/MRR · arm 구분 · arm 비교 · p2_evaluate 산출물 ·
      기존 20건 human label 내용
```

**"원본 자막"과 "파이프라인 STT"를 구분한다.** 영상에 burn-in된 제작자 자막은 원본
영상의 일부이므로 볼 수 있다. `is_subtitle_credit`·Whisper 산출물은 파이프라인
산출물이므로 볼 수 없다.

코드로 고정: `p2_ai_draft.EVIDENCE_ALLOWED` · `EVIDENCE_FORBIDDEN`, 초안 스키마의
`FORBIDDEN_FIELDS`, 그리고 retrieval·evaluation 모듈 import 0(테스트로 검사).

## 4. AI가 만드는 것은 초안뿐

```
초안       draft_text · draft_gt_start · draft_gt_end (+ rationale · evidence_seg_idx)
아닌 것     GT
자동 복사    없다 — 초안을 active intake에 옮겨 "완료"로 세지 않는다
필수       사람이 원본 영상을 확인한 뒤 accept · edit · reject+manual 중 하나
```

라벨러는 초안을 **행 값과 분리해** 보여 준다. 저장 시 행동을 명시하지 않으면 거부한다
(`"AI 초안이 있는 행은 accepted·edited·rejected_manual 중 하나를 명시해야 저장된다 —
초안을 보여 준 것만으로 완료되지 않는다"`).

`accepted`는 **초안을 그대로 확정했다는 뜻**이다. 값이 다르면 저장이 거부되고 `edited`로
기록하라고 알린다 — audit이 사실과 어긋나지 않게 하는 게이트다.

## 5. 프롬프트를 결과 전에 고정

```
템플릿      p2_ai_draft.PROMPT_TEMPLATE
prompt_sha256  e7b153d095031f867c5866dc6d312a8232fd3e1759a70203078450b13dba76ff
기록 항목    ai_model · ai_provider · ai_model_version · settings · generated_at ·
           prompt_sha256 (초안마다)
```

템플릿은 유형 정의(자막형·장면형·복합형)를 프로젝트 정의 그대로 담고, 검색 시스템·캡션
모델·임베딩·색인·검색 결과·순위·점수에서 추론하지 말라고 명시하며, **사람이 원본 영상을
직접 보고 확정한다**고 적는다. few-shot 예시는 넣지 않는다(테스트로 검사).

행마다 채워 넣는 값과 무관하게 **해시는 하나로 고정**된다. 초안의 `prompt_sha256`이
고정 템플릿과 다르면 검증에서 거부한다 — 생성 도중 프롬프트를 바꾸는 경로를 막는다.

## 6. 온라인 튜닝을 기본 프로토콜로 만들지 않는다

```
순서   프롬프트 고정 → 전량 생성 → 산출물 동결 → 그 뒤 사람 심사
금지   10건 생성 → 사람이 고쳐봄 → 프롬프트 개선 → 나머지 생성
이유   annotation 프로토콜이 시간에 따라 달라진다
```

UI·형식 시험이 필요하면 **실제 P2 행이 아닌 합성/데모 영상**에서만 한다.

## 7. 산출물 분리

```
초안        label_kit/p2_ai_assist/p2_ai_drafts.jsonl        동결 산출물
심사 audit   label_kit/p2_ai_assist/p2_adjudication_audit.csv
최종 GT      label_kit/p2/p2_label_intake.csv                 여기 하나뿐
```

초안 산출물은 **이미 있으면 덮지 않는다**(재생성은 별도 승인 사건). 사람의 심사가 초안을
덮어쓰지 않는다 — 심사 결과는 audit에, 최종 값은 작업 CSV에 각각 남는다.

## 8. 심사 provenance

```
label_origin   human_only | ai_first_human_adjudicated
draft_action   not_applicable | accepted | edited | rejected_manual
audit 열        query_id · label_origin · draft_action · recorded_at
```

audit에 최종 `text`·`gt_start`·`gt_end`를 담지 않는다(열 구성 검증으로 차단).
`human_only`는 `not_applicable`만, `ai_first_human_adjudicated`는 나머지 셋 중 하나만
허용한다.

현재 상태: **20행 seed 완료** — 전부 `human_only` / `not_applicable`, 나머지 155행은
`missing`으로 보고된다.

## 9. 음성 근거가 필요한 유형 — **이 도구 환경에서는 사람이 한다**

실측한 도구 환경:

```
컨택트시트 JPG   읽을 수 있다 (합성 이미지로 확인)
원본 mp4        읽을 수 없다 — "This tool cannot read binary files"
원본 음성       재생·인식 수단이 없다
```

따라서 **음성 근거가 필요한 유형은 초안을 만들지 않는다.**

```
자막형   말소리에 답이 있다        → requires_human_audio
복합형   발화와 화면 양쪽이 필요    → requires_human_audio
장면형   화면에 답이 있다          → 초안 가능 (시트의 시각 근거만으로 성립)
```

금지: 시각 정보만으로 발화 내용을 추측하는 것 · 파이프라인 STT를 대신 읽는 것.

남은 155행의 분포(`p2_ai_draft plan`, audio 미지원):

```
초안 가능 (장면형)          61행
사람 작성 (자막형 38 · 복합형 56)  94행
```

즉 **이 환경에서 AI가 덜어 주는 노동은 155행 중 61행(39%)**이다. 음성을 이해하는 도구를
쓸 수 있게 되면 `--audio-supported`로 다시 계획하고, 그때 늘어나는 범위는 **별도 승인
사건**으로 다룬다.

## 10. 초안 품질 게이트

사람이 reject/manual할 수 있는 사유:

```
질의가 그 영상에 실제로 없다 · 경계가 틀렸다 · 동결 유형에 명백히 안 맞는다 ·
지나치게 모호하다 · 같은 영상의 기존 질의와 사실상 중복이다 ·
원본에서 확인할 수 없는 내용을 만들어 넣었다
```

**판단 기준으로 쓸 수 없는 것:**

```
3B/4B가 잘 찾을 것 같다 · 검색이 잘 될 것 같다 ·
특정 모델 캡션과 표현이 잘 맞는다
```

## 11. 중복 처리

같은 영상의 5개 질의는 서로 다른 검색 의도를 갖는 것이 바람직하다. 중복 판단은
**질의문 · 원본 영상의 사건/구간 · 동결 유형**으로만 한다. **검색 결과를 보지 않는다.**
필요하면 사람이 하나를 수동 수정한다. `query_id`·`query_type`은 바꾸지 않는다.

## 12. 라벨러 통합

```
표시    현재 질의 · 컨택트시트 · 원본 영상 · AI 초안(질의문·구간·모델·근거)
버튼    초안 그대로 확정 / 초안 불러와 수정 / 초안 거부·직접 작성
저장    행동을 명시하지 않으면 거부. 표시만으로 완료되지 않는다
자동저장  임시 저장은 audit을 기록하지 않고 완료로 세지 않는다
```

`state()`는 초안을 `proposals`로 **행 값과 분리해** 싣는다. 초안을 표시하는 코드 경로에
저장 호출이 없다(테스트로 검사).

## 13. build 계약 불변

```
최종 검증기   python scripts/p2_label_intake.py build
불변         gt_seg_idx 파생 · duration 검증 · query_id · query_type ·
            활성 설계 175 · common.derive_gt_seg_idx · 부분 제출 거부
```

AI-assisted라는 이유로 build 규칙을 느슨하게 하지 않는다.

## 14. PRIMARY·retrieval·evaluation 불변

```
p2_retrieve · p2_evaluate · alpha=0.0 · 캡션 단독 PRIMARY · 후보 풀 ·
RR/MRR · cluster bootstrap · B=2000 · seed 20260820 · CI 규칙 ·
half-width 0.04 · exclusion · verdict · adoption
```

전부 그대로다. 순서도 불변: `175/175 → build PASS → FINAL GT freeze → 최초 retrieval
→ evaluate`.

`label_origin`·`draft_action`·`p2_ai_draft`는 `p2_retrieve`·`p2_evaluate` 어디에도
등장하지 않는다(테스트로 검사).

## 15. label_origin별 사후 분석을 하지 않는다

금지:

> "AI-assisted 행에서는 3B가 이겼다" · "human-only 20에서는 4B가 이겼다"를 보고
> annotation mode에 따라 PRIMARY를 재해석하는 것.

`label_origin`은 audit metadata다. 별도 분석을 원하면 **P2 결과 전에 따로
사전등록**해야 한다. 이번에는 만들지 않는다.

## 16. no outcome-based top-up 유지

175가 fixed N이다. AI-assisted로 바꿨다고 315로 되돌리지 않고, 결과를 보고 라벨을
추가하지 않는다. `p2_active_design` 로더가 `fixed_n`·`no_outcome_based_top_up` 플래그를
검사하므로 코드 수준에서도 막혀 있다.

## 17. 한계 — source heterogeneity

```
20행    사람이 원본만 보고 처음부터 작성
155행   AI 초안(장면형 61) 또는 사람 작성(94) + 전부 사람 확정
```

두 경로의 질의 문체·구간 폭 분포가 다를 수 있다. **그 이질성을 PRIMARY 판정에서 통제하지
않는다**(층으로 쓰지 않는다). 결과 보고에 이 사실을 한계로 적는다.

또 이 환경에서 AI는 **컨택트시트(구간당 대표 프레임 1장)만** 본다. 원본 영상을 프레임
단위로 보지 못하므로 초안 경계는 5초 격자에 가까운 근사이고, **정확한 경계는 사람이
원본에서 확정한다.**

## 18. 지금 하지 않은 것

```
실제 155행(또는 61행) AI 초안 생성   HOLD — 사용자 승인 후
프롬프트 튜닝                      하지 않는다
20건 재작성·수정                    하지 않는다
P2 retrieval · evaluate            HOLD
```

## 19. 생성 주체에 대한 주의 — **이 세션이 초안을 만들면 안 된다**

이 세션은 표본 규모 검토 과정에서 **AI Hub 2×2의 arm별 per-query RR**(3B/4B 캡션 단독)을
열었다. P2 산출물은 아니지만 arm 대비의 방향을 알고 있는 문맥이다.

> 초안 생성은 **arm 결과를 본 적 없는 별도 문맥**에서 실행한다. 고정 프롬프트와
> 컨택트시트만 받는 새 에이전트로 돌리고, 그 사실을 초안 산출물의 provenance에 적는다.

이 조항이 없으면 "초안이 arm 우열 지식에 물들지 않았다"를 나중에 주장할 수 없다.
