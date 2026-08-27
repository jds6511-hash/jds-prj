# POST-M9 최종 산출물 사양 (2026-08-27 확정)

최종 산출물 구조를 `M8 → M9 → POST-M9 문서화`로 고정한다. 이 문서가 그 계약이다.

```
확정 시점   2026-08-27
선행 조건   M8 판정 → M8 freeze → M9 실행 완료
            **M9 완료 전에는 아래 산출물을 만들지 않는다**
```

관련: [M8_M9_PROTOCOL](M8_M9_PROTOCOL_2026-08-26.md) §7 ·
[M8_M9_DECISIONS](M8_M9_DECISIONS_2026-08-26.md)

---

## 1. canonical source — 이 셋만이 사실이다

```
segments.json      STT · caption의 source of truth
report.json        M8 canonical AAR
m9_result.json     M9 canonical validation result
```

렌더 계층은 이 셋을 **읽기만** 한다. 산출물이 원천과 어긋나면 산출물이 틀린 것이다.

## 2. 최종 산출물 구조

```
work/<video_id>/
├── segments.json                      # 원천 (M1~M3)
├── report.json                        # M8
├── m9_result.json                     # M9
├── <video_id>_stt_transcript.txt      # 전체 STT 전사문   ← M9 완료 후 생성
├── <video_id>_aar_report.hwpx         # 인간 열람용 보고서 ← M9 완료 후 생성
└── final_deliverable_manifest.json    # 해시·provenance   ← M9 완료 후 생성
```

**canonical human-readable deliverable은 `.hwpx`다.** `.hwp`는 기관 제출 규칙이 요구할
때만 검증 완료된 HWPX에서 변환해 덧붙인다(§8).

## 3. `<video_id>_stt_transcript.txt` — deterministic export

```
frozen segments.json  →  deterministic export  →  stt_transcript.txt
```

M9가 새 STT를 만드는 파일이 **아니다.**

```
금지   새 STT 실행 · LLM 교정 · 요약 · 문장 다듬기 · segment 병합·생략
유지   모든 segment. 시간 정렬 보존
형식   [seg#N] HH:MM:SS - HH:MM:SS
       <subtitle>
빈 값   subtitle이 비어 있어도 생략하지 않고 `[전사 없음]`으로 표시
```

예:

```
[seg#0] 00:00:00 - 00:00:05
안녕하세요. 오늘은 …

[seg#1] 00:00:05 - 00:00:10
[전사 없음]

[seg#2] 00:00:10 - 00:00:15
지금 출발 지점에 …
```

`seg_idx` · timestamp · text가 `segments.json`과 **exact하게** 대응해야 한다(§6 V1~V3).

무발화 구간을 지우지 않는 이유는 둘이다 — ① 구간 번호가 인용(`[seg#N]`)의 주소라
비면 주소가 밀린다 ② "말이 없었다"와 "전사에 실패했다"를 뒤에서 구분할 수 있어야 한다.

## 4. HWPX 구성

전체 STT를 본문 뒤에 복제하지 않는다. **AAR에서 실제 인용된 구간의 STT만 부록에 넣고,
전체 전사문은 TXT 별첨**으로 둔다. 수백 페이지 전사문이 보고서를 삼키는 것을 막는다.

```
1  표지
2  분석 대상 및 개요
3  전체 AAR 요약
4  주요 이벤트 타임라인
5  핵심 관찰
6  근거 상세      claim → citation → seg_idx → timestamp → STT → caption
7  M9 검증 결과   coverage · groundedness · verdict · limitations
8  부록 A         AAR에서 **실제 인용된** segment의 STT 전사
9  부록 B         provenance / 생성 정보
```

마지막에 다음을 명시한다.

> 전체 STT 전사문은 `<video_id>_stt_transcript.txt` 별첨

## 5. Post-M9 renderer 규칙 — 새 분석이 0개다

```
report.json ──────┐
segments.json ────┼→ deterministic renderer ├→ transcript.txt
m9_result.json ───┘                          └→ report.hwpx
```

```
금지   새 LLM 호출 · 새 요약 생성 · STT 수정 · claim 수정 · citation 수정
       M9 지표 재계산 · M9 결과 재해석
허용   formatting · export
```

### M9 FAIL을 숨기지 않는다

**M9 COMPLETE와 M9 PASS는 계속 별개다.** FAIL이어도 산출물은 만들 수 있지만, HWPX에
실제 상태를 그대로 적는다.

```
M9 validation status: FAIL
```

FAIL 결과를 "검증 완료된 보고서"처럼 표현하지 않는다. 이것은 M8 쪽의
`evaluation COMPLETE ≠ acceptance PASS` 분리와 같은 원칙이다.

## 6. `final_deliverable_manifest.json`

"이 HWPX와 TXT가 정말 M9를 통과한 그 report/segments에서 나온 것인가"를 나중에 확인하기
위한 파일이다.

```json
{
  "video_id": "...",
  "segments_sha256": "...",
  "report_sha256": "...",
  "m9_result_sha256": "...",
  "transcript_sha256": "...",
  "hwpx_sha256": "...",
  "m8_freeze_id": "...",
  "m9_protocol_id": "...",
  "m9_verdict": "...",
  "generated_at": "..."
}
```

`m8_freeze_id`는 `scripts/m8_freeze.py`가 발급한 동결 manifest의 id다 — 렌더된 보고서가
**어느 동결본에서 나온 M8인지**를 이 값으로 잇는다.

## 7. 자동 검증 (필수) — V1~V8

렌더러가 돌고 나면 반드시 자동으로 확인한다. 하나라도 어긋나면 산출물을 배포하지 않는다.

```
V1  transcript의 모든 seg_idx가 segments.json과 일치
V2  transcript timestamp가 segments.json과 일치
V3  transcript text가 segments.json subtitle과 일치 (빈 값은 [전사 없음])
V4  HWPX의 AAR claim text가 report.json과 일치
V5  HWPX citation이 report.json과 일치
V6  HWPX STT evidence가 segments.json과 일치
V7  HWPX M9 verdict가 m9_result.json과 일치
V8  manifest hash 전건 일치
```

V4~V6은 "렌더러가 조용히 문장을 다듬었는지"를 잡는 검사다. 사람이 읽기 좋게 고치는
행위가 곧 claim 수정이므로 **차이가 나면 실패로 본다.**

## 8. `.hwp`

기관 제출 규칙이 `.hwp`를 반드시 요구할 때만, **검증 완료된 HWPX에서** 변환한다.
변환 과정에서도 내용 생성·수정은 금지다. 변환본은 canonical이 아니라 파생물이다.

## 9. 실행 순서 (흔들지 않는다)

```
M8 판정(C1~C3) → M8 freeze → M9 실행 → m9_result.json 확정
→ transcript.txt · report.hwpx · final_deliverable_manifest.json
```

M9 공식 test 개방은 그 앞 단계에서 **별도 승인 사건**으로 남아 있다.

## 10. 구현 상태

```
사양            확정 (이 문서)
transcript 내보내기  미구현 — M9 완료 후 필요한 시점에 만든다
HWPX 렌더러        미구현
V1~V8 검증기        미구현
```

지금 만들지 않는 이유는 하나다 — 렌더러는 `m9_result.json`의 실제 스키마에 맞춰야 하고,
그 파일은 아직 존재하지 않는다. 없는 입력에 맞춘 렌더러는 M9가 끝나면 다시 쓰게 된다.
