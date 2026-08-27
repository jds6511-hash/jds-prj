# 영상 장면 검색 및 AAR 보고서 자동 생성 시스템

한국어 vlog 한 편을 넣고 자연어로 질의하면, **학습 없이**(frozen 임베딩) **자막(말한 것)
+ 장면 캡션(보이는 것)** 을 결합해 원하는 순간을 찾는다. 확장으로 질의 없이 영상 전체를
훑어 근거 인용(`[seg#N]`)이 달린 사후검토 리포트(AAR, After-Action Review)를 생성한다.

핵심 문제의식: **자막 검색은 아무도 말하지 않은 장면을 못 찾는다.** 실제 질의의 1/3이
그런 유형이었고, 거기서 기존 방식의 MRR은 0.174였다.

## 실제로 어떻게 동작하나

아래는 공식 test 질의 `pb_q10`의 **실제 실행 출력**이다(발췌·요약 아님, 수치는
`results/eval_test.json`과 일치).

**질의:** `'HONG KONG'이라는 간판이 걸린 옷가게 거리 장면`

| 방식 | 정답(seg#147) 순위 |
|---|---|
| baseline — 자막만 (α=1.0) | **204위** |
| proposed — 자막+캡션 (α=0.5) | **1위** |

왜 이런 차이가 나는가. 정답 세그먼트의 두 채널을 보면 바로 드러난다.

```
seg#147  (735s~740s)

자막 : 아니 건널때 그런거있어 인도도 그러는데 갈까말까 멈추면 안되고
        그냥 가는길 가면 오토바이들은 알아서 피해가더라고
         → 간판·옷가게·거리에 관한 단어가 하나도 없다. 자막 검색이 못 찾는 이유.

캡션 : 화면에는 세 명의 남성이 거리를 걷고 있습니다. … 배경에는 다양한 상점들이
        보이며, 한 상점에는 "HONG KONG"이라는 글자가 크게 쓰여 있습니다.
         → 질의가 가리키는 것이 여기에 있다.
```

재현:

```bash
python src/m5_search.py --video-id panibottle_vietnam1 --alpha 1.0 \
  --query "'HONG KONG'이라는 간판이 걸린 옷가게 거리 장면"   # baseline
python src/m5_search.py --video-id panibottle_vietnam1 --alpha 0.5 \
  --query "'HONG KONG'이라는 간판이 걸린 옷가게 거리 장면"   # proposed
```

> 데모 GIF는 **만들지 않기로 했다**(2026-08-09 결정). 시연은 녹화물이 아니라
> 라이브 검색으로 하고, 웹 UI(`src/m7_webui.py`)는 로컬 실행 가능하다.

## 핵심 결과 (공식 test, n=39 질의 / 영상 4편)

| 지표 | baseline (자막만) | proposed (자막+캡션) | Δ 95% CI | 유의 |
|---|---|---|---|---|
| MRR | 0.649 | **0.829** | [+0.058, +0.310] | 예 |
| Hit@1 | 0.564 | **0.769** | [+0.077, +0.359] | 예 |
| Hit@5 | 0.769 | 0.872 | [−0.026, +0.256] | **아니오** |
| Hit@10 | 0.795 | 0.923 | [−0.026, +0.282] | **아니오** |

유형별 (같은 질의셋을 유형으로 쪼갠 것 — 사후 부분집합이라 검정하지 않는다):

| 유형 | n | baseline MRR | proposed MRR |
|---|---|---|---|
| 장면형 (무발화 장면) | 13 | 0.174 | **0.718** |
| 복합형 | 14 | 0.825 | 0.887 |
| 자막형 | 12 | 0.958 | 0.880 ← **하락(트레이드오프)** |

CI는 **paired bootstrap**, B=2,000, seed 42, 양측 95%(`config.yaml`의 `bootstrap_B`·`seed`).
원본: [`results/eval_test.json`](results/eval_test.json)(`diff_ci95` 필드),
[`results/alpha_search_dev.json`](results/alpha_search_dev.json)(dev α 탐색).
확정치 전체 표는 [`docs/DESIGN_SPEC.md`](docs/DESIGN_SPEC.md) §8-0.

## Quick Start

```bash
# 1) 시스템 의존성 — ffmpeg는 필수다(M1이 subprocess로 직접 호출한다)
ffmpeg -version            # 없으면 먼저 설치

# 2) 파이썬 패키지
pip install -r requirements.txt

# 3) 테스트 — GPU 없이 CPU만으로 통과한다(약 1분, 1,775건)
python -m pytest tests/ -q

# 4) 영상 1편 인덱싱 → 검색
cp <내영상>.mp4 data/videos/myvideo.mp4
python src/m1_preprocess.py --config config.yaml --video-id myvideo   # 5초 분할+오디오
python src/m2_keyframe.py   --config config.yaml --video-id myvideo   # 대표 프레임
python src/m3_generate.py   --config config.yaml --video-id myvideo   # 자막+캡션 (가장 오래)
python src/m4_index.py      --config config.yaml --video-id myvideo   # 임베딩
python src/m5_search.py     --config config.yaml --video-id myvideo --query "찾고 싶은 장면"

# 5) 데모 — preflight 후 웹 UI (권장 진입점)
python scripts/demo.py --list                          # 인덱스 완성 영상 목록
python scripts/demo.py --video-id myvideo --check-only  # 배포 구성·인덱스 정합 12항목만 확인
python scripts/demo.py --video-id myvideo               # preflight 통과 시 웹 UI 시작

# (웹 UI 직접 실행도 가능하다 — 인덱스 preflight는 붙지 않는다.
#  배포 α와 자격 경계는 이 경로에서도 강제된다. 다른 α는 명시 플래그로만:
#  --alpha 0.7 --allow-nondeployment-alpha  ← 그 실행은 배포 구성이 아니다)
python src/m7_webui.py --alpha 0.5 --port 7860
```

`scripts/demo.py`는 검색을 재구현하지 않는다 — `m5_search.search`와 `m7_webui.create_app`을
그대로 쓰고 앞에 **fail-closed preflight**만 붙인다. 배포 구성(`Qwen2.5-VL-3B`·4bit·
`KURE-v1`·α=0.5)과 다른 조합, 낡은 임베딩(`text_hash` 불일치), test split 영상,
external E2E 전용 영상(`eligible_for_public_demo: false`)은 **시작 자체를 거부한다.**

모델은 최초 실행 시 HuggingFace에서 자동 다운로드된다(수동 준비 불필요).

## 시스템 요구사항

| 항목 | 값 | 비고 |
|---|---|---|
| Python | **3.12** | 개발·검증 환경 |
| 외부 바이너리 | **ffmpeg** | M1의 오디오 추출. requirements.txt로 안 깔린다 |
| GPU (M1~M7) | VRAM **6GB**로 충분 | 기본 config가 4bit(`vlm_4bit: true`) |
| GPU (M8~M9) | VRAM **20GB** (bf16) | 6GB 불가 실측. `llm_4bit: true`면 축소 가능 |
| CUDA / torch | cu12x·cu13x 모두 동작 확인 | 드라이버가 받쳐주면 무관 |
| 디스크 (모델) | 검색만 **약 12GB** / M8~M9 포함 **약 27GB** | 실측: Whisper large-v3 2.9GB + Qwen2.5-VL-3B 7.1GB + KURE-v1 2.2GB (+Qwen2.5-7B 15GB) |
| 디스크 (산출물) | 영상 1편당 **약 75MB** | 프레임+오디오+임베딩 |
| CPU 전용 실행 | 이론상 가능, **비권장** | Whisper·VLM에 CPU 폴백은 있으나 수십 배 느리다 |

**처리 시간 실측** (RTX 3060 Laptop 6GB 기준, 33분 영상 395세그먼트):
M1 수 초 · M2 약 25분 · **M3 약 75분**(Whisper + 캡션 395회) · M4 약 2분 · M6 약 2분.
M3가 전체의 대부분이다. GPU 성능에 비례해 줄어든다.

## 재현 가능 범위 (정직하게)

원본 영상은 YouTube 공개 vlog이고 저작물이므로 저장소에 넣지 않았다. 자막·캡션은 그
영상에서 파생된 텍스트라 같은 이유로 제외했다.

| 항목 | 저장소 포함 | 재현 방법 |
|---|---|---|
| 평가 질의·정답 라벨 (dev 96 / test 39 / 무관 20) | **O** `data/queries/` | 그대로 사용 |
| 확정 평가 결과 JSON | **O** `results/` | 대조용 |
| 코드·단위테스트·설정 | **O** | `pytest tests/ -q` (GPU 불필요) |
| 원본 영상 | X | 사용자가 `data/videos/`에 직접 배치 |
| 자막·캡션 (`work/*/segments.json`) | X | M1~M3 실행 |
| 임베딩 (`work/*/emb_*.npy`) | X | M4 실행 |

평가 진입점에는 경계가 하나 더 있다. **test 39건 접촉은 승인 사건이므로**
`src/m6_evaluate.py`는 `--dev-only` 없이 돌리려면 `--test-opening '<사유>'`를,
`src/m9_report_eval.py`는(질의를 `split=="test"`로 하드코딩해 읽으므로 실행 자체가
test 접촉이다) 항상 `--test-opening '<사유>'`를 요구한다. 사유는 결과 JSON에 기록된다.

**따라서 `python src/m6_evaluate.py --dev-only`는 clone 직후에 동작하지 않는다** —
`work/{video_id}/emb_sub.npy`·`emb_cap.npy`·`meta.json`을 요구하고([m5_search.py:60-73](src/m5_search.py#L60-L73)),
셋 다 저장소에 없다. 같은 영상을 구해 M1~M4를 돌린 뒤에야 평가가 재현된다.

정리하면 **코드·절차·평가 라벨은 완전 공개, 데이터는 비공개**다. 동일 수치의 완전
재현은 원본 영상 확보가 전제다.

**캡션에는 단서가 하나 더 붙는다 (2026-08-07 실측).** VLM 캡셔닝은 그리디 디코딩이라
같은 환경에서는 결정적이지만 **환경을 건너면 아니다.** 같은 모델·양자화·프롬프트로
RTX 3060(개발 노트북)과 RTX 4090(서버)에서 각각 생성한 dev 655개 캡션 중 **완전일치는
168개(25.6%)**였고, 표기 차이가 아니라 내용이 바뀌었다. 부동소수점 누적 차이로 토큰
하나가 갈리면 그 뒤가 전부 달라지기 때문이다. 따라서 **다른 GPU에서 M3을 돌리면 캡션이
달라지고 검색 수치도 달라진다** — 코드·config가 같아도 그렇다. 자막(Whisper)·임베딩·
검색·평가 단계는 이 문제가 없다.

## 구현 상태

| 범위 | 상태 |
|---|---|
| M1~M7 영상 검색 + 웹 UI | **완료 · 공식 평가 완료** |
| M8~M9 AAR 생성·이중 평가 | **구현 완료**(2026-08-07) · 결함 4건 규명·수정. **프로젝트 필수 완료 범위**로 승격(2026-08-26) — M8은 dev에서 판정·동결까지, M9는 M8 freeze 후 test-opening 승인 사건. 로컬 6GB에서는 생성 불가(7B, 서버 전용). 완료 프로토콜·잔여 결정 6건: [M8_M9_PROTOCOL_2026-08-26.md](docs/finalization/M8_M9_PROTOCOL_2026-08-26.md) |
| 최종 문서 산출 (HWPX/HWP) | 미착수 — **M9 이후 필수 산출물**. `report.json`+`report_eval_*.json`을 서식만 입혀 렌더한다(새 LLM 호출 없음) |
| 화자분리 (pyannote) | 실행 가능 확인 완료 — 화자 수 추정 오차 −3~0, 클러스터 순도 0.958(우연 기저 0.45) |
| 회의록 생성 | 미착수 — Phase 4로 계획(설계: [docs/planning/phase4_회의록_설계.md](docs/planning/phase4_회의록_설계.md)) |
| 화자별 요약 | **범위에서 제외**(2026-08-09 결정) |

M8/M9는 결함 **4건**이 순차로 드러나 매번 수정했다(DESIGN_SPEC 8-5(6-a)~(6-f)):
① 리포트가 인용 마커만 남고 서술이 빔, ② 생성 상한에 걸려 뒷부분 잘림, ③ 한 문장이
전체 세그먼트의 89%를 인용하는 **번호 몰아쓰기**, ④ 같은 줄이 362회 반복되는 **반복 루프**.
③④는 감지된 영상에서만 규칙을 켜는 **감지 시 상향** 방식으로 고쳤다 — 규칙을 기본
경로에 넣었더니 정상 영상이 깎였기 때문이다(커버 0.844→0.418 실측).

**네 결함 모두 "성공"으로 보고됐다.** 검사가 전부 수량(문장 수·인용 수·파싱 성공률)을
셌기 때문이고, 매번 질적 검사를 하나씩 추가했다. **M9 judge 자체도 고장나 있었다** —
요약을 벌하는 대칭 매칭 프롬프트와 실행되지 않은 CoT. 정답이 객관적으로 정해진 합성
검증셋으로 계측기를 먼저 검증한 뒤(groundedness 0.63→0.97, coverage 0.60→0.90)
프롬프트를 교정했다. M9는 `split=="test"`가 하드코딩돼 **실행 자체가 test 접촉**이라,
2회를 접촉 이력에 올리고 교정 전 1회는 무효 처리했다(아래 §평가 방법과 연구 규율).

## 파이프라인

```
M1 5초 분할+오디오 → M2 대표 프레임 → M3 자막(Whisper large-v3)+캡션(Qwen2.5-VL-3B)
  → M4 임베딩(KURE-v1) → M5 z-score 정규화 + α 가중합 검색 → M6 평가(dev 탐색→test)
  → M7 웹 UI
(+ M8 AAR 리포트 생성 → M9 Coverage·Groundedness 이중 평가)
```

`src/mN_*.py` ↔ `tests/test_mN_*.py`가 1:1 대응한다(TDD로 작성).

```
src/        M1~M9 + common.py(공용 계약) + llm.py(로컬 LLM 로더)
tests/      모듈별 단위테스트 1,996건
config.yaml 확정 config (α는 여기 없다 — CLI 주입)
data/queries/  질의·정답 라벨 (공개)
results/    확정 평가 결과 (공개)
docs/       설계 명세·변경 이력·오류 분석·발표 자료
docs/probes/  모든 대안 탐색 스크립트 (dev-only)
```

## 평가 방법과 연구 규율

- **dev/test 분리**: 모든 튜닝·ablation은 dev(96질의/영상 3편)에서만. α, 정규화 방식,
  저관련도 경고 임계값(내부 config 키 이름은 `abstention_tau`지만 **실제 동작은 배너
  경고뿐이고 순위·결과를 바꾸지 않는다**) 등 **모든 선택이 dev에서 끝난 뒤** test를 돌렸다.
- **test 접촉 이력**: 튜닝 목적 접촉 **0회**, 확정 절차 공식 평가 **7회**(검색 M6 5회 +
  리포트 M9 2회). 7회 각각의 사유와, 무효 처리한 1회(M9 계측기 결함)와
  유일한 경계 사례 1건(pb_q08)까지 [DESIGN_SPEC §8-6](docs/DESIGN_SPEC.md)에 기록했다.
  반복 접촉이 holdout 과적합이 아닌 이유는 적응성(adaptivity) 기준으로 §8-6에서 방어한다.
- **캡션 수동 편집 금지**: 재생성은 자동 오염 판정분만(`common.is_corrupted_caption`).
  자막 크레딧 환각 제거도 같은 원칙의 자동 판정이다(`common.is_subtitle_credit`).
- **라벨은 프레임 실물 검증**: 캡션·자막 텍스트를 보고 정답을 정하지 않는다.
- 상세: [CLAUDE.md](CLAUDE.md).

## 한계

- **표본이 작다.** test는 질의 39건이지만 **영상은 4편**이다. 질의 단위 부트스트랩은 같은
  영상 안 질의들의 상관을 무시해 분산을 과소추정한다 — 영상 수준 불확실성은 이 CI보다
  크다. Hit@5·Hit@10은 CI가 0을 포함해 **유의를 주장하지 않는다.**
- **유형별 수치는 검정하지 않았다.** 장면형 0.174→0.718은 강한 관측이지만 사후 부분집합
  이므로 다중비교 문제가 있다. 헤드라인은 전체 MRR·Hit@1이다.
- **자막형은 하락했다**(0.958→0.880). 캡션 채널이 이미 자막으로 맞히던 질의에 노이즈를
  주는 구간이 있다.
- **실사용 실패 모드 2종** — 동의어 갭, "언급 ≠ 행위". 처방은
  [오류분석](docs/archive/오류분석_test_2026-07-13.md)과 방어 문서 Q13.
- **평가 도메인이 좁다.** 한국어 vlog 11편(그중 평가 대상 7편)이다.

## 현재 연구 상태 (2026-08-26)

README 위쪽의 **핵심 결과는 확정 배포 구성으로 끝난 공식 test 결과**다. 그 이후 진행한
것들의 현재 상태는 다음과 같다 — **어느 것도 배포 구성을 바꾸지 않았다.**

| 항목 | 상태 |
|---|---|
| 배포 캡션 모델 | `Qwen2.5-VL-3B` / P0 / 4bit **유지(incumbent)** |
| `Qwen3-VL-4B` | **viable candidate · 채택 아님 · 우열 미해결.** 운영상 실행 가능함은 확인됐다 |
| P2 (fresh 표본) | **HOLD** — 라벨 20/175에서 중단, retrieval·evaluation 미실행, 부분 20건 미분석 |
| P3 (확증 설계) | **설계 동결 · 실행 HOLD.** 300영상 × 5질의 = 1,500 GT는 가정 위의 설계 목표이지 검출 보장 수치가 아니다 |
| test 39 / M9 | **HOLD** — 이번 기간 접촉 0회. 39→72 확장도 열지 않았다 |
| M8 research evaluation | **HOLD**. AAR demo generation(기능 확인용 실행)과는 다른 사건이다 |
| AAR demo generation | **functional path 완주(2026-08-26).** dev 1편(149구간)을 서버에서 생성 → 반입 → 로컬 렌더 → 근거 추적까지 확인했다. **리포트 내용의 정확도를 잰 것이 아니다** |
| external E2E | **functional validation COMPLETE** — scene/speech/mixed/long-form 4편 PASS. 벤치마크가 아니다 |
| 캡션→검색 케이스 스터디 | **정성 사례 연구.** 채택 근거·성능 추정이 아니다 |

**external E2E**는 외부 공개 영상 4편이 현행 배포 경로를 end-to-end로 통과하는지만 본
기능 검증이다(68:36 · 824구간 long-form 포함). **정확도·벤치마크 성능·일반화 증명이
아니다.** 원본 영상은 저장소에 포함되지 않는다.

**캡션→검색 케이스 스터디**는 같은 프레임에서 두 캡션 모델이 서로 다른 요소를 기술할 때
검색 순위가 달라질 수 있음을 보인 **한 영상·5장면·15질의의 정성 관찰**이다.
참고 수치는 top-1 2/15 대 2/15, target 순위가 더 높았던 질의 4/15 대 11/15, 순위 중위수
31위 대 10위 — **한 영상의 illustrative observation이고 성능 추정치가 아니다.**
상세: [1페이지 요약](docs/tutor/캡션검색_케이스스터디_1페이지.md) ·
[전체 결과](docs/finalization/CAPTION_RETRIEVAL_CASESTUDY_RESULTS_2026-08-25.md)

## 문서

- **[docs/DESIGN_SPEC.md](docs/DESIGN_SPEC.md)** — 모듈 API·데이터 스키마 계약. §8-0 확정
  상태 스냅샷, §8-1~8-7 각 결정의 실측 근거.
- **[docs/DESIGN_SPEC_CHANGELOG.md](docs/DESIGN_SPEC_CHANGELOG.md)** — 확정치에 도달한
  날짜별 변천(문제 발견→처방→재개정).
- **[docs/IMPLEMENTATION_GUIDE.md](docs/IMPLEMENTATION_GUIDE.md)** — 선행연구 기반 설계 근거.
- **[docs/presentation/](docs/presentation/)** — 발표 슬라이드, 예상질문 방어(Q1~Q17), 시연 런북.
- **[docs/archive/오류분석_test_2026-07-13.md](docs/archive/오류분석_test_2026-07-13.md)** — 사례 기반 정성 분석.
- **[docs/probes/](docs/probes/)** — 대안·ablation 탐색 스크립트 전부. 각 파일 docstring에
  목적과 규율 준수 여부를 적었다(dev-only, 공식 결과 미접촉).
- **[docs/finalization/](docs/finalization/)** — 최종화 산출물: 시스템 감사, 데모 시나리오,
  한계·향후 과제, external E2E 결과, 캡션→검색 케이스 스터디, AAR 서버 runbook.
- 최신 진행 상황: `docs/작업현황_*.md` 중 가장 최근 날짜 파일.

## 사용 모델

| 역할 | 모델 |
|---|---|
| 자막 (STT) | `faster-whisper large-v3` |
| 장면 캡션 (VLM) | `Qwen/Qwen2.5-VL-3B-Instruct` (4bit NF4) |
| 임베딩 | `nlpai-lab/KURE-v1` |
| AAR 생성·판정 (M8/M9) | `Qwen/Qwen2.5-7B-Instruct` |
| 화자분리 | `pyannote/speaker-diarization-community-1` |

클라우드 API는 쓰지 않는다. 다만 **전부가 노트북에서 도는 것은 아니다** —
검색·재생(M1~M7)은 RTX 3060 Laptop 6GB에서 동작하지만, **AAR 생성(M8/M9, 7B)은 로컬
6GB에서 실행 불가**이고 서버 GPU가 필요하다. 로컬에서는 서버에서 만든 `report.json`을
렌더하는 경로만 쓴다 —
[AAR 서버 runbook](docs/finalization/AAR_SERVER_RUNBOOK_2026-08-26.md).
