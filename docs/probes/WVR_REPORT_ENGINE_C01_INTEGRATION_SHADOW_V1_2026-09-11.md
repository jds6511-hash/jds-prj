# WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1 — 실행 결과 (2026-09-12 실행)

사전등록: `docs/preregistration/WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1_2026-09-11.md`
(문서명은 사전등록 §12에 동결된 이름을 그대로 쓴다. 실행일은 2026-09-12다.)

```
상태   EXECUTED / REVIEW_PENDING
```

**이 문서는 관측값만 적는다.** engine 우열 · production 채택 · 보고서 품질 PASS ·
C02~C05 실행 여부 · M9 실행 여부는 전부 reviewer 결정이다(사전등록 §13).

---

## A. 실행 요약

```
실행 호스트     kixlab2 · RTX 4090 24GB (실행 직전 유휴 40MiB)
격리 클론       /ssd/daeseok/jds-prj-rei-c01   (기존 클론 /ssd/daeseok/jds-prj 미접촉)
code_git_head   9c477ec366541cb83e9aeeb62f6ecd60e6ca44c8
모델            Qwen/Qwen2.5-7B-Instruct  revision a09a35458c702b33eeacc393d103063234e8bc28
                llm_4bit: false · do_sample: false
새 visual inference   0
새 STT               0
retry                0
```

동결 순서대로 4 cell을 한 번씩 실행했고 전부 exit 0이다.

```
cell      engine  view              시작(UTC)              종료(UTC)              exit
a_alpha   α       OVERLAP_VIEW      2026-09-12T13:31:19Z   2026-09-12T13:31:46Z    0
b_alpha   α       NONOVERLAP_VIEW   2026-09-12T13:31:46Z   2026-09-12T13:32:12Z    0
a_beta    β       OVERLAP_VIEW      2026-09-12T13:32:12Z   2026-09-12T13:32:42Z    0
b_beta    β       NONOVERLAP_VIEW   2026-09-12T13:32:42Z   2026-09-12T13:33:11Z    0
```

실행 전 preflight(모델 미적재, loader/schema 계약만)에서 4개 조합 모두
`n_segments=24 · seg_len=24`로 통과했다.

---

## B. 2×2 matrix

```
                          OVERLAP_VIEW                NONOVERLAP_VIEW
Engine α / m8_report      Aα  exit 0                  Bα  exit 0
                          문장 24 · 인용 24/24        문장 24 · 인용 24/24
                          fallback 0                  fallback 0

Engine β / v2.1-B2        Aβ  exit 0                  Bβ  exit 0
                          S0~S7 전부 _SUCCESS         S0~S7 전부 _SUCCESS
                          HWPX 생성 O                 HWPX 생성 O
                          presentation eligible 0/10  presentation eligible 0/10
```

---

## C. 공통 입력 계측 (adapter 산출물)

```
                    segment  temporal   duplicate   subtitle    caption
                    count    coverage   coverage    populated   populated
OVERLAP_VIEW          24      600.0초    552.0초      24/24       24/24
NONOVERLAP_VIEW       24      600.0초      0.0초      23/24       24/24
```

Aα·Aβ는 동일 segments.json(`a647769259cdf8d8…`), Bα·Bβ는 동일
segments.json(`53d660c05097e97f…`)을 받았다 — 두 engine에 같은 semantic source가
들어갔다.

---

## D. Engine α 측정 (α-Q1 ~ α-Q6)

```
α-Q1 loader/schema     PASS  common.load_segments가 seg_len_sec=24로 두 view 모두 수용.
                             idx 연속·start==idx*24 불변식 위반 없음.
α-Q2 report.json       생성됨. schema_version 2. 두 cell 모두 문장 24개.
α-Q3 map/reduce        분할 경로가 실행되지 않았다. generate_report는
                       len(segments)=24 <= map_chunk_size=60 이므로 단일 호출
                       경로를 탄다(src/m8_report.py:228). map_raw_outputs=[] ·
                       map_retries=[] 는 그 결과지 실패가 아니다.
                       이 입력 크기에서는 map/reduce가 계측되지 않았다.
α-Q4 [seg#N] 인용      인용 24건 · unique 24건 · 존재하지 않는 segment 인용 0건 ·
                       인용 없는 문장 0건. segment당 정확히 1문장 1인용이다.
α-Q5 overlap 중복      caption source가 동일하므로 Aα·Bα의 문장 수·인용 수는 같다.
                       시간 의미는 다르다 — 같은 [seg#i]가 Aα에서는 [i*24, i*24+48),
                       Bα에서는 [i*24, i*24+24)를 가리킨다. α는 인용을 segment idx로만
                       달고 시간을 따로 쓰지 않으므로, 중복 자체를 표면화하지 않는다.
α-Q6 subtitle 통합     Bα 입력은 subtitle 23/24(빈 문자열 1건)인데도
                       문장 24개가 전부 생성됐다 — 빈 subtitle에서 생성이 끊기지 않는다.
                       Aα·Bα 문장 텍스트는 서로 다르다(같은 caption, 다른 subtitle 범위).
```

§10 fallback 계측: `map_retries` 0 · `reduce_retry` 없음 ·
`degenerate_dropped` 0 · `truncated_tail` 없음 · 빈 보고서 0 — 두 cell 모두.

HWPX는 α의 gate가 아니다(사전등록 §9) — α에 HWPX 경로가 없다.

---

## E. Engine β 측정 (β-Q1 ~ β-Q7)

```
β-Q1 segments 입력     PASS  S0 ingest ~ S2 raw_index까지 오류 없이 진행.
                             canonical_episodes 10 / expected 10 (두 cell).
β-Q2 canonical 생성    PASS  S5 aar_canonical.json 생성. llm_calls 10 ·
                             prompt_refusals 0 · llm_failures 0 · retries 0.
                             parse_status VALID_PARSE 10/10.
β-Q3 highlights/synthesis  단계는 완료됐으나 **내용이 비었다.**
                             presentation eligible 0/10 ·
                             excluded_by_dialogue_grounding 10/10.
                             highlights 2개 전부 summary_status = NO_RELIABLE_CONTENT.
                             synthesis source_episode_ids = [] ·
                             결론 "요약이 제공된 구간이 없어 결론을 적지 않는다".
β-Q4 HWPX 생성         PASS  두 cell 모두 report.hwpx 생성. zip open OK ·
                             엔트리 6개 · mimetype 존재 · 손상 엔트리 없음.
                             Aβ 4312 bytes · Bβ 4328 bytes.
                             구조는 유효하고, 본문 내용은 위 β-Q3대로 비어 있다.
β-Q5 timestamp/display PASS  highlight 시간이 표시된다.
                             Aβ  H01 00:00–05:36 · H02 05:12–10:00
                             Bβ  H01 00:00–05:12 · H02 05:12–10:00
β-Q6 overlap 중복      **두 view가 여기서 갈린다.** Aβ는 H01 end(336초)가
                             H02 start(312초)보다 뒤라 24초 겹친다. Bβ는 312초에서
                             정확히 맞물려 겹치지 않는다. 즉 adapter의 view 차이가
                             β의 표시 시간 구간까지 그대로 전파된다.
β-Q7 subtitle 통합     Bβ에서만 FAIL_NO_SUPPORT 1건(no_support_ref)이 추가로 났고,
                             그 차이는 subtitle 23/24 입력과 같은 방향이다.
                             Aβ는 FAIL_UNSUPPORTED 10/10.
```

### 인용 (β)

```
Aβ  anchor_cites 24건 · unique 24건 · 존재하지 않는 segment 인용 0건
Bβ  동일
```

β는 `[seg#N]` 계약을 쓰지 않는다. 근거는 episode별 `anchor_cites` ·
`provenance`(`asr:NNNNNN` / `vlm:NNNNNN`) · `support_span`으로 표현된다.
사전등록 §9대로 β에 α의 인용 계약을 요구하지 않았다.

### §10 no silent fallback — 관측된 실패를 그대로 적는다

```
grounding_status   Aβ  FAIL_UNSUPPORTED 10
                   Bβ  FAIL_UNSUPPORTED 9 · FAIL_NO_SUPPORT 1
reason code        Aβ  unsupported_anchor 45
                   Bβ  unsupported_anchor 43 · no_support_ref 1
결과               presentation eligible 0 · 보고서 본문 NO_RELIABLE_CONTENT 4곳
```

기전(코드 대조로 확인한 것만 적는다):

```
1. β의 prompt 계약은 episode_content_v2 — summary + dialogue_note를 요구한다.
2. 모델이 dialogue_note에 발화 인용 대신 인용 표식을 넣었다.
   raw 예: {"summary": "아이스크림을 준비하고 있습니다.",
            "dialogue_note": "seg#0, seg#1, seg#2", "stt_cites": [0,1,2]}
3. src/v2_1_grounding.py:169-174 는 dialogue_note의 anchor가 인용된 ASR 근거
   텍스트에 문자열로 나타나는지 본다. 'seg' · '0' · '2' 가 없으므로
   unsupported_anchor → FAIL_UNSUPPORTED.
4. apply_grounding이 실패한 episode의 dialogue를 지우고, presentation이
   dialogue grounding 실패 episode를 제외 → eligible 0 → NO_RELIABLE_CONTENT.
```

### 대조 맥락 (기존 baseline 산출물 read-only 조회)

이 실행과 비교 가능한 기존 수치를 판단 없이 병기한다.

```
runs/v3_paired/r0_v2   prompt_version episode_content_v2 (이번 cell과 동일 계약)
                       grounding  FAIL_UNSUPPORTED 22 · FAIL_NO_SUPPORT 12 ·
                                  FAIL_REFERENCE 4 · NOT_APPLICABLE 3
                       presentation  episodes 41 · eligible 2 · 제외 38

runs/v3_paired/r1_v3   prompt_version episode_content_v3_summary_only
                       grounding  NOT_APPLICABLE 41
                       presentation  episodes 41 · eligible 39 · 제외 0
```

즉 **v2 계약에서의 대량 제외는 baseline 자체에서도 관측된 값이다**(41 중 38 제외,
eligible 2). 사전등록 §6은 β 호출에 `--contract`를 동결하지 않았고 orchestrator
기본값이 v2이므로 이번 4 cell은 v2로 돌았다. **v3 계약 재실행은 이번 사건에 없다** —
좋은 결과를 얻기 위한 retry 금지(§6)이자, 새 arm 추가는 reviewer 승인 사건이다.

---

## F. 사전등록 §9 공통 비교 지표

```
                          Aα        Bα        Aβ            Bβ
segment count             24        24        24            24
temporal coverage(초)     600.0     600.0     600.0         600.0
duplicate coverage(초)    552.0       0.0     552.0           0.0
subtitle populated        24/24     23/24     24/24         23/24
caption populated         24/24     24/24     24/24         24/24
generation completion     완료      완료      완료          완료
fallback usage            0         0         0             0
citation count            24        24        24            24
unique citation count     24        24        24            24
존재하지 않는 인용        0         0         0             0
section completion        n/a       n/a       5/5           5/5
HWPX generated            n/a       n/a       O             O
HWPX 구조 검증            n/a       n/a       zip OK        zip OK
```

semantic quality는 gate로 쓰지 않았다. 참고 관찰만 남긴다 — α 문장은 caption의
관측 요약을 문장화했고 인물명("Jonathan")이 등장한다. 이 이름의 출처가 caption인지
subtitle인지는 이번 계측 범위 밖이다.

---

## G. Baseline 보호 확인

실행 전후로 아래 경로의 내용이 바뀌지 않았다.

```
config.yaml                                72475952bbf56581…0a47af2f   불변
work_full/full_xekZO4n4QuE/segments.json   aa008317023c884a…f4799c92   불변
runs/v3_paired/submission_manifest.json    073942ee212a5b22…aee958cee  불변
src/m8_report.py · src/v2_1_render_hwpx.py · src/v2_1_segments.py ·
scripts/v2_1_b2_orchestrate.py                                         불변
```

격리 클론의 tracked 파일 변경은 0건이다(`git status --porcelain`에서 `??`만 존재).
쓰기는 `work_rei_c01/` · `runs/rei_c01/` · `configs/rei_c01_*.yaml`에만 일어났다.

`results/eval_test.json`은 격리 클론의 checkout으로 파일 mtime이 갱신됐으나
**내용은 동일하다** — local·server·HEAD 세 곳의 git blob이 전부
`a90ddedd2042cc4e97d783b75fef35341aac9d91`이다. official test를 읽지도 쓰지도
않았고 M9는 호출되지 않았다.

*주의(방법론): 로컬은 `core.autocrlf=true`라 같은 내용도 서버와 디스크 sha256이
다르게 나온다. 기계를 건너는 동일성 확인은 git blob id로 한다.*

---

## H. 사전등록 대비 편차

```
1. β의 --run-dir 를 runs/rei_c01/<cell>/ 이 아니라 그 아래 b2run/ 으로 잡았다.
   orchestrator가 --clean으로 run-dir를 비우는데, cell 디렉터리에는 이미 입력
   segments.json·cell.json이 있어 지워질 경로였다. 산출물 위치만 한 단계
   내려갔고 §7의 격리 경계를 벗어나지 않는다.
2. --producer-version 은 adapter commit 18d9dce 를 넣었다(§6이 "<기록>"으로만
   남긴 값). β manifest의 code_revision 은 실행 시점 git head 9c477ec 다.
3. --window-sec 은 §6에 동결돼 있지 않아 기본값을 썼다. 기본은
   src/v2_1_fixed_window.py의 WINDOW_SEC=60.0 이며 baseline v3_paired와 같은 값이다.
4. --contract 는 §6에 동결돼 있지 않아 기본값 v2로 돌았다(E절 참조).
```

---

## I. 산출물

```
runs/rei_c01/adapter_manifest.json          생성 전 동결 기록
runs/rei_c01/static_gate.json               S1~S12 12/12 PASS
runs/rei_c01/integration_matrix.json        본 문서의 수치 원본
runs/rei_c01/{a,b}_alpha/  segments.json · report.json · run.log · execution_record.json
runs/rei_c01/{a,b}_beta/   segments.json · run.log · execution_record.json
                           b2run/S0~S7 · b2run/raw · b2run/run_manifest.json ·
                           b2run/gpu_poll.jsonl · b2run/S7/report.hwpx · report.md
scripts/rei_c01_server_run.sh               동결 순서 실행기
scripts/rei_c01_integration_matrix.py       계측 집계기
```

---

## J. executor가 결정하지 않은 것

```
최종 production engine · α vs β winner · 보고서 품질 PASS
β를 v3 계약으로 재실행할지 · C02~C05 실행 여부 · M9 실행 여부
```

---

## K. 상태

```
WVR_REPORT_ENGINE_C01_INTEGRATION_SHADOW_V1
EXECUTED / REVIEW_PENDING
```

reviewer가 `REPORT_ENGINE_INTEGRATION_PASS` / `_HOLD` / `_INCONCLUSIVE` 중
하나를 결정한다.
