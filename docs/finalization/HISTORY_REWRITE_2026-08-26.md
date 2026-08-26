# 히스토리 재작성 기록 — 케이스 스터디 논의용 프레임 제거 (2026-08-26)

## 왜 했나

`docs/finalization/caption_retrieval_casestudy_results.json`이 논의용 프레임 디렉터리를
**"미추적 · 튜터 논의 한정 · 공개 금지"**로 선언해 두었는데, 실제로는 `acb8650`에서
**27장이 git에 추적되고 있었다.** 선언만 있고 강제가 없었다 — 2026-08-26 F4에서 고친
데모 진입점 결함과 같은 유형이다.

`.gitignore`만 추가하면 현재 HEAD에서는 사라지지만 **push하는 순간 과거 커밋의 blob이
따라 올라간다.** 그래서 히스토리에서 제거했다.

**지금이 가장 싼 시점이었다** — `acb8650`과 그 이후가 원격에 하나도 올라가 있지 않았다
(`git branch -r --contains acb8650` 결과 없음, origin은 `528d488`).

## 무엇을 했나

```
대상       runs/casestudy_caption_retrieval/*/frames_for_discussion/*.jpg  27장
방법       git filter-branch --index-filter --prune-empty -- origin/master..HEAD
범위       **미푸시 lineage만** (15커밋). 원격 히스토리는 건드리지 않았다
파일       삭제하지 않았다 — 로컬에 남겨 PPT 재생성·튜터 논의에 계속 쓴다
차단       .gitignore `runs/casestudy_caption_retrieval/*/frames_for_discussion/`
가드       tests/test_casestudy_frames_untracked.py — 재추적되면 실패한다
백업       branch backup/pre-frame-rewrite · tag backup-pre-frame-rewrite
```

## old → new SHA 매핑

**`acb8650` 이전 5개 커밋은 SHA가 바뀌지 않았다.** 그 커밋들의 tree에 해당 경로가
없어서 재작성이 내용을 바꾸지 않았기 때문이다. 덕분에 **frozen 케이스 스터디 artifact가
기록한 provenance SHA가 전부 그대로 유효하다.**

| old | new | 상태 | 제목 |
|---|---|---|---|
| `5b02427` | `5b02427` | **불변** | feat(finalization-F2): PHASE 2 external E2E 실행 |
| `31b5b02` | `31b5b02` | **불변** | prereg(casestudy): 캡션→검색 케이스 스터디 계획 동결 |
| `931b8ac` | `931b8ac` | **불변** | prereg(casestudy): outcome-blind amendment |
| `105857e` | `105857e` | **불변** | docs: 캡션 오염 검출기 미탐률 자체 측정 |
| `84ff245` | `84ff245` | **불변** | audit(casestudy): STEP 5.5 comparability audit |
| `acb8650` | `1440571` | 변경 | feat(casestudy): STEP 6-8 완료 |
| `8999bef` | `53f210c` | 변경 | feat(finalization-F2): PHASE 3 external E2E |
| `851933d` | `e77f494` | 변경 | feat(finalization-F2): PHASE 4 long-form E2E |
| `f42fdb2` | `e3964d7` | 변경 | docs(tutor): 케이스 스터디 1페이지 요약 + '오염 0' 표현 정정 |
| `2faeea5` | `be718b4` | 변경 | docs(finalization-F3): AAR 서버 runbook + 서버 config 생성 |
| `2ceb7ce` | `e6f8e98` | 변경 | fix(finalization-F4): 문서-코드 정합성 감사 + 데모 진입점 경계 결함 1건 |
| `cf3f7ef` | `451c800` | 변경 | fix(test): 감사 문서를 preflight 항목 수 stale 검사에서 제외 |
| `e00603d` | `7621fe1` | 변경 | docs(finalization-F5): 최종 보고서 source pack + claim-ev |
| `1a09b5e` | `637e129` | 변경 | feat(finalization-AAR): 서버에서 AAR demo artifact 1회 생성 |
| `dd65ee1` | `d26c6f5` | 변경 | docs(tutor): 캡션 → 검색 케이스 스터디 슬라이드 생성기 (10장) |

## frozen artifact 영향 — 없다

아래 frozen artifact가 기록한 commit SHA는 **전부 재작성 전과 같고 현재 HEAD의 조상으로
확인됐다.** 따라서 **frozen artifact를 한 글자도 고치지 않았다.**

```
caption_retrieval_casestudy_plan.json / results.json
   plan_commit                 31b5b02   불변 · HEAD의 조상
   amendment_commit            931b8ac   불변 · HEAD의 조상
   comparability_audit_commit  84ff245   불변 · HEAD의 조상
   arm_run_commits.3b          931b8ac…  불변
   arm_run_commits.4b          105857e…  불변
   git_head_at_outcome_access  84ff245…  불변
caption_retrieval_casestudy_comparability_audit.json   같은 두 SHA · 불변
runs/.../step6_retrieval_alpha0.json                   같은 SHA들 · 불변
docs/probes/casestudy_step6_retrieval.py               같은 SHA들 · 불변
CAPTION_RETRIEVAL_CASESTUDY_RESULTS / AMENDMENT .md    같은 SHA들 · 불변
```

## 갱신한 active 문서 — 3건

`e00603d`(F5 커밋)만 SHA가 바뀌었고, 그것을 참조한 곳은 전부 이번 세션에 만든 F5
문서였다.

```
CLAIM_EVIDENCE_MATRIX_2026-08-26.md    C15 exact — AAR 실행 시점 코드 HEAD
FINAL_REPORT_SOURCE_PACK_2026-08-26.md §13 실행 기록 (재작성 전 SHA도 병기)
final_report_facts_2026-08-26.json     aar.demo_run.code_provenance
                                       local_git_head 갱신 + local_git_head_at_run 보존
```

**AAR 실행 provenance는 깨지지 않았다.** 재작성이 제거한 것은 jpg뿐이고 `src/`·`scripts/`
바이트는 그대로다 — `code_manifest_sha256 = 4e0193e8…`가 그 증거이고 재작성 전후 같다.

## 검증

```
git ls-files <frames_dir>                      0건
git log --all -- <frames_dir>                  현재 lineage에 없음
git rev-list --objects --all | grep <27 blob>  reachable 0건 (reflog 만료 + gc 후)
.gitignore                                     신규 add 차단 확인
로컬 파일                                       27장 유지 · 매니페스트 해시 동일
PPT 재생성                                      PASS (프레임을 ignored 사본에서 읽는다)
```

## 하지 않은 것

```
원격 히스토리 재작성   없음 (push 안 함 · origin은 528d488 그대로)
frozen artifact 수정   없음
프레임 파일 삭제       없음
push                  없음
```
