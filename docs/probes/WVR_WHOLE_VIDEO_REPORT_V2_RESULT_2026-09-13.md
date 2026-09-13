# WVR_WHOLE_VIDEO_REPORT_V2 — 실행 결과 (2026-09-13)

상태: `EXECUTED / REVIEW_PENDING`. 최종 report quality PASS/HOLD는 reviewer가 결정한다.

## ANALYSIS — 최초 생성 원문

음식 준비 및 조리와 구매 또는 둘러보기가 반복적으로 나타나며, 식사가 여러 차례 중간에 배치된다. 의류 작업 및 수선은 한 번만 등장하고, 외출 준비와 이동, 포장 작업은 특정 시점에서 순차적으로 연결된다. 영상은 식사로 종료된다.

## CONCLUSION — 최초 생성 원문

음식 준비 및 조리와 구매 또는 둘러보기가 반복되며, 식사는 중간에 여러 번 등장한다. 의류 작업 및 수선은 한 번만 나타나고, 외출 준비와 이동, 포장 작업은 특정 시점에 순차적으로 이어진다. 영상은 식사로 끝난다.

## 실행 횟수

```text
Analysis inference       1
Conclusion inference     1
visual inference         0
STT inference            0
β/v3 regeneration        0
retry                    0
```

두 생성은 `Qwen/Qwen3-VL-8B-Instruct` revision
`0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`, bf16, SDPA, NVIDIA GeForce
RTX 4090의 text-only runtime으로 수행했다.

## 사용자-facing 본문 검증

```text
frozen SHORT_OVERVIEW verbatim       true
frozen DETAILED_OVERVIEW verbatim    true
H01~H09 heading                      0
β/v3 generated narrative section     0
seg# identifier                      0
logical section count                5
Analysis present                     true
Conclusion present                   true
```

Analysis/Conclusion 검사에서 unknown activity, context/intent overclaim, 내부 identifier는
각각 0건이며 두 문서의 final phase는 모두 `식사`다. Conclusion의 activity set은 입력
Overview와 Analysis의 activity set을 벗어나지 않았다.

β/v3 raw/intermediate artifact는 삭제하거나 재생성하지 않았다. 사용자-facing 본문에는
`eligible 36/41`과 다음 5개 quality exclusion code만 남겼다.

```text
EP10 OUTPUT_LANGUAGE_DRIFT
EP21 OUTPUT_LANGUAGE_DRIFT
EP23 OUTPUT_LANGUAGE_CONTRACT_FAILURE + OUTPUT_LANGUAGE_DRIFT
EP28 PARSE_CONTRACT_FAILURE
EP30 PARSE_CONTRACT_FAILURE
```

## HWPX

기존 `scripts/v2_1_hwpx_owpml.py` renderer를 변경하지 않고 최종 Markdown을 다시
렌더했다.

```text
generated               true
package structural errors 0
semantic text match     true
Markdown nonempty lines 23
HWPX semantic lines     23
GUI layout              GUI_LAYOUT_UNVERIFIED
```

## 보호·해시

서버 실행 전후 보호 검사는 모두 통과했다.

```text
Overview                 1580a4204b9157ebd6fece4532d2b8ad18e1ee9cc0b7c58b1dab05659d6aba88
Canonical flow           f1bb720e48b602030143eebd43a200098cc24a125176116e1ff7587295c2858f
Timeline                 ba43a395c26342b6e028b32e33db629c82bf08c3d74785e211c7b04fb5537937
Timeline lineage         23d9734363c5f98c507bce4b4c76ae913f9359d091d22204ebfa5261fb758e8e
β/v3 tree (server)       63f7e620654376344cf7853023755512d0eeaa6384e22f4303eb36fc9fb5bf3a
M3 STT                   aa008317023c884a206c2ea8ce9f1de5db809c2638fca257f964a58df4799c92
```

서버의 β/v3 tree hash는 실행 전후 동일하다. 로컬 미러와 서버 원본을 파일별로 다시
대조한 결과 505/505개 경로와 내용 해시가 모두 일치했다. 로컬과 Linux 서버에서 계산한
aggregate tree hash가 다른 것은 `pathlib.Path`의 플랫폼별 정렬 순서 차이이며 파일 내용
차이가 아니다.

```text
final_report.md          9d4d901760d37c9e9b9c03e304739c2f3f81a082092bfadf198f0506cf357095
final_report.hwpx        9783487b7c91e0257d6505b753d8f0cd2bcfac48a1577501236ef638030708c1
analysis_raw.txt         f4f4fa698a0696fa3b28029f1e0524ed578ef6628ef4345022f47cbeb8ef5dda
conclusion_raw.txt       1ba185fd93fbccbc13ba051e58a96bdc355be467378b16803c357fe3378b4350
```

관련 로컬 테스트는 `34 passed`다. 공식 test는 `UNTOUCHED`, M9는
`NOT_INVOKED`로 유지했다.

## 실제 최종 보고서 본문

```markdown
# 영상 전체 보고서

## 개요

음식 준비 및 조리와 구매 또는 둘러보기가 먼저 이어진다.  
다시 음식 준비 및 조리가 나타나며 식사가 추가된다.  
식사 후 구매 또는 둘러보기가 다시 나타나고, 이동과 외출 준비, 포장 작업, 의류 작업 및 수선 등이 순차적으로 이어진다.  
영상은 식사로 끝난다.

## 상세 개요

음식 준비 및 조리와 구매 또는 둘러보기가 먼저 이어진다. 이후 음식 준비 및 조리가 다시 나타나며, 식사가 추가된다. 식사가 끝나면 다시 구매 또는 둘러보기가 나타나고, 이동과 외출 준비, 포장 작업, 의류 작업 및 수선 등이 순차적으로 이어진다. 영상은 식사로 끝난다.

## 분석

음식 준비 및 조리와 구매 또는 둘러보기가 반복적으로 나타나며, 식사가 여러 차례 중간에 배치된다. 의류 작업 및 수선은 한 번만 등장하고, 외출 준비와 이동, 포장 작업은 특정 시점에서 순차적으로 연결된다. 영상은 식사로 종료된다.

## 결론

음식 준비 및 조리와 구매 또는 둘러보기가 반복되며, 식사는 중간에 여러 번 등장한다. 의류 작업 및 수선은 한 번만 나타나고, 외출 준비와 이동, 포장 작업은 특정 시점에 순차적으로 이어진다. 영상은 식사로 끝난다.

## 근거 및 생성 정보

- 원본 길이: 2424.186485초
- 관찰 범위: [0, 2424.0)초
- 시각 모델: Qwen/Qwen3-VL-8B-Instruct · revision 0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
- 관찰 설정: 48초 window · 24초 stride · 0.5fps
- 정규화 timeline/lineage: 96개 entry · 중복 제거 후 연속 범위
- M3 STT: auxiliary evidence로만 사용 · 새 STT 없음
- β/v3 processing: eligible 36/41
- quality exclusions 5건: EP10 OUTPUT_LANGUAGE_DRIFT · EP21 OUTPUT_LANGUAGE_DRIFT · EP23 OUTPUT_LANGUAGE_CONTRACT_FAILURE + OUTPUT_LANGUAGE_DRIFT · EP28 PARSE_CONTRACT_FAILURE · EP30 PARSE_CONTRACT_FAILURE
- terminal remainder: 0.186485초
- 알려진 한계: 일부 구간의 STT·생성 품질 문제로 제외가 발생했으며, 제외된 자연어 요약과 β/v3 episode별 생성문은 사용자 본문에 포함하지 않았다.
```

## 산출물

```text
runs/wvr_whole_video_report_v2/final_report.md
runs/wvr_whole_video_report_v2/final_report.hwpx
runs/wvr_whole_video_report_v2/analysis_prompt.txt
runs/wvr_whole_video_report_v2/analysis_raw.txt
runs/wvr_whole_video_report_v2/conclusion_prompt.txt
runs/wvr_whole_video_report_v2/conclusion_raw.txt
runs/wvr_whole_video_report_v2/execution_record.json
runs/wvr_whole_video_report_v2/result.json
```

```text
WVR_WHOLE_VIDEO_REPORT_V2
EXECUTED / REVIEW_PENDING
```
