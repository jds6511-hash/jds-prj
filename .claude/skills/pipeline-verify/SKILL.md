---
name: pipeline-verify
description: GPU 배치(재캡셔닝·재임베딩·평가) 완료 후 산출물을 검증하는 확정 체크리스트. 배치가 끝났을 때, 또는 "결과 검증해" 요청 시 사용.
---

# 파이프라인 배치 검증 체크리스트

배치 exit 0은 성공 증거가 아니다. 아래를 순서대로 실측하고, 전부 통과해야 "검증 완료"를 선언한다.

## 체크리스트 (해당 항목만)

1. **Phase 타임스탬프**: 배치 로그에서 `grep "==="`로 각 단계 시작/완료 확인. 로그의
   한글은 cp949로 깨질 수 있다 — **수치는 절대 로그에서 읽지 말고 UTF-8 JSON에서 읽는다.**
2. **오염 잔존 스캔** (재캡셔닝 후): 전 대상 영상 segments.json에 `common.is_corrupted_caption`
   전수 적용. 본 인덱스는 잔존 0이어야 정상. 잔존이 있으면 재캡셔닝 대상 목록(로그의
   "오염 캡션 N건 재생성 대상")에 있었는지 확인 — 있었다면 "재시도 실패 시 greedy 유지"
   규약에 따른 정상 동작(문서화), 없었다면 감지 휴리스틱 버그.
3. **text_hash 대조** (재임베딩 후): 각 영상 meta.json의 text_hash ==
   `common.index_text_hash(segments.json doc)`. 불일치면 m4 미실행 — 낡은 임베딩.
4. **emb shape**: emb_sub/emb_cap == (n_segments, 1024) × 2.
5. **평가 결과 전후 비교** (M6 실행 시): eval_test.json의 per_query 순위를 직전 결과와
   전건 대조. 변화가 있으면 어떤 질의가 왜 움직였는지 규명 후 보고(무단 "개선됐다" 금지).
   dev는 alpha_star·tie_set·per_alpha 곡선 비교.
6. **provenance 필드**: 결과 JSON에 static_threshold·recompute_gt_seg_idx 등이
   실효값으로 기록됐는지 확인(config 기본값 아닌 실제 사용값).

## 검증 후

- 결론이 바뀌는 수치면 docs(DESIGN_SPEC 8-6, ablation_plan) 갱신 + 커밋.
- 작업현황 스냅샷(docs/작업현황_*.md)이 낡았으면 갱신.
