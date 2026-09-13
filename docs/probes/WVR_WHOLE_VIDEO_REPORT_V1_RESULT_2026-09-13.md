# WVR_WHOLE_VIDEO_REPORT_V1 — 실행 결과 (2026-09-13)

상태: `EXECUTED / REVIEW_PENDING`. 최종 report quality PASS/HOLD는 reviewer가 결정한다.

## ANALYSIS — 생성 원문

음식 준비 및 조리와 구매 또는 둘러보기가 처음으로 나타나며, 이후 음식 준비 및 조리가 반복적으로 이어진다. 식사가 추가되며, 이는 이후 여러 번 반복된다. 구매 또는 둘러보기가 여러 번 등장하며, 이동과 외출 준비, 포장 작업, 의류 작업 및 수선 등이 그 사이에 삽입된다. 영상은 식사로 끝난다.

## CONCLUSION — 생성 원문

음식 준비 및 조리와 구매 또는 둘러보기가 먼저 이어진다.  
음식 준비 및 조리가 다시 나타나며 식사가 추가된다.  
식사 후 구매 또는 둘러보기가 다시 나타나고, 이동과 외출 준비, 포장 작업, 의류 작업 및 수선 등이 순차적으로 이어진다.  
영상은 식사로 끝난다.

## β/v3

| 항목 | 관측값 |
|---|---:|
| canonical episodes | 41 |
| presentation eligible | 36 |
| presentation excluded | 5 |
| dialogue grounding excluded | 0 |
| β/v3 LLM calls | 41 |
| prompt refusals / LLM failures / retries | 0 / 0 / 0 |
| summary mode | MODEL_ABSTRACTIVE 38 · SPARSE_EVIDENCE_DETERMINISTIC 3 |

엔진의 기본 5개 보고서 절(개요 · 주요 사건 및 내용 · 핵심 내용 분석 · 결론 · 근거 및 생성 정보)은 모두 존재한다. 품질 제외는 EP10/EP21 `OUTPUT_LANGUAGE_DRIFT`, EP23 `OUTPUT_LANGUAGE_CONTRACT_FAILURE + OUTPUT_LANGUAGE_DRIFT`, EP28/EP30 `PARSE_CONTRACT_FAILURE`다. 9개 보조 highlight 중 H02·H05·H06에 제외 사유가 표시됐다. β/v3가 자체 만든 개요·분석·결론은 최종 본문에 사용하지 않았고, 적격 구간의 `주요 사건 및 내용` 절만 보조 자료로 연결했다.

## HWPX

최종 HWPX 생성: true. 패키지 구조 검증 오류: 0. 물리 section 1개, 논리 본문 절 6개(개요 · 상세 개요 · 분석 · 결론 · β/v3 보조 구간 요약 · 근거 및 생성 정보). HWPX semantic text와 최종 Markdown 비어 있지 않은 줄의 순서·내용이 일치했다. 한글 GUI에서의 실제 열림·레이아웃은 검증하지 않았다.

## 실행·동결

```
Analysis inference      1  Qwen/Qwen3-VL-8B-Instruct · text-only
Conclusion inference    1  Qwen/Qwen3-VL-8B-Instruct · text-only
β/v3 engine execution   1  Qwen/Qwen2.5-7B-Instruct · contract v3
visual inference        0
STT inference           0
retry                   0
```

Qwen3-VL revision `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`, bf16 · SDPA · RTX 4090. 동결 Overview branch 4개 정규화 해시가 생성 전후 동일했다. Analysis/Conclusion machine check 10개 모두 통과했다. 이는 보고서 품질 판정이 아니다.

생성 전 gate: R1~R10 PASS, 101개 24초 입력, 2424초 연속 커버리지, 중복/빈틈 0, 기존 M3 STT 재집계, caption 101/101 · subtitle 98/101. 서버에서 M3 원본 파일은 없었고 원본 STT 전송은 자동 보안 검토에서 차단됐다. 따라서 서버는 이미 gate PASS로 커밋된 adapter `segments.json`만 소비했다. 새 STT는 없었다.

최초 서버 호출은 모델 추론 전에 Windows CRLF/Linux LF의 `overview_result.json` byte SHA 불일치로 중단됐다. 생성 0회 상태에서 §12 erratum을 별도 커밋하고 CRLF→LF만 정규화한 해시 gate를 재실행한 뒤 최초 inference를 수행했다. 기존 raw를 재시도하거나 수정하지 않았다.

## 보존 위치·해시

```
runs/wvr_whole_video_report_v1/final_report.md
  SHA256 e7613fe68dbd4360e0de8fc399df8cfc9ddcada300419cfe199e40d71dd2dca8
runs/wvr_whole_video_report_v1/final_report.hwpx
  SHA256 83b8b90006aa2e8026c78fe51cb19aa3928f6aa8ef53d13bb63510e7e0498b17
runs/wvr_whole_video_report_v1/analysis_raw.txt
  SHA256 6a8329f0d41593aee497761564b82cf260306fdc5851177d4804db3f3f7b4110
runs/wvr_whole_video_report_v1/conclusion_raw.txt
  SHA256 79d195ec9ae73e077b730aaf8cd4afc33c75eabf25badff9846841cf84a46835
runs/wvr_whole_video_report_v1/result.json
  SHA256 33bb43307e1280e0daa07fdb6c9b65c2bf095f6660be3932816f69278571b59f
```

실행 코드 HEAD `7df48f953aecf5bfb584c591f7486287cfabe1ff`. 엔진 source와 frozen Overview 문장은 수정하지 않았다. 로컬 관련 테스트 29개 통과. 공식 test와 M9는 열지 않았다.

## 실제 최종 보고서 본문

최종 본문은 [`final_report.md`](../../runs/wvr_whole_video_report_v1/final_report.md)에 원문 그대로 보존했다. 최종 HWPX는 같은 폴더의 `final_report.hwpx`다. 특히 β/v3 보조 구간은 개별 구간 요약에 명백한 노이즈·추정·언어 혼합이 남아 있으므로, machine eligibility를 최종 보고서 내용 품질 승인으로 해석하지 않는다. reviewer가 그 보조 구간의 포함 적절성까지 판정해야 한다.

```
WVR_WHOLE_VIDEO_REPORT_V1
EXECUTED / REVIEW_PENDING
```
