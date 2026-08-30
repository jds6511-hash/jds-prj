# Local Video Report v2.1 — 아키텍처 규격 (2026-08-30)

```
status   SPEC CONFIRMED · 구현 미착수
purpose  완전 로컬 영상 → 근거 추적 가능한 AAR
network  실행 중 외부 인터넷 불필요
```

```
아님   공식 M8 결과 수정 · BCS v0 재판정 · M9 대체 · 새 event GT 평가 체계
```

기존 frozen artifact는 그대로 보존한다. v2.1은 **후속 제품 아키텍처**다.

---

## 0. 중심 원칙

> **생성 모델은 "무슨 일이 있었는지"를 해석하지만, "어디서 사건을 자를지"의 정본을
> 만들지 않는다.**

그리고 v2.1에서 추가된 원칙 하나.

> **정본 시간구조와 사람이 읽는 보고서 구조는 같은 것이 아니다.**
> 정본은 겹침 없는 완전 partition, 보고서는 중첩 가능한 의미 단위.

두 번째 원칙의 출처는 `REPORT_FORMAT_REFERENCE_2026-08-30.md`(사람이 작성한 형식
참조 · **GT 아님**)다. 그 표의 행들이 실제로 겹치고 중첩된다.

---

## 1. 층 구조

```
VIDEO
  ↓
5초 canonical segments
  ├─ ASR ─┐
  ├─ VLM caption
  └─ OCR(optional)
  ↓
deterministic sanitation      (text 수정 없음 · status만 부착)
  ↓
evidence_timeline  (참조 중심)
  ↓
boundary_signal.json          (provider와 무관하게 항상 생성)
  ↓
BoundaryProvider  [fixed_window_v1 default]
  ↓
Canonical Episodes            overlap 0 · gap 0 · exactly once
  ↓
Episode Content LLM           summary 필수 · dialogue_note 선택
  ↓
Claim grounding validator
  ↓
aar_canonical.json            ← 여기까지가 정본
  ↓
Presentation Highlights       중첩 허용
  ↓
Global Synthesis              validated 입력만
  ↓
Report Profile Renderer → MD / HWPX
```

---

## 2. Canonical Episode ≠ Report Highlight

```
Canonical Episode   기계가 시간을 관리하는 구조
Report Highlight    사람이 이야기를 이해하는 구조
```

```
Canonical   overlap 0 · gap 0 · exactly once · 시간순
Highlight   중첩 허용 · 부분 참조 허용 · 같은 Episode 다중 참조 허용
```

**Highlight는 canonical episode를 절대 수정하지 않는다.**

---

## 3. 입도 격차는 표현 계층에서 푼다

```
형식 참조   29분 → 주요 행 9개
BCS v0     27분 → Episode 32개
```

boundary provider가 9개를 만들게 하지 않는다 — 그러면 "몇 개가 정답인가"가
되돌아온다(은퇴시킨 C2 라벨과 같은 함정).

```
canonical Episodes  (촘촘)
      ↓ Highlight Builder
presentation Highlights  (굵게)
```

**행 수를 목표로 최적화하지 않는다.** 형식 참조의 9행은 format reference이지
target count가 아니다.

---

## 4. Highlight 스키마

```json
{
  "highlight_id": "H02",
  "label": "제나의 과거 회상",
  "episode_refs": ["EP02", "EP03"],
  "segment_refs": [12, 13, 14],
  "display_range": {"start_sec": 60, "end_sec": 180},
  "summary": "..."
}
```

canonical이 아니다. 실패해도 정본은 유효하다.

---

## 5. BoundaryProvider

```python
class BoundaryProvider:
    def detect(self, segments, caption_embeddings) -> list[int]:
        """Episode 시작 seg_idx 목록만 반환한다. span은 코드가 만든다."""
```

`caption_embeddings`는 **VLM이 생성한 caption text를 KURE-v1로 임베딩한 것**이다
(실측: `m4_index.py`가 `emb_cap.npy`를 그렇게 만든다). **시각 임베딩이 아니다.**

### default: `fixed_window_v1`

```yaml
boundary:
  provider: fixed_window_v1
```

의미는 "60초가 진짜 사건 경계다"가 아니다.

> **의미적 경계를 확신할 수 없으므로 canonical 시간 partition을 단순하고 결정적인
> 방식으로 유지한다.** 의미 구조는 Highlight Layer가 담당한다.

근거: 모델 대조 진단에서 **붕괴하지 않은 arm도 간격 10(50초)의 등차수열**을 냈다
(Qwen `[110,120,130,140,150]` · Kanana `[225,245,255,265,275]`). LLM이 정상일 때
내놓는 것도 사실상 균등 분할이었다.

### candidate: `caption_text_change_point`

```
입력   VLM caption → KURE-v1 임베딩 → 인접·국소 거리
상태   CANDIDATE — C0 관찰 단계
```

**이 신호는 이미지 차이가 아니라 "VLM이 무엇을 언어로 보존했는지"의 변화를 잰다.**
캡션이 옷 색 수준으로 흔들리면 거리도 흔들린다. C0가 먼저 볼 항목이다.

임계값(`0.55` 등)·최소 간격·smoothing을 **지금 명세에 박지 않는다.**

### 금지: `LLM_FREE_BOUNDARY`

canonical path에서 금지. diagnostic 모듈로는 보존 가능.

근거: `MODEL_DEGENERACY_DIAG_RESULT_2026-08-30.md` — Qwen은 full에서, Kanana는
caption-only에서 붕괴했고 위치 Jaccard가 어느 쌍에서도 0.2 미만이었다.

---

## 6. 모델 교체 불변성 — 범위를 정확히 적는다

```
content model 교체 (text LLM)
  fixed_window        경계 불변
  change_point        경계 불변
  → architecture invariant. 테스트는 회귀 가드다(자명하게 통과)

vision caption model 교체 (VLM)
  fixed_window        경계 불변
  change_point        경계 불변 보장 없음  ← caption text가 달라진다
```

> **"모델을 바꿔도 시간축이 동일하다"는 약속은 `fixed_window`에서만 완전히
> 성립한다.**

---

## 7. `boundary_signal.json`은 provider와 무관하게 항상 생성

```json
{
  "signal_type": "caption_embedding_distance",
  "embedding_model": "nlpai-lab/KURE-v1",
  "segments": [{"seg_idx": 123, "adjacent_distance": 0.43}]
}
```

fixed_window를 쓰더라도 저장한다 — 나중에 C를 다시 연구할 때 VLM·임베딩을 재실행할
필요가 없다.

---

## 8. Evidence — 참조 중심, text 무수정

```
정본 STT   segments.json / ASR artifact
sanitation text를 고치지 않는다. status만 붙인다.
```

```json
{"asr_id": "ASR123", "source_text_hash": "sha256:...",
 "status": "OVERLAY_OR_URL", "usable_for_claims": false}
```

`evidence_timeline`은 전체 text를 복제하지 않고 참조를 갖는다.

```json
{"seg_idx": 123, "asr_refs": ["ASR123", "ASR124"], "ocr_refs": []}
```

**검색 인덱스의 원문과 AAR의 원문이 갈라지는 상황을 막는다.** provenance에 인덱스
`text_hash`를 링크한다.

### ASR status

```
USABLE · EMPTY · REPEATED_CONTAMINATION · OVERLAY_OR_URL
FOREIGN_SCRIPT_SUSPECT · UNKNOWN
```

판정은 **결정적 특징만** 쓴다(반복 횟수 · URL/채널 패턴 · script 검사).
LLM에게 "이 발화가 진짜인가"를 분류시키지 않는다.

임계 근거는 `BCS_PROTOTYPE_SPEC_2026-08-29.md` §4(패널 18편 실측).
`is_corrupted_caption`의 반복 규칙은 STT에 쓰지 않는다 — 실제 발화를 지운다.

---

## 9. OCR은 보수적으로

```yaml
ocr:
  enabled: false
```

활성화해도 기본은:

```
status = UNKNOWN · usable_for_claims = false
```

```
저장 YES · 표시 가능 YES · claim 승격 NO
```

`IN_SCENE / EDITORIAL_OVERLAY` 분류기를 **근거 없이 발명하지 않는다.** ASR
sanitation이 방어 가능한 이유는 실측이 있었기 때문이고, OCR에는 그 실측이 없다.
승격 규칙은 측정 후 별도 사전등록.

(형식 참조의 `쪽샘 44호분`이 OCR이 실제로 필요한 사례임은 확인됐다.)

---

## 10. preview / report는 코드 인터록

```python
if manifest.analysis_mode != "report":
    raise ViewError("report rendering requires analysis_mode=report")
```

문서 규칙이 아니라 실행 불변식이다.

```
preview  15~20초 간격 · UI 미리보기 · 정식 근거로 사용 불가
report   5초 고정 · 대표 프레임 ≥ 1 · canonical evidence
hybrid   5초 유지 + scene-change frame을 **추가 evidence로만**
         (scene cut 자체는 Episode 경계가 되지 않는다)
```

---

## 11. RAW는 parse보다 먼저 저장 — 강제 규칙

```
model response
  ↓ RAW atomic write
  ↓ parse
  ↓ parsed artifact 저장
  ↓ validate
```

`response → parse 실패 → raw 소실`은 금지다. 2026-08-29에 두 번 났다.

---

## 12. Parse Contract를 독립 계층으로

```
RAW → NORMALIZE → PARSE → SEMANTIC VALIDATION
```

`55` · `"55"` · `"seg#55"`는 의미가 같으므로 **normalize 대상**이다.

status taxonomy.

```
MODEL_OUTPUT_MISSING
PARSE_CONTRACT_FAILURE        ← 모델 실패가 아니다
SEMANTIC_VALIDATION_FAILURE
GROUNDING_FAILURE
```

이 프로젝트의 최악 사고 셋이 전부 표기를 계약으로 착각한 것이었다
(v2 canary 맨 배열 · BCS `"seg#55"` cites · 깨진 JSON 폴백).

---

## 13. Content LLM에 요구하는 것 — 최소

```
필수   summary            문장 하나
선택   dialogue_note + stt_cites
```

모델에게 `source` · `support_span` · `anchor_cites`를 요구하지 않는다.
**필수 필드가 늘어나는 만큼 문서 전체가 죽을 확률이 는다**(v1 · v3 · v4 · softyeon).

`title`은 canonical 필드에서 **제외**한다. 표현 계층에서 `EP03 — 주요 구간`으로
충분하다.

자유 증식 필드(`key_actions[]` · `actors[]` · `importance[]`)를 canonical에 두지
않는다 — v1에서 사건 수 폭증의 통로였다.

---

## 14. Support는 코드가 파생

```json
{"episode_id": "EP03", "start_seg": 51, "end_seg": 79,
 "summary": "...",
 "support_span": {"start_seg": 51, "end_seg": 79},
 "anchor_cites": [51, 65, 79]}
```

`support_span` · `anchor_cites`는 **pipeline-generated field**다. 모델 출력이 아니다.
`source`도 코드가 파생한다(span 안에 usable STT가 없으면 visual).

---

## 15. Claim grounding

`dialogue_note`에만 강한 provenance를 요구한다.

```
1  cite한 seg가 실제 존재?
2  Episode span 내부?
3  그 seg에 STT가 실제 존재?
4  sanitation status == USABLE?
```

하나라도 실패하면 **dialogue만 제거하고 summary는 유지**한다.

```
source = stt      USABLE STT cite 필수
source = visual   해당 segment의 valid visual observation 필수
source = ocr      usable OCR cite 필수 (현재 승격 금지이므로 미사용)
```

모델의 자기 신고를 믿지 않는다. 코드가 확인한다.

`uncertainty_note`는 **두지 않는다** — 모델이 스스로 불확실하다고 쓰는 것은 검증
방법이 없다. 대신 결정적 `quality_notes`.

```json
{"usable_stt_count": 315, "excluded_stt_count": 29,
 "rejected_claims": 2, "ocr_available": false}
```

---

## 16. 실패 의미론

```
OK · INVALID · BLOCKED · PARTIAL
```

```json
{"stage": "content", "status": "PARTIAL",
 "reason": "dialogue_claim_rejected", "episode_id": "EP15"}
```

dialogue 하나가 실패했다고 Episode를 버리지 않는다.
**구조 자체가 깨졌을 때만 report render를 거부한다.**

```
금지   구조 invalid → 임의 singleton Episode → 정상 보고서로 표시
허용   canonical valid + 예쁜 title 생성 실패 → "EP03 — 주요 구간"
```

> 구조 fallback 금지, presentation fallback 허용.

---

## 17. Global Synthesis — canonical 밖, validated 입력만

```
aar_canonical.json → validated Highlights → Global Synthesis → report_synthesis.json
```

입력에서 **제외**한다.

```
raw STT   NO      raw captions   NO
```

입력에 **포함**한다.

```
validated Episode summaries · validated Highlights · validated dialogue claims
```

v1에서 LLM 개요가 `supports`에 전부 나열하고 통과했던 문제를 줄인다.

```json
{"text": "...", "supports": ["H02", "H04", "H06"]}
```

검증은 **존재하지 않는 ID 거부**까지다. semantic entailment를 자동으로 완전히
검증한다고 주장하지 않는다. 따라서 global synthesis는
**presentation-level generated interpretation**으로 명확히 구분한다.

---

## 18. Canonical / Presentation 최종 구분

```
CANONICAL
  segments · raw evidence refs · sanitation statuses · boundary signals
  episodes · validated episode summaries · validated dialogue claims

PRESENTATION
  highlight grouping · highlight labels
  overview · analysis · conclusion · MD/HWPX formatting
```

---

## 19. Report Profile `narrative_analysis_v1`

형식 참조를 따른다(`REPORT_FORMAT_REFERENCE_2026-08-30.md`).

```
1  개요                Global synthesis
2  주요 사건 및 내용      Highlight table   | 구간 | 주요 사건 | 내용 |
3  핵심 내용 분석        validated Highlights 기반 synthesis
4  결론                전체 흐름
5  근거 및 생성 정보      provenance · sanitation 결과 (부록 가능)
```

Canonical Episode 30여 개를 표에 그대로 내지 않는다. §2 표는 Highlight가 담당한다.

---

## 20. 한계 — 명시한다

```
서사 시간 미표현
  canonical schema는 recorded/video timeline만 다룬다.
  "과거 영상으로 소개된다" 같은 flashback·회상 관계를 표현하지 못한다.
  향후 temporal_relation(FLASHBACK / REFERENCE_TO_PAST)을 검토할 수 있으나 미구현.

경계의 지위
  fixed_window Episode는 사건 경계가 아니라 시간 창이다.
  렌더러가 이 사실을 문서에 명시한다.

global synthesis
  entailment 자동 검증 불가. presentation-level 해석으로 표시한다.

OCR
  claim 승격 규칙 미측정.
```

---

## 21. 디렉터리 · 모듈

```
outputs/<video_id>/
├── manifest.json
├── media/{media.json, audio.wav, frames/}
├── raw/{asr.json, vision/, ocr/, content/}
├── evidence/{segments.json, asr_status.json, vision.json,
│             ocr_status.json, evidence_timeline.json}
├── structure/{boundary_signal.json, episodes.json}
├── canonical/aar_canonical.json
├── presentation/{report_highlights.json, report_synthesis.json}
└── rendered/{report.md, report.hwpx}
```

```
src/v2/
├── media.py · segments.py · asr.py · vision.py · ocr.py
├── sanitation/{asr.py, ocr.py, scripts.py}
├── timeline.py
├── boundary/{base.py, fixed.py, change_point.py, diagnostics.py}
├── episodes.py
├── content/{generate.py, parse.py, schema.py}
├── grounding.py · canonical.py
├── presentation/{highlights.py, synthesis.py}
├── render/{markdown.py, hwpx.py}
└── provenance.py
```

---

## 22. Config

```yaml
pipeline:  {offline: true}
media:     {analysis_mode: report, segment_seconds: 5}
asr:       {model: faster-whisper-large-v3}
vision:    {provider: ollama, model: qwen2.5vl:7b}
ocr:       {enabled: false}
boundary:  {provider: fixed_window_v1}      # change_point는 C 검증 전까지 candidate
content:   {provider: ollama, model: qwen3:8b, temperature: 0}
grounding: {require_source_cites: true, reject_unusable_stt: true}
render:    {markdown: true, hwpx: true, profile: narrative_analysis_v1}
```

---

## 23. 필수 회귀 테스트

```
구조        overlap 0 · gap 0 · exactly once · 결정적 순서
오염        3I7 fixture — "마포구청 인터넷 방송국 홈페이지"가 canonical claim에 등장 금지
            "다음 영상에서 만나요"가 usable dialogue claim 금지
근거        source=stt + unusable STT cite → reject
            source=stt + STT 없음          → reject
표기 관용    55 · "55" · "seg#55" 전부 수용
            파싱 실패는 PARSE_CONTRACT_FAILURE로 분류 (≠ MODEL_FAILURE)
내구성      malformed JSON → raw 보존 · 이전 checkpoint 보존
표현        title 없음 → report valid
            dialogue 없음 → dialogue 절 생략
            rejected claim의 cite가 부록에 나오면 FAIL
모드        analysis_mode != report → render 거부
불변성      content model 교체 → Episode 경계 동일
            (vision model 교체는 change_point에서 보장하지 않음 — 테스트도 그렇게 적는다)
```

---

## 24. 구현 순서

```
V2-P0  segment schema · raw-before-parse · provenance · ASR/OCR sanitation · evidence timeline
V2-P1  BoundaryProvider 인터페이스 · fixed_window 구현 · change_point candidate · Episode 불변식
V2-P2  Episode summary · optional dialogue · source/cite 검증 · partial rejection
V2-P3  aar_canonical.json · MD/HWPX 렌더러 · Highlight Builder · Global Synthesis
V2-P4  UI (upload · progress · timeline · Episode explorer · evidence click-through · download)
```

**구현 미착수.** BCS v0가 P0~P3의 축소판을 이미 구현했고 HWPX 두 편을 냈다.
최종 보고서·발표와 자원이 경쟁하므로 착수 시점은 별도 판단이다.

---

## 25. C와의 관계

v2.1 전체가 C 하나에 베팅하지 않는다.

```
C0 결과 좋음   caption_text_change_point → provider 후보 승격
C0 결과 나쁨   fixed_window 유지
```

`BoundaryProvider`를 인터페이스로 분리했으므로 **provider 교체만으로 끝나고
나머지 파이프라인은 바뀌지 않는다.**
