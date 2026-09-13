# WVR_WHOLE_VIDEO_REPORT_V3_USABILITY — 실행 결과 (2026-09-13)

상태: `EXECUTED / REVIEW_PENDING`. 이 variant는 reviewer-PASS V2 baseline을
대체하지 않으며, executor는 V3의 최종 품질 PASS/HOLD를 선언하지 않는다.

## 최초 결과

### ONE_LINE_SUMMARY

이 영상은 음식 준비 및 조리와 식사를 비롯해 구매 또는 둘러보기, 이동, 외출 준비, 포장 작업, 의류 작업 및 수선이 시간에 따라 전환되는 과정을 담고 있다.

### HIGHLIGHTS

1. `00:24–04:00` — 음식 준비 및 조리
2. `12:24–14:24` — 구매 또는 둘러보기
3. `16:48–19:12` — 구매 또는 둘러보기
4. `21:36–22:24` — 구매 또는 둘러보기 · 음식 준비 및 조리
5. `26:24–29:36` — 음식 준비 및 조리
6. `31:12–39:12` — 음식 준비 및 조리
7. `39:12–40:24` — 식사

## 선정·실행

결과 계산 전 선정 규칙을 commit `7ac2f13`으로 고정했다. 96개 timeline entry를
동일 activity tuple 기준 46개 contiguous block으로 병합하고, 관찰 범위를 6개 동일
시간층으로 나눈 뒤 각 층에서 overlap duration이 가장 긴 미선택 block을 골랐다.
canonical final phase `[2352, 2424)`는 별도로 보존했다.

```text
deterministic report build  1
retry                       0
visual inference            0
STT inference               0
β/v3 regeneration           0
text generation inference   0
```

## Validation

```text
highlight count                     7
timestamps monotonic                true
highlight overlap                   0
lineage completeness                100%
early/middle/late coverage          true
unknown activity                    0
internal identifier exposure        0
context/intent overclaim            0
final phase consistency             PASS — 식사 [2352,2424)
frozen Overview                     unchanged / verbatim
frozen Analysis                     unchanged / verbatim
frozen Conclusion                   unchanged / verbatim
technical metadata moved            true
frozen source hashes                before == after
```

## 최초 결과의 reviewer 확인 필요 사항

결과 확인 후 규칙을 고치거나 더 좋은 문장을 고르는 재생성은 하지 않았다. 따라서 다음
초기 출력 특성이 그대로 남아 있다.

- 6등분 최대-overlap 규칙에서 긴 음식 준비·구매 block이 우세해, 이동·외출 준비·포장·
  의류 작업은 한 줄 요약과 frozen Overview에는 있지만 7개 highlight에는 선택되지 않았다.
- 복합 label을 단순 조사로 연결해 `구매 또는 둘러보기과 음식 준비 및 조리`라는
  부자연스러운 한국어가 2개 설명에 남았다.
- 같은 broad activity가 떨어진 대표 구간에 다시 선택됐을 때도 `전환된다`고 표현한
  설명이 있다.
- 생성된 technical appendix의 `selection rule commit` 필드는 실행 당시 HEAD
  `186f67a`를 기록했다. 실제 pre-computation selection-rule commit은 `7ac2f13`이다.

이 항목들은 source, timestamp, lineage 또는 final phase의 기계 검증 실패는 아니지만,
사용자-facing usability 품질 판정에서 reviewer가 별도로 고려해야 한다.

## HWPX

```text
generated             true
structural errors     0
semantic text match   true
GUI layout            GUI_LAYOUT_UNVERIFIED
```

## 테스트

```text
local report-related tests   38 passed
server report-related tests  34 passed, 4 skipped
server full suite            4942 passed, 175 failed, 30 skipped, 19 errors
```

전체 suite 실패·오류는 기존 누락 artifact, 기존 frozen-hash 불일치, P2/P3 상태 등
V3 외부 상태다. 이번 작업에서는 수정하지 않았다. official test는 `UNTOUCHED`, M9는
`NOT_INVOKED`다.

## Artifact SHA256

```text
final_report_v3.md
1416ee82bd33bd4c73f04693ef1037be3c0add3af4095af7160d7b65b7724829

final_report_v3.hwpx
b3befee4c8d2c6cee5a7f698495588808d2fd28e646a07d862a3a2bdd6bd8c4c

final_report_v3_technical_appendix.md
ae50d90c9fbd6e840b3624d69e7c1e428281fa23ab1ab57906f2f1d936b8dd04

highlights.json
719f8192d5aeed1830f644fa4623de230a0570f2e2c63cd1be9dd5a1c9c5da99

highlight_lineage.json
99071af66c53ad69bd04ed6ab187a6583651572a44702e9cea96d7bf72efb89a
```

## FINAL REPORT BODY

```markdown
# 영상 전체 보고서

## 한 줄 요약

이 영상은 음식 준비 및 조리와 식사를 비롯해 구매 또는 둘러보기, 이동, 외출 준비, 포장 작업, 의류 작업 및 수선이 시간에 따라 전환되는 과정을 담고 있다.

## 개요

음식 준비 및 조리와 구매 또는 둘러보기가 먼저 이어진다.  
다시 음식 준비 및 조리가 나타나며 식사가 추가된다.  
식사 후 구매 또는 둘러보기가 다시 나타나고, 이동과 외출 준비, 포장 작업, 의류 작업 및 수선 등이 순차적으로 이어진다.  
영상은 식사로 끝난다.

## 주요 구간

### 00:24–04:00

음식 준비 및 조리

음식 준비 및 조리 활동이 이어지며, 이후 대표 구간에서는 구매 또는 둘러보기 활동으로 전환된다.

### 12:24–14:24

구매 또는 둘러보기

구매 또는 둘러보기 활동이 이어지며, 이후 대표 구간에서는 구매 또는 둘러보기 활동으로 전환된다.

### 16:48–19:12

구매 또는 둘러보기

구매 또는 둘러보기 활동이 이어지며, 이후 대표 구간에서는 구매 또는 둘러보기과 음식 준비 및 조리 활동으로 전환된다.

### 21:36–22:24

구매 또는 둘러보기 · 음식 준비 및 조리

구매 또는 둘러보기과 음식 준비 및 조리 활동이 이어지며, 이후 대표 구간에서는 음식 준비 및 조리 활동으로 전환된다.

### 26:24–29:36

음식 준비 및 조리

음식 준비 및 조리 활동이 이어지며, 이후 대표 구간에서는 음식 준비 및 조리 활동으로 전환된다.

### 31:12–39:12

음식 준비 및 조리

음식 준비 및 조리 활동이 이어지며, 이후 대표 구간에서는 식사 활동으로 전환된다.

### 39:12–40:24

식사

식사 활동이 이어지며 영상의 관찰 구간이 마무리된다.

## 상세 개요

음식 준비 및 조리와 구매 또는 둘러보기가 먼저 이어진다. 이후 음식 준비 및 조리가 다시 나타나며, 식사가 추가된다. 식사가 끝나면 다시 구매 또는 둘러보기가 나타나고, 이동과 외출 준비, 포장 작업, 의류 작업 및 수선 등이 순차적으로 이어진다. 영상은 식사로 끝난다.

## 분석

음식 준비 및 조리와 구매 또는 둘러보기가 반복적으로 나타나며, 식사가 여러 차례 중간에 배치된다. 의류 작업 및 수선은 한 번만 등장하고, 외출 준비와 이동, 포장 작업은 특정 시점에서 순차적으로 연결된다. 영상은 식사로 종료된다.

## 결론

음식 준비 및 조리와 구매 또는 둘러보기가 반복되며, 식사는 중간에 여러 번 등장한다. 의류 작업 및 수선은 한 번만 나타나고, 외출 준비와 이동, 포장 작업은 특정 시점에 순차적으로 이어진다. 영상은 식사로 끝난다.

## 생성 및 근거 요약

- 전체 영상 약 40분의 동결 시각 관찰 timeline을 기반으로 작성했다.
- 주요 구간은 timeline의 시간과 활동을 결정 규칙으로 압축했으며 새 영상·음성 추론은 하지 않았다.
- 품질 기준을 충족하지 못한 보조 음성·생성 구간은 사실 근거에서 제외했다.
```

```text
WVR_WHOLE_VIDEO_REPORT_V3_USABILITY
EXECUTED / REVIEW_PENDING
```
