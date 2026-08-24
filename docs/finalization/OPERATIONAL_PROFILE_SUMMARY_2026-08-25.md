# 운영 프로필 요약 (발표용, 2026-08-25)

**새로 돌리지 않았다.** 동결된 `p3_opcost_v1` 실측을 정리한 것이다
(`docs/probes/_scratch/p3_opcost_full_prelim_no_reserved.json` · `p3_opcost_full.json` ·
판정 `p3_opcost_verdict.json`).

## 측정 조건

```
장치        실제 6GB 배포 노트북 — RTX 3060 Laptop, vram_total 6.0GB
정밀도      양 arm 실효 4bit (quantization_mismatch false)
표본        프레임 40장 · 영상 11편 · seed 20260824로 사전 동결 (경로 해시 정렬, 내용 신호 미사용)
배치        3b → 4b → 3b → 4b 교대, 블록 2개
비저장      캡션 문자열을 남기지 않는다 (길이·토큰 수만)
```

## 배포 모델 (3B) 처리 시간 — 시스템 요구사항의 근거

RTX 3060 Laptop 6GB, 33분 영상 395세그먼트 기준 실측:

```
M1 수 초 · M2 약 25분 · M3 약 75분 (Whisper + 캡션 395회) · M4 약 2분 · M6 약 2분
```

M3가 전체의 대부분이다. 디스크는 검색만 약 12GB(Whisper 2.9 + VLM 7.1 + KURE 2.2),
산출물은 영상 1편당 약 75MB.

## 3B vs 4B 운영 대조 (배포 조건)

| 항목 | 3B/P0 (배포) | 4B/P0 (후보) | 차이 |
|---|---|---|---|
| frame당 wall-clock 중위수 (1차, authoritative) | 8.061s | **5.974s** | 비 0.7411 |
| frame당 wall-clock 중위수 (2차, 재현) | 8.344s | **5.895s** | 비 0.7065 |
| peak allocated VRAM | 2.440GB | 3.043GB | +0.604GB |
| peak reserved VRAM | 2.637GB | 3.068GB | **+0.431GB** |
| 생성 중 최소 free VRAM | 2.338 / 2.420GB | 1.906GB | 약 −0.45GB |
| 모델 저장 | 7.00GB | 8.28GB | **+1.28GB** |
| OOM · 실패 | 0 · 0 | 0 · 0 | 없음 |
| 출력 길이 · 토큰 | 133.6자 · 92.2 | 82.9자 · 59.7 | 토큰 비 0.6475 |
| wall-clock 대비 출력 토큰 rate | 11.05 | 10.13 | 비 0.9165 |

**두 실행에서 출력 길이·토큰이 완전 동일했다**(133.6/92.2, 82.9/59.7) — 통제된 조건에서
캡션 생성은 결정적이라는 결론과 일치한다. timing만 3B +3.5%, 4B −1.3% 움직이고 방향은
불변이었다.

## 판정

> **deployment blocker는 관측되지 않았고, resource-footprint penalty는 관측됐다.**

throughput penalty·OOM은 없지만 VRAM reserved +0.431GB · 생성 headroom 약 −0.45GB ·
저장 +1.28GB라는 비용이 분명히 있다.

## 표현 규칙 (동결)

```
쓴다     "동일 prompt/config에서 4B가 더 짧은 출력을 생성했고, 그 결과 end-to-end
         caption wall-clock이 더 짧게 관측됐다"
         "wall-clock 대비 출력 토큰 rate는 3B가 높게 관측됐다"

쓰지 않는다  "4B가 운영비가 더 싸다"        (전력·금전 비용 미측정)
           "4B가 계산적으로 더 효율적이다"   (출력 길이 차이가 섞여 있다)
           "토큰당 처리속도"               (분모가 전체 caption wall-clock이다 —
                                        decoder token-generation speed가 아니다)
           "4B의 우위는 대부분 출력이 짧기 때문이다"  (generation kernel 속도 미분리)
           "order effect 없음"            (블록 2개)
```

`minimum_generation_free_vram`은 **generation loop 구간만** 샘플링했다. model load 구간의
free VRAM 수치는 없고, 로드 성공 사실만 관측됐다(arm별 3회 × 2블록 전부 성공, OOM 0).

**40장은 통계적 모집단 추정이 아니라** deployment operational feasibility의 descriptive
measurement다.

## 측정하지 않은 것

```
retrieval 성능 · 캡션 품질 · MRR · 전력 소비 · 금전 비용
수천 구간 연속 실행의 장기 안정성 · model load 구간의 free VRAM 수치
```
