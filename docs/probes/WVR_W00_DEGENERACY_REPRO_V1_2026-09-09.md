# WVR_W00_DEGENERACY_REPRO_V1 결과 (2026-09-09)

사전등록: `docs/preregistration/WVR_W00_DEGENERACY_REPRO_V1_2026-09-09.md`
(commit `ccd048c` — GPU 실행 전 freeze) · 구현 `797f491` · 서버 RTX 4090

```
primary verdict     REPRODUCIBLE   (3/3 · reason ALL_RUNS_DEGENERATE)
determinism 축       EXACT_RAW_REPRODUCTION  (raw byte-identical · distinct hash 1)
원본 W00 무변경        True   (record·raw 해시 사전등록값과 일치)
identity gate       R1·R2·R3 전부 INPUT_IDENTITY_OK
```

normative source는 `runs/wvr_light_v1/w00_repro_summary.json`이다.
recovery 실험을 시작하지 않았고 24초 subdivision 추론도 하지 않았다.

## A. provenance

```
prereg commit        ccd048cbafd706481c6bd4041a2fda051bad9b43
implementation       797f491bd3fe463b391d3c5a44d93b7e4386d57c
video sha256         ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
model revision       0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
prompt hash          37f9588e58d0cb96e9a81e8842cbc3e8707404d0346f4aa5e2f4bc273075d273
runtime config hash  cb43ffd357d771ff2923f2d3e0dec0f48f85bba660171cfc3832a298f4fef5aa
                     (원본 W00과 동일 — 다르면 실행이 거부된다)
```

## B. input identity (원본 W00 대비)

```
항목                    R1        R2        R3
video sha256           동일       동일       동일
window [0,48)          동일       동일       동일
24 timestamps          동일       동일       동일
24 픽셀 해시             동일       동일       동일
serialized prompt      동일       동일       동일
prompt hash            동일       동일       동일
model revision         동일       동일       동일
runtime config hash    동일       동일       동일
generation config      동일       동일       동일
status                 INPUT_IDENTITY_OK ×3
```

원본 산출물 해시도 실행 전·후 그대로다.

```
shadow_v1_W00.json     c8e65b74b8c71aa9…   불변
shadow_v1_W00_raw.txt  c5e4f7526eb83d95…   불변
```

## C. run별 raw 요약

```
                       R1              R2              R3
technical status       PARSE_FAILURE   PARSE_FAILURE   PARSE_FAILURE
technical valid        False           False           False
generated tokens       4,096           4,096           4,096
finish reason          length          length          length
raw chars              11,533          11,533          11,533
completed objects      95              95              95
unique signatures      2               2               2
zero-length intervals  95              95              95
positive-duration      0               0               0
max global repeat      48              48              48
max consecutive repeat 1               1               1
first repeat           object #2 · offset 254 (3 run 동일)
JSON complete          False           False           False
degeneracy             MODEL_OUTPUT_DEGENERACY ×3
추론 벽시계              142.7초         144.7초         144.5초
```

`max consecutive repeat = 1`인 이유는 두 signature가 **교대**하기 때문이다
(연속 동일이 아니라 A-B-A-B 형태). 전역 반복은 48·47회다.

참고 기록 — forensic에서 관측된 두 signature와의 exact-string 일치:

```
S1  a person / pouring / liquid from a bottle into a bowl   48회 (R1·R2·R3 동일)
S2  a person / holding / a bottle                           47회 (R1·R2·R3 동일)
```

문구 일치는 참고이고 판정 기준이 아니다 — 판정은 구조(무진행 반복 · zero-length 지배 ·
미완결)로 했다.

## D. cross-run 비교

```
raw output hash        c5e4f7526eb83d95… (3 run 전부 동일 · distinct 1)
raw byte-identical     True
first 400자 동일        True
top signature 집합 동일  True
failure 구조 동일        True
generated token spread [4096, 4096]
```

추가 관측: **세 run의 raw 해시가 원본 W00의 raw 해시와도 같다**
(`c5e4f7526eb83d95…`). 즉 이번 재현은 원본과 바이트 단위로 일치한다.

## E. primary verdict

```
REPRODUCIBLE
reason   ALL_RUNS_DEGENERATE (3/3)
게이트    사전등록 §9 그대로 — 비율 임계를 새로 만들지 않았다
별도 축   EXACT_RAW_REPRODUCTION (§10 · primary verdict를 바꾸지 않는다)
```

## F. 의미하는 것과 의미하지 않는 것

말하는 것:

```
동일 입력·동일 설정·fresh process 3회에서 W00의 MODEL_OUTPUT_DEGENERACY가 3/3 재현됐다
세 raw가 서로, 그리고 원본 W00과도 byte-identical이다 —
  이 실패는 일시적 흔들림이 아니라 이 입력·이 설정에서 재현되는 결정적 출력이다
zero-length interval 95/95 · 양수 duration 0건 — 시간 축이 전진하지 않는다
95개 object 중 unique signature는 2개이고 교대 루프다
```

말하지 않는 것:

```
원인이 48초 context다 · 원인이 영상 내용이다 · prompt가 나쁘다 · 4096이 부족하다
                                        → 어느 것도 이 사건이 규명하지 않았다
다른 창·다른 영상·다른 설정에서도 이런 루프가 생기는가   측정하지 않았다
recovery 방법이 무엇인가                            시험하지 않았다
original W00의 상태 변경                           WINDOW_INVALID 유지 (소급 VALID 금지)
overlap semantic stability · frame-grounding        NOT ADJUDICATED · mapping 봉인 유지
```

이 3회는 retry가 아니라 사전등록된 관측 3건이다. **성공 run을 골라 production output이나
SHADOW_V1 복구에 쓰지 않았다** (애초에 성공 run이 없다).

## G. 검증

```
새 테스트   tests/test_wvr_w00_repro.py  WVR-K01~K18  18/18
뮤테이션    K-M1~M20 전부 RED (구멍 없음)
경계 확인   원본 W00·blind map·overlap packet 미접촉 ·
          현행 제출본 해시 5732075871fd… 불변 · test split 미접촉
```

## H. 상태

```
WVR_W00_DEGENERACY_REPRO_V1    CLOSED / REPRODUCIBLE (3/3 · EXACT_RAW_REPRODUCTION)
WVR_W00_DEGENERACY_FORENSIC_V1 CLOSED / MODEL_OUTPUT_DEGENERACY (불변)
WVR_EVENT_EXTRACTION_SHADOW_V1 CLOSED / INCONCLUSIVE (불변)
original W00                   WINDOW_INVALID 유지
production Event extraction    HOLD
Chapter / Highlight / Overview / Analysis / Conclusion   HOLD
0.5fps                         PROVISIONAL WORKING DENSITY ONLY
현행 제출본                      READ-ONLY        official test UNOPENED        M9 HOLD
token cap 4096 → 8192          승인되지 않았다
24초/12초 subdivision 추론       금지 (리뷰어 승인 전)
```

## I. 후속 branch (기록만 · 실행하지 않았다)

리뷰어의 provisional branch 중 `REPRODUCIBLE` 경로에 해당한다.

```
REPRODUCIBLE → failed-window subdivision recovery 실험 후보
               48초 → 24초 local windows / 12초 overlap · prompt·runtime 불변
```

**이 사건에서 실행하지 않았다.** 다음 사건 여부·형태는 리뷰어가 결정한다.

## J. 산출물

```
runs/wvr_light_v1/w00_repro_R{1,2,3}.json       run record (identity·구조·판정)
runs/wvr_light_v1/w00_repro_R{1,2,3}_raw.txt    raw 원문 (파싱 전 저장)
runs/wvr_light_v1/w00_repro_summary.json        identity·run 표·교차 비교·게이트
runs/wvr_light_v1/w00_repro.log                 배치 로그
src/wvr_w00_repro.py · scripts/wvr_w00_repro_run.py ·
scripts/wvr_w00_repro_summary.py · scripts/wvr_w00_repro_batch.sh ·
tests/test_wvr_w00_repro.py
```
