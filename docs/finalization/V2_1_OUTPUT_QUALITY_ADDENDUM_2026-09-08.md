# Decision addendum — report output quality gate (2026-09-08)

측정·결과를 보기 **전에** 상수를 고정한다. 이번 영상 결과를 보고 조정하지 않는다.
조정하려면 별도 사건이다.

```
사건 분류   final-output validation defect correction
            (VAD0 채택 사건과 다르다 — 39→40 non-regression gate와 혼동하지 않는다)
```

## 1. freeze한 상수

```
QUALITY_POLICY_VERSION            output_quality_v1
FOREIGN_SCRIPT_RUN_MIN            8      연속 Han/Kana(+CJK 구두점) codepoint
PRESENTATION_GROUP_WINDOW_SEC     300    presentation-format 상수 (canonical 파생값 아니다)
```

`300`은 **새 presentation-format 상수**다. 60초 canonical window의 배수라서 새 임계값이
아니라고 쓰지 않는다. 이 영상에서 몇 개 group이 나오는지를 보고 바꾸지 않는다.

`8`도 magic number다. named constant · 이 문서 · fixture 셋으로 고정한다.

## 2. 판정 상태와 효력

```
PASS      정상
SUSPECT   diagnostic 있음 · 자동 제외 아님
FAIL      presentation eligibility에서 제외
```

interlock은 `quality.status != FAIL`을 AND한다. **`== PASS`로 좁히지 않는다** —
그러면 diagnostic이 곧 자동 삭제가 되어 Q2/Q3의 계약과 모순된다.

## 3. 규칙

```
Q1 unexpected foreign-script drift    FAIL   OUTPUT_LANGUAGE_DRIFT
   한국어 계약 문서에서 연속 Han/Kana run >= 8 codepoint
   CJK 구두점(，。？！ 등)은 run을 잇는 문자로 센다 — 문장부호로 끊어서 회피되지 않게

Q4 output-language contract failure   FAIL   OUTPUT_LANGUAGE_CONTRACT_FAILURE
   한국어 요약인데 Hangul이 0자
   **비율 임계값을 쓰지 않는다** (ratio 규칙은 새 임계값 선택 사건이므로 만들지 않았다)

Q2 mixed Hangul/Latin token           SUSPECT  OUTPUT_BROKEN_MIXED_SCRIPT
   한 토큰 안에 Hangul과 Latin 문자가 섞임 (예: 카레우don)
   자동 교정·자동 제외 없다 — diagnostic이다

Q3 excessive repetition               SUSPECT  OUTPUT_EXCESSIVE_REPETITION
   요약 안에서 토큰 또는 2-gram이 **바로 이어서** 반복
   횟수 임계값을 쓰지 않는다 (인접 중복만 본다 — threshold-free)
```

Q1은 통과시켜야 하는 것도 같이 고정한다.

```
영어 브랜드명 · MBTI · URL · 짧은 loanword · 한두 자 한자 표현   PASS
   Q1은 Latin을 세지 않고, 짧은 Han run은 기준 미달이다
```

Q2·Q3를 자동 제외 규칙으로 승격하는 것은 **별도 사건**이다.

## 4. quality 실패 시 하지 않는 것

```
LLM 재시도 · 다른 모델 fallback · 자동 번역 · 임의 보정 · raw output 수정
```

하는 것은 하나다 — presentation eligibility에서 빼고 사유를 적는다. canonical
episode 41개와 raw model output은 그대로 남는다.

## 5. presentation grouping

```
presentation_group_window_sec = 300
anchor                        = canonical video start (0초)
assignment                    = episode.start_sec가 속한 300초 bin
canonical episode split       금지
새 내용 기반 boundary/provider  만들지 않는다
```

기존 `build_highlights()`의 multi-episode 의미론을 그대로 쓴다.

## 6. 이번 사건에서 바꾸지 않는 것

```
src/v2_1_sanitation.py        frozen production semantics
canonical 41 episode · fixed-window partition
raw STT (수정·삭제·정렬 금지)
B1 확정 인덱스
repository default contract    episode_content_v2
VAD0 default                   OFF
VAD threshold                  tuning 금지
LLM 재실행                      금지 (S5 확정 정본을 provenance로 사용)
기존 제출본                     FROZEN · rollback
```

## 7. 표현·주장

```
허용   known malformed output을 정상 content로 세지 않는 정책 교정이다
금지   semantic correctness가 검증됐다 · ASR 정확도가 개선됐다
       STT 환각이 해결됐다 · 보고서가 더 사실적이다
```

`presentation eligible 40 → 39`는 성능 퇴행이 아니고, VAD0 paired gate와 다른 사건이다.

## 8. frozen acceptance와 충돌해 보류한 항목

아래 둘은 Gate C acceptance 매트릭스에 잠긴 테스트를 바꿔야 하므로 **이 사건에서
실행하지 않는다**. 별도 승인 사건으로 남긴다.

```
개요 압축 (group 대표문)   GLS-001 이 "모든 eligible episode summary가 개요에 있다"를 요구
                          (tests/test_v2_1_synthesis.py::test_gls_001_… · C-04)
핵심 내용 분석 섹션 제거     SECTION_NAMES 5절 고정 + 한글 E2E가 5절 존재를 요구
                          (tests/test_v2_1_presentation.py:264 · tests/test_v2_1_hwpx_via_hangul.py:120)
```

대신 이번에 하는 것은 **중복 축소**다 — 핵심 내용 분석에서 요약 문장을 다시 인쇄하지
않고 group·lineage만 적는다. GLS-002(highlight 구조)는 그대로 만족한다.
