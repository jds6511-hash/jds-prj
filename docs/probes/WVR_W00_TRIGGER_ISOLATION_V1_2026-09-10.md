# WVR_W00_TRIGGER_ISOLATION_V1 결과 (2026-09-10)

사전등록: `docs/preregistration/WVR_W00_TRIGGER_ISOLATION_V1_2026-09-10.md`
(commit `79d5813` — GPU 실행 전 freeze) · 구현 `0165524` · 서버 RTX 4090

```
primary verdict   JOINT_OR_INTERACTION_EFFECT_SUPPORTED   (reason MIXED_PATTERN)
패턴               A INVALID · B INVALID · C INVALID · D VALID
blocker           없음 — 측정은 유효했다 (INCONCLUSIVE 아님)
control           A raw가 원본 W00 raw와 byte-identical (c5e4f752…) — 재현됨
분리 self-check    SEPARABLE · 4 arm pixel_values 바이트 동일(860adccd…) ·
                  M0/M1 timestamp 마커 실제로 다름
```

normative source는 `runs/wvr_light_v1/trigger_v1_summary.json`이다.
recovery를 시도하지 않았고 prompt 문구·schema·token cap·표집·창 길이를 바꾸지 않았다.

## A. provenance

```
prereg commit         79d581355672df3af7ca3ac72b5a480559437efb
implementation        0165524687e1a6fd8dc73187d69f5c46de8ab058   (실행 commit)
video sha256          ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
model revision        0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
prompt template hash  37f9588e58d0cb96e9a81e8842cbc3e8707404d0346f4aa5e2f4bc273075d273
                      (4 arm 동일 — 문구는 바뀌지 않았다)
runtime config hash   cb43ffd357d771ff… (4 arm 동일 · 원본 W00과도 동일)
transformers          5.14.1 · do_sample_frames False · do_resize False
```

## B. 조작 표

```
arm  픽셀        prompt window   rendered prompt   frames_indices   markers        입력토큰
A    W00 24장    0.0 – 48.0      c936901940b8…     0 … 1,380        1.0 … 45.0     2,135
B    W00 24장    0.0 – 48.0      c936901940b8…     3,600 … 4,980    121.0 … 165.0  2,150
C    W00 24장    120.0 – 168.0   374a86118e0e…     0 … 1,380        1.0 … 45.0     2,138
D    W00 24장    120.0 – 168.0   374a86118e0e…     3,600 … 4,980    121.0 … 165.0  2,153

픽셀 identity     4 arm 전부 원본 W00 24 해시와 일치 · arm 간 pixel_values sha256 동일
                 (860adccd0ade… · shape 동일 · video token 1,728 동일)
고정 metadata     duration 2424.186485 · total_num_frames 72,724 · fps 30.0000041 ·
                 width/height · backend pyav — 4 arm 동일
조작 필드          frames_indices 하나뿐 (A==C · B==D · A≠B)
입력 토큰 차이      숫자 문자열 길이 차이에서 온다(2,135~2,153) — 조작의 부수효과로 기록만 한다
```

self-check(모델 없이 processor만)가 GPU 사용 전에 위 분리를 실측했다:
`pixel_values_identical_across_arms=True`, `markers_differ_between_M0_and_M1=True`,
`M0_indices_equal_decoded=True`.

## C. 출력

```
                       A (P0M0)        B (P0M1)        C (P1M0)     D (P1M1)
technical status       WINDOW_INVALID  WINDOW_INVALID  WINDOW_INVALID  WINDOW_VALID
parse status           PARSE_FAILURE   OK              CONTRACT_VIOLATION  OK
generated tokens       4,096           530             6            745
finish reason          length          stop            stop         stop
generation cap hit     True            False           False        False
raw chars              11,533          1,505           14           1,930
완성 object              95              11              0            16
raw unique signature   2               1               0            9
zero-duration          95              0               0            0
positive-duration      0               11              0            16
최대 signature 반복       48              11              0            6
최대 연속 반복             1 (A-B 교대)     11              0            6
JSON 완결                False           True            True         True
collapsed / unique     0 / 0           1 / 1           0 / 0        9 / 9
representation         degenerate      degenerate      degenerate   정상
추론 벽시계               142.2초         20.0초          1.8초         28.3초
raw hash               c5e4f752…       09104f0f…       8aed5463…    01496012…
```

실패 사유:

```
A   PARSE_FAILURE · NO_EVENT · TRUNCATED_AT_CAP ·
    OUTPUT_LANGUAGE_CONTRACT_FAILURE · EVENT_REPRESENTATION_DEGENERACY
B   EVENT_REPRESENTATION_DEGENERACY  (이 한 건뿐)
C   CONTRACT_VIOLATION · NO_EVENT · OUTPUT_LANGUAGE_CONTRACT_FAILURE ·
    EVENT_REPRESENTATION_DEGENERACY
D   없음
```

세 실패의 **모양이 서로 다르다**.

```
A   원본 W00과 같은 실패 — cap 도달 · zero-duration 95/95 · JSON 미완결 ·
    두 signature 교대(48/47회). raw가 원본과 byte-identical이다.
B   JSON을 정상 종료했고 시간은 전진하지만(11개 양수 구간) signature가 하나뿐이라
    ("a person / pouring / liquid from a bottle into a glass" ×11) collapse 후 1개 →
    V2 representation 기준 degenerate.
C   출력 전체가 `{"events": []}` 14자다. 빈 목록은 프롬프트가 허용하지만 이번 게이트는
    event가 없으면 NO_EVENT로 INVALID다. 루프도 truncation도 아니다.
D   16개 object · 9개 signature · 양수 구간 · JSON 완결 — 유일한 VALID.
```

`OUTPUT_LANGUAGE_CONTRACT_FAILURE`는 A와 C에 붙었고 **한국어 출력이 아니다** — event
목록이 비어 `english_only([])`가 만족을 주지 않아서 붙는 사유다.

## D. 교차 비교 (AUDIT_DIAGNOSTIC_ONLY)

```
A_vs_B  raw 상이 · 첫 분기 offset 42        A_vs_C  raw 상이 · offset 12
A_vs_D  raw 상이 · offset 26               B_vs_D  raw 상이 · offset 26
C_vs_D  raw 상이 · offset 12
```

네 arm의 raw는 모두 다르다. 이 비교는 판정 authority가 아니고 semantic 우열·사실성을
판정하지 않는다.

## E. primary verdict

```
JOINT_OR_INTERACTION_EFFECT_SUPPORTED
reason    MIXED_PATTERN
패턴       A invalid · B invalid · C invalid · D valid
게이트      사전등록 §13·§14 그대로 — 우선순위 INCONCLUSIVE → CONTROL_NOT_REPRODUCED →
          2×2 패턴. 두 main-effect 패턴(P만/M만) 어느 쪽과도 일치하지 않는다.
blocker   없음 (조작 감사 전 항목 통과 · 픽셀 합치 통과 · self-check SEPARABLE)
```

`PROMPT_TIME_EFFECT_SUPPORTED`(A·B invalid & C·D valid)도,
`METADATA_TIME_EFFECT_SUPPORTED`(A·C invalid & B·D valid)도 아니다 — 한 채널만 옮기면
(B 또는 C) 여전히 INVALID였고, **두 채널을 함께 옮긴 D에서만 VALID**였다.

## F. 의미 / 비의미

말하는 것:

```
동일 픽셀·동일 prompt 문구·동일 runtime에서 absolute-time encoding 조합만 바꿨더니
  기술 판정이 달라졌다 — 이번 W00 pixel set에서 두 시간 채널의 조합과 degeneracy
  상태 사이에 연관이 관찰됐다
control A는 원본 W00 raw와 byte 단위로 같았다 — control이 재현됐다
한 채널만 옮긴 B·C도 INVALID였고, 실패 모양은 A(루프+cap) · B(단일 signature) ·
  C(빈 목록)로 서로 달랐다
측정은 유효했다 — pixel_values 바이트 동일 · 고정 metadata 6필드 동일 ·
  조작 필드는 frames_indices 하나 · rendered prompt는 창 숫자값만 다름
```

말하지 않는 것 (사전등록 §16):

```
근본 원인을 규명했다 · Qwen 내부 메커니즘을 규명했다 · start_sec=0 bug를 증명했다 ·
metadata가 모델을 망가뜨린다 · prompt가 잘못됐다        전부 금지이고 주장하지 않는다
D가 semantic하게 옳다                                  판정하지 않았다
recovery 방법을 찾았다                                 이 사건은 recovery가 아니다
+120초가 특별하다 · 다른 shift에서도 같다                 측정하지 않았다 (shift 1개)
영상 초반 픽셀 자체의 효과                                이번 설계는 픽셀을 고정했다 —
                                                    visual-content isolation은 별도 사건
```

## G. 검증

```
새 테스트   tests/test_wvr_trigger_v1.py  WVR-N01~N43  43/43
뮤테이션    N-M1~N-M53 전부 RED (구멍 없음)
전체 스위트  4,769 passed · 2 skipped · 0 failed
clean tree · HEAD == origin/master
경계 확인   선행 산출물 8개 무변경 (W00 record/raw · C0/C1/C2 record/raw) ·
          SHADOW_V1 blind map 미접촉 · 현행 제출본 5732075871fd… 불변 ·
          official test 미접촉 · 서버 GPU idle
```

## H. 상태 (실행 후에도 유지)

```
WVR_W00_TRIGGER_ISOLATION_V1  CLOSED / JOINT_OR_INTERACTION_EFFECT_SUPPORTED
SHADOW_V1 INCONCLUSIVE · W00_FORENSIC MODEL_OUTPUT_DEGENERACY ·
W00_REPRO REPRODUCIBLE · SUBDIVISION_RECOVERY FAIL ·
RECURSIVE_SUBDIVISION_RECOVERY FAIL                      전부 불변
original W00 · C0 WINDOW_INVALID · C1 · C2 WINDOW_VALID   유지
production Event extraction · Overview / Analysis / Conclusion   HOLD
0.5fps                    PROVISIONAL WORKING DENSITY ONLY
현행 제출본  READ-ONLY      official test UNOPENED      M9 HOLD
후속 visual-content isolation · prompt/schema mutation · token-cap 변경 ·
retry/fallback 정책 · 다른 shift 값                        리뷰어 승인 전 실행 금지
```

## I. 산출물

```
runs/wvr_light_v1/trigger_v1_{A,B,C,D}.json      arm record (조작·픽셀 identity·판정)
runs/wvr_light_v1/trigger_v1_{A,B,C,D}_raw.txt   raw 원문 (파싱 전 저장)
runs/wvr_light_v1/trigger_v1_selfcheck.json      픽셀/metadata 분리 실측 (hard blocker)
runs/wvr_light_v1/trigger_v1_summary.json        arm 표·조작 감사·교차 비교·verdict
runs/wvr_light_v1/trigger_v1.log                 배치 로그
src/wvr_trigger_v1.py · scripts/wvr_trigger_run.py ·
scripts/wvr_trigger_summary.py · scripts/wvr_trigger_selfcheck.py ·
scripts/wvr_trigger_validate.py · scripts/wvr_trigger_batch.sh ·
tests/test_wvr_trigger_v1.py
```

여기서 멈춘다. 다음 설계는 리뷰어가 결정한다.
