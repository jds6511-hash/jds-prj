# 사전등록 — STT_RETRANSCRIBE_V1 (2026-09-08)

**이 문서는 결과를 보기 전에 쓴다.** 실행 후 파라미터·게이트·성공 문구를 고치지 않는다.
고치려면 새 사전등록 사건이다.

```
승인 범위    3분 canary × 2회 (600–780초)
HOLD        full 40.4분 재전사 · B1' adoption · B2 재생성 · 제출본 교체
```

## 1. 질문

이번 canary가 답하는 질문은 하나다.

```
같은 입력·같은 설정에서 같은 transcript가 나오는가?
```

두 번째 질문은 그 다음이다.

```
frozen VAD speech 구간 밖에서 생성되는 transcript가 줄어드는가?
```

**"더 그럴듯해 보인다"는 통과 사유가 아니다.** Phase B가 그렇게 실패했다
(`docs/probes/STT_METADATA_PHASE_B_CANARY_2026-09-07.md` — 같은 오디오 2회 실행에서
transcript가 서로 달랐고, 원인은 temperature fallback이었다).

## 2. 새 decoding arm (freeze)

```
model                            faster-whisper large-v3
language                         ko
beam_size                        5
best_of                          5
condition_on_previous_text       False
word_timestamps                  True
hallucination_silence_threshold  1.0
vad_filter                       True      ← 현행은 False (m3_generate.py 주석 "VAD 금지")
temperature                      0.0       ← 단일 scalar. fallback ladder를 없앤다
```

현행 production과 다른 것은 **`vad_filter`와 `temperature` 둘뿐**이다. 나머지는
`src/m3_generate.py:155-159`의 실효값을 그대로 옮겼다.

`temperature`는 리스트가 아니라 단일 `0.0`으로 쓴다 — 의도는 fallback ladder
(0.0 → 0.2 → … → 1.0) 자체의 제거다. 실행 후 resolved manifest에서
**observed temperature가 0.0뿐**임을 확인한다.

## 3. VAD 파라미터 (Phase A에서 freeze한 값 그대로)

library default에 의존하지 않고 resolved value를 manifest에 전부 적는다.

```
faster_whisper                1.2.1
VAD model                     silero_vad_v6.onnx
model sha256                  4cbf549b8326f60f80f2536d9eefeb450a9abe83365a098031c89719f1be17d2
threshold                     0.5
neg_threshold                 0.35
min_speech_duration_ms        0
min_silence_duration_ms       2000
speech_pad_ms                 400
max_speech_duration_s         inf       (Phase A resolved value)
sampling_rate                 16000
```

출처: `runs/stt_sanitation_v1/full_xekZO4n4QuE/manifest.json` ·
`scripts/stt_vad_sidecar.py`의 `VAD_PARAMS`.

## 4. canary 구간

```
600–780초 (10:00–13:00)
```

Phase B canary와 **같은 구간**이다. 이번 오류를 본 뒤 고른 구간이 아니다
(`data/provenance/videos.json`의 `canary_xekZO4n4QuE_600_780` · sha256
`c7c26b27…`가 그 이력을 보존한다).

## 5. 실행 설계

```
run1  work_sttv2/canary_run1/     완전 독립
run2  work_sttv2/canary_run2/     run1 산출물·캐시를 재사용하지 않는다
```

모델 weight 캐시 재사용은 허용한다. transcript output·stt_cache 재사용은 금지한다.

## 6. Hard gates

```
C1  provenance complete            model · faster-whisper · CUDA/CTranslate2 ·
                                   decoding + VAD resolved parameter 전부 기록
C2  deterministic pairing          run1 == run2
                                   ordered (start_sec, end_sec, normalized_text) 전체
                                   utterance count · merged segment 구조 · output hash
C3  no temperature fallback        observed temperature == 0.0 only
C4  VAD resolved params exact      §3의 값과 전건 일치
C5  raw→merged lineage complete    버려진 것까지 남는다
C6  timestamp validity             start <= end · zero-duration · nonfinite 집계
C7  old artifacts unchanged        기존 stt_cache · B1 확정 인덱스 ·
                                   runs/vad0_paired · runs/quality_candidate ·
                                   제출 artifact 해시 무변경
C8  canonical mapping unchanged    canary 범위의 segment_id · start · end 동일
```

**C2 실패 = `FULL_RETRANSCRIPTION = HOLD`로 종료한다.** 그 뒤 temperature·beam·VAD
threshold·no_speech_threshold를 움직여 다시 맞추지 않는다 — 그것은 새 사전등록이다.

## 7. 측정 (run별)

```
audio duration · VAD speech duration · VAD speech chunk count
utterance count · utterance duration total
EMPTY / non-empty output count
raw transcript hash · merged transcript hash
start>end · zero-duration · nonfinite timestamp count
```

기존 frozen transcript와 대조.

```
old / new utterance count
exact retained · removed · changed · newly emitted
text change rate
```

## 8. VAD mechanism metric

Phase A frozen VAD interval을 기준으로 센다(측정 도구는 그대로 쓴다).

```
speech_overlap_ratio == 0 인 utterance 수     old vs new
speech_overlap_ratio > 0  인 utterance 수     old vs new
```

## 9. false-negative risk (반드시 함께 기록)

VAD를 켜면 실제 발화도 누락될 수 있다. GT가 없으므로 proxy만 적는다.

```
기존 transcript 존재 AND 새 transcript EMPTY 인 구간 수
그 구간의 caption 존재 여부 (diagnostic only)
```

## 10. 결론 문구

결과가 지지할 때만 아래 문장을 쓴다.

```
VAD-constrained deterministic decoding reduced transcription emitted outside
the frozen VAD speech regions.
```

금지:

```
hallucination이 줄었다 · ASR accuracy가 향상됐다
VAD가 hallucination을 검출한다 · 실제 무발화 GT를 확인했다
누락된 것은 전부 환각이다 · 남은 것은 전부 실제 발화다
```

## 11. 하지 않는 것

```
no_speech_threshold · VAD threshold · beam · best_of tuning
prompt bias / hotwords · domain vocabulary
Latin blacklist · repeat blacklist · 사람의 문장 삭제
새 Whisper 모델 비교 · 새 human GT
canonical segment 경계 변경 (485 identity와 시간 경계는 그대로다)
기존 stt_cache · B1 확정 인덱스 · 제출 artifact 수정
```

## 12. canary PASS가 뜻하지 않는 것

```
full 재전사 승인 · B1' adoption · B2 재생성 · 제출본 교체
```

전부 별도 승인 사건이다. canary는 **계측 품질**을 재는 것이고, 신호 품질을 재는
것이 아니다.

## 13. VAD0 자동 승계 금지

새 transcript를 만들었다는 이유로 기존 `speech_overlap_ratio == 0 → SUSPECT`를
자동 적용하지 않는다. 새 transcript에서 zero-overlap이 얼마나 남는지 **다시 측정**한
뒤 별도 사건으로 판단한다. 거의 0이면 VAD0는 redundant safeguard일 수 있다.
