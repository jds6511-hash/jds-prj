# STT_RETRANSCRIBE_V1 canary 결과 (2026-09-08 · 600–780초 × 2회)

사전등록: `docs/preregistration/STT_RETRANSCRIBE_V1_2026-09-08.md` (commit 1d36bad)

```
FULL_RETRANSCRIPTION            HOLD 유지
CANARY_DETERMINISM              평가 불가 — 두 실행이 모두 빈 전사였다
게이트 C1~C8                     정의대로는 전부 true, 그러나 **공허한 통과**다
```

## 1. 무슨 일이 났나

`vad_filter=True` + Phase A freeze VAD 파라미터로 이 3분 클립을 돌리면
**전사가 0발화**로 나온다.

```
오디오                            180.0초
frozen VAD가 찾은 발화             1.68초 (speech chunk 1개 · 178.32–180.00초)
duration_after_vad                1.68초
새 전사 발화 수                    0
기존(현행 설정) 전사 발화 수         26
```

VAD가 오디오의 **0.93%만 발화로 판정**했고, 디코더에는 그 1.68초만 들어갔다.
그 1.68초에서도 출력이 나오지 않았다.

## 2. 게이트가 공허하게 통과했다

행이 0개면 대부분의 검사가 자동으로 통과한다. 숨기지 않고 적는다.

```
C2 determinism      run1 == run2 (ordered digest 4f53cda1… 동일)
                    그러나 **둘 다 빈 전사**다 — 재현성을 판정한 것이 아니다
C3 temperature      관측값 [] (행이 없어 관측 자체가 없다)
C5 lineage          0행 → 0행
C6 timestamp        0행 → 위반 0
C8 canonical mapping 원 실행에서 0행이었다 — 계측 결함(아래 §5)
C1 provenance       실질 통과 (decoding·VAD resolved 값 기록됨)
C7 old artifacts    실질 통과 (감시 6개 해시 무변경)
```

따라서 **사전등록의 첫 질문(run1 == run2)은 답을 얻지 못했다.** 빈 전사 두 개가
같다는 사실은 temperature 고정의 효과를 증명하지 못한다.

## 3. 사라진 것에 실제 발화가 포함돼 있다

기존 전사 26발화 중 VAD 발화 구간과 겹치는 것은 3건이고, 전부 자연스러운 한국어
대화다. 새 전사에서는 **이 3건도 사라졌다.**

```
177.54–178.54  샘플 두께 이정도니까
178.54–178.92  아 네
178.92–179.98  앉아보시고 그러시면 됩니다
```

나머지 23건은 조리 지시문 형태다(`오븐에 2분간 구워주세요`, `크림치즈를 넣어주세요`
중복, `parmesan`, `깨`, `달걀` 등). GT가 없으므로 이것이 환각이라고 판정하지 않는다.

즉 이 클립에서 VAD-제약 디코딩은 **의심 문장과 실제 발화를 함께 제거**했다.
false-negative 위험은 가설이 아니라 이 실측에서 실현됐다.

## 4. 두 해석 — GT 없이 가를 수 없다

```
해석 A   이 구간에 발화가 거의 없고, 기존 26발화 대부분이 무발화 생성이다
         (VAD는 맞았고, 마지막 3건만 실제 발화였다)
해석 B   음악·잡음 아래 발화가 있는데 frozen VAD 파라미터가 너무 엄격하다
         (min_silence 2000ms · threshold 0.5 · pad 400ms)
```

Phase A의 전체 영상 측정(사용 가능 STT 294 중 210이 zero-overlap)과 방향은 같지만,
어느 해석이 맞는지는 **여기서 가릴 수 없다.**

## 5. 계측 결함 하나 (보정)

C8은 요청 범위(600–780초 절대 시간)로 클립 `segments.json`(0–180초 상대 시간)을
필터해 **0행**이 됐다. 0행은 통과가 아니다.

```
보정          runs/stt_retranscribe_v1/canary_600_780_mapping_correction.json
방법          재전사 없이 오프라인 재계산
결과          36행 · segment_id 0–35 · 5초 격자 경계 무변경
코드 수정      segments_range()로 segments 자체 시간 기준을 쓰게 했고,
              0행이면 C8이 통과하지 않도록 막았다 (테스트 1건 추가)
실행 코드      ef8c148f4b9bfc77… (이 canary가 돌린 파일)
보정 코드      cfe9932c3720…     (계측 수정 후)
```

## 6. 사전등록의 결함

사전등록에 **비퇴화(non-degeneracy) 전제조건이 없었다.** "run1 == run2"만 요구했고,
"전사가 비어 있지 않아야 한다"를 넣지 않았다. 그래서 가장 나쁜 결과가 형식상
전부 PASS로 보인다.

이 조건을 지금 추가해 재판정하지 않는다 — 결과를 본 뒤 게이트를 고치는 것이다.
**새 사전등록 사건으로 남긴다.**

## 7. 판정

```
FULL_RETRANSCRIPTION      HOLD 유지 (승인 후보로 올리지 않는다)
threshold 조정으로 살리기   하지 않는다 (사전등록 §6)
```

허용 문구는 이것뿐이다.

```
At the frozen Phase-A VAD parameters, VAD-constrained decoding produced no
transcript for this canary interval; the run-to-run comparison is therefore
degenerate and does not establish determinism.
```

쓰지 않는 문구:

```
VAD-constrained deterministic decoding reduced transcription emitted outside
the frozen VAD speech regions.       ← 결과가 지지하지 않는다 (전사가 0이다)
hallucination이 줄었다 · ASR이 정확해졌다 · 무발화가 확인됐다
```

## 8. 다음 선택지 (실행 승인 없음)

```
① VAD-제약 디코딩 종료          "frozen 파라미터에서 too aggressive"로 닫는다
② 새 사전등록                   비퇴화 게이트 + VAD 파라미터 재검토
                               → 파라미터를 건드리는 순간 threshold 사건이므로 별도 승인
③ 진단 프로브(acceptance 밖)     발화가 분명한 구간(예: 8~9분대)에서 같은 파라미터로
                               VAD만 재실행해 "엄격함"이 전역적인지 본다
                               POST_HOC_DIAGNOSTIC_ONLY = true 로만 기록
```

## 9. 산출물

```
runs/stt_retranscribe_v1/canary_600_780.json                    2회 실행 결과·게이트
runs/stt_retranscribe_v1/canary_600_780_mapping_correction.json C8 보정(재전사 없음)
work_sttv2/canary_run1/transcript.json · canary_run2/transcript.json
scripts/stt_retranscribe_canary.py · tests/test_stt_retranscribe_canary.py (23건)
```

기존 산출물 무변경 확인(감시 6개): 기존 stt_cache 2종 · 클립 segments · 전체
segments · 현행 제출본 hwpx · rollback hwpx.
