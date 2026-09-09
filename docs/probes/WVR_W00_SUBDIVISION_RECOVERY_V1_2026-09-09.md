# WVR_W00_SUBDIVISION_RECOVERY_V1 결과 (2026-09-09)

사전등록: `docs/preregistration/WVR_W00_SUBDIVISION_RECOVERY_V1_2026-09-09.md`
(commit `e593914` — GPU 실행 전 freeze) · 구현 `fb8f75f` · 서버 RTX 4090

```
primary verdict     SUBDIVISION_RECOVERY_FAIL   (reason CHILD_TECHNICAL_INVALID)
child 판정           C0 WINDOW_INVALID · C1 WINDOW_VALID · C2 WINDOW_VALID   (2/3)
blocker             없음 — 측정 자체는 유효했다 (INCONCLUSIVE 아님)
공유 프레임 identity   R-O1 6/6 · R-O2 6/6 · 픽셀 해시 불일치 0
계보 대조             child별 12/12 프레임이 기존 C01 계보와 픽셀 동일 · 불일치 0
packet              생성하지 않았다 (사전등록 §11·§13 — PASS일 때만)
```

normative source는 `runs/wvr_light_v1/subdiv_v1_summary.json`이다.
semantic 판정·frame support 판정은 하지 않았고, 후속 branch도 실행하지 않았다.

## A. provenance

```
prereg commit        e593914d69826c378ce59c3476b036396ac3a723
implementation       fb8f75fda38264081e15e30b1952dfc4b691b506  (실행 commit)
사후 수정              21c8359195213094dc68fee3b52e1df3a4c4bc6b  (§H 참조 · 게이트 불변)
video sha256         ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
model revision       0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
prompt hash          37f9588e58d0cb96e9a81e8842cbc3e8707404d0346f4aa5e2f4bc273075d273
runtime config hash  082494b61c8b2fb1c5ba614b59254f86b442a34274b95e8a20b00ccff6459be3
                     (C0·C1·C2 동일. W00의 cb43ffd3…과 다른 이유는 해시 대상 dict에
                      window_sec 24·frames_per_window 12가 들어가기 때문이고,
                      그 두 값이 이 사건이 시험하는 유일한 변경이다)
inference 설정 변경    NONE (창 기하 제외 전 항목 W00과 동일 · 실행 전 게이트가 확인)
token cap            4096 (상향 없음) · repetition_penalty 1.0 · greedy
```

## B. child 입력

```
child   span        frames  timestamps                                    입력 토큰
C0      [0,24)      12      0,2,4,6,8,10,12,14,16,18,20,22                1,217 (video 864)
C1      [12,36)     12      12,14,16,18,20,22,24,26,28,30,32,34           1,221 (video 864)
C2      [24,48)     12      24,26,28,30,32,34,36,38,40,42,44,46           1,221 (video 864)

parent coverage      [0,48) · gap 0 · union [0,48)
공유 프레임            R-O1 [12,24) → 12,14,16,18,20,22   (6개 · 픽셀 해시 동일)
                     R-O2 [24,36) → 24,26,28,30,32,34   (6개 · 픽셀 해시 동일)
계보                  각 child 12프레임 전부 기존 C01 계보(원본 W00 record + frame bank)와
                     픽셀 sha256 동일 · 불일치 0 · 미대조 0
raw output hash      C0 7460a5b61821e41b… · C1 9316f9f62b519ef0… · C2 70815aeee2408bd1…
```

프레임 픽셀 해시 전량은 각 `subdiv_v1_C*.json`의 `frame_hashes`에 있다.

## C. 출력

```
                       C0              C1              C2
technical status       WINDOW_INVALID  WINDOW_VALID    WINDOW_VALID
parse status           PARSE_FAILURE   OK              OK
generated tokens       4,096           355             352
finish reason          length          stop            stop
generation cap hit     True            False           False
raw chars              11,713          980             949
완성 object              93              8               8
raw unique signature   3               2               8
zero-duration          93              0               0
positive-duration      0               8               8
최대 signature 반복       31              7               1
JSON 완결                False           True            True
collapsed event        0               2               8
collapsed unique       0               2               8
representation         degenerate      정상              정상
추론 벽시계               143.6초         13.7초          13.7초
peak VRAM              17,521.6 MiB    17,103.6 MiB    17,103.6 MiB
```

C0의 실패 사유 목록은
`['PARSE_FAILURE', 'NO_EVENT', 'TRUNCATED_AT_CAP', 'OUTPUT_LANGUAGE_CONTRACT_FAILURE',
'EVENT_REPRESENTATION_DEGENERACY']`이고 전부 model-output 어휘다(blocker 0건).

**`OUTPUT_LANGUAGE_CONTRACT_FAILURE`를 "한국어가 나왔다"로 읽지 마라.** 이 사유는 파싱이
실패해 event 목록이 비었을 때 `english_only([])`가 만족을 주지 않기 때문에 붙는다. C0 raw
11,713자에 비ASCII 문자는 **0개**이고 한글은 없다. 원본 W00에도 같은 사유가 같은 이유로
붙어 있었다(2026-09-09 forensic 기록과 일치).

C0 루프의 구조 — 세 signature가 **순환**한다(연속 동일이 아니라 A-B-C-A-B-C):

```
S1  a person / pouring  / liquid from a bottle into a bowl   31회
S2  a person / holding  / a bottle of liquid                 31회
S3  a person / standing / in front of a counter              31회
첫 반복  object #3 · offset 387        최대 연속 동일  1
tail    "…"action": "pouring"," 에서 잘림 (미완결)
```

문구 일치는 참고이고 판정 기준이 아니다 — 판정은 구조(무진행 반복 · zero-length 지배 ·
미완결 · cap 도달)로 했다.

## D. recovery verdict

```
SUBDIVISION_RECOVERY_FAIL
reason      CHILD_TECHNICAL_INVALID     (C0 WINDOW_INVALID)
valid       2/3
blockers    없음
게이트        사전등록 §9 그대로 — 우선순위 INCONCLUSIVE → FAIL → PASS.
            결과를 본 뒤 예외를 만들지 않았다.
event 상태   SUBDIVISION_RECOVERY_FAIL   (PASS가 아니므로 SEMANTIC_REVIEW_PENDING 아님)
```

## E. 48초 W00과의 구조 비교 (구조 항목만 · 우열 주장 없음)

```
                       W00 [0,48)      C0 [0,24)       C1 [12,36)   C2 [24,48)
frames                 24              12              12           12
입력 토큰                2,135           1,217           1,221        1,221
generated tokens       4,096 (cap)     4,096 (cap)     355          352
완성 object              95              93              8            8
unique signature       2               3               2            8
zero-duration          95/95           93/93           0/8          0/8
최대 반복                48              31              7            1
JSON 완결                False           False           True         True
raw output hash        c5e4f752…       7460a5b6…       9316f9f6…    70815aee…
technical status       WINDOW_INVALID  WINDOW_INVALID  WINDOW_VALID WINDOW_VALID
```

관측 사실 두 가지만 적는다.

```
① parent와 같은 시각에서 시작하는 C0는 창을 24초로 줄여도 같은 종류의 실패를 냈다 —
  cap 도달 · zero-duration 지배 · 미완결 · 무진행 반복. raw는 W00과 byte-identical이
  아니다(해시 상이 · signature 2개 → 3개 · 반복 48 → 31).
② parent 구간의 나머지를 덮는 C1·C2는 기술적으로 유효한 출력을 냈다.
```

`24초가 안전하다`·`48초가 원인이다`·`영상 내용이 원인이다`·`prompt가 원인이다`는
**이 사건이 규명하지 않았다.** C0가 실패한 원인은 이 사건의 측정 대상이 아니다.

## F. packet

```
blind overlap packet   생성하지 않았다
frame audit packet     생성하지 않았다
사유                    사전등록 §11·§13 — 3/3 VALID(PASS)일 때만 생성한다
추가 사유                R-O1 [12,24)은 한쪽(C0)이 유효 event를 만들지 못했으므로
                       두 child 비교 자체가 성립하지 않는다
mapping                생성하지 않았다 (blind map 파일 없음)
```

`R-O2 [24,36)`은 두 child가 모두 유효하지만 **사건 게이트가 FAIL이므로 packet을
만들지 않았다.** 사후에 게이트를 우회해 부분 packet을 만들지 않았다.

## G. 검증

```
새 테스트   tests/test_wvr_subdivision_v1.py  WVR-L01~L44  44/44
뮤테이션    L-M1~L-M39 전부 RED (구멍 없음)
전체 스위트  4,681 passed · 2 skipped · 0 failed
clean tree · HEAD == origin/master
경계 확인   원본 W00 record c8e65b74… · raw c5e4f752… 불변 (실행 전·후 게이트로 확인)
          SHADOW_V1 blind map 10282152… 미접촉 · reveal 없음 · 23 overlap 미판정
          현행 제출본 5732075871fd… 불변 · official test 미접촉
```

## H. 실행 중 발견한 결함 (공개)

런너의 진단 필드 한 줄이 개발 중 잔여 코드(`... if False else None`)로 남아
`record["structure"]`가 세 child 모두 `None`으로 저장됐다.

```
영향 없음    child 기술 게이트·recovery 판정은 V2 parse/representation과 metrics만 쓴다.
           C0/C1/C2의 판정값(WINDOW_INVALID·VALID·VALID)과 FAIL 판정은 이 필드와 무관하다.
조치        런너를 fx.raw_structure로 고치고(commit 21c8359), 요약 도구는 record에 구조가
           없으면 **파싱 전에 저장된 raw 원문**에서 사후 계산하며 출처를
           `structure_source`로 표시한다. 이번 §C 수치의 출처는 셋 다
           `raw_file_post_hoc`다.
하지 않은 것  추론 재실행 · raw 수정 · 게이트·판정 어휘·해석 제한 변경
```

## I. 의미하는 것과 의미하지 않는 것

말하는 것:

```
사전등록된 24초/12초 분해 3 child 중 C0가 model-output 실패로 WINDOW_INVALID였고,
사전등록 게이트에 따라 이 사건은 SUBDIVISION_RECOVERY_FAIL이다
측정은 유효했다 — 계보 픽셀 동일 · 공유 프레임 identity 12/12 · 설정 변경 NONE
C1·C2는 같은 prompt·runtime에서 기술적으로 유효한 출력을 냈다
```

말하지 않는 것:

```
24초 subdivision architecture가 불가능하다            일반화하지 않는다 (사전등록 §10)
C0 실패의 원인 (창 길이·내용·prompt·cap)               이 사건이 규명하지 않았다
C1·C2 출력이 semantic하게 옳다                        판정하지 않았다 (packet 없음)
0.5fps가 충분하다                                    NOT ESTABLISHED 유지
Event extraction이 해결됐다                          아니다 — production은 HOLD
```

## J. 상태 (실행 후에도 유지)

```
WVR_W00_SUBDIVISION_RECOVERY_V1  CLOSED / SUBDIVISION_RECOVERY_FAIL (2/3)
WVR_W00_DEGENERACY_REPRO_V1      CLOSED / REPRODUCIBLE (불변)
WVR_W00_DEGENERACY_FORENSIC_V1   CLOSED / MODEL_OUTPUT_DEGENERACY (불변)
WVR_EVENT_EXTRACTION_SHADOW_V1   CLOSED / INCONCLUSIVE (불변 · 소급 복구 없음)
original W00                     WINDOW_INVALID 유지
production Event extraction      HOLD
Chapter / Highlight / Overview / Analysis / Conclusion / HWPX   HOLD
0.5fps                           PROVISIONAL WORKING DENSITY ONLY
현행 제출본                        READ-ONLY      official test UNOPENED      M9 HOLD
token cap 4096 → 8192            승인되지 않았다
전체 C01 24초 재실행                금지 (이번 사건 범위 아님)
```

## K. 후속 branch (기록만 · 실행하지 않았다)

사전등록 §18의 `RECOVERY FAIL` 경로에 해당한다.

```
RECOVERY FAIL → 24초 subdivision도 현행 prompt/runtime에서 recovery 불충분
```

다음 사건 여부·형태는 리뷰어가 결정한다. 여기서 멈춘다.

## L. 산출물

```
runs/wvr_light_v1/subdiv_v1_C{0,1,2}.json       child record (identity·계보·판정)
runs/wvr_light_v1/subdiv_v1_C{0,1,2}_raw.txt    raw 원문 (파싱 전 저장)
runs/wvr_light_v1/subdiv_v1_summary.json        child 표·겹침 identity·게이트·구조 비교
runs/wvr_light_v1/subdiv_v1.log                 배치 로그
src/wvr_subdivision_v1.py · scripts/wvr_subdiv_run.py ·
scripts/wvr_subdiv_summary.py · scripts/wvr_subdiv_frames.py ·
scripts/wvr_subdiv_validate.py · scripts/wvr_subdiv_batch.sh ·
tests/test_wvr_subdivision_v1.py
```
