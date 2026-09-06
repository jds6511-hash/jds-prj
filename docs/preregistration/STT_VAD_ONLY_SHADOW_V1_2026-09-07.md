# STT_VAD_ONLY_SHADOW_V1 — 사전등록 (2026-09-07)

```
이전 설계   STT_EVIDENCE_SANITATION_V1 Phase B/C/D
            Phase B canary COMPLETE / GATE FAIL (B-C5)
            Phase C CANCELLED under current design
            Phase D (VAD AND no_speech_prob) 설계 폐기 — 전제가 반증됐다

이 트랙     VAD-only STT abstention **shadow** evaluation
            APPROVED FOR PREREGISTRATION (2026-09-07)

(ii) N-run stability      DEFER · research-only (`WhisperDecodeStability_v1`)
(iii) transcript 교체      HOLD
submission artifact        FROZEN · 재생성 금지
```

이 문서는 **내용을 고치지 않는 문서**다.

---

## 1. 왜 이전 설계를 폐기하는가

Phase B canary(2026-09-07)가 세 가지를 확정했다.

```
1  현재 B1 transcript는 **특정 과거 Whisper 실행의 산물**이다.
2  그 실행의 decoder metadata(no_speech_prob 등)는 저장돼 있지 않다.
3  같은 기계·같은 커밋·같은 파라미터로 다시 돌려도 같은 transcript가 나오지 않는다.
   (같은 환경 2회: 41발화 vs 25발화 · 공통 문자열 7개)
```

따라서 새로 뽑은 `no_speech_prob`를 기존 문장의 속성으로 붙이면 **provenance가 거짓**이
된다. 그 경로를 닫는다.

반면 Phase A의 VAD 값은 **지금 저장돼 있는 바로 그 transcript의 시간 구간**에 대해
결정적으로 계산된 sidecar다. evidence를 교체하지 않고 sanitation을 연구할 수 있는
유일하게 깨끗한 신호다.

## 2. 규칙 — 임의 임계값 없이 시작한다

```
SUSPECT_STT_VAD0 :=  existing status == VALID
                     AND speech_overlap_ratio == 0
```

```
raw text                  그대로
raw artifact              그대로
shadow status             SUSPECT candidate
usable_for_claims         **shadow 계산에서만** false
production 판정            바뀌지 않는다
```

```
nearest_speech_gap_sec · latin_present · normalized_repeat_count
    → diagnostic only. 규칙 입력이 아니다.
`gap > X초` 같은 항을 추가하지 않는다 — 그것이 곧 임계값 선택 사건이다.
```

`overlap == 0`은 **정확히 0**을 뜻한다(Phase A 정의: padding 적용 후 VAD speech 구간
합집합과의 교집합 길이가 0). Phase A 실측으로 제출 영상 usable 294구간 중 210구간
(71.4%)이 여기 해당한다.

**210/294를 production SUSPECT로 바꾸라는 뜻이 아니다.** 71.4%는 매우 큰 개입이므로
먼저 shadow로 downstream 영향을 잰다.

## 3. 실험 설계 — 저장된 B1 그대로, 두 arm

```
S0 CONTROL   현행 sanitation 그대로
S1 SHADOW    VALID + speech_overlap_ratio == 0  →  SUSPECT  →  claim evidence 제외
```

```
고정   저장된 B1 segments.json (sha256 aa008317023c884a206c…) · 재전사 없음
      모델·프롬프트 계약·경계 provider·window_sec 60 · canonical partition
      grounding 규칙 · OPEN-12 표현 자격 · A2' 렌더러
바뀌는 것  ASR 채널의 claim eligibility **하나뿐**
```

### 2단으로 나눈다

```
Tier 1  LLM 없이 — 결정적 계층까지
        sanitation → timeline → episode → claim evidence 수 → PromptError(ERR-009) 여부
        GEO·TRI 매핑 테스트 · 합성 fixture 회귀
        로컬 CPU · GPU 불필요 · 승인 §8-A

Tier 2  LLM 포함 — 표현까지
        같은 41 episode로 S0/S1 paired 서버 실행 1회
        summary·grounding·presentation eligibility 변화
        4090 · 승인 §8-B (Tier 1 결과 확인 후 별도 승인)
```

Tier 1에서 이미 "유의미한 episode가 대량으로 비어버린다"가 확인되면 Tier 2를 열지
않고 닫는다.

## 4. 구현 경계

```
src/v2_1_sanitation.py 수정        금지 (v2.1 확정 계층)
production 기본 동작 변경           금지 — shadow는 명시적으로 켤 때만 적용된다
확정 인덱스·raw artifact 수정       금지
submission artifact 재생성          금지
사람이 살릴 문장을 고르는 행위       금지
```

```
허용   신규 모듈(shadow 판정) + orchestrator의 옵션 플래그(기본 off)
       v3 병행 계약과 같은 방식이다 — 기존 경로를 그대로 두고 옆에 둔다
```

## 5. 지표

### mechanism (주장은 여기까지)

```
low/no-VAD-speech STT의 usable_for_claims
   S0 = 현재값(제출 영상 210구간이 usable)
   S1 = 0
```

### safety (이쪽이 더 중요하다)

```
GEO-001 · GEO-004 매핑 테스트 회귀        실측(source-level 추론 금지)
TRI-005 sparse safe mode 회귀
eligible evidence가 0이 된 episode 수
ERR-009(PromptError) 진입 episode 수      전량 명시
canonical summary가 바뀐 episode 수        (Tier 2)
VALID_PARSE 분포 변화                      (Tier 2)
presentation eligibility 변화              (Tier 2 · 현재 39/41)
canonical partition 변화                   0이어야 한다
raw 보존                                   100%이어야 한다
```

### diff 산출물

```
S1에서 claim evidence로 쓰이지 못하게 된 STT 전량 (구간·원문·overlap·gap)
그로 인해 사라진 downstream 내용 (Tier 2: episode별 summary diff)
```

전량 기록한다. **사람이 그 목록을 보고 살릴 문장을 고르지 않는다.**

## 6. 채택 관문 (shadow 결과가 좋다는 것만으로 채택하지 않는다)

```
raw preservation                 100%
canonical partition change       0
GEO mapped regression            0
TRI regression                   0
new structural failure           0
ERR-009 transition               전량 명시
presentation recall degradation  전량 명시
```

해석 규칙을 미리 정한다.

```
STT 210건 제외 → 보고서 거의 동일        VAD-only abstention이 값싸고 안전하다는 증거
유의미한 episode가 대량 empty            VAD-only는 너무 거칠다 → 트랙을 닫는다
```

**두 번째 경우에 임계값을 조금씩 움직여 맞추지 않는다.** 그 순간 이 트랙의 의미가
사라진다.

## 7. 주장하지 않을 것

```
overlap == 0 = hallucination              아니다 — GT가 없다
temperature > 0 = hallucination           아니다
   안전한 표현: temperature fallback introduced run-to-run transcript instability
                in the observed canary
STT 품질이 좋아졌다                        측정 대상이 아니다
보고서가 더 사실적이다                      측정 대상이 아니다
현재 제출본이 잘못됐다                      이 트랙은 그 판단을 하지 않는다
```

## 8. 승인이 필요한 것

```
A  Tier 1 구현 + 실행 (로컬 CPU · LLM 없음 · 결정적 계층까지)
B  Tier 2 S0/S1 paired 서버 실행 1회 (Tier 1 결과 확인 후 별도 승인)
C  production 채택 (§6 관문 전부 충족 + 별도 승인)
```

```
불변   submission arm = episode_content_v3_summary_only · HWPX sha256 f874f643…
      repository default contract = episode_content_v2
      v2.1 baseline 6e79ac3 · GRD-004 P1 WAIVED
      M9 HOLD · official test UNOPENED · 검색 파이프라인 M1~M7 동결
      확정 인덱스 자막 무변경 · 재전사 없음
```
