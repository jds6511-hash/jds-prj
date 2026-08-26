# 재현성·운영 안전장치 요약 (2026-08-25)

핵심 메시지 하나:

> **성능 숫자만 만든 것이 아니라, 잘못된 run·config·artifact가 정상 결과처럼 쓰이는 것을
> 막는 안전장치를 만들었다.**

내부 구현을 전부 설명하지 않는다. 무엇을 막는 장치인지만 적는다.

## 1. 잘못된 조합으로 시작하지 못한다 — preflight

`scripts/demo.py`가 시작 전 12항목을 확인하고, 하나라도 어긋나면 **실행하지 않는다.**

```
배포 identity   caption_model · vlm_4bit · embed_model · seg_len_sec · static_threshold · α=0.5
인덱스          4개 산출물 존재 · segments 불변식 · 임베딩 행 수·차원 일치
정합            meta.json의 text_hash == segments.json 해시   (재캡셔닝 후 m4 미실행 차단)
                인덱스를 만든 embed_model == 현재 config      (점수 비교 불가 차단)
연구 경계        test split 영상은 데모로 돌리지 않는다
경고            mp4 없음 → 재생 불가(검색은 됨) · CUDA 없음 → 느림
```

"일단 실행하고 이상하면 알림"이 아니다. `--check-only`로 시연 전에 미리 찍어 볼 수 있다.

## 2. 낡은 임베딩으로 검색되지 않는다 — text_hash

캡션·자막이 바뀐 뒤 M4를 돌리지 않으면 `common.index_text_hash` 대조에서 걸린다.
M5 로드가 `ValueError`를 던지고, preflight는 그보다 먼저 막는다.

## 3. 캡션을 사람이 골라 고치지 못한다 — 자동 판정만

```
common.is_corrupted_caption   오염 판정. 재생성은 --recaption-corrupted로만
common.is_subtitle_credit     STT 크레딧 환각 제거. 전체 일치로만 판정
```

내용을 보고 고르는 경로를 두지 않는다. 표시 계층 정리(`display_clean`)는 **인덱스·임베딩·
랭킹·평가에 불개입**이다.

## 4. 라벨이 검색 결과를 볼 수 없다 — allowlist

`scripts/label_guard.py`가 `idx`·`start`·`end`·`rep_frame`만 통과시킨다. 같은
`segments.json`에 `caption`·`subtitle`이 들어 있으므로 **관행이 아니라 도구가 막는다.**
라벨 도구는 `m5_search`·`m6_evaluate`를 import조차 하지 않는다.

## 5. 진행 판정을 프로세스 유무로 하지 않는다 — 마커·상태

```
scripts/run_status.py          단계 완료 마커 (STAGE_*_DONE)
scripts/exp_launcher.py        RUN_COMPLETE + validator PASS + plan_hash 불일치 시 REPORT 거부
scripts/canary_coverage.py     plan_schema_version >= 2면 canary 선언 누락 시 fail-closed
                               (기존 4개 계획만 out-of-plan allowlist로 면제)
```

2026-08-17에 `pgrep` 문자열 매칭·즉석 `/tmp` 스크립트로 사고 3건이 났다(GPU 8.5시간 유휴,
배타 플래그 조합, 편집본 ≠ 실행본). 그래서 정식 배치는 **git에 등록된 스크립트로만** 돌리고
진행 판정은 완료 마커 + validator로 한다.

## 6. 동결 artifact의 바이트가 흔들리지 않는다

`.gitattributes`에 `-text`를 걸고 `git add -f`로 추적한다. index 바이트 == worktree 바이트를
확인한다(플랫폼 개행 변환으로 해시가 바뀌는 것을 막는다).

## 7. 생성이 결정적임을 실측했다

같은 서버·commit·경로에서 AI Hub 2,328구간을 재생성했더니 **상이 0건, 완전일치 1.0**이고
MRR도 소수 4자리까지 같았다. `p3_opcost` 두 실행에서도 출력 길이·토큰이 완전 동일했다
(3B 133.6자·92.2토큰 / 4B 82.9자·59.7토큰).

**단, 기계를 건너면 캡션 문자열은 대부분 달라진다** — 노트북↔서버 완전일치율 25.6%(dev)·
23.2%(AI Hub A-half). 그러나 562질의 검색 성능 차이는 Δ−0.0046 CI[−0.0267, +0.0174]로
**큰 방향성 환경 페널티는 재현되지 않았다.** 문자열이 달라지는 것을 곧 성능 저하로 읽지 않는다.

## 8. test를 여는 것이 사건으로 분리돼 있다

```
test 39         확정 config로 공식 평가 완료. 튜닝 접촉 0회 · 확정 절차 7회 (사유 전건 기록)
M9              split=="test" 하드코딩 — 실행 자체가 test 접촉. 승인 없이 실행 금지
39 → 72 확장     신규 33건 준비됨. 별도 test-opening 이벤트로 HOLD
데모             preflight가 test 영상을 거부한다
```

## 9. 리포트 주장이 추적 가능하다

M8은 모든 문장에 `[seg#N]` 인용을 강제하고, 저장 시 4개를 검증한다 — 인용 범위 · 서술 공백 ·
reduce 퇴화(한 문장이 전체의 89% 인용) · 반복 루프. `scripts/aar_view.py`가 각 주장을
**시각·자막·캡션·재생 위치**까지 잇고, 잇지 못하면 예외를 던진다.

## 10. 테스트

```
python -m pytest tests/ -q        GPU 불필요
```

`src/mN_*.py` ↔ `tests/test_mN_*.py`가 1:1로 대응한다. 안전장치도 각각 테스트가 있다 —
preflight 23건 · AAR 추적 13건 · gallery 10건 · coverage 게이트 14건 · 권한 감사 55건.
