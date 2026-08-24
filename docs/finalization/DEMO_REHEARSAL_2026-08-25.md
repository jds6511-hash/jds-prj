# 데모 리허설 체크리스트 + fallback (2026-08-25)

**슬라이드보다 먼저 이걸 한 번 통과시킨다.** 8분 사용자 흐름이 한 번도 막히지 않는지가
발표 성패를 가른다.

## 1. AAR 사전 생성물 확보 (발표 전에 반드시)

M8은 로컬 6GB에서 돌지 않는다. 발표 당일 서버·20GB GPU에 의존하면 전체 데모가 함께
무너진다. 그래서 **미리 만들어 두고 로컬에서 렌더만 한다.**

```
이름     AAR demo generation (finalization functional run)
아님     M8 research evaluation / taxonomy / human review — 그쪽은 HOLD다
```

절차:

```
1  서버(RTX 4090 24GB)에서 dev 영상 1~2편에 M8 1회 실행
   HF_HOME=/ssd/$USER/cache python src/m8_report.py --config config_server.yaml --video-id <dev>
   → work/<dev>/report.json
   ※ 본 config를 편집하지 않는다. 저장은 /ssd

2  report.json을 노트북 work/<dev>/ 로 가져온다

3  로컬에서 정합 확인 (GPU 불필요)
   python scripts/demo.py --video-id <dev> --check-only
   → "AAR 사전 생성물   사용 가능 (문장 N · 인용 구간 M)"

4  발표용 마크다운을 미리 렌더해 둔다
   python scripts/aar_view.py --video-id <dev> --out-md docs/finalization/AAR_<dev>.md
```

정합 검사가 막는 것:

```
report.json 없음                → available: false, 이유 표시
인용이 범위 밖                   → TraceError
인용 없는 문장                   → TraceError
video_id 불일치                 → TraceError
schema_version 미지원            → TraceError
생성 시점 n_segments ≠ 현재 인덱스  → TraceError (인용 번호가 다른 구간을 가리킨다)
```

**AAR가 없어도 검색 데모는 막히지 않는다** — preflight는 경고만 남기고 통과한다.

## 2. 8분 리허설 — 실제로 손을 움직여 본다

| 시각 | 동작 | 통과 기준 |
|---|---|---|
| 0:00 | `python scripts/demo.py --list` | dev 영상이 보이고 test 4편에 `(test split — 데모 불가)` 표시 |
| 0:30 | `python scripts/demo.py --video-id <dev> --check-only` | `preflight PASS — 확인 11항목` · AAR 상태 줄 확인 |
| 1:00 | `python scripts/demo.py --video-id <dev>` → 브라우저 | 페이지 로드 · 헤더에 α=0.5 표시 |
| 1:30 | 장면 중심 질의 | 결과 카드 3장 · 순위·구간·점수·발화/화면 근거 |
| 2:30 | 결과 클릭 | 해당 timestamp로 이동·재생 |
| 3:30 | 발화 중심 질의 | 자막 근거가 질의와 맞는지 눈으로 확인 |
| 5:00 | 복합 질의 | 두 채널이 함께 걸리는지 |
| 6:30 | 영상에 없는 것 질의 | low-relevance 경고 배너 (결과는 그대로 표시된다) |
| 7:00 | AAR 렌더 보여주기 | 사전 생성 md — 문장 → 시각 → 근거 → 재생 위치 |
| 8:00 | 종료 | 브라우저·서버 정상 종료 |

리허설에서 확인할 것 — **말이 아니라 화면**:

```
결과 카드가 잘리지 않는가 (긴 캡션·자막)
클릭 → seek이 정확한 구간으로 가는가
같은 질의를 두 번 넣어도 같은 결과인가
브라우저 새로고침 후에도 영상이 붙어 있는가
경고 배너가 무관 질의에서만 뜨는가
```

## 3. fallback 3단

```
1순위  라이브 검색 (scripts/demo.py)                    노트북만 있으면 된다
2순위  --check-only 출력 + SUCCESS_FAILURE_GALLERY 표    실제 실행 출력이다
3순위  README의 pb_q10 대조표                           공표된 test 결과

AAR   1순위 사전 렌더된 AAR_<dev>.md
      2순위 aar_view --out-md 를 현장에서 재실행 (GPU 불필요)
      3순위 AAR_TRACEABILITY 문서의 구조 설명으로 대체
```

라이브 M8 생성은 **보여줄 수 있으면 보여주고, 실패하면 즉시 사전 생성물로 넘어간다.**
서버 연결·GPU 상태를 발표 성패의 조건으로 두지 않는다.

## 4. 리허설 직전 60초 점검

```
python -m pytest tests/ -q                            전체 통과
python scripts/demo.py --video-id <dev> --check-only   11항목 + AAR 상태
ls data/videos/<dev>.mp4                              재생 대상 존재
포트 7860 비어 있는지                                   이전 서버 종료 확인
브라우저 캐시 새로고침                                   구 프런트 자산 방지
```

## 5. 리허설에서 나온 것을 기록한다

발견 → 수정 → 재리허설. **슬라이드 본문 작성은 이 루프가 한 번 깨끗하게 돌고 난 뒤에
시작한다.**

```
발견 항목      무엇이 막혔나 · 어느 단계에서 · 재현되나
수정           일반적인 UX/버그 수정은 그대로 진행 (finalization 범위)
멈춤 조건       frozen methodology·deployment identity·test/P2/P3를 건드려야 하면 멈추고 보고
```
