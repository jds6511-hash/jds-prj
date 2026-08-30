"""A-10 합성 fixture — Gate A의 공용 입력.

티켓: `docs/finalization/V2_1_GATE_A_TICKETS_2026-08-30.md` A-10
소비: A-05 sanitation · A-08 fixed_window_v1 · A-09 canonical validator

전부 코드로 만든다. **`work/`·`runs/`를 읽지 않는다** — 실제 영상 산출물에
의존하면 fixture가 인덱스 재생성에 따라 흔들리고, Gate A는 결정적이어야 한다.

```
S1  exact 60s        12 × 5s          경계·partition의 기준선
S2  partial tail     12 × 5s + 2s     마지막 구간만 짧다
S3  no STT           caption만        3I7류
S4  no caption       ASR만            대칭 결손
S5  all empty        전 채널 공백      "없음"과 "실패"를 가르는 입력
S6  instruction echo VLM 지시문 반복   C0에서 최대 peak였던 실제 결함
S7  malformed        parser payload   raw는 있고 구조가 깨졌다
S8  OCR only         OCR 단독 주장     단독 근거 승격 금지 검증용
```

문자열은 전부 실측에서 가져왔다 — 지어낸 오염 표본으로 sanitation을 맞추면
실제 산출물에서 빗나간다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from v2_1_segments import CanonicalSegment, legacy_segments_to_canonical

#: 2026-08-30 C0에서 geoje chunk3 최대 peak(d=0.6798)였던 실제 VLM 출력.
INSTRUCTION_ECHO = (
    "네, 알겠습니다. 다음은 주어진 요청에 따라 한 문장의 한국어로 객관적인 묘사입니다."
)

#: 영상 전체에 반복되는 boilerplate. 반복만으로는 삭제 근거가 아니다(OPEN-7).
BOILERPLATE = "다음 영상에서 만나요."

#: 실제 발화인데 반복 규칙으로 지워졌던 문장. geoje에서 11건이 사라졌다.
EXCITED_SPEECH = "나 잡았어!!! 나 잡았어!!!"

#: 구조가 깨진 LLM 출력. 문장으로 건져 올리면 안 된다(EP21 사고).
MALFORMED_PAYLOAD = '{"summary": "해변에서 소스를 넣었다", "dialogue_note": '

FOREIGN_CAPTION = "夕阳西下，天空被染成了温暖的橙红色。"


def _segments(count: int, tail_sec: float | None = None) -> list[CanonicalSegment]:
    """5초 등간격 segment. `tail_sec`을 주면 마지막 구간만 그 길이로 만든다."""
    legacy = [{"idx": i, "start": i * 5.0, "end": i * 5.0 + 5.0} for i in range(count)]
    if tail_sec is not None:
        last = legacy[-1]
        legacy[-1] = {"idx": last["idx"], "start": last["start"],
                      "end": last["start"] + tail_sec}
    return legacy_segments_to_canonical(legacy)


@dataclass(frozen=True)
class Scenario:
    """합성 영상 하나. 채널 값은 `segment_id → raw payload` 매핑이다."""

    name: str
    note: str
    segments: list[CanonicalSegment]
    asr: dict[int, str] = field(default_factory=dict)
    caption: dict[int, str] = field(default_factory=dict)
    ocr: dict[int, str] = field(default_factory=dict)

    @property
    def duration_sec(self) -> float:
        return self.segments[-1].end_sec - self.segments[0].start_sec

    @property
    def segment_ids(self) -> list[int]:
        return [s.segment_id for s in self.segments]

    def channel(self, source_type: str) -> dict[int, str]:
        return {"asr": self.asr, "vlm": self.caption, "ocr": self.ocr}[source_type]


def _s1() -> Scenario:
    """정상 12구간. 반복 boilerplate 8건과 실제 반복 발화를 함께 담는다.

    SAN-011(출현 ≥8 → SUSPECT)과 SAN-010(실제 발화 보존)을 **같은 영상 안에서**
    구분해야 하기 때문이다. 두 규칙을 서로 다른 fixture로 나누면 둘이 충돌하는
    상황을 재현하지 못한다.
    """
    asr = {i: BOILERPLATE for i in range(8)}
    asr[8] = EXCITED_SPEECH
    asr[9] = "여기 소스를 넣으면 돼."
    asr[10] = "해변으로 내려가 보자."
    asr[11] = ""
    caption = {i: "두 여성이 해변에 앉아 있습니다." for i in range(12)}
    return Scenario("S1", "exact 60s · 12 × 5s", _segments(12), asr, caption)


def _s2() -> Scenario:
    segments = _segments(13, tail_sec=2.0)
    caption = {s.segment_id: "해변을 걷고 있습니다." for s in segments}
    return Scenario("S2", "partial tail 62s · 12 × 5s + 2s", segments, {}, caption)


def _s3() -> Scenario:
    caption = {i: "산길을 오르는 사람이 보입니다." for i in range(12)}
    return Scenario("S3", "no STT · caption only (3I7류)", _segments(12), {}, caption)


def _s4() -> Scenario:
    asr = {i: "그래서 어제 말한 대로 했어." for i in range(12)}
    return Scenario("S4", "no caption · ASR only", _segments(12), asr, {})


def _s5() -> Scenario:
    blank = {i: "" for i in range(12)}
    return Scenario("S5", "all modalities empty", _segments(12),
                    dict(blank), dict(blank), dict(blank))


def _s6() -> Scenario:
    caption = {i: "두 여성이 앉아 있습니다." for i in range(12)}
    caption[3] = INSTRUCTION_ECHO
    caption[7] = FOREIGN_CAPTION
    return Scenario("S6", "instruction echo · foreign caption", _segments(12),
                    {}, caption)


def _s7() -> Scenario:
    caption = {i: "두 여성이 앉아 있습니다." for i in range(12)}
    caption[5] = MALFORMED_PAYLOAD
    return Scenario("S7", "malformed parser payload", _segments(12), {}, caption)


def _s8() -> Scenario:
    ocr = {i: "" for i in range(12)}
    ocr[4] = "출발 09:30 김해공항"
    return Scenario("S8", "OCR-only assertion", _segments(12), {}, {}, ocr)


SCENARIOS = {s.name: s for s in (_s1(), _s2(), _s3(), _s4(), _s5(), _s6(), _s7(), _s8())}


def scenario(name: str) -> Scenario:
    return SCENARIOS[name]


# ── partition fixture ────────────────────────────────────────────────────
#: span은 segment_id 폐구간 `(start, end)`다. canonical은 겹침 0 · 빈틈 0 ·
#: 모든 segment가 정확히 한 번.
CANONICAL_PARTITION = [(0, 3), (4, 7), (8, 11)]

CORRUPT_PARTITIONS = {
    "overlap": [(0, 4), (4, 7), (8, 11)],       # seg#4가 두 span에 있다
    "gap": [(0, 3), (5, 7), (8, 11)],           # seg#4가 어디에도 없다
    "duplicate": [(0, 3), (0, 3), (4, 11)],     # 같은 span이 두 번
    "unassigned": [(0, 3), (4, 7)],             # seg#8~11이 남는다
}


def assigned_counts(spans, segment_ids):
    """segment_id별 배정 횟수. canonical이면 전부 정확히 1이다."""
    counts = {segment_id: 0 for segment_id in segment_ids}
    for start, end in spans:
        for segment_id in range(start, end + 1):
            if segment_id in counts:
                counts[segment_id] += 1
    return counts
