# WVR_W00_RECURSIVE_SUBDIVISION_RECOVERY_V1 결과 (2026-09-10)

사전등록:
`docs/preregistration/WVR_W00_RECURSIVE_SUBDIVISION_RECOVERY_V1_2026-09-09.md`
(commit `4c0f24a` — GPU 실행 전 freeze) · 구현 `43e5852` · 서버 RTX 4090

```
primary verdict     RECURSIVE_SUBDIVISION_RECOVERY_FAIL  (reason CHILD_TECHNICAL_INVALID)
child 판정           D0 WINDOW_INVALID · D1 WINDOW_INVALID · D2 WINDOW_VALID  (1/3)
blocker             없음 — 측정 자체는 유효했다 (INCONCLUSIVE 아님)
공유 프레임 identity   RR-O1 3/3 · RR-O2 3/3 · 픽셀 해시 불일치 0
계보 대조             child별 6/6 프레임이 C0 record·frame bank와 픽셀 동일 · 불일치 0
packet · frame audit 생성하지 않았다 (사전등록 §12·§14 — PASS일 때만)
선행 산출물            C0·C1·C2·W00 record/raw 8개 전부 무변경 (실행 전 게이트 + 실행 후 재확인)
```

normative source는 `runs/wvr_light_v1/recur_v1_summary.json`이다.
semantic 판정·frame support 판정은 하지 않았고, 6초/3초로의 재귀도 하지 않았다.

## A. provenance

```
prereg commit        4c0f24a0f6bf3a7821d0fdc1776b499b64e32346
implementation       43e58521565715f34a76fca3435fec85c5d1fa66   (실행 commit)
video sha256         ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
model revision       0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
prompt hash          37f9588e58d0cb96e9a81e8842cbc3e8707404d0346f4aa5e2f4bc273075d273
runtime config hash  cd98cb53c363b004…  (D0·D1·D2 동일)
                     C0의 082494b6…과 다른 부분은 해시 대상 dict의 window_sec 12·
                     frames_per_window 6뿐이고, 그 둘이 이번 사건의 유일한 변경이다
inference 설정 변경    NONE (창 기하 제외 전 항목 C0와 동일 · 실행 전 게이트가 확인)
token cap            4096 유지 · repetition_penalty 1.0 · greedy
```

## B. child 입력

```
child   span        frames  timestamps            입력 토큰(video)
D0      [0,12)      6       0,2,4,6,8,10          758 (432)
D1      [6,18)      6       6,8,10,12,14,16       760 (432)
D2      [12,24)     6       12,14,16,18,20,22     762 (432)

parent coverage   C0 [0,24) · gap 0 · union [0,24)
공유 프레임         RR-O1 [6,12) → 6, 8, 10      (3장 · 픽셀 해시 동일)
                  RR-O2 [12,18) → 12, 14, 16   (3장 · 픽셀 해시 동일)
계보               각 child 6프레임 전부 C0 record·frame bank와 픽셀 sha256 동일 ·
                  불일치 0 · 미대조 0
raw output hash   D0 e8b6ac649450353d… · D1 0ed264565917ebbe… · D2 a635354d0421de42…
```

## C. 출력

```
                       D0              D1              D2
technical status       WINDOW_INVALID  WINDOW_INVALID  WINDOW_VALID
parse status           PARSE_FAILURE   OK              OK
generated tokens       4,096           574             179
finish reason          length          stop            stop
generation cap hit     True            False           False
raw chars              11,074          1,565           484
완성 object              95              12              4
raw unique signature   23              1               2
zero-duration          95              0               0
positive-duration      0               12              4
최대 signature 반복       73              12              3
최대 연속 동일             73              12              3
JSON 완결                False           True            True
collapsed event        0               1               2
collapsed unique       0               1               2
representation         degenerate      degenerate      정상
추론 벽시계               143.2초         21.1초          7.5초
peak VRAM              17,446.0 MiB    16,963.4 MiB    16,963.6 MiB
```

실패 사유:

```
D0   PARSE_FAILURE · NO_EVENT · TRUNCATED_AT_CAP ·
     OUTPUT_LANGUAGE_CONTRACT_FAILURE · EVENT_REPRESENTATION_DEGENERACY
D1   EVENT_REPRESENTATION_DEGENERACY  (이 한 건뿐)
```

두 실패의 **구조가 다르다**.

```
D0   4096 cap 도달 · zero-duration 95/95 · JSON 미완결.
     상위 signature 하나가 연속 73회 반복된다
     (a person / wearing / a black hairpin — 다른 22개 signature는 각 1회).
     첫 반복은 object #23이다 → 앞부분은 다양했고 이후 한 문구에 갇혔다.
D1   cap에 닿지 않고 JSON을 정상 종료했다. 12개 object가 1초 단위로 시간은 전진하지만
     (6-7, 7-8, …, 17-18) signature가 12개 모두 동일해
     (person / squeezing / cream from a bag onto bread) collapse 후 event 1개 ·
     unique 1개가 되어 V2 representation 기준으로 degenerate다.
```

`OUTPUT_LANGUAGE_CONTRACT_FAILURE`는 D0에만 붙었고 **한국어 출력이 아니다** — 파싱
실패로 event 목록이 비어 `english_only([])`가 만족을 주지 않아서 붙는다. D0·D1·D2 raw
모두 비ASCII 0자, 한글 0자다.

D2 출력(참고 기록 · semantic 판정 아님):

```
12–15  person / holds / sticker sheet
15–17  person / holds / plastic bag with rice
17–21  person / holds / plastic bag with rice
21–24  person / holds / plastic bag with rice
```

## D. 깊이 비교 (구조 항목만 · 셋 다 0초에서 시작)

```
                       W00 [0,48)      C0 [0,24)       D0 [0,12)
frames                 24              12              6
입력 토큰                2,135           1,217           758
generated tokens       4,096 (cap)     4,096 (cap)     4,096 (cap)
raw chars              11,533          11,713          11,074
완성 object              95              93              95
raw unique signature   2               3               23
zero-duration          95/95           93/93           95/95
positive-duration      0               0               0
최대 반복                48              31              73
JSON 완결                False           False           False
degeneracy             MODEL_OUTPUT    MODEL_OUTPUT    representation degenerate
raw hash               c5e4f752…       7460a5b6…       e8b6ac64…
status                 WINDOW_INVALID  WINDOW_INVALID  WINDOW_INVALID
```

기록하는 것은 하나다 — **0초에서 시작하는 창은 48초·24초·12초 세 depth에서 모두 같은
종류의 실패(cap 도달 · zero-duration 지배 · JSON 미완결)를 냈고, raw는 서로 다르다.**

`start_sec=0이 원인`이라고 단정하지 않는다. 창 길이·영상 내용·prompt·cap 중 무엇이
원인인지는 이 사건이 규명하지 않았다. 실패가 어느 subdivision depth까지 지속되는지만
기록한다.

`C1 [12,36) VALID`과 `D2 [12,24) VALID`는 시각을 공유하지만 context가 달라
**equivalent truth로 취급하지 않았고**, PASS가 아니므로 context stability packet도
만들지 않았다.

## E. technical verdict

```
RECURSIVE_SUBDIVISION_RECOVERY_FAIL
reason      CHILD_TECHNICAL_INVALID     (D0 · D1 WINDOW_INVALID)
valid       1/3
blockers    없음
게이트        사전등록 §9 그대로 — 우선순위 INCONCLUSIVE → FAIL → PASS.
            결과를 본 뒤 예외를 만들지 않았다.
event 상태   RECURSIVE_SUBDIVISION_RECOVERY_FAIL  (SEMANTIC_REVIEW_PENDING 아님)
```

## F. packet

```
blind overlap packet   생성하지 않았다      frame audit packet   생성하지 않았다
mapping                생성하지 않았다 (blind map 파일 없음)
사유                    사전등록 §12·§14 — 3/3 VALID일 때만 생성한다
추가 사유                RR-O1 [6,12)은 양쪽(D0·D1)이 모두 INVALID이고,
                       RR-O2 [12,18)도 한쪽(D1)이 INVALID여서 두 child 비교가 성립하지 않는다
```

게이트를 우회한 부분 packet은 만들지 않았다.

## G. 검증

```
새 테스트   tests/test_wvr_recursive_v1.py  WVR-M01~M44  44/44
뮤테이션    M-M1~M-M46 전부 RED (구멍 없음)
전체 스위트  4,725 passed · 2 skipped · 0 failed
clean tree · HEAD == origin/master
경계 확인   선행 산출물 8개 무변경 —
          subdiv_v1_C0.json 7925172a… · C0_raw 7460a5b6… ·
          C1.json 44b7f96c… · C1_raw 9316f9f6… ·
          C2.json cb77b4b2… · C2_raw 70815aee… ·
          shadow_v1_W00.json c8e65b74… · W00_raw c5e4f752…
          C1·C2 재실행 없음 · SHADOW_V1 blind map 10282152… 미접촉 · reveal 없음
          현행 제출본 5732075871fd… 불변 · official test 미접촉
```

## H. 의미하는 것과 의미하지 않는 것

말하는 것:

```
사전등록된 12초/6초 재분해 3 child 중 D0·D1이 model-output 실패로 WINDOW_INVALID였고,
사전등록 게이트에 따라 이 사건은 RECURSIVE_SUBDIVISION_RECOVERY_FAIL이다
측정은 유효했다 — 계보 픽셀 6/6 동일 · 공유 프레임 identity 3/3 두 겹침 · 설정 변경 NONE
D0은 상위 앞선 depth들과 같은 종류의 실패, D1은 다른 종류의 실패(무진행 아님 ·
  JSON 정상 종료 · 단일 signature)였다
D2 [12,24)는 같은 prompt·runtime에서 기술적으로 유효한 출력을 냈다
```

말하지 않는 것:

```
모든 더 짧은 window가 실패한다              일반화하지 않는다 (사전등록 §16)
12초가 universally safe하다 · 0초 boundary가 원인 · 24초가 원인 ·
영상 내용이 원인 · prompt가 원인            이 사건이 규명하지 않았다
D1·D2 출력이 semantic하게 옳다              판정하지 않았다 (packet 없음)
hierarchical fallback을 production 채택      아니다 — 채택 근거로 쓰지 않는다
0.5fps가 충분하다                          NOT ESTABLISHED 유지
Event extraction이 해결됐다                 아니다 — production은 HOLD
```

## I. 상태 (실행 후에도 유지)

```
WVR_W00_RECURSIVE_SUBDIVISION_RECOVERY_V1  CLOSED / RECURSIVE_SUBDIVISION_RECOVERY_FAIL (1/3)
WVR_W00_SUBDIVISION_RECOVERY_V1            CLOSED / SUBDIVISION_RECOVERY_FAIL (불변)
WVR_W00_DEGENERACY_REPRO_V1                CLOSED / REPRODUCIBLE (불변)
WVR_W00_DEGENERACY_FORENSIC_V1             CLOSED / MODEL_OUTPUT_DEGENERACY (불변)
WVR_EVENT_EXTRACTION_SHADOW_V1             CLOSED / INCONCLUSIVE (불변 · 소급 복구 없음)
C0 WINDOW_INVALID · C1 WINDOW_VALID · C2 WINDOW_VALID · W00 WINDOW_INVALID   유지
production Event extraction                HOLD
Chapter / Highlight / Overview / Analysis / Conclusion / HWPX   HOLD
0.5fps                                     PROVISIONAL WORKING DENSITY ONLY
현행 제출본  READ-ONLY      official test UNOPENED      M9 HOLD
token cap 4096 → 8192                      승인되지 않았다
6초 window / 3초 overlap 재귀                금지 (사전등록 §18 STOP 규칙)
전체 C01 재분해 · fallback 정책 채택            금지
```

## J. 다음 단계

사전등록 §18 STOP 규칙에 따라 **12초에서 멈췄다.** 다음 minimum context / failure
policy는 리뷰어가 별도 설계한다. 어떤 후속 사건도 열지 않았다.

## K. 산출물

```
runs/wvr_light_v1/recur_v1_D{0,1,2}.json      child record (identity·계보·판정)
runs/wvr_light_v1/recur_v1_D{0,1,2}_raw.txt   raw 원문 (파싱 전 저장)
runs/wvr_light_v1/recur_v1_summary.json       child 표·겹침 identity·게이트·깊이 비교
runs/wvr_light_v1/recur_v1.log                배치 로그
src/wvr_recursive_v1.py · scripts/wvr_recur_run.py ·
scripts/wvr_recur_summary.py · scripts/wvr_recur_frames.py ·
scripts/wvr_recur_validate.py · scripts/wvr_recur_batch.sh ·
tests/test_wvr_recursive_v1.py
```
