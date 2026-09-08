# 최종 상태 — R1-VAD0 제출 arm CLOSED (2026-09-07)

> 2026-09-08 갱신: 이 arm(hwpx `4e10aaab…`)은 이제 **rollback baseline**이다.
> 현행 제출 arm은 `R1-VAD0-QUALITY`(v3 + STT_VAD0 + output_quality_v1 + 300초 grouping)이며
> `V2_1_SUBMISSION_QUALITY_PROMOTION_2026-09-08.md`가 그 상태를 적는다.
> 이 문서 본문은 당시 판정 기록이므로 수치를 고치지 않는다.

이 문서는 **닫힌 상태의 기록**이다. 수치를 고치지 않는다. 근거 문서:
`V2_1_SUBMISSION_VAD0_PROMOTION_2026-09-07.md`(승격),
`../probes/STT_VAD0_SHADOW_TIER2_2026-09-07.md`(paired 결과),
`../preregistration/STT_VAD_ONLY_SHADOW_V1_2026-09-07.md`(사전등록).

```
STT_VAD0 SUBMISSION-PROFILE ADOPTION   CLOSED
```

## 1. 잠근 상태

```
V2.1 IMPLEMENTATION_COMPLETE   YES
B2 OPERATIONAL_COMPLETE        YES

SUBMISSION_READY               YES
SUBMISSION ARM                 R1-VAD0
PROMPT CONTRACT                episode_content_v3_summary_only
STT EVIDENCE POLICY            STT_VAD0

presentation                   40 / 41 eligible
parse-contract failure         1 / 41

repository default             episode_content_v2
VAD0 default                   OFF

GRD-004                        P1 WAIVED
semantic entailment            UNVERIFIED
official test                  UNOPENED
M9                             HOLD

rollback submission            f874f643112704120cd3b043c3667b71ffd4f25105ca1fccf345b936d4e4a91d
current submission             4e10aaaba1d8a6e510c4749efc4a6e1bf5a5dbb5dba963403a84379bcd92ff90
current submission tag         submission-vad0-2026-09-07
```

## 2. 제출 artifact 고정

추가 모델 실행·threshold 조정 없이 현재 artifact를 고정한다.

```
submission artifact   runs/vad0_paired/s1_shadow/report.hwpx
manifest              runs/vad0_paired/submission_manifest_vad0.json
사본                   Desktop/v3_submission_vad0/
rollback artifact     runs/v3_paired/r1_v3/report.hwpx  ·  tag submission-ready-2026-09-03
rollback manifest     runs/v3_paired/submission_manifest.json
```

실험에서 검증한 arm과 제출 artifact가 분리되지 않았다 — Tier 2 S1을 재실행 없이
승격했고, paired-run 지문 불일치는 manifest 생성기의 guard가 막는다.

## 3. 채택 범위

```
STT_VAD0 submission-profile adoption   YES
production-wide adoption               NO
repository default                     unchanged
SHADOW_VAD0_DEFAULT                    False
raw STT / B1 index                     unchanged
threshold tuning                       NO
transcript replacement                 HOLD
semantic correctness                   UNVERIFIED
```

## 4. 허용 주장과 한계

```
A deterministic abstention layer reduced the use of low-speech-confidence STT as claim evidence without degrading the paired report pipeline.
```

한계를 함께 남긴다.

```
21 / 41 episode에서 ASR 근거가 전량 빠졌다 (캡션 근거는 남았다)
zero-overlap은 실제 무발화 GT가 아니다
40 / 41은 비퇴행 게이트 통과다 — parse 2 -> 1 변화를 일반화하지 않는다
```

## 5. 주장하지 않는 것

```
VAD0가 Whisper hallucination을 검출했다   검증된 검출기가 아니다
210건을 제거했다                          GT가 없다
semantic accuracy가 향상됐다               측정하지 않았다
```

## 6. 남은 개선은 post-submission 연구 사건

```
WhisperDecodeStability_v1        DEFER · research-only
transcript replacement           HOLD
production-wide STT_VAD0 채택     별도 승인 사건
search-research E0               실행 승인 없음 (alpha_star 0.5 vs 1.0 선행 정리)
box alignment · caption 화면문자 인용 · TRI-005 C1/C2      별도 티켓
official test 접근 · test39→72 확장 · M9 실행 · 새 human GT   금지 / HOLD
```
