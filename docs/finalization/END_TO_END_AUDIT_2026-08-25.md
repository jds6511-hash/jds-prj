# end-to-end 감사 — 현재 구현 상태 (2026-08-25)

**성격:** 조사 문서. 새 연구 수치를 계산하지 않았고 코드를 바꾸지 않았다.
**대상:** 현행 배포 경로 `Qwen2.5-VL-3B / P0 / 4bit · KURE-v1 · late fusion α=0.5`.

`project_phase = FINALIZATION` · `research_model_selection = HOLD`.

---

## 1. 단계별 감사

| # | 단계 | entrypoint | 필요 입력 | 산출물 | 의존 | 실패 조건 | 상태 | 노출 | 테스트 |
|---|---|---|---|---|---|---|---|---|---|
| M1 | 5초 분할 + 오디오 | `src/m1_preprocess.py --config --video-id` | `data/videos/{id}.mp4` | `work/{id}/audio.wav` · `segments.json`(골격) · 분할 메타 | **ffmpeg 바이너리** | ffmpeg 없음 · 영상 없음 | 완료 | 내부 | `tests/test_m1.py` |
| M2 | 대표 프레임 | `src/m2_keyframe.py` | M1 산출물 | `work/{id}/frames/` · `motion_score` | ffmpeg·numpy | 프레임 추출 실패 | 완료 | 내부 | `tests/test_m2.py` |
| M3 | 자막(Whisper large-v3) + 캡션(VLM) | `src/m3_generate.py` | M1·M2 산출물 | `segments.json`(`subtitle`·`caption`) · `stt_cache.json` | GPU 6GB · HF 캐시 | VRAM 부족 · 빈 캡션 | 완료 | 내부 | `test_m3*.py` 3파일 |
| M4 | 임베딩 | `src/m4_index.py` | `segments.json` | `emb_sub.npy` · `emb_cap.npy` · `meta.json`(`text_hash`) | KURE-v1 | 재캡셔닝 후 미실행 → M5에서 `ValueError` | 완료 | 내부 | `tests/test_m4.py` |
| M5 | 검색 (z-score → α 가중합) | `src/m5_search.py --query --alpha` / `search()` import | 임베딩 3종 + `segments.json` | `Result(idx, score, start, end)` 리스트 | numpy | `text_hash` 불일치 · 산출물 누락 | 완료 | **사용자** | `tests/test_m5.py` |
| M6 | 평가 (dev 탐색 → test) | `src/m6_evaluate.py` | 질의 라벨 + 인덱스 | `results/*.json` | M5 | GT 파생 규칙 위반 | 완료·**동결** | 내부 | `tests/test_m6.py` |
| M7-D | Gradio 데모 | `src/m7_demo.py --video-id` | 인덱스 + mp4 | 없음 (대화형) | gradio | 인덱스 누락 | 완료 | 사용자 | `tests/test_m7.py` |
| M7-W | FastAPI 웹 UI | `src/m7_webui.py --alpha 0.5 --port` | 인덱스 + mp4 | `results/search_log.jsonl` | fastapi·uvicorn | 인덱싱 미완 → 409 | 완료 | **사용자** | `tests/test_m7_webui.py` |
| M8 | AAR 리포트 생성 | `src/m8_report.py --video-id` | `segments.json` | `report.json` · `raw_output` | **LLM 7B, VRAM 20GB** | 로컬 6GB 실행 불가 (실측) | 구현 완료 · **로컬 실행 불가** | 사용자 | `tests/test_m8.py` · `test_m8_metrics.py` |
| M9 | 리포트 이중 평가 | `src/m9_report_eval.py` | `report.json` + test 질의 | 평가 JSON | LLM 7B | **`split=="test"` 하드코딩** | 완료 · **절대 HOLD** | 내부 | `tests/test_m9.py` |

---

## 2. 사용자 흐름 — 실제로 이어져 있는 구간

```
mp4 배치 → M1 → M2 → M3 → M4 → (인덱스 완성)
        → 자연어 질의 → M5 융합 검색 → top-k 구간 → 재생·근거 표시      ← 이어져 있다
        → AAR 리포트                                                  ← 끊겨 있다 (로컬 VRAM)
```

**웹 UI가 M1~M4를 서브프로세스로 직접 호출한다**(`m7_webui.PIPELINE`). 업로드 한 번으로
인덱싱까지 가고, GPU 보호를 위해 `JobStore`가 동시 1건만 허용한다. 즉 사용자 관점의
end-to-end는 이미 하나의 진입점에서 돈다.

**끊긴 곳은 AAR 하나다.** `report_model: Qwen/Qwen2.5-7B-Instruct`이고 6GB 로컬 실행이
불가하다는 것이 실측 확인 사항이다(3B 하향은 프롬프트 예시 복사 오염으로 기각). 랩실
GPU(RTX 4090 24GB)에서 `llm_4bit: false`로 올린다는 것이 현재 규약이다.

---

## 3. 검색 결과 UX — 이미 있는 것

`POST /api/search` 응답 (`src/m7_webui.py:212-256`):

```
results[]   idx · start · end · score(소수 3자리) · subtitle · caption
raw         채널별 raw 코사인 통계 (raw_sub_max · raw_cap_max · per-seg 점수)
low_relevance  abstention τ=0.55 미달 경고 (max(sub,cap) 기준). 결과를 숨기지 않는다
```

프런트(`src/webui/index.html`):

```
rank 표시      "N위 · score" (`.rank` · `.score`, tabular-nums)
근거 표시      자막·캡션 각각. 없으면 "없음"
재생·이동      seek(sec) → player.currentTime = sec; play()
영상 소스      GET /api/video/{id} — FileResponse, starlette Range 지원
구간 목록      GET /api/segments/{id} — 전 구간 자막·캡션
설정 표시      GET /api/meta — alpha · seg_len_sec · embed_model
```

표시 계층에만 `display_clean()`이 걸려 있다 — Whisper 반복 환각 collapse + 잔여 한자·가나
제거. **인덱스·임베딩·랭킹·평가에는 불개입.**

### 3-1. 확인된 gap

| gap | 근거 | 영향 |
|---|---|---|
| **preflight 없음** | `m7_webui.main()`은 `--alpha`만 필수. 모델·인덱스 identity·provenance·device를 시작 전에 확인하지 않는다 | 잘못된 인덱스·config 조합으로 시작될 수 있다. "일단 실행하고 이상하면 알림" 상태 |
| top-k 고정 3 | `top = results[:3]` | 발표에서 4위 이하를 못 보여준다 |
| 응답에 `rank`·`video_id`·`query` 없음 | 프런트가 배열 순서로 순위를 만든다 | 결과를 파일로 남기거나 보고서에 넣을 때 스키마가 불완전 |
| 데모 진입점 2개 | `m7_demo.py`(Gradio) · `m7_webui.py`(FastAPI) | 처음 보는 사용자가 무엇을 실행할지 모른다 |

---

## 4. 데모에 쓸 수 있는 자료 — 경계 확인

```
dev (사용 가능)   _10_000_Every_Day_You_Survive_In_The_Wilderness (36질의)
                gwaktube_soviet_apartment (30) · kheritage_grave_excavation (30)
test (사용 금지)   gemini_promo(8) · itsub_viral_gadgets(10) ·
                panibottle_vietnam1(11) · yunnamnopo_tongyeong(10)
```

`work/`에 인덱스가 있는 영상은 11편이고, 위 dev 3편과 test 4편이 모두 포함된다.
**새 데모 시나리오는 dev 3편으로만 만든다.** 이미 공표된 test 결과(README의 `pb_q10`
예시, `results/eval_test.json`)는 **공표된 결과의 인용**으로만 쓰고 새로 실행하지 않는다.

인덱스 산출물 확인 (dev 3편 전부 동일 구성):

```
audio.wav · frames/ · segments.json · stt_cache.json · emb_sub.npy · emb_cap.npy · meta.json
```

---

## 5. 재현성·안전장치 — 이미 구축된 것

| 장치 | 위치 | 역할 |
|---|---|---|
| `text_hash` 대조 | `common.index_text_hash` → M5 로드 | 재캡셔닝 후 m4 미실행이면 `ValueError`로 차단 |
| 자동 오염 판정 | `common.is_corrupted_caption` · `is_subtitle_credit` | 내용을 보고 고르지 않는다. 전체 일치 판정만 |
| CANARY coverage 게이트 | `scripts/canary_coverage.py` | `plan_schema_version >= 2`면 선언 누락 시 fail-closed. 기존 4개 계획만 allowlist 면제 |
| 단계 마커·상태 | `scripts/run_status.py` · `p2_index_batch.stage_marker` | 진행 판정을 "프로세스가 사라졌는가"가 아니라 완료 마커로 |
| `RUN_COMPLETE` + validator | `scripts/exp_launcher.py` | plan_hash 불일치 시 REPORT 거부 |
| provenance | `src/provenance.py` · `scripts/video_registry.py` | 영상 identity·해시. registry는 **read-only 어댑터**(SoT 전환 HOLD) |
| 라벨 누출 차단 | `scripts/label_guard.py` allowlist | 라벨 도구가 `segments.json`을 직접 읽지 못한다 |
| 동결 artifact 바이트 고정 | `.gitattributes` `-text` + `git add -f` | 개행 변환으로 해시가 흔들리지 않는다 |
| 결정성 증거 | `docs/재분석_2x2_2026-08-18.md` §8 | 같은 서버·commit·경로에서 2,328구간 재생성 → 상이 0건 |

---

## 6. 연구 상태 (변경 없음, 참조용)

```
3B ↔ 4B      unresolved. AI Hub +0.0310 ↔ dev −0.0903 (둘 다 CI가 0 배제)
             배포 3B 유지 이유는 "3B 우월 증명"이 아니라 "교체할 fresh evidence 없음"
P2           annotation HOLD · retrieval/evaluate 미실행 · outcome 미열람
P3-A         설계 동결 · 실행 HOLD (annotation logistics·반출 권한 미해결)
I1           R_only(2) 동결 · validation까지. production hard gate 아님
M8           exploratory unfinished · HOLD
registry SoT HOLD
test / M9    절대 HOLD
```

---

## 7. FINALIZATION 우선순위에 대한 감사 결론

```
FINALIZATION-P0  demo entrypoint + preflight (**유일한 실질 코드 gap**)
FINALIZATION-P1  결과 스키마 보완(rank·video_id·query·top-k) · AAR 경계 문서화
FINALIZATION-P2  descriptive 성공/실패 gallery · 운영·재현성 정리
FINALIZATION-P3  README/architecture/case study/발표 자료
```

**검색 UX·재생·근거 표시는 이미 구현돼 있다** — 새로 만들 것이 아니라 스키마를 채우고
진입점을 하나로 모으는 일이다. 대형 프런트엔드 재작성은 하지 않는다.
