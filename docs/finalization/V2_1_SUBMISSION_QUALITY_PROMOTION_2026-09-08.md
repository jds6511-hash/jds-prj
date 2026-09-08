# 제출 arm 승격 — R1-VAD0-QUALITY (2026-09-08 · TRACK A)

근거: `V2_1_QUALITY_CANDIDATE_2026-09-08.md`(결과) ·
`V2_1_OUTPUT_QUALITY_ADDENDUM_2026-09-08.md`(상수 freeze)
직전 arm: `V2_1_FINAL_STATUS_2026-09-07.md` (rollback)

```
SUBMISSION ARM     R1-VAD0-QUALITY
정책 3층            episode_content_v3_summary_only
                   + STT_VAD0
                   + output_quality_v1
표현 상수           fixed presentation grouping 300초
LLM 재실행          없음 — 기존 S5 content artifact 재사용
```

## 1. 두 artifact

```
NEW  runs/quality_candidate/S7/report.hwpx
     5732075871fd7902d52239cebced28f9489a0f558dac67c61f5d2ca994e9cd7b (10,185 B)
     tag submission-quality-2026-09-08

OLD  runs/vad0_paired/s1_shadow/report.hwpx
     4e10aaaba1d8a6e510c4749efc4a6e1bf5a5dbb5dba963403a84379bcd92ff90
     tag submission-vad0-2026-09-07 — rollback 유지 (삭제·덮어쓰기 금지)

이전  runs/v3_paired/r1_v3/report.hwpx
     f874f643112704120cd3b043c3667b71ffd4f25105ca1fccf345b936d4e4a91d
     tag submission-ready-2026-09-03 — rollback 유지
```

## 2. 승격 시 다시 확인한 것

그 정확한 파일에 대해 실측했다. 모델·LLM은 다시 돌리지 않았다.

```
hwpx sha256 일치       manifest 기재값 == 파일 실측값
A2' 구조 validator     PASS
한글 Open()            True
PDF export             True · 115,382 bytes
본문                   7,907자 · ■5 ┌9 │47 └9
rollback 2건           해시 전건 일치 (변경 0)
```

승격 스크립트는 지문 대조를 먼저 한다 — candidate의 `source_run_fingerprint`가 직전
제출본 `fingerprint`와 다르면 거부한다. `llm_rerun`이 false가 아니어도 거부한다.

## 3. 제출 수치

```
canonical episode        41
presentation eligible    39
quality PASS 38 · SUSPECT 1 · FAIL 2
표현되지 않는 구간        EP13 (OUTPUT_LANGUAGE_DRIFT) · EP17 (PARSE_CONTRACT_FAILURE)
canonical partition hash a52a0bdf00d49972… (원본과 동일)
presentation group       9 (300초 bin)
claim evidence           777 → 567 (STT_VAD0)
```

`39`는 직전 arm의 `40`보다 하나 적다. 이것은 성능 퇴행이 아니라 **known malformed
output을 정상 content로 세지 않는 정책 교정**이다(EP13에 중국어 drift가 노출돼 있었다).

## 4. 채택 범위 밖 (무변경)

```
repository default 계약   episode_content_v2
SHADOW_VAD0_DEFAULT       False
src/v2_1_sanitation.py    무변경
raw STT · B1 확정 인덱스   무변경
canonical 41 episode · fixed-window partition
official test             UNOPENED · M9 HOLD
full 재전사 · B1' · B2 재생성   HOLD
```

## 5. 산출물

```
runs/quality_candidate/submission_manifest_quality.json   제출 manifest 정본
Desktop/v3_submission_quality/                            사본
  report_quality.hwpx · .pdf · .md · report_quality_hwpx_text.txt
  submission_manifest_quality.json · candidate_manifest.json
  stt_{transcript,utterances}_full_xekZO4n4QuE.txt
```

## 6. SUBMISSION_READY

```
SUBMISSION_READY = YES
```

뜻은 좁다 — 실행·렌더링·회수율·출력 언어 계약까지다. 요약의 **의미적 사실성은 독립
검증되지 않았다**. 아래는 계속 주장하지 않는다.

```
STT 환각이 제거됐다 · ASR 정확도가 개선됐다
VAD0가 hallucination detector다
output quality gate가 사실 오류를 걸러낸다   — 걸러낸 것은 출력 언어 계약 위반이다
```
