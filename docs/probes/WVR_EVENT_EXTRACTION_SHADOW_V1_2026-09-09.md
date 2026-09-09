# WVR_EVENT_EXTRACTION_SHADOW_V1 실행 기록 (2026-09-09)

사전등록: `docs/preregistration/WVR_EVENT_EXTRACTION_SHADOW_V1_2026-09-09.md`
(commit `d3cef5e` — GPU 실행 전 freeze) · 서버 RTX 4090 · 창당 fresh process 1회

```
실행           24/24 완료 (추론 24회) · 재시도 0회
기술 게이트     INCONCLUSIVE   reason WINDOW_TECHNICAL_INVALID
                W00 [0,48) INVALID — 생성 상한 4096 도달로 JSON 미완결
                나머지 23창 WINDOW_VALID
겹침 identity   23/23 OK — 공유 12/12 · 픽셀 sha256 불일치 0
semantic 판정   null (executor가 채우지 않는다 — reviewer 전용)
```

normative source는 `runs/wvr_light_v1/shadow_v1_summary.json`이다.

## A. provenance

```
prereg commit           d3cef5e18d3b4e103af2354cd3f4fe1c5d9f8c1c
실행 commit(서버 HEAD)    d3cef5e18d3b4e103af2354cd3f4fe1c5d9f8c1c
video sha256            ea0e9f486661282056a36781a57d6d74e40da02c03ad9159b75c21fe435676cc
                        (V2·SHORT_WINDOW·FRAME_ADJUDICATION과 동일 파일)
model                   Qwen/Qwen3-VL-8B-Instruct
model revision          0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
prompt                  SAMPLING_DIAG_PROMPT_V2
prompt hash             37f9588e58d0cb96e9a81e8842cbc3e8707404d0346f4aa5e2f4bc273075d273
runtime config hash     창별 record의 runtime_config_hash에 기록 (동일 설정 → 동일 해시)
inference config change NONE (SHORT_WINDOW_V1 S0 대비 · 창마다 preflight에서 대조)
blinding salt           prereg SHA d3cef5e…를 그대로 사용 (결정적 · 재현 가능)
```

## B. 창 실행 요약 (24/24)

```
win  span      frm    in   gen  raw  col uniq  status          reasons
W00    0- 48    24  2135  4096    0    0    0  WINDOW_INVALID  PARSE_FAILURE · NO_EVENT ·
                                                               TRUNCATED_AT_CAP ·
                                                               OUTPUT_LANGUAGE_CONTRACT_FAILURE
W01   24- 72    24  2139   696   16   11   11  WINDOW_VALID
W02   48- 96    24  2139   449   10   10   10  WINDOW_VALID
W03   72-120    24  2145   498   11    9    9  WINDOW_VALID
W04   96-144    24  2151   575   12    6    6  WINDOW_VALID
W05  120-168    24  2153   452   10    6    5  WINDOW_VALID
W06  144-192    24  2153   476   10   10    6  WINDOW_VALID
W07  168-216    24  2153   640   14    8    8  WINDOW_VALID
W08  192-240    24  2153   790   16    2    2  WINDOW_VALID
W09  216-264    24  2153   582   12    6    6  WINDOW_VALID
W10  240-288    24  2153   267    6    4    4  WINDOW_VALID
W11  264-312    24  2153   291    6    6    4  WINDOW_VALID
W12  288-336    24  2153   454   10    6    4  WINDOW_VALID
W13  312-360    24  2153   695   15    2    2  WINDOW_VALID
W14  336-384    24  2153   576   12    4    4  WINDOW_VALID
W15  360-408    24  2153   462   10    9    9  WINDOW_VALID
W16  384-432    24  2153   562   12    7    6  WINDOW_VALID
W17  408-456    24  2153   324    7    6    5  WINDOW_VALID
W18  432-480    24  2153   425    9    5    5  WINDOW_VALID
W19  456-504    24  2153   558   12   12   12  WINDOW_VALID
W20  480-528    24  2153   771   16    3    3  WINDOW_VALID
W21  504-552    24  2153   477   10    8    8  WINDOW_VALID
W22  528-576    24  2153   458   10   10   10  WINDOW_VALID
W23  552-600    24  2153   473   10   10   10  WINDOW_VALID
```

```
frame count       24/24 창 모두 24프레임 · 0.5fps 격자 정확
raw persisted     24/24 (파싱 전에 원문 저장)
runtime failure   0건 · OOM 0건
생성 상한 도달      W00 1건 (4096) · 나머지 23창 최대 790
언어 계약          23창 만족 · W00은 아래 사유
representation    degeneracy W00 1건 (collapsed 0)
```

### W00 [0,48) 실패의 성격 (재시도하지 않았다)

```
raw 길이           11,533자 — 파일로 보존됨 (shadow_v1_W00_raw.txt)
관측 형태          "start_sec": 0.0, "end_sec": 0.0 event를 반복 생성하다가
                  4096 토큰 상한에서 JSON이 문장 중간에 끊겼다
                  raw 마지막: … "object_or_state": "liquid from a bottle into a bowl"},
                             {"start_sec":
파싱              PARSE_FAILURE (미완결 JSON) → collapsed 0 → NO_EVENT
언어 플래그         OUTPUT_LANGUAGE_CONTRACT_FAILURE는 **파싱 실패의 하류 결과**다 —
                  raw에 한글·한자는 0자이고 latin_chars가 0으로 계산됐기 때문이다.
                  독립적인 언어 위반으로 읽지 마라
```

사전등록 §9에 따라 이 창은 INVALID provenance로 남기고 재실행하지 않았다.
이 때문에 기술 게이트가 `INCONCLUSIVE`이고, 23 overlap semantic 판정을 사건 결론으로
승격할 수 없다. `O01`(W00×W01)은 사전등록 frame-audit overlap 7개 중 하나이기도 하다.

## C. 겹침 identity (23/23)

```
overlap 수          23
공유 timestamp      전 overlap 12/12 (기대 12) · 누락 0
픽셀 sha256 동일성   불일치 0 — 같은 시각의 model-input 픽셀이 두 창에서 완전히 같다
frame bank 대조      576건 검사(24창 × 24프레임) · 불일치 0
```

즉 **인접 창이 같은 시각에 본 픽셀은 동일하다.** 표집·디코딩 경로가 창에 따라 달라지지
않았다는 뜻이고, 이후 overlap 차이를 입력 차이로 설명할 수 없다.

## D. collapsed Local Event

창별 raw·collapsed·unique signature 수는 §B 표에 있다. 원문은 창별 record의
`parsed.collapsed`에 그대로 보존돼 있고 **executor는 semantic 품질을 평가하지 않는다.**

```
collapsed 합계(23 valid 창)   161  · raw 합계 262
최소·최대 collapsed           2 (W08 · W13) ~ 12 (W19)
```

## E. blinded overlap packet (23)

```
파일   runs/wvr_light_v1/shadow_v1_overlap_packet.md   (461줄)
표기   overlap id · 절대 시간 범위 · Arm A / Arm B의 clipped event sequence
가림   어느 Arm이 앞선 창인지 표시하지 않는다
mapping runs/wvr_light_v1/shadow_v1_blind_map.json — reviewer 판정 확정 전 열람 금지
clip   경계를 넘는 event는 overlap 범위로 자르고 (clipped) 표시 ·
       원본 구간은 창 record에 보존
```

`O01`의 Arm 한쪽은 `(겹치는 event 없음)`으로 나온다 — W00이 INVALID여서 파싱된
event가 0건이기 때문이다.

blinding은 **절차적**이다: 창 record 파일명이 창 id를 담고 있어 저장소에서 mapping을
복원할 수 있다. packet만 읽는다는 규율에 의존한다.

## F. frame audit packet (사전등록 7 overlap)

```
overlap   O01 [24,48) · O04 [96,120) · O05 [120,144) · O12 [288,312) ·
          O18 [432,456) · O19 [456,480) · O23 [552,576)
구성       overlap마다 공유 12프레임 대지 1장 + 개별 PNG + 절대 시각 + 픽셀 sha256
경로       runs/wvr_light_v1/frames_shadow/O{nn}_shared_sheet.png · F{시각}.png (84장)
명세       runs/wvr_light_v1/shadow_frame_audit.json
bank      runs/wvr_light_v1/shadow_frame_bank.json — 0·2·…·598초 300프레임의
          픽셀 sha256 전량. PNG는 사전등록대로 audit 84장만 저장(정책을 사전 명시)
```

support 판정(`SUPPORTED`·`PARTIALLY_SUPPORTED`·`UNSUPPORTED`·`FRAMES_INSUFFICIENT`)은
**reviewer 전용**이다. executor는 내리지 않았다.

## G. 자동 matcher (AUDIT_DIAGNOSTIC_ONLY)

허용오차 4.0초 기준, 23 overlap 합계.

```
시간정렬 후보   204
EQUIVALENT       1
ADJUDICATION   181
```

파일 `runs/wvr_light_v1/shadow_v1_matcher_audit.json`. V2·SHORT_WINDOW에서와 같은
한계가 재현됐다 — exact-string matcher는 표현 차이를 흡수하지 못한다.
**semantic·materiality·PASS 계산 authority가 아니다.**

## H. 테스트 · 뮤테이션

```
새 테스트   tests/test_wvr_shadow_v1.py  WVR-H01~H33  33/33 통과
뮤테이션    H-M1~M22 전부 RED (구멍 없음)
```

### 실행 후 테스트 단언 1건 정정 (공개)

```
H32   최초 단언 "모든 창이 생성 상한에 도달하지 않는다" → 기하 불변식이 아니라
      결과에 대한 기대였고 W00이 상한에 도달해 RED가 됐다.
      정정 후: 기하(24프레임·창 시작·raw persist)를 검사하고, 상한 도달 창이 있으면
      **그것이 INVALID로 잡혔는지**를 단언한다.
      게이트·판정값은 바꾸지 않았다 — 동결 게이트가 이미 W00을 INVALID로,
      사건 판정을 INCONCLUSIVE로 냈다.
```

## I. 상태 (reviewer 판정 전)

```
EVENT_EXTRACTION_SHADOW_V1        EXECUTED / REVIEW_PENDING
                                  기술 게이트 INCONCLUSIVE (W00 INVALID)
0.25fps semantic sufficiency      NOT ESTABLISHED
0.5fps                            PROVISIONAL WORKING DENSITY ONLY
production Event extraction       HOLD
Chapter / Highlight / Overview / Analysis / Conclusion   HOLD
현행 제출본 R1-VAD0-QUALITY         READ-ONLY (해시 재확인: 5732075871fd… 불변)
official test                     UNOPENED        M9  HOLD
```

## J. 이 실행이 말하는 것과 말하지 않는 것

말하는 것:

```
24창 전부 계약대로 실행됐고(24프레임·격자 정확·raw 선저장·재시도 0) 23창이 기술 검증을 통과했다
인접 창이 같은 시각에 본 픽셀은 23/23 overlap에서 완전히 동일하다
0.5fps·48초 창에서 10분 전체를 24회 추론으로 덮는 것은 용량상 문제가 없었다
  (입력 2,135~2,153 토큰 · 생성 최대 790 · OOM 0 · 창당 벽시계 약 40초)
동일 프롬프트·동일 설정에서도 창 하나(W00)는 반복 생성으로 상한에 닿아 무효가 됐다
```

말하지 않는 것:

```
overlap semantic stability          reviewer 판정 전이다 (executor 금지)
frame grounding                     reviewer 판정 전이다 · 범위는 7/23 overlap뿐
Event Map · Chapter · Overview      만들지 않았다. event를 concat하지도 않았다
0.5fps 충분성 · production 승격      주장 금지
```

## K. 산출물

```
runs/wvr_light_v1/shadow_v1_W{00..23}.json        창 record (provenance·해시·collapsed)
runs/wvr_light_v1/shadow_v1_W{00..23}_raw.txt     raw 원문 (파싱 전 저장)
runs/wvr_light_v1/shadow_v1_summary.json          창 표 · identity · 기술 게이트
runs/wvr_light_v1/shadow_v1_overlap_packet.md     blinded 23 overlap
runs/wvr_light_v1/shadow_v1_blind_map.json        mapping (판정 전 열람 금지)
runs/wvr_light_v1/shadow_v1_matcher_audit.json    AUDIT_DIAGNOSTIC_ONLY
runs/wvr_light_v1/shadow_frame_bank.json          300프레임 해시
runs/wvr_light_v1/shadow_frame_audit.json         7 overlap audit 명세
runs/wvr_light_v1/frames_shadow/                  공유 프레임 84장 + 대지 7장
runs/wvr_light_v1/shadow_v1.log                   배치 로그
```

기존 사건 산출물·현행 제출본은 변경하지 않았다.
