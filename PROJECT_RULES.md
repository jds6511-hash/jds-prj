# PROJECT_RULES.md — 코딩 중 상시 참조용 요약

> 프로젝트: 멀티모달 LLM 기반 영상 장면 검색 및 AAR 보고서 자동 생성 시스템
> (제1부: 자막 vs 자막+장면 결합 검색 비교 / 제2부: [seg#N] 근거 인용 AAR 리포트 생성)

> 근거·상세는 IMPLEMENTATION_GUIDE.md(v2), 스키마·시그니처는 DESIGN_SPEC.md 참조.
> 이 파일은 "코딩하다 헷갈릴 때 3초 안에 확인"하는 용도의 압축본이다.

## 절대 규칙 (어기면 실험 무효)

1. **검색 연산 순서 고정** — `s_sub·s_cap 코사인 계산 → 각각 per-query min-max 정규화(단일 영상 범위) → 정적 세그먼트 s_cap_norm[i] = s_sub_norm[i] 치환 → α 가중합`. 순서 변경 금지. (v2 8-2, 8-4)
2. **정규화 범위 = 해당 단일 영상의 세그먼트 배열.** 영상 경계 넘는 minmax 금지. (v2 8-2)
3. **α grid search는 dev셋에서만.** test로 α를 고르는 코드 경로 자체를 만들지 않는다. 동률 시 α 큰 값(자막 우선). (v2 9-1)
4. **baseline = search(α=1.0).** 별도 함수/경로 금지 — 정규화·치환 인프라 동일해야 비교 대칭. (v2 8-4)
5. **자막·캡션·질의는 같은 임베딩 모델.** model_name은 config 한 곳에서만. (v2 7-8)
6. **주지표 = 세그먼트 인덱스 Hit/Recall@k + MRR.** IoU@0.5/0.3은 보조로만 병기. (v2 8-3)
7. **dev/test는 video_id 단위 분리.** 같은 영상의 질의가 갈라지면 누수 → 로드 시 assert. (v2 5-1)
8. **클라우드 API 금지** (OpenAI 임베딩, Clova 등). 전부 온프레미스.
9. **VLM은 캡션 생성기로만 (frozen).** 검색·랭킹에 VLM 직접 투입 금지. (v2 7-2)
10. **AAR judge:** report_model과 다른 패밀리 1순위. 동일 모델은 `same_model_judge: true` 명시 + 사람 스팟체크 20문장 자동 추출. judge 프롬프트에 "확신 없으면 ungrounded(보수 판정)" 명시. (v2 17-4, 17-6)

## 고정값 (config.yaml과 일치해야 함)

| 항목 | 값 | 비고 |
|---|---|---|
| 세그먼트 길이 | 5초 고정, start=idx*5 (정수 초 내림) | end=min(start+5, dur) |
| 프레임 샘플링 | 3 fps | 대표 프레임 선택용 |
| STT | Whisper large-v3 | 부족 시 turbo |
| 캡션 VLM | Qwen2.5-VL-7B-Instruct | 메모리 부족 시 3B |
| 임베딩 | KURE-v1 (BGE-M3 dev 비교 완료 2026-07-10, 전 지점 우세로 확정) | 장면형 질의 분리 검증 (v2 8-5) |
| α grid | 0.0~1.0, step 0.1 | 선택 기준 mrr (쌍체 부트스트랩 CI tie_set, DESIGN_SPEC 8-1) |
| 평가 k | 1, 5, 10 | |
| 출력 형식 | 정수 초 `[[시작,끝],...]` | Chrono 근거 (v2 6장) |
| 캡션 언어 | 한국어 (질의 언어와 일치) | |
| AAR chunk | 60 세그먼트/청크, 초과 시 map-reduce | reduce는 "새 사실 추가 금지" |

## 엣지 케이스 처방

- **정적 세그먼트** (motion_score < threshold): 대표 프레임 = 중간 프레임 fallback, `is_static=true` 기록. **캡션은 생성하되** 검색 시 점수만 치환 — 캡션 버리기 금지. (v2 8-4)
- **minmax에서 max==min**: 0 벡터 반환 (균등 처리).
- **경계 걸친 발화**: 더 많이 걸친 세그먼트에 귀속 + 경계 문장은 양쪽 중복 허용. (v2 8-1)
- **무발화 세그먼트**: subtitle="" 그대로 임베딩. 특별 처리 금지 (대칭성).
- **AAR 문장에 [seg#N] 인용 없음**: 저장은 하되 자동 ungrounded. 검열 금지, raw_output 보존. (v2 15-1)
- **gt_seg_idx 산출**: 정답 구간과 1초 이상 겹치는 모든 세그먼트, 최소 1개(최대 겹침) 보장.

## 모듈 실행 순서

```
M1 전처리 → M2 대표프레임 → M3 자막·캡션 → M4 임베딩
                                └→ M5 검색 → M6 평가(dev α → test) / M7 데모
M3 산출 → M8 AAR 생성 → M9 AAR 평가
```

각 모듈: `python src/mN_*.py --config config.yaml --video-id {id}` / 입력 스키마 위반 시 fail-fast + "run mX first" 안내.

## 검증 체크리스트 (모듈 완료 기준 발췌)

- [ ] M1: n_segments == ceil(duration/5), 마지막 end == duration(±0.5s)
- [ ] M2: 전 세그먼트 rep_frame 존재, is_static 비율 로그 (>50%면 threshold 경고)
- [ ] M3: caption 빈 문자열 0건 (실패 시 1회 재시도 후 목록 출력)
- [ ] M4: npy row == n_segments, L2 norm 편차 < 1e-4, meta.json에 모델명·차원 기록
- [ ] M6: dev/test video_id 교집합 없음 assert 통과
- [ ] M9: cites 인덱스 범위 [0, n_segments) assert 통과
