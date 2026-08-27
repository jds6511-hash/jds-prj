# M8 C2 판정 패널 — 신규 2편 sourcing rule (2026-08-27)

**이 문서는 후보를 하나도 보기 전에 동결한다.** 후보 목록을 본 뒤 이 규칙을 고치면
"자동 선정"이라는 말이 절차에서 성립하지 않는다.

```
목적        M8 C2 판정 패널 N=8 중 신규 2편의 후보 풀을 만드는 규칙
적용 범위    후보 발견 + 적격 필터까지. 최종 2편 선택은 별도 deterministic rule(§6)
동결 시점    후보 조회 실행 전
frozen_before_candidate_review   YES
```

기존 절차 재사용: `docs/P2_영상후보_스크리닝규격_2026-08-20.md`의 **hard 기준을 그대로**
쓴다(재생 시간·한국어 발화·기존 평가 영상 배제). 그 문서에 없는 항목만 아래에서 보탠다 —
발견 경로·기간·정렬·종료 규칙·채널 조건.

---

## 1. 발견 경로 (discovery source)

```
경로        YouTube 검색. yt-dlp `ytsearch<N>:<검색어>` · --skip-download
조회 정보    metadata만 (id · title · channel · duration · upload_date · availability)
금지        영상 재생, 캡션·자막 열람, 내용 판단
```

**metadata-only다.** 영상을 보고 "사건이 많아 보인다" 같은 판단을 하지 않는다.

## 2. 검색어 — 동결 목록

기존 6편과 장르가 겹치지 않는 쪽으로 넓게 잡되, 난이도를 겨냥한 표현을 쓰지 않는다.

```
1  브이로그 일상
2  다큐멘터리 한국
3  공방 제작 과정
4  등산 종주 기록
5  시장 골목 탐방
6  캠핑 자연 기록
```

**검색어를 후보 조회 후에 바꾸지 않는다.** 풀이 비면 규칙을 넓히지 말고 HOLD로 보고한다.

## 3. 조회 규모·종료 규칙

```
검색어당 조회   상위 20건 (관련도 기본 정렬)
종료           6개 검색어 조회가 끝나면 종료. 추가 검색어·추가 페이지 없음
중복 처리       같은 source_id가 여러 검색어에 나오면 첫 등장만 남긴다
```

## 4. 적격 필터 (E1~E13)

E1~E11은 사용자 지시서의 조건을 그대로 따른다. E12·E13은 P2 규격에서 가져온 hard 기준이다.

```
E1   dev/test 평가 질의가 붙어 있지 않다
E2   공식 test split이 아니다
E3   E2E 전용 영상이 아니다
E4   P2/P3 전용 자원이 아니다
E5   M8 report 생성 이력이 없다
E6   표본 소비 선언 대상이 아니다
E7   독립 reference 사건 작성이 가능하다
E8   이 프로젝트에서 caption·search·rank·frame을 사례 분석 목적으로 열람한 이력이 없다
E9   정상 취득 가능하다 (공개 · 연령제한 없음 · 지역 차단 없음 · 라이브 아님)
E10  5초 분할 및 M1~M5 처리가 기술적으로 가능하다
E11  내부 연구 사용 조건상 이번 평가에 사용 가능하다
E12  재생 시간 750~2000초        ← P2 스크리닝 규격 §0 그대로 (구간 150~400)
E13  한국어 발화 포함             ← P2 규격 §1. metadata proxy로 판정한다(§4-1)
```

### 4-1. 한국어 발화 판정 — proxy임을 명시한다

STT를 돌려서 확인하면 그 자체가 GPU 비용이고 내용 접촉이다. P2가 같은 문제에서 쓴
방식을 따른다 — **플랫폼 audio-language metadata를 proxy로 쓰고, 명시적으로 비한국어인
경우만 배제한다.** metadata가 없으면 `unresolved`로 두고 배제하지 않는다.
이것은 검증이 아니라 반증되지 않았다는 수준의 주장이다.

### 4-2. 채널 조건

```
C1  신규 2편은 서로 다른 채널
C2  신규 2편은 기존 6편의 채널과 다른 채널
```

**기존 6편 중 3편(`baekmansonghee_jirisan` · `softyeon_ceramics` · `jissi_farm`)은
취득 시점에 출처를 기록하지 않아 채널 identity를 모른다.** 추측해 채우지 않는다
(registry의 legacy 규칙과 같다). 따라서 C2는 **채널을 아는 3편**(`kbs_banff` ·
`wonyi_gyeongju` · `wonyi_geoje`)에 대해서만 강제되고, 나머지 3편에 대해서는
검증 불가로 기록한다.

## 5. 후보 풀 동결

```
1  이 문서 동결 (sha256 기록)
2  §1~§3으로 후보 조회
3  §4 필터 적용
4  적격 후보 풀 JSON 저장 → candidate_pool_sha256 기록
5  그 뒤에야 §6 해시 정렬을 계산한다
```

**해시 순위를 본 뒤 풀에 영상을 추가하거나 빼지 않는다.**

## 6. Deterministic selection rule

```
namespace   "M8-C2-N8-v1"
seed commit "f035073"
algorithm   SHA256(namespace + "|" + seed_commit + "|" + normalized_video_id)
정렬        selection_key 오름차순
```

`normalized_video_id`는 **YouTube source_id를 공백만 제거한 값**이다. 대소문자를 접지
않는다 — YouTube ID는 대소문자를 구분하므로 casefold하면 서로 다른 영상이 같은 키로
접힐 수 있다. 이 예외를 여기 적어 둔다.

```
rank 1     NEW_PRIMARY_1
rank 2 …   NEW_PRIMARY_2 = PRIMARY_1과 채널이 다른 첫 후보
           채널이 같아 건너뛴 후보는 RESERVE 목록 맨 앞으로 이동한다
그 이후     RESERVE_1, RESERVE_2, … (rank 순)
```

**이 채널 tie 처리 규칙도 해시를 계산하기 전에 정한다.** 계산 후에 정하면 결과를 보고
만든 규칙이 된다.

## 7. 교체 규칙

primary가 실패해도 사람이 새 영상을 고르지 않는다. reserve 순서를 그대로 쓴다.

```
허용 사유   TECH_FILE_UNAVAILABLE · TECH_DOWNLOAD_FAILURE · TECH_DECODE_FAILURE
           TECH_SEGMENTATION_FAILURE · TECH_PIPELINE_FAILURE · RIGHTS_NOT_USABLE
           PREDEFINED_AUTOMATIC_QC_FAILURE
금지 사유   사건이 적어 보임 · 쉬워/어려워 보임 · 라벨링이 번거로움 · M8 결과가 낮음
           Event Recall이 낮음 · 장르 취향 · 캡션 품질이 눈에 안 좋음 · 결과 균형 조정
```

교체가 나면 manifest를 덮어쓰지 않고 amendment 레코드를 추가한다.

## 8. 이 규칙이 하지 않는 것

```
M8 report 생성 · Event Recall 계산 · M9 · test 접촉        NO
caption·subtitle·retrieval 기반 선정                      NO
사람의 난이도 판단                                        NO
N·threshold·통계량 변경                                   NO
대표성 주장 ("한국어 장영상을 대표한다")                    NO
```

N=8은 확률표본이 아니다. **사전 정의된 적격 조건과 deterministic selection rule로 고정한
M8 구조 판정 패널**이다.
