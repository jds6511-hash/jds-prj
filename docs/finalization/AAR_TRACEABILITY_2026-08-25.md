# AAR 추적성 — 현재 구조와 경계 (2026-08-25)

목표는 "LLM이 멋진 글을 쓰는 것"이 아니라 **근거가 추적 가능한 리포트**다.

## 구조

```
segments.json  (5초 구간별 subtitle · caption)
      ↓  M8 m8_report — map-reduce, [seg#N] 인용 강제
report.json    sentences[{sent_id, text, cites:[seg_idx…]}] + provenance + raw_output
      ↓  scripts/aar_view.py — LLM 미사용, 읽기 전용
주장 → 인용 구간 → 시각(start~end) → 자막·캡션 근거 → 재생 위치(seek_to)
```

`aar_view`가 문장마다 만드는 것:

```
text        report.json의 서술 그대로 (새 문장을 만들지 않는다)
cites       인용한 구간 인덱스
spans       각 인용의 start~end
time_range  최소 start ~ 최대 end
seek_to     재생 시작 위치
evidence    구간별 자막·캡션 (인덱스에 저장된 실제 값만)
timeline    첫 인용 시각 순 정렬
```

## fail-closed

| 조건 | 처리 |
|---|---|
| 인용이 범위 밖 | `TraceError` — 추적 불가한 주장을 리포트에 남기지 않는다 |
| 인용이 없는 문장 | `TraceError` |
| `video_id` 불일치 | `TraceError` |
| `schema_version` 미지원 | `TraceError` (현재 지원 v2) |
| `report.json` 없음·파싱 실패 | `TraceError` |

M8 생성 단계에도 이미 검증이 4개 있다(`m8_report.save_report`): 인용 범위 · 서술 공백 ·
reduce 퇴화(한 문장이 전체의 89% 인용) · 반복 루프(distinct ratio). **네 결함 모두 과거에
"성공"으로 보고된 적이 있고**, 검사가 전부 수량만 셌기 때문이었다 — 그래서 질적 검사를
하나씩 추가했다(DESIGN_SPEC 8-5(6-a)~(6-f)).

## 실행 경계

```
M8 로컬 실행 불가       report_model = Qwen/Qwen2.5-7B-Instruct, VRAM 20GB 필요.
                     6GB 로컬 불가 실측. 3B 하향은 프롬프트 예시 복사 오염으로 기각
서버 실행             랩실 RTX 4090 24GB, config_server.yaml 사본 사용
aar_view              GPU·LLM 불필요. 이미 있는 report.json만 읽는다
M9                   split=="test" 하드코딩 — **실행 자체가 test 접촉**. 절대 HOLD
```

## M8 연구 경계 (이번 작업에서 하지 않은 것)

M8 exploratory human classification은 HOLD다. 따라서:

```
M8 53건 신규 human review        하지 않았다
기존 M8 PRIMARY 재계산            하지 않았다
6분류를 자동 final labeling으로 승격  하지 않았다
M9·test 결과처럼 표현              하지 않았다
```

`aar_view`의 `cited_fraction`은 **인용된 구간 비율이라는 기술값이고 M9의 coverage 지표가
아니다.** 산출물에 `m9_evaluated: false` · `test_split_used: false`를 명시한다.

## 현재 상태

report.json이 저장소에 없다(원본 영상·파생 텍스트를 공개하지 않는 정책과 같은 이유).
따라서 `aar_view`는 **서버에서 M8을 돌린 뒤** 또는 사용자가 직접 M8을 실행한 뒤에 쓴다.
계약은 테스트 13건으로 고정했다(`tests/test_aar_view.py`).

```
python scripts/aar_view.py --video-id <id> --out-md docs/finalization/AAR_<id>.md
```
