# quality candidate — 최종 출력 결함 교정 결과 (2026-09-08)

사전등록·freeze: `V2_1_OUTPUT_QUALITY_ADDENDUM_2026-09-08.md`
기존 제출본: `V2_1_FINAL_STATUS_2026-09-07.md` (FROZEN · rollback)

```
사건        final-output validation defect correction
LLM 재실행   없음 — S5 확정 정본을 그대로 쓰고 표현 계층만 다시 만들었다
결과        보고서에서 중국어 drift 소멸 · presentation eligible 40 → 39
```

## 1. 무엇을 고쳤나

```
P0  output quality gate          src/v2_1_output_quality.py (신규)
    FAIL-only interlock          summary_eligible_for_presentation()에 AND 1항
P1  300초 presentation grouping   41 episode → 9 group (canonical 무변경)
    핵심 내용 분석 중복 제거        요약 문장 재인쇄 대신 group·lineage만
P2  부재 사유 표시                 "상태: OUTPUT_LANGUAGE_DRIFT" 등 코드로
    결론 문구                     "확인된 구간" → "요약이 제공된 구간"
    전사문 타임스탬프              45.98초가 `…45.10` → `…46.0` (자리올림 버그)
    전사문 헤더                   "자동 생성 STT 원문 — 미검증 · 편집하지 않음"
```

## 2. 판정 결과 (41 episode)

```
quality PASS      38
quality SUSPECT    1     EP02 · OUTPUT_BROKEN_MIXED_SCRIPT ("카레우don") — 제외 아님
quality FAIL       2     EP13 · OUTPUT_LANGUAGE_DRIFT (연속 한자 33자)
                         EP17 · 요약 없음(PARSE_CONTRACT_FAILURE)
presentation eligible   39 / 41
```

`EP17`은 원래도 parse 실패로 빠져 있었다. 이번에 새로 빠진 것은 **EP13 하나**다.
사유는 층 순서대로 하나만 적는다 — EP17은 `PARSE_CONTRACT_FAILURE`로 적힌다.

```
보고서 본문의 한자 줄        3 → 0
"상태:" 사유 줄              0 → 2 (OUTPUT_LANGUAGE_DRIFT · PARSE_CONTRACT_FAILURE)
```

## 3. presentation grouping

```
window 300초 · anchor 0초 · 41 episode → 9 group
H01 EP01–05 · H02 EP06–10 · H03 EP11–15 · H04 EP16–20 · H05 EP21–25
H06 EP26–30 · H07 EP31–35 · H08 EP36–40 · H09 EP41
canonical partition hash   a52a0bdf00d49972… (원본과 동일 — 쪼개지 않았다)
```

group 개수는 목표가 아니라 결과다. 9개가 나왔다고 window를 바꾸지 않았다.

`H03`은 `구성 5구간 · 요약 출처 4구간`으로 적히고, 왜 하나가 빠졌는지는 같은 상자의
`상태: OUTPUT_LANGUAGE_DRIFT`가 말한다.

## 4. 실물 검증 (그 candidate 파일 자체)

```
A2' 구조 validator   PASS
한글 Open()          True
PDF export           True · 115,181 bytes
본문 길이            7,887자 (기존 14,460자 — 중복 절 제거분)
상자 글리프          ■ 5 · ┌ 9 · │ 47 · └ 9
hwpx sha256          8ef856451fa2bf391e51d0824c0eb26457317976b82bd87a8e7a4fc2863e4f2c
```

## 5. 전사문 타임스탬프 audit

```
내부 표현        decimal seconds (t0 · t1)
`17.10` 정체     표기 버그였다 — 정수부를 자른 뒤 소수부만 반올림해 10이 나왔다
start <= end     437발화 전건 충족
0 길이 발화       0건
비단조 1건        1711.20 다음이 1710.50 — **Whisper 출력 자체**의 순서 역전
                 정렬해 숨기지 않는다(진단으로 보존)
수정 범위        표기 함수만. 텍스트 0건 변경 · 스탬프 38건 교정
```

## 6. 원본 무변경

```
runs/vad0_paired/s1_shadow/report.hwpx   4e10aaab… (재확인 · 무변경)
runs/v3_paired/r1_v3/report.hwpx         f874f643… (재확인 · 무변경)
raw STT · B1 확정 인덱스 · canonical 41 episode · fixed-window partition
src/v2_1_sanitation.py · repository default contract · VAD0 default OFF
```

## 7. 이번 사건에서 하지 못한 것 (frozen acceptance 충돌)

```
개요 압축                  GLS-001이 "모든 eligible episode summary가 개요에 있다"를 요구
                          → 개요는 여전히 39문장 이어붙임이다
핵심 내용 분석 섹션 제거     SECTION_NAMES 5절 + 한글 E2E가 5절 존재를 요구
                          → 섹션은 남기고 문장 중복만 제거했다
```

둘 다 Gate C acceptance 매트릭스에 잠긴 테스트를 바꿔야 하므로 **별도 승인 사건**이다.
삼중 반복 중 하나(핵심 내용 분석)는 이번에 해소됐고, 개요는 남아 있다.

## 8. 주장하지 않는 것

```
semantic correctness가 검증됐다        아니다 — 여전히 미검증
STT 환각이 해결됐다                    아니다
ASR word accuracy가 개선됐다           측정하지 않았다
VAD0가 hallucination detector다        아니다
EP13 요약이 틀렸다고 판정했다            판정한 것은 **출력 언어 계약 위반**이다
```

이번에 한 것은 하나다 — **known malformed output을 정상 content로 세지 않는다.**

## 9. 산출물

```
runs/quality_candidate/S6/presentation.json · S7/report.hwpx · S7/report.md
runs/quality_candidate/candidate_manifest.json      provenance 정본
runs/quality_candidate/stt_{transcript,utterances}_full_xekZO4n4QuE.txt
Desktop/v3_submission_quality/                      사본(hwpx·pdf·md·전사문 2종·manifest)
```

제출 arm 교체는 아직 하지 않았다 — 현행 제출본은 `submission-vad0-2026-09-07`이다.
