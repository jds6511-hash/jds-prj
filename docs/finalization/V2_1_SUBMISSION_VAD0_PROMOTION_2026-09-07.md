# 제출 profile에 STT_VAD0 채택 (2026-09-07)

트랙 `STT_EVIDENCE_SANITATION_V1` · 사전등록
`docs/preregistration/STT_VAD_ONLY_SHADOW_V1_2026-09-07.md`
Tier 2 결과 `docs/probes/STT_VAD0_SHADOW_TIER2_2026-09-07.md`

```
STT_VAD0

submission profile adoption       APPROVED
selected arm                      v3 summary-only + explicit VAD0
repository default                OFF / unchanged
src/v2_1_sanitation.py            unchanged
raw STT                           unchanged
B1 accepted index                 unchanged

production-wide adoption          NOT ADOPTED
Whisper transcript replacement    HOLD
VAD threshold tuning              NO
new human GT                      NO

semantic correctness              UNVERIFIED
```

## 1. 무엇을 채택했나

`speech_overlap_ratio == 0`인 기존 VALID STT를 **claim evidence로 쓰지 않는**
결정적 abstention 정책 하나다. 사전등록된 단일 조건 그대로이며 임계값을 결과에
맞춰 움직이지 않았다. 근거를 추가하지 않는 one-way 정책이고 raw STT는 그대로다.

```
규칙        existing VALID AND speech_overlap_ratio == 0 -> SUSPECT
입력        speech_overlap_ratio 하나뿐
텍스트      수정 없음 (SUSPECT는 원문을 보존하고 claim 자격만 뺀다)
사람 개입   없음 (문장을 보고 고르지 않는다)
```

## 2. 재실행하지 않았다

새 제출본은 Tier 2 S1 arm에서 **이미 생성·검증된 그 파일**이다. 모델·LLM을 다시
돌리면 채택 근거가 된 실험과 제출 artifact가 분리되므로 재실행하지 않았다.
manifest 생성기는 S1 run의 지문이 `paired_metrics`의 S1 지문과 같은지 확인하고,
다르면 거부한다 — 다른 실행의 산출물에 paired 수치를 붙일 수 없다.

```
제출 artifact   runs/vad0_paired/s1_shadow/report.hwpx
hwpx sha256     4e10aaaba1d8a6e510c4749efc4a6e1bf5a5dbb5dba963403a84379bcd92ff90
code_revision   3ee4341c0fd1f963255e092b1726ac25dceff0c8
paired commit   958276b06bcbf3983f00b9132edffba4185a8dcd
한글 Open()     True · PDF export True (137,546 bytes) · 본문 14,460자
구조 validator  PASS
```

## 3. rollback artifact 보존

기존 제출본을 삭제하거나 덮어쓰지 않았다. manifest도 그대로 남아 있다.

```
rollback  runs/v3_paired/r1_v3/report.hwpx
          hwpx sha256 f874f643112704120cd3b043c3667b71ffd4f25105ca1fccf345b936d4e4a91d
          manifest runs/v3_paired/submission_manifest.json  (eligible 39 · parse 실패 2)
          tag      submission-ready-2026-09-03 = 0c60c7a
현행      runs/vad0_paired/submission_manifest_vad0.json    (eligible 40 · parse 실패 1)
사본      Desktop/v3_submission_vad0/  ·  기존 사본 Desktop/v3_submission/ 유지
```

## 4. 제출 수치

수치는 손으로 적지 않았다. paired 결과와 Phase A manifest에서 읽는다.

```
                              rollback   현행
presentation eligible          39 / 41    40 / 41
parse contract failure          2          1
claim evidence                 777        567
```

`40 / 41`은 **비퇴행 게이트를 통과했다**는 뜻이다. `2 -> 1 변화를 일반화하지 않는다` —
근거 집합이 바뀌면 모델 출력이 바뀌고 그중 하나가 파싱에 성공한 것이며, VAD가 파싱을
개선한다는 결론을 뒷받침하지 않는다.

```
non-regression gate   presentation S1 >= S0   PASS
                      parse        S1 <= S0   PASS
                      근거 증가 episode 0      PASS
```

## 5. VAD provenance (freeze된 값)

```
faster_whisper 1.2.1 · silero_vad_v6.onnx
sha256 4cbf549b8326f60f80f2536d9eefeb450a9abe83365a098031c89719f1be17d2
threshold 0.5 · neg_threshold 0.35 · min_speech_duration_ms 0
max_speech_duration_s inf · min_silence_duration_ms 2000 · speech_pad_ms 400
measurements sha256 e1914741cf7a550fc654f4078d812a08f0bc20a06ee5ccb4bf829bdcfe3caa63
```

## 6. 채택 범위 밖

채택은 제출 profile 하나다. 저장소 기본값은 건드리지 않았다.

```
repository default 계약     episode_content_v2      (v3 승격 없음)
SHADOW_VAD0_DEFAULT         False                   (VAD0 default off)
src/v2_1_sanitation.py      무변경                   (VAD 의존 없음)
raw STT · B1 확정 인덱스     무변경
전사문 교체                  HOLD
WhisperDecodeStability_v1   DEFER · research-only
M9 · official test 39       HOLD · UNOPENED
```

## 7. 허용되는 주장

```
A deterministic abstention layer reduced the use of low-speech-confidence STT as claim evidence without degrading the paired report pipeline.
```

좁게 읽어야 한다: **zero-VAD-overlap STT를 제출 보고서의 claim evidence로 쓰지 않는
보수적 abstention policy가 paired pipeline을 악화시키지 않았다**까지다.

## 8. 주장하지 않는 것

```
210 hallucinations removed         아니다 — 실제 발화/비발화 GT가 없다
semantic accuracy improved         측정하지 않았다
VAD0 detects hallucination         검증된 검출기가 아니다
39 -> 40이 성능 개선이다             비퇴행 조건을 충족했다는 뜻이다
carryover 17 -> 5이 환각 제거다      evidence-dependence proxy이며 문자열 일치일 뿐이다
```

한계도 같이 적는다. 41편 중 **21편에서 ASR 근거가 전량 빠졌고**(캡션 근거는 남았다),
zero-overlap 구간이 실제 무발화였는지는 검증되지 않았다.
