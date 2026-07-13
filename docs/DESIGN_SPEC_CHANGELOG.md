# DESIGN_SPEC 연대기 (변천 기록)

DESIGN_SPEC.md 본문은 **확정 근거**만 담고, 이 파일은 각 결정에 도달한 **날짜별 경과**(문제 발견 → 1차 처방 → 재개정)를 담는다. 확정 최종치는 DESIGN_SPEC §8-0 스냅샷 표를, 결정의 근거는 §8-1~8-7을 본다. 여기 수치는 전부 본문·프로브·results JSON에 근거하며 새 주장을 만들지 않는다(재구성).

## 2026-07-07 — v1

- 모듈별 상세설계서 최초 작성.

## 2026-07-09 — v1.1 정합성 감사

- 정합성 감사(docs/설계점검_2026-07-09.md) 반영: 3-2 오버랩 자막 귀속 규칙 재기술, 4-2 motion_score를 픽셀 정규화 RMS로 명시, §6 config 동기화, 4-6 derive_gt_seg_idx·4-9 check_judge_config 등재.
- M2 샘플 수집을 순차 디코딩(`sample_segments_sequential`)으로 확정 — 시크 방식과 동등성 실측 검증(2영상, motion/is_static/t_rep 완전 일치).
- M5 `search_with_stats` 등재(정규화 이전 raw 코사인 통계 반환 — abstention 설계 데이터).
- 캡션 프롬프트에 anti-OCR 문구 추가(번인 자막 OCR 전사로 s_cap≈s_sub 되는 문제 부분 완화).
- [예정] 태그 규약 도입.

## 2026-07-10 — dev 확장·α 경과·임베딩 확정

- **dev 3영상 96건으로 확장**(Wilderness/kheritage_grave_excavation/gwaktube_soviet_apartment).
- **α 경과(핵심):** 1차 dev 33건에서는 tiebreak(larger)가 α*를 1.0(=baseline)으로 수렴시킴 → dev 확장(59·81·96건)에서 0.6으로 안정화 → **오염 캡션 21건 선별 재생성 후 α=0.6이 tie_set에서 탈락하며 α*=0.5로 최종 확정**. 상세: docs/평가분석_2026-07-10.md.
- KURE-v1 vs BGE-M3 dev 비교 — KURE-v1이 전 지점(α 양끝 포함) 우세, embed_model=KURE-v1 확정.
- spiderman_trailer(구 test) 장르 부적합으로 전면 제외. 당시 test n=19.
- 오염 캡션 선별 재생성 경로(M3 `--recaption-corrupted`) 구현 — greedy 결정성 때문에 오염 감지 시 샘플링(temp 0.7) 재시도.

## 2026-07-11 — ablation 확정·test 확장·abstention 1차·방어장치

- **static_threshold=0 확정**(ablation_plan 2-4-2): dev 96 스윕에서 치환 off가 유의 우세(mrr +0.035, CI 0 배제). → 정적 치환 폐기.
- seg_len(5초 유지)·caption_prompt(P0 유지) ablation 완료(ablation_plan 1-6, 3-6).
- **test 영상 4개(n=39)로 확장**(panibottle/gemini/yunnamnopo/itsub).
- **abstention 1차 τ=0.48**(raw_sub_max 단독 채널): 오배제 2/96, 무관 감지 13/20. `results/abstention_calibration.json`.
- 오염 감지 휴리스틱 강화: 비한글 `절대 개수 ≥3 OR 비율 >0.2`(비율 단독은 긴 캡션 부분 혼입 누락) + 동일 구 3회 반복 정규식. 전 7영상 1,587세그 오탐 0, 신규 19건 적발.
- **재캡셔닝→재임베딩 누락 방어:** M4가 subtitle+caption SHA256(`text_hash`)을 meta.json에 기록, M5 로드가 대조 — `--force` 없이도 텍스트 변경 자동 감지, 낡은 임베딩 평가 경로를 ValueError로 차단.
- M8/M9 로컬 불가 실측: 7B는 4bit로도 6GB 초과, 3B 하향은 M8이 프롬프트 예시 문장을 전 영상 복사하는 오염으로 기각. M9 judge는 오염 리포트를 groundedness=0으로 정확 판정(negative control 통과).

## 2026-07-13 — 융합 정규화 개정·abstention 채널 개정·8장 소화·정합

- **융합 정규화 minmax → z-score 개정(사용자 승인):** per-query minmax는 극값 하나가 유효 범위를 압축해 dev 96에서 유의 손실(z-score α=0.4가 minmax α=0.5 대비 mrr +0.065, CI [+0.032,+0.103]; 무정규화 raw합조차 +0.045 유의; RRF는 −0.18 유의 열세로 기각). docs/probes/fusion_alternatives_probe.py. 절차: dev 비교 → 승인 → dev α 재탐색(α*=0.5 유지) → **test 재평가(접촉 5회째)**.
- **abstention 채널 개정 sub 단독 → max(sub,cap), τ 0.48 → 0.55**(설계 점검 1): sub 단독은 장면형 구조적 편향(무발화 장면은 자막과 안 붙음)이라 오배제 2건이 장면형·복합형이었음. 캡션 채널 분리력 확인(장면형 유관 cap_max median 0.672 vs 무관 0.535) → max 채널로 오배제 0/96·무관 감지 14/20(양축 개선). 유관 max채널 최솟값 0.558로 τ=0.55 여유 0.008 얇음은 한계 병기. results/abstention_calibration_maxch.json.
- **빈 자막 바닥 효과 실측**(설계 점검 5): KURE는 빈 문자열에 결정적 단일 벡터 반환(데모영상 32% 동일). 무관 질의에서 이 코사인이 raw_sub_max 바닥을 형성 → τ가 embed_model 종속인 또 다른 이유.
- **8-3 캡션 상한·후처리 구현:** (a) max_new_tokens config화(기본 128, 동작 불변), (b)(c) truncate/CJK strip 함수 구현·M3 통합하되 **기본 off**(현행 인덱스·평가 불변). dev 영향 (b)15%·(c)12%·합계 24% — 채택 시 재임베딩+test 재평가라 발표 후 과제.
- **emb_joint 제3 arm 미채택**([예정] 해제): dev 96에서 proposed(α=0.5)와 통계적 구분 불가(쌍체 CI [−0.082,+0.025] 0 포함). 유형 프로파일만 상이(joint가 장면형 우세·자막형 열세). arm 교체는 test 재평가 유발이라 현행 유지. docs/probes/emb_joint_probe.py.
- **IoU 항등성 각주**: test GT가 전부 1~2세그·격자 정렬이라 iou@0.5_r@1 ≡ hit@1(수학적 동일). test 표의 IoU는 독립 지표로 세지 않음. 분별력은 dev 3+세그 6건·seg_len ablation에서만.
- **GT 라벨 예외 1건**: wl_q03(dev)만 gt_seg_idx가 파생값의 초집합(같은 사실 영상 후반 재등장 seg 312 수동 추가). 스키마에 다중 인스턴스 개념 부재라 예외로 보존. test 라벨엔 예외 없음.
- **tie-break 강건성 실측(설계 점검 3 대응):** baseline 장면형 저점(0.17)이 무발화 동일벡터+stable-sort 아티팩트인지 dev 38건 점검 — top-1 distinct 15/17·9/10·9/11, GT 동점블록>1은 4/38. baseline은 질의에 반응 → 자막 신호 부재의 실체로 확정(아티팩트 아님). docs/probes/tiebreak_baseline_probe.py.
- **문서 정합 작업:** 구현가이드(IMPLEMENTATION_GUIDE.md) minmax→z-score·치환 off 개정 반영, 중간발표 덱 평이화(16→10장), docx 2종 v1 스냅샷 배너, DESIGN_SPEC §8-0 스냅샷 표 신설·본 CHANGELOG 분리.
- **최종 헤드라인(test n=39, z-score):** baseline hit@1 0.5641/mrr 0.6489 → proposed(α*=0.5) hit@1 **0.7692**/mrr **0.8286**. 쌍체 부트스트랩 95% CI: mrr [0.058,0.310]·hit@1 [0.077,0.359] 0 배제(유의); hit@5/10은 0 포함(유의 주장 금지). 장면형 0.174→0.718 최대 개선. 영상별 +0.140~0.153 균질.
- **test 접촉 이력:** 튜닝 0회 / 공식 평가 5회 — ① n=19 최초, ② n=39 확장, ③ static_threshold=0 재평가, ④ 세정·재임베딩 재검증(순위 39건 전건 불변), ⑤ z-score 개정 재평가.
