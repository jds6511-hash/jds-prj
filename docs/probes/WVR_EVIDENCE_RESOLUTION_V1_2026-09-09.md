# WVR_SAMPLING_SEMANTIC_DENSITY_EVIDENCE_RESOLUTION_V1 결과 (2026-09-09)

사전등록: `docs/preregistration/WVR_EVIDENCE_RESOLUTION_V1_2026-09-09.md`
(commit `8c90cdf` freeze · 실행 전 errata 2건 `b921385`·`0a2bce8`)
실행 commit `0a2bce8` · GPU 미사용 · 새 추론 0회

```
사건 판정   BRANCH_C_EVIDENCE_INCONCLUSIVE
근거        REFERENCE_ONLY 3 · ARM_ONLY 10 · BOTH_SUPPORTED 0 · NEITHER_RESOLVED 37
            양방향이 함께 나왔으므로 사전등록 §9에 따라 A도 B도 아니다
리뷰어 지목 9행   8행 NEITHER_RESOLVED · 1행 ARM_ONLY (D1 470–480)
```

**결정적 충돌은 이 evidence 층으로 갈리지 않았다.** 리뷰어가 지목한 D1 `420–450 sewing`
과 D2 `104–112 potato ricer`를 포함해 8/9가 미해결이다.

normative source는 `runs/wvr_light_v1/evidence_resolution_v1.json`이다.

## 1. 입력 동일성 (해시 검증 통과)

```
영상        full_xekZO4n4QuE.mp4     sha ea0e9f48…  (V2 probe와 같은 파일)
evidence    segments.json            sha aa008317…  485구간 · 5초
            == submission_manifest_quality.json input.segments_sha256
canonical   runs/vad0_paired/s1_shadow/S5/aar_canonical.json
            채택 제출본 source_run · 41 episode · fixed_window_v1 60초
V2 출력     density_v2_D{1,2,3}_S{0,1}.json  6건 전부 arm_validity.valid true
```

`torch`·`transformers`는 import되지 않았다(WVR-E22). V2 산출물 6건·요약 1건은
바이트 단위로 무변경이다.

## 2. 충돌 후보 — 결정적 selector가 뽑은 것

```
pair  tol 4.0  tol 8.0  리뷰어 지목 처리                      최종 대조 행
D1      10       11     4건 전부 EXACT_IN_DETERMINISTIC_SET       10
D2      37       54     2건 EXACT · 1건 EXACT_ADDED ·
                        1건 DECOMPOSED (136–152 → 136–144·144–152)  40
D3       0        0     지목 없음                                  0
```

D2는 `SELECTOR_INCOMPLETE`다 — 지목 4건 중 2건이 결정적 집합에 verbatim으로 없었다
(`128–136`, `136–152`). 두 건 모두 S0·S1이 `balls`·`potato` 토큰을 공유해 이중 disjoint
조건에서 탈락한 것이고, 사전등록 §6-2 규칙대로 합집합에 넣어 대조했다.

**D3는 충돌 후보가 0건이다.** S0·S1이 세 창 중 가장 어휘가 겹치는 창이어서
(`coating potato balls` ↔ `coating potato mixture` 등) 이중 disjoint 쌍이 없었다.
즉 D3는 이 사건에 아무 정보도 주지 않는다.

## 3. claim 단위 판정

```
EVIDENCE_SUPPORTS      13
EVIDENCE_CONTRADICTS   13
EVIDENCE_UNRESOLVED    74
```

```
지지 hit 채널   caption 17건 · subtitle 0건
독립 표면형     17/17 (action·object가 같은 어휘로 맞은 hit은 없었다)
LEXICON_UNCOVERED  0건 — 모든 claim이 사전에 덮여 있었다
```

**subtitle(Whisper) 채널은 단 한 건도 해결하지 못했다.** 이 창들의 자막은 시각
활동과 무관하다(예: 420–450초 `화장실 뀨` · `예방접종 서비스로 시원하게 먹으려구요`).
즉 이 사건에서 **독립 modality는 실질적으로 작동하지 않았고**, 판정은 전부 캡션
채널 — 다른 VLM 출력 — 에 의존했다.

## 4. 리뷰어 지목 9행 상세

```
pair  창        S0(0.5fps) claim              S1(0.25fps) claim                  판정
D1  380–390  eating breaded food          cooking chicken with a torch     NEITHER_RESOLVED
D1  420–450  eating breaded food          sewing pajama pants (machine)    NEITHER_RESOLVED
D1  450–460  eating breaded food          chopping tomato with a knife     NEITHER_RESOLVED
D1  470–480  eating breaded food          cooking tomato and egg in a pan  ARM_ONLY_SUPPORTED
D2  104–112  cooking balls in oven        using potato ricer               NEITHER_RESOLVED
D2  112–120  cooking balls in oven        pouring potato mash into a bowl  NEITHER_RESOLVED
D2  128–136  cooking balls in oven        shaping potato mixture           NEITHER_RESOLVED
D2  136–144  cooking balls in oven        coating potato balls in egg      NEITHER_RESOLVED
D2  144–152  cooking balls in oven        coating potato balls in breadcrumbs NEITHER_RESOLVED
```

해결된 1행:

```
D1 470–480   seg95 caption "젓가락으로 요리를 집어 들고 있으며, 그 요리는 검정색 팬 안에"
             S1 지지 (action 요리·조리 + object 토마토·팬) · S0는 같은 창에서 지지 0
             → ARM_ONLY_SUPPORTED
```

## 5. 판정값을 그대로 읽는 방법 (그리고 읽지 말아야 하는 방법)

`EVIDENCE_CONTRADICTS`는 사전등록 §8-3의 정의 그대로 **"같은 겹침 창에서 경쟁 claim은
어휘적으로 지지됐고 본 claim은 지지 0"**을 뜻한다. 그것은 claim이 거짓이라는 뜻이
아니다. 5초 캡션이 그 활동을 언급하지 않는 것만으로도 이 값이 나온다.

또한 지지 판정이 붙은 13건도 캡션의 어휘 일치이며, 캡션 자체가
**Qwen2.5-VL-3B-4bit 출력**이다. 이번 창의 캡션에는 명백한 생성 오류가 섞여 있다
(`스터치머신` · `셀프리스` · `라디에이터 스푼` · `노란색 요리용품`). 따라서
**어느 arm이 사실이었는지는 이 사건으로 결정되지 않는다.**

## 6. 판정에 쓰지 않은 관측 — partial 일치 비대칭

사전등록은 한 차원만 맞은 경우를 `partial`로 기록하고 지지로 세지 않는다(§8-2).
기록된 값은 이렇다.

```
리뷰어 지목 9행    S0 partial 18건 · S1 partial 12건
전체 50행          S0 partial 76건 · S1 partial 85건
```

가장 논쟁적인 D1 `420–450` 창의 partial은 방향이 갈린다.

```
S0  1건  action `먹`만 (object 미일치)
S1  3건  object `기계`·`잠옷`만 (action 미일치)
캡션  420–425 "오렌지색과 분홍색 줄무늬가 있는 옷을 들고 있다"
      430–435 "기계 위에서 주황색 의상이 가까워져 있는 모습"
      435–440 "여성의 손이 노란색 카디건을 …  배경에는 수제 기계"
      440–445 "파란 체크 무늬 잠옷 … 앞에는 노란색 스터치머신"
```

즉 이 창의 캡션은 **옷·기계에 관한 서술이고 식사 서술이 아니다.** 그러나 캡션이
재봉 동작을 명시하지 않았기 때문에 사전등록 규칙에서는 양쪽 모두 미지지가 된다.

**이 비대칭을 판정으로 승격하지 않는다.** 결과를 본 뒤 규칙을 느슨하게 해서
`ARM_ONLY_SUPPORTED`를 만드는 것은 사후 임계값 도입이다. 이 절은 리뷰어의 다음
설계 판단을 위한 관측으로만 남긴다.

## 7. 이 사건이 답한 것과 답하지 못한 것

답한 것:

```
채택 제출본의 canonical evidence 층은 V2의 report-material 충돌을 가르지 못한다
  — 지목 9행 중 8행 미해결, 전체 50행 중 37행 미해결
subtitle(독립 modality)은 이 창들에서 판정력이 0이다
D3 창은 이중 disjoint 충돌이 없어 이 질문에 기여하지 않는다
분기 계산 결과는 양방향 혼재(3 대 10)이므로 A·B 중 하나로 정리되지 않는다
```

답하지 못한 것:

```
어느 arm의 서술이 사실인가            evidence 층에 그 판별력이 없다
0.25fps의 semantic sufficiency        여전히 NOT ESTABLISHED (주장 금지 플래그 유지)
representation collapse 가설           지지도 기각도 되지 않았다 (분기 A 조건 미충족)
```

## 8. 상태

```
WVR_EVIDENCE_RESOLUTION_V1        CLOSED / BRANCH_C_EVIDENCE_INCONCLUSIVE
density V2                        CLOSED / PAIRED_OUTPUT_STABILITY_HOLD (불변)
0.25fps semantic sufficiency       NOT ESTABLISHED       0.5fps factual authority  NO
WVR event extraction              HOLD
현행 제출본                         READ-ONLY / NO PROMOTION
official test  UNOPENED     M9  HOLD
```

분기 C의 다음 단계는 사전등록에 적힌 대로 **리뷰어가 짧은 동일-window paired probe를
새로 설계하는 것**이다. 이 사건은 그 설계를 하지 않는다. 프레임 실물 열람으로 판정을
격상하는 것도 별도 승인 사건이다(사전등록 §10).

## 9. 산출물

```
runs/wvr_light_v1/evidence_resolution_v1.json      50행 판정 · 인용 원문 · 합계 · 분기
src/wvr_evidence_v1.py · src/wvr_evidence_lexicon.py (사전 sha 450f5dac…)
scripts/wvr_evidence_resolve.py
tests/test_wvr_evidence_v1.py                      WVR-E01~E32
뮤테이션 M1~M22 전부 RED (scratchpad ev_mutate.py · git 미추적)
```
