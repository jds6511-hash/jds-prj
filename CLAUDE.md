# 프로젝트 규율 (한국어 영상 모먼트 검색 파이프라인)

어떤 모델·세션이든 이 프로젝트에서 작업할 때 반드시 지킬 규칙. 위반은 연구 타당성을 깨뜨린다.

## 절대 규칙 (방법론)

1. **test 재평가 금지.** test 39건은 확정 config로 공식 평가가 끝났다(접촉 이력: 튜닝 0회,
   확정 절차 재평가 4회 — DESIGN_SPEC 8-6). 확정 config가 바뀌는 예외 상황에만, dev 절차
   완료 후 사용자 승인을 받아 재평가한다. 모든 튜닝·ablation·실험은 dev 전용.
2. **캡션 수동 편집 금지.** 캡션 수정은 `common.is_corrupted_caption` 자동 판정분만
   `m3 --recaption-corrupted`로 재생성(leakage 방지). 내용을 보고 고르거나 고치면 안 된다.
3. **라벨 작성 시 검색 결과 참조 금지.** GT는 프레임 실물 검증으로만(캡션 불신).
   test 라벨은 병합 전 유형별 목표 사전 등록. gt_seg_idx는 gt_start/end 파생 규칙 준수
   (유일한 예외 wl_q03은 8-6에 문서화됨 — 새 예외를 만들지 마라).
4. **변형 실험 격리.** config 사본에 paths.work/results 동시 분리, 항상 config.yaml에서
   재생성(scratchpad의 gen_ablation_configs.py 패턴). 본 config·본 인덱스를 실험으로
   오염시키지 않는다.
5. **α는 config에 없다** — CLI 주입(`--alpha`), 확정값은 results/alpha_search_dev.json의
   alpha_star. static_threshold=0(치환 off)·abstention max(sub,cap) τ=0.55는 실측 확정,
   근거 없이 되돌리지 마라.

## 실무 규칙

- **재캡셔닝 후 m4 실행 필수.** text_hash가 자동 감지·차단하지만(M5 ValueError), m4를
  돌려야 갱신된다. `--force` 불필요(해시가 변경 감지).
- **GPU 배치**: bash 스크립트 + run_in_background. 콘솔 수치는 cp949로 깨지므로
  **최종 수치는 항상 UTF-8 JSON 파일에서 확인**한다. 완료 후 검증 절차는
  `.claude/skills/pipeline-verify` 참조.
- **M8/M9는 로컬 실행 불가**(7B가 6GB 초과 실측, 3B는 예시 복사 오염으로 기각).
  서버 GPU 확보 전에는 실행 시도하지 마라. 격리된 오염 산출물을 되살리지 마라.
- **완료 주장 전 검증**: 테스트 전체 실행(`python3 -m pytest tests/ -q`) + 해당되면
  브라우저 E2E(`scripts/m7_browser_e2e.py`). 증거 없는 "될 것이다" 금지.
- 코드 변경은 TDD(실패 테스트 먼저), 커밋 전 전체 테스트 통과 확인.

## 재시작 시

`docs/작업현황_<최신날짜>.md`부터 읽는다. 확정 수치·다음 할 일·주의사항이 거기 있다.
발표 예상질문 대응은 `docs/presentation/예상질문_방어.md`.
