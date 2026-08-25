/* 튜터 회의 자료 덱 — 2026-08-25
 *
 * 원본: docs/tutor/튜터회의_2026-08-25.md (상세 근거판)
 * 이 덱은 회의용 축약판이다. 수치는 전부 원본 문서의 근거 파일에서 인용한다.
 *
 * 출력 위치가 docs/tutor/_local/ 인 이유: AI Hub 프레임을 embed하는데
 * 재배포 권한이 확인되지 않았고 얼굴이 식별 가능하다. _local/ 은 .gitignore 대상이다.
 *
 * 실행:  node docs/presentation/build_tutor_deck.js
 */
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "../..");
const FRAMES = path.join(ROOT, "docs/probes/_scratch/caption_examples_frames");
const OUTDIR = path.join(ROOT, "docs/tutor/_local");
const OUT = path.join(OUTDIR, "튜터회의_2026-08-25.pptx");

const p = new pptxgen();
p.layout = "LAYOUT_WIDE";
p.title = "진행 보고 2026-08-25 — 한국어 영상 모먼트 검색";

const W = 13.33, H = 7.5;
const INK = "12343B";        // 딥 틸잉크 — 어두운 지면·제목
const PAPER = "F7F7F4";      // 본문 지면
const TEAL = "2C6E75";       // 3B(현행) 고정색
const AMBER = "B45309";      // 4B(후보) 고정색
const MUTED = "6B7280";
const LINE = "DCDCD6";
const WHITE = "FFFFFF";
const F = "맑은 고딕";
const MONO = "Consolas";

let page = 0;

function foot(s, dark) {
  const c = dark ? "8FA9AE" : MUTED;
  s.addText("진행 보고 · 2026-08-17 ~ 08-25", {
    x: 0.62, y: H - 0.44, w: 8, h: 0.3, fontSize: 9, color: c, fontFace: F, margin: 0,
  });
  s.addText(String(page), {
    x: W - 1.1, y: H - 0.44, w: 0.5, h: 0.3, fontSize: 9, color: c,
    fontFace: F, align: "right", margin: 0,
  });
}

function slide(kicker, title) {
  page++;
  const s = p.addSlide();
  s.background = { color: PAPER };
  if (kicker) {
    s.addText(kicker, {
      x: 0.62, y: 0.4, w: 12, h: 0.28, fontSize: 11, bold: true,
      color: TEAL, charSpacing: 2, fontFace: F, margin: 0,
    });
  }
  s.addText(title, {
    x: 0.6, y: 0.72, w: 12.1, h: 0.7, fontSize: 27, bold: true,
    color: INK, fontFace: F, margin: 0,
  });
  s.addShape(p.shapes.LINE, {
    x: 0.62, y: 1.5, w: 12.1, h: 0, line: { color: LINE, width: 1 },
  });
  foot(s, false);
  return s;
}

function darkSlide() {
  page++;
  const s = p.addSlide();
  s.background = { color: INK };
  return s;
}

function card(s, x, y, w, h, fill) {
  s.addShape(p.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: fill || WHITE },
    line: { color: LINE, width: 1 },
  });
}

/* 라벨 + 큰 수치 + 설명 */
function stat(s, x, y, w, label, value, note, color) {
  s.addText(label, {
    x, y, w, h: 0.28, fontSize: 11, bold: true, color: MUTED, fontFace: F, margin: 0,
  });
  s.addText(value, {
    x, y: y + 0.26, w, h: 0.62, fontSize: 30, bold: true,
    color: color || INK, fontFace: F, margin: 0,
  });
  if (note) {
    s.addText(note, {
      x, y: y + 0.92, w, h: 0.5, fontSize: 11, color: MUTED,
      fontFace: F, margin: 0, lineSpacingMultiple: 1.15,
    });
  }
}

/* 표 공용 옵션 (매 호출마다 새 객체) */
function tbl(s, rows, opts) {
  s.addTable(rows, Object.assign({
    fontFace: F, fontSize: 12, color: INK, border: { type: "solid", color: LINE, pt: 1 },
    align: "left", valign: "middle", autoPage: false,
  }, opts));
}
function th(t, align) {
  return { text: t, options: { bold: true, color: WHITE, fill: { color: INK }, fontSize: 11.5, align: align || "left" } };
}
function td(t, o) {
  return { text: t, options: Object.assign({ fontSize: 12 }, o || {}) };
}

/* ══════════ S1 표지 ══════════ */
{
  const s = darkSlide();
  s.addText("진행 보고", {
    x: 0.95, y: 1.9, w: 11.4, h: 0.4, fontSize: 13, bold: true,
    color: "7FB3B8", charSpacing: 3, fontFace: F, margin: 0,
  });
  s.addText("화면 설명 모델 비교, 새 데이터 확보 시도,\n그리고 최종화 전환", {
    x: 0.92, y: 2.35, w: 11.5, h: 1.7, fontSize: 34, bold: true,
    color: WHITE, fontFace: F, lineSpacingMultiple: 1.15, margin: 0,
  });
  s.addText([
    { text: "긴 한국어 영상에서 ", options: { color: "CFDDDF" } },
    { text: "말로 물어보면 그 장면을 찾아주는", options: { color: "9BC7CC", bold: true } },
    { text: " 시스템", options: { color: "CFDDDF" } },
  ], {
    x: 0.95, y: 4.25, w: 11.4, h: 0.5, fontSize: 16, fontFace: F, margin: 0,
  });
  s.addText("2026-08-17(월) ~ 08-25(화)", {
    x: 0.95, y: 6.35, w: 11.4, h: 0.4, fontSize: 14, bold: true,
    color: WHITE, fontFace: F, margin: 0,
  });
}

/* ══════════ S2 프로젝트 한 장 ══════════ */
{
  const s = slide("배경", "이 시스템이 하는 일");
  s.addText([
    { text: "20분짜리 요리 영상에 ", options: {} },
    { text: "“깻잎 소스를 만드는 장면”", options: { bold: true, color: TEAL } },
    { text: "이라고 입력하면 → ", options: {} },
    { text: "04:35~04:40", options: { bold: true, color: AMBER, fontFace: MONO } },
    { text: " 구간을 1순위로 띄우고 그 지점부터 재생한다.", options: {} },
  ], { x: 0.62, y: 1.75, w: 12.1, h: 0.5, fontSize: 15, fontFace: F, margin: 0 });

  const steps = [
    ["1", "5초씩 자른다", "영상을 구간 단위로 분할"],
    ["2", "두 종류의 글을 만든다", "자막 = 말소리 받아쓰기\n캡션 = 화면을 보고 쓴 설명"],
    ["3", "벡터로 바꿔 저장", "질문도 같은 방식으로 변환"],
    ["4", "비슷한 구간을 순위로", "재생 위치까지 함께 반환"],
  ];
  steps.forEach((v, i) => {
    const x = 0.62 + i * 3.09;
    card(s, x, 2.5, 2.85, 1.75);
    s.addText(v[0], { x: x + 0.18, y: 2.62, w: 0.5, h: 0.35, fontSize: 13, bold: true, color: AMBER, fontFace: MONO, margin: 0 });
    s.addText(v[1], { x: x + 0.18, y: 2.98, w: 2.5, h: 0.35, fontSize: 13.5, bold: true, color: INK, fontFace: F, margin: 0 });
    s.addText(v[2], { x: x + 0.18, y: 3.33, w: 2.5, h: 0.8, fontSize: 11, color: MUTED, fontFace: F, margin: 0, lineSpacingMultiple: 1.15 });
  });

  card(s, 0.62, 4.55, 12.1, 1.5, "EFF3F2");
  s.addText("이번 기간의 핵심 질문", { x: 0.95, y: 4.75, w: 11.5, h: 0.3, fontSize: 11, bold: true, color: TEAL, fontFace: F, margin: 0 });
  s.addText([
    { text: "화면 설명(캡션)을 쓰는 모델을 무엇으로 할 것인가.", options: { bold: true } },
    { text: "  현행 ", options: {} },
    { text: "Qwen2.5-VL-3B", options: { bold: true, color: TEAL } },
    { text: "  vs  후보 ", options: {} },
    { text: "Qwen3-VL-4B", options: { bold: true, color: AMBER } },
  ], { x: 0.95, y: 5.08, w: 11.5, h: 0.4, fontSize: 15, color: INK, fontFace: F, margin: 0 });
  s.addText("자막·검색 코드·평가 방식은 전부 고정하고 캡션 모델만 교체해서 비교한다.", {
    x: 0.95, y: 5.5, w: 11.5, h: 0.35, fontSize: 12, color: MUTED, fontFace: F, margin: 0,
  });

  s.addText("MRR = 정답 구간이 1등이면 1.0, 2등 0.5, 4등 0.25. 질의 전체 평균.  ·  MRR +0.03 ≈ 100개 질문 중 6개가 2등에서 1등으로.", {
    x: 0.62, y: 6.3, w: 12.1, h: 0.35, fontSize: 11.5, color: MUTED, fontFace: F, margin: 0,
  });
}

/* ══════════ S3 이번 기간 요약 ══════════ */
{
  const s = slide("요약", "이번 기간에 한 일");
  const rows = [
    [th(""), th("기간"), th("한 일"), th("결과")],
    [td("A", { bold: true, color: TEAL }), td("08-17~18"), td("3B와 4B 결과가 왜 엇갈리는지 규명"), td("원인 미해결 · 새 데이터 필요로 결론", { bold: true })],
    [td("B", { bold: true, color: TEAL }), td("08-20~24"), td("새 데이터(P2) 35편 준비"), td("재료는 완성, 정답 라벨 20/175에서 중단", { bold: true })],
    [td("C", { bold: true, color: TEAL }), td("08-24"), td("제대로 결판내려면 얼마나 드나 계산"), td("현재 설계 기준 약 1,500개 라벨 → 실행 보류", { bold: true })],
    [td("D", { bold: true, color: TEAL }), td("08-25"), td("최종 산출물 완성 단계로 전환"), td("데모 · UI · 외부 영상 기능 검증 착수", { bold: true })],
  ];
  tbl(s, rows, { x: 0.62, y: 1.8, w: 12.1, colW: [0.55, 1.5, 4.6, 5.45], rowH: 0.5 });

  card(s, 0.62, 4.9, 12.1, 1.5, "EFF3F2");
  s.addText("현재 상태", { x: 0.95, y: 5.08, w: 4, h: 0.3, fontSize: 11, bold: true, color: TEAL, fontFace: F, margin: 0 });
  s.addText([
    { text: "배포 모델은 그대로 3B다. ", options: { bold: true } },
    { text: "다만 지금 3B를 쓰는 이유는 “3B가 이겼기 때문”이 아니라 ", options: {} },
    { text: "“바꿀 만한 새로운 근거를 확보하지 못했기 때문”", options: { bold: true, color: AMBER } },
    { text: "이다. 3B 우세 증거도, 4B 기각 증거도 없다.", options: {} },
  ], { x: 0.95, y: 5.42, w: 11.4, h: 0.8, fontSize: 14, color: INK, fontFace: F, margin: 0, lineSpacingMultiple: 1.2 });
}

/* ══════════ S4 흐름 A — 방향이 반대 ══════════ */
{
  const s = slide("흐름 A · 08-17~18", "두 데이터에서 차이의 방향이 반대로 나타났다");
  const rows = [
    [th("어떤 데이터로 쟀나"), th("Δ (4B − 3B)", "center"), th("95% 신뢰구간", "center"), th("읽는 법")],
    [td("AI Hub (공개 데이터셋)\n1,086질문 · 194영상"),
     td("+0.031", { bold: true, color: AMBER, align: "center", fontSize: 17 }),
     td("[+0.008, +0.054]", { align: "center", fontFace: MONO, fontSize: 11 }),
     td("4B 방향의 차이 확인", { bold: true })],
    [td("dev (우리 영상)\n96질문 · 3영상"),
     td("−0.090", { bold: true, color: TEAL, align: "center", fontSize: 17 }),
     td("[−0.211, −0.028]", { align: "center", fontFace: MONO, fontSize: 11 }),
     td("3B 방향의 차이 관찰 — 영상 3편뿐이라 진단용", { bold: true })],
  ];
  tbl(s, rows, { x: 0.62, y: 1.8, w: 12.1, colW: [3.5, 2.0, 2.6, 4.0], rowH: 0.85 });

  card(s, 0.62, 4.75, 5.9, 1.35, "EFF3F2");
  s.addText("비교 조건은 통제됐다", { x: 0.9, y: 4.88, w: 5.4, h: 0.3, fontSize: 11, bold: true, color: TEAL, fontFace: F, margin: 0 });
  s.addText("자막만 켜고 재보면 세 조건의 점수가 완전히 같았다 (dev 자막 단독 0.4144). 캡션 말고는 아무것도 안 바뀌었다는 기계적 확인이다.", {
    x: 0.9, y: 5.18, w: 5.35, h: 0.8, fontSize: 12, color: INK, fontFace: F, margin: 0, lineSpacingMultiple: 1.2,
  });

  card(s, 6.82, 4.75, 5.9, 1.35, "EFF3F2");
  s.addText("dev는 왜 공식 판정에 못 쓰나", { x: 7.1, y: 4.88, w: 5.4, h: 0.3, fontSize: 11, bold: true, color: TEAL, fontFace: F, margin: 0 });
  s.addText("영상이 3편이라 오차범위가 ±0.09다. 이 크기의 차이를 판정할 정밀도가 없어 진단 목적으로만 인용한다.", {
    x: 7.1, y: 5.18, w: 5.35, h: 0.8, fontSize: 12, color: INK, fontFace: F, margin: 0, lineSpacingMultiple: 1.2,
  });

  s.addText("다음 두 장은 두 모델의 캡션이 실제로 어떻게 다르고, 그것이 순위를 어떻게 바꾸는지 보여준다.", {
    x: 0.62, y: 6.35, w: 12.1, h: 0.35, fontSize: 12, color: MUTED, fontFace: F, margin: 0,
  });
}

/* ══════════ 캡션 사례 공용 ══════════ */
function captionCase(opts) {
  const s = slide(opts.kicker, opts.title);
  const img = path.join(FRAMES, opts.image);
  if (fs.existsSync(img)) {
    s.addImage({ path: img, x: 0.62, y: 1.8, w: 5.35, h: 3.01 });
  } else {
    card(s, 0.62, 1.8, 5.35, 3.01, "E7E7E2");
    s.addText("프레임 없음 — caption_example_extract.py 실행 필요", {
      x: 0.62, y: 3.1, w: 5.35, h: 0.4, fontSize: 11, color: MUTED, align: "center", fontFace: F, margin: 0,
    });
  }
  s.addText(opts.frameNote, {
    x: 0.62, y: 4.86, w: 5.35, h: 0.5, fontSize: 10.5, color: MUTED,
    fontFace: F, margin: 0, lineSpacingMultiple: 1.15,
  });

  s.addText([
    { text: "질의   ", options: { color: MUTED, fontFace: MONO } },
    { text: opts.query, options: { bold: true } },
  ], { x: 6.3, y: 1.8, w: 6.4, h: 0.35, fontSize: 14.5, color: INK, fontFace: F, margin: 0 });

  const rk = [
    [th("모델", "center"), th("순위", "center"), th("점수", "center")],
    [td("3B (현행)", { bold: true, color: TEAL, align: "center" }),
     td(opts.rank3, { align: "center", bold: true, fontSize: 14 }),
     td(opts.rr3, { align: "center", fontFace: MONO, fontSize: 11 })],
    [td("4B (후보)", { bold: true, color: AMBER, align: "center" }),
     td(opts.rank4, { align: "center", bold: true, fontSize: 14 }),
     td(opts.rr4, { align: "center", fontFace: MONO, fontSize: 11 })],
  ];
  tbl(s, rk, { x: 6.3, y: 2.25, w: 6.4, colW: [2.4, 2.0, 2.0], rowH: 0.42 });

  card(s, 6.3, 3.68, 6.4, 1.12, WHITE);
  s.addText("3B 캡션", { x: 6.48, y: 3.74, w: 1.2, h: 0.25, fontSize: 10, bold: true, color: TEAL, fontFace: F, margin: 0 });
  s.addText(opts.cap3, { x: 6.48, y: 3.98, w: 6.05, h: 0.78, fontSize: 10.5, color: INK, fontFace: F, margin: 0, lineSpacingMultiple: 1.1 });

  card(s, 6.3, 4.88, 6.4, 1.2, WHITE);
  s.addText("4B 캡션", { x: 6.48, y: 4.94, w: 1.2, h: 0.25, fontSize: 10, bold: true, color: AMBER, fontFace: F, margin: 0 });
  s.addText(opts.cap4, { x: 6.48, y: 5.18, w: 6.05, h: 0.86, fontSize: 10.5, color: INK, fontFace: F, margin: 0, lineSpacingMultiple: 1.1 });

  s.addText(opts.point, {
    x: 0.62, y: 6.28, w: 12.1, h: 0.6, fontSize: 13, color: INK,
    fontFace: F, margin: 0, lineSpacingMultiple: 1.2,
  });
  return s;
}

/* ══════════ S5 사례 ① ══════════ */
captionCase({
  kicker: "흐름 A · 캡션 실물 ①",
  title: "질문이 묻는 “동작”이 캡션에 있느냐가 순위를 갈랐다",
  image: "B_4B우세__D3_DR_0922_000283_seg06.jpg",
  frameNote: "정답 = 6번 구간 (30~34초). 자물쇠가 빽빽한 난간 앞에서 여성이 상체를 앞으로 숙이고 있다.",
  query: "여자가 몸을 숙인다",
  rank3: "12위 / 12", rr3: "0.083",
  rank4: "1위", rr4: "1.000",
  cap3: "여성은 검은색 재킷을 입고 있으며, 그녀는 다소 놀란 듯한 표정으로 주변을 살피고 있습니다. 그녀의 앞에는 다양한 색상과 모양의 사랑의 문구가 달린 열쇠가 걸려 있는 금속 철제 장식이 보입니다. …  (167자)",
  cap4: "여성이 빨간색과 다양한 색상의 애정을 상징하는 잠금장치들이 가득한 금속 링 위에서 몸을 기울이며 바라보고 있다.  (62자)",
  point: "4B는 “몸을 기울이며”라고 썼고 3B는 자세를 아예 쓰지 않았다. 3B 캡션이 틀린 것이 아니라 오히려 더 자세하다 — 다만 질문이 묻는 항목이 그 안에 없다.",
});

/* ══════════ S6 사례 ② ══════════ */
captionCase({
  kicker: "흐름 A · 캡션 실물 ②",
  title: "더 정확한 캡션이 더 낮은 순위를 받기도 한다",
  image: "C_3B우세__D3_DR_0922_000321_seg00.jpg",
  frameNote: "정답 = 0번 구간 (0~4초). 정자 안에서 긴 머리 여성이 왼쪽으로 지나가고, 뒤쪽에 배낭 멘 사람 둘이 앉아 있다.",
  query: "여자가 주위를 둘러본다",
  rank3: "1위", rr3: "1.000",
  rank4: "12위 / 12", rr4: "0.083",
  cap3: "화면에는 나무로 만든 야외 공간이 보입니다. 한 여성이 왼쪽으로 향해 걸어가며, 그녀는 긴 머리를 가지고 있습니다. 그녀의 옆에는 다른 사람이 앉아 있으며, 그 사람은 모자를 쓰고 있습니다. …  (136자)",
  cap4: "숲 속에 있는 목재 구조의 편백으로 된 발코니에서 세 명의 사람이 서 있거나 앉아 있다. 왼쪽에는 긴 검은 머리를 가진 여성이 … 중앙에는 나무 기둥 사이에 앉아 있는 남성이 파란색 배낭을 메고 있고, 머리 위에 흰색 모자를 ▮ (글자 수 상한에서 잘림, 184자)",
  point: "4B 쪽이 화면 사실관계는 더 정확하다(사람 셋 · 흰 모자 · 파란 배낭). 그런데 세부를 나열하다 질문이 가리키는 인물의 비중이 묻혔고 길이 상한에서 문장이 잘렸다 — 캡션 정확도와 검색 순위는 같은 축이 아니다.",
});

/* ══════════ S7 성향 + 분포 ══════════ */
{
  const s = slide("흐름 A · 정리", "성향은 다르고, 전체 차이는 상쇄되고 남은 값이다");
  const rows = [
    [th(""), th("3B (현행)"), th("4B (후보)")],
    [td("평균 캡션 길이", { bold: true }), td("131.4자", { color: TEAL, bold: true }), td("82.0자", { color: AMBER, bold: true })],
    [td("주로 쓰는 내용", { bold: true }), td("옷 · 색 · 배경을 나열"), td("동작 · 자세를 압축해서")],
    [td("실패하는 방식", { bold: true }), td("동작을 안 써서 놓친다"), td("많이 써서 핵심이 묻히거나 잘린다")],
  ];
  tbl(s, rows, { x: 0.62, y: 1.8, w: 6.5, colW: [1.9, 2.05, 2.55], rowH: 0.55 });
  s.addText("길이는 2,328구간 실측이다. 성향 서술은 위 사례에서 보이는 경향이며 따로 측정한 값이 아니다.", {
    x: 0.62, y: 4.05, w: 6.5, h: 0.5, fontSize: 10.5, color: MUTED, fontFace: F, margin: 0, lineSpacingMultiple: 1.15,
  });

  card(s, 7.42, 1.8, 5.3, 2.75, "EFF3F2");
  s.addText("1,086질문에서 어느 쪽이 더 높은 순위였나", {
    x: 7.7, y: 1.98, w: 4.8, h: 0.3, fontSize: 11, bold: true, color: TEAL, fontFace: F, margin: 0,
  });
  const dist = [["4B가 더 높음", "42.1%", AMBER], ["3B가 더 높음", "33.8%", TEAL], ["완전히 동일", "24.1%", MUTED]];
  dist.forEach((d, i) => {
    const y = 2.4 + i * 0.68;
    s.addText(d[0], { x: 7.7, y, w: 2.6, h: 0.45, fontSize: 13, color: INK, fontFace: F, valign: "middle", margin: 0 });
    s.addText(d[1], { x: 10.3, y, w: 2.1, h: 0.45, fontSize: 22, bold: true, color: d[2], align: "right", fontFace: F, valign: "middle", margin: 0 });
  });

  card(s, 0.62, 4.75, 12.1, 1.3, WHITE);
  s.addText([
    { text: "질문마다 이기는 쪽이 다르고 서로 상쇄된다. ", options: { bold: true } },
    { text: "그렇게 상쇄하고 남은 것이 평균 +0.031이다. 즉 “4B가 전반적으로 낫다”가 아니라 ", options: {} },
    { text: "“이기는 질문이 조금 더 많다”", options: { bold: true, color: AMBER } },
    { text: " 수준이고, 그래서 어떤 질문이 많이 들어있는 데이터를 쓰느냐에 따라 방향이 달라질 수 있다.", options: {} },
  ], { x: 0.95, y: 4.95, w: 11.4, h: 0.95, fontSize: 13.5, color: INK, fontFace: F, margin: 0, lineSpacingMultiple: 1.25 });
}

/* ══════════ S8 방향이 갈리는 가능한 설명 ══════════ */
{
  const s = slide("흐름 A · 가능한 설명", "질문 유형에 따라 방향이 달라진다");
  const rows = [
    [th("dev 질문 유형"), th("개수", "center"), th("Δ (4B − 3B)", "center"), th("")],
    [td("장면형 — 화면에 무엇이 보이나", { bold: true }), td("38", { align: "center" }),
     td("+0.013", { align: "center", bold: true, color: AMBER, fontSize: 15 }), td("4B가 근소하게 앞선다")],
    [td("자막형 — 누가 무엇을 말하나"), td("24", { align: "center" }),
     td("−0.041", { align: "center", fontFace: MONO }), td("")],
    [td("복합형 — 말과 화면을 함께 봐야 함", { bold: true }), td("34", { align: "center" }),
     td("−0.241", { align: "center", bold: true, color: TEAL, fontSize: 15 }), td("전체 −0.090을 끌고 가는 층", { bold: true })],
  ];
  tbl(s, rows, { x: 0.62, y: 1.8, w: 12.1, colW: [4.6, 1.3, 2.4, 3.8], rowH: 0.6 });

  card(s, 0.62, 4.3, 12.1, 1.65, "EFF3F2");
  s.addText([
    { text: "AI Hub에는 “여자가 몸을 숙인다”처럼 짧은 동작·장면 서술형 질문이 많이 보이지만, 전체 질문에 유형 라벨이 없어 정확한 구성 비율은 확인하지 못했다. ", options: {} },
    { text: "따라서 이것은 방향이 갈리는 이유의 가능한 설명 중 하나이지, 확인된 원인이 아니다.", options: { bold: true } },
  ], { x: 0.95, y: 4.5, w: 11.4, h: 0.95, fontSize: 13.5, color: INK, fontFace: F, margin: 0, lineSpacingMultiple: 1.25 });
  s.addText("이 층 구분은 결과를 보고 만든 것이 아니라 라벨 파일에 원래 있던 값이고, 코드가 다른 축으로 쪼개는 것을 막고 있다.", {
    x: 0.95, y: 5.52, w: 11.4, h: 0.32, fontSize: 11, color: MUTED, fontFace: F, margin: 0,
  });

  s.addText("여기서 나온 설계 요구사항 — 새 데이터를 만들 때 질문 유형 구성을 반드시 맞춘다. P2에는 복합 62 / 자막 44 / 장면 69로 쿼터를 미리 배정했다.", {
    x: 0.62, y: 6.2, w: 12.1, h: 0.4, fontSize: 12, color: MUTED, fontFace: F, margin: 0,
  });
}

/* ══════════ S9 두 데이터 비교 + 결론 ══════════ */
{
  const s = slide("흐름 A · 결론", "어느 쪽도 단독으로 결론을 내기 어렵다");
  const rows = [
    [th(""), th("AI Hub"), th("dev (우리 영상)")],
    [td("영상 1편 길이", { bold: true }), td("60초"), td("12~26분")],
    [td("규모", { bold: true }), td("194편 · 2,328구간"), td("3편 · 612구간")],
    [td("질문 하나당 후보 구간", { bold: true }), td("12개", { bold: true }), td("149~314개", { bold: true })],
    [td("무작위 기준 점수", { bold: true }), td("약 0.26", { bold: true, color: AMBER }), td("0.02~0.04")],
    [td("자막 상태", { bold: true }), td("69%가 빈칸, 28편은 자막 없음"), td("정상")],
  ];
  tbl(s, rows, { x: 0.62, y: 1.8, w: 7.6, colW: [2.8, 2.6, 2.2], rowH: 0.44 });

  const notes = [
    ["문제 난이도가 다르다", "AI Hub는 후보가 12개뿐이라 무작위 기준도 약 0.26으로 높다. 절대 MRR을 긴 영상 검색 성능처럼 읽으면 안 된다."],
    ["문제 성격이 다르다", "60초 클립은 장면이 하나라 구간끼리 구별이 잘 안 된다(캡션 유사도 0.76 vs 우리 0.56)."],
    ["AI Hub는 이미 한 번 썼다", "모델 후보를 고를 때 쓴 데이터라 같은 데이터의 결과를 독립 확인으로 세지 않는다."],
  ];
  notes.forEach((n, i) => {
    const y = 1.8 + i * 1.2;
    s.addText(n[0], { x: 8.5, y, w: 4.2, h: 0.3, fontSize: 12.5, bold: true, color: TEAL, fontFace: F, margin: 0 });
    s.addText(n[1], { x: 8.5, y: y + 0.32, w: 4.22, h: 0.95, fontSize: 11, color: INK, fontFace: F, margin: 0, lineSpacingMultiple: 1.2 });
  });

  card(s, 0.62, 5.65, 12.1, 0.95, "EFF3F2");
  s.addText([
    { text: "하나는 우리 과제와 다른 쉬운 문제이고 이미 썼으며, 다른 하나는 영상 3편이라 정밀도가 없다. ", options: {} },
    { text: "→ 우리 과제와 같은 성격의 긴 영상으로, 판정 가능한 규모의 새 데이터가 필요하다.", options: { bold: true } },
  ], { x: 0.95, y: 5.85, w: 11.4, h: 0.6, fontSize: 13.5, color: INK, fontFace: F, margin: 0, lineSpacingMultiple: 1.2 });
}

/* ══════════ S10 흐름 B — P2 중단 ══════════ */
{
  const s = slide("흐름 B · 08-20~24", "새 데이터를 만들다 정답 라벨에서 멈췄다");
  const rows = [
    [th("단계"), th("상태")],
    [td("영상 35편 선정 · 다운로드 · 출처 기록 · 형식 검증"), td("완료", { bold: true })],
    [td("3B용 · 4B용 캡션 두 벌 생성 + 색인"), td("완료 · 검증 17항목 통과", { bold: true })],
    [td("질문 175개 배정 (복합 62 / 자막 44 / 장면 69)"), td("완료", { bold: true })],
    [td("정답 라벨 작성", { bold: true }), td("20 / 175에서 중단", { bold: true, color: AMBER })],
    [td("검색 실행 · 평가", { bold: true }), td("한 번도 실행하지 않음", { bold: true, color: AMBER })],
  ];
  tbl(s, rows, { x: 0.62, y: 1.8, w: 6.9, colW: [4.9, 2.0], rowH: 0.46 });

  card(s, 7.82, 1.8, 4.9, 2.9, "EFF3F2");
  s.addText("왜 줄이지 않고 멈췄나", { x: 8.1, y: 1.98, w: 4.4, h: 0.3, fontSize: 12, bold: true, color: TEAL, fontFace: F, margin: 0 });
  s.addText("이번 평가에서는 정답 위치를 사람이 원본 영상에서 확인해야 했다. 자동 모델 결과를 그대로 정답으로 쓰면 평가 대상 시스템과 독립된 GT라고 보기 어려워 사용하지 않았다.\n\n남은 155개를 기간 안에 끝낼 수 없었고, “175를 50으로 줄이자”는 결과를 보고 규모를 조정하는 것이라 하지 않았다.", {
    x: 8.1, y: 2.3, w: 4.4, h: 2.3, fontSize: 11.5, color: INK, fontFace: F, margin: 0, lineSpacingMultiple: 1.22,
  });

  card(s, 0.62, 4.85, 12.1, 1.35, WHITE);
  s.addText("멈추는 방식도 절차대로", { x: 0.95, y: 5.0, w: 5, h: 0.3, fontSize: 11, bold: true, color: TEAL, fontFace: F, margin: 0 });
  s.addText("① 라벨 도구 정상 종료 확인   ② 종료 전후 파일 해시 동일 확인(덮어쓰기 0건)   ③ 작업 파일 수정 없이 상태만 기록 · 산출물 8종 해시 동결   ④ 채점 결과 미열람을 항목별로 확인", {
    x: 0.95, y: 5.32, w: 11.4, h: 0.4, fontSize: 12, color: INK, fontFace: F, margin: 0,
  });
  s.addText("작성한 20개는 어떤 분석에도 쓰지 않는다. “실패한 실험”이 아니라 라벨 비용에 의한 중단(HOLD)으로 기록했다.", {
    x: 0.95, y: 5.72, w: 11.4, h: 0.35, fontSize: 12, bold: true, color: INK, fontFace: F, margin: 0,
  });
}

/* ══════════ S11 흐름 C — 비용 ══════════ */
{
  const s = slide("흐름 C · 08-24", "제대로 결판내려면 얼마가 드나");
  const rows = [
    [th("결정 (결과 보기 전에 동결)"), th("값")],
    [td("얼마나 좋아져야 바꿀 가치가 있나"), td("MRR +0.02 초과  (≈ 100질문 중 4개가 2등→1등)", { bold: true })],
    [td("얼마나 정밀하게 재야 하나"), td("오차범위 ±0.02", { bold: true })],
    [td("그러려면 데이터가 얼마나 필요한가", { bold: true }), td("영상 300편 × 질문 5개 = 약 1,500개 라벨", { bold: true, color: AMBER })],
    [td("누가 라벨을 다나 / 실행"), td("외부 전문 작업자 / 보류", { bold: true })],
  ];
  tbl(s, rows, { x: 0.62, y: 1.8, w: 7.2, colW: [3.3, 3.9], rowH: 0.52 });
  s.addText("+0.02는 데이터가 알려준 값이 아니라 “이 정도는 좋아져야 교체할 만하다”고 우리가 정한 정책 기준이다.\n1,500은 현재 동결한 설계 기준의 필요량이고, “1,500개면 반드시 판정된다”는 뜻이 아니다.", {
    x: 0.62, y: 4.5, w: 7.2, h: 0.8, fontSize: 10.5, color: MUTED, fontFace: F, margin: 0, lineSpacingMultiple: 1.2,
  });

  const rows2 = [
    [th("실제 배포 노트북 (6GB, 양쪽 4bit)"), th("3B", "center"), th("4B", "center")],
    [td("프레임 1장 처리"), td("8.06초", { align: "center", color: TEAL }), td("5.97초", { align: "center", bold: true, color: AMBER })],
    [td("VRAM 사용"), td("2.64GB", { align: "center", color: TEAL }), td("3.07GB", { align: "center", color: AMBER })],
    [td("모델 파일"), td("7.0GB", { align: "center", color: TEAL }), td("8.3GB", { align: "center", color: AMBER })],
    [td("메모리 부족 오류"), td("0건", { align: "center" }), td("0건", { align: "center" })],
  ];
  tbl(s, rows2, { x: 8.12, y: 1.8, w: 4.6, colW: [2.2, 1.2, 1.2], rowH: 0.46 });
  s.addText("배포를 막을 요인은 없었고, 자원을 더 쓰는 비용은 있다. 전기요금·비용은 재지 않았다.", {
    x: 8.12, y: 4.15, w: 4.6, h: 0.6, fontSize: 10.5, color: MUTED, fontFace: F, margin: 0, lineSpacingMultiple: 1.2,
  });

  card(s, 0.62, 5.45, 12.1, 1.0, "EFF3F2");
  s.addText([
    { text: "역설 — ", options: { bold: true, color: AMBER } },
    { text: "4B가 실제 노트북에서도 충분히 돌아간다는 사실은 ", options: {} },
    { text: "라벨 부담을 줄여주지 않는다", options: { bold: true } },
    { text: ". 전환 장벽이 작을수록 “조금만 좋아져도 바꿀 만하다”가 되고, 그만큼 더 정밀하게 재야 해서 필요한 라벨 수는 오히려 늘어난다.", options: {} },
  ], { x: 0.95, y: 5.62, w: 11.4, h: 0.7, fontSize: 13, color: INK, fontFace: F, margin: 0, lineSpacingMultiple: 1.2 });
}

/* ══════════ S12 권리 ══════════ */
{
  const s = slide("흐름 C · 08-24", "외부 작업자에게 영상을 보낼 수 있는지 먼저 확인했다");
  stat(s, 0.62, 1.9, 3.6, "감사 대상", "35편", "기존에 확보한 영상 전체", INK);
  stat(s, 4.42, 1.9, 3.6, "권리 판정", "전부 불명확", "자동으로 yes를 주지 않는다", AMBER);
  stat(s, 8.22, 1.9, 4.5, "전달 가능", "0편", "파일럿 후보 10편도 0/10", AMBER);

  card(s, 0.62, 3.75, 12.1, 1.55, "EFF3F2");
  s.addText("확인한 것", { x: 0.95, y: 3.92, w: 4, h: 0.3, fontSize: 11, bold: true, color: TEAL, fontFace: F, margin: 0 });
  s.addText("저작권 라이선스가 허용되더라도 영상 속 인물의 초상권·개인정보나 영상에 포함된 제3자 콘텐츠까지 자동으로 해결되는 것은 아니다. 그래서 외부 작업자에게 전달할 권리는 별도로 확인해야 했고, “내가 봐도 되는 권리”와 “사본을 남에게 보낼 권리”를 분리해서 판정하도록 도구를 고쳤다.", {
    x: 0.95, y: 4.24, w: 11.4, h: 0.95, fontSize: 13, color: INK, fontFace: F, margin: 0, lineSpacingMultiple: 1.25,
  });

  s.addText("이 결과는 작업이 막힌 것이 아니라 안전장치가 먼저 작동한 것이다 — 확인되지 않은 영상을 내보내지 않았다.", {
    x: 0.62, y: 5.65, w: 12.1, h: 0.4, fontSize: 13, bold: true, color: INK, fontFace: F, margin: 0,
  });
}

/* ══════════ S13 흐름 D — 최종화 ══════════ */
{
  const s = slide("흐름 D · 08-25", "최종 산출물 완성 단계로 전환했다");
  const rows = [
    [th("한 것"), th("내용")],
    [td("코드 감사부터", { bold: true }), td("실제로 빠진 것은 실행 전 점검 하나뿐이었다 — 검색·재생·근거 표시는 이미 있었다")],
    [td("데모 단일 진입점"), td("잘못된 설정으로 시연되는 것을 11개 항목으로 사전 차단")],
    [td("검색 UI 결함 3건"), td("긴 문장이 카드 밖으로 넘침 · 결과 0건일 때 빈 화면 · 잘못된 입력이 서버 오류")],
    [td("발표용 대비책"), td("발표 당일 서버 GPU 없이도 리포트가 뜨도록 사전계산 경로 마련")],
    [td("외부 영상 기능 검증", { bold: true }), td("우리 데이터가 아닌 공개 영상 4편 — 성능 측정이 아니라 기능 확인")],
  ];
  tbl(s, rows, { x: 0.62, y: 1.8, w: 12.1, colW: [2.7, 9.4], rowH: 0.46 });

  card(s, 0.62, 4.7, 5.9, 1.5, WHITE);
  s.addText("외부 영상 1편차 (4분 48초 · 58구간)", { x: 0.9, y: 4.85, w: 5.4, h: 0.3, fontSize: 11, bold: true, color: TEAL, fontFace: F, margin: 0 });
  s.addText("캡션 58/58 · 자막 47/58 · 결측 0 · 총 538초\n클릭한 구간 시작 시각으로 정확히 이동 → 기능 통과.\n남은 3편(10분·21분·68분)은 순서대로 진행 중.", {
    x: 0.9, y: 5.15, w: 5.4, h: 0.95, fontSize: 11.5, color: INK, fontFace: F, margin: 0, lineSpacingMultiple: 1.2,
  });

  card(s, 6.82, 4.7, 5.9, 1.5, "EFF3F2");
  s.addText("발견 1건 — 그리고 기준을 바꾸지 않았다", { x: 7.1, y: 4.85, w: 5.4, h: 0.3, fontSize: 11, bold: true, color: AMBER, fontFace: F, margin: 0 });
  s.addText("캡션 1건에 AI 지시문 echo가 그대로 들어갔고 검색 순위에도 영향을 줄 수 있었다. 사례 하나를 본 뒤 검출 규칙이나 표시 방식을 사후 변경하지 않고, REVIEW로 기록해 한계로 남겼다.", {
    x: 7.1, y: 5.15, w: 5.4, h: 0.95, fontSize: 11.5, color: INK, fontFace: F, margin: 0, lineSpacingMultiple: 1.2,
  });
}

/* ══════════ S14 GO / HOLD ══════════ */
{
  const s = slide("현재 경계", "지금 진행하는 것과 막아둔 것");
  card(s, 0.62, 1.85, 5.9, 2.2, WHITE);
  s.addText("진행", { x: 0.9, y: 2.0, w: 5.4, h: 0.3, fontSize: 12, bold: true, color: TEAL, fontFace: F, margin: 0 });
  s.addText([
    { text: "최종화 작업", options: { breakLine: true, bullet: true } },
    { text: "데모 · 검색 UI · 외부 영상 기능 검증", options: { breakLine: true, bullet: true } },
    { text: "문서 정리 · 최종 보고서 재료", options: { bullet: true } },
  ], { x: 1.0, y: 2.35, w: 5.2, h: 1.5, fontSize: 13, color: INK, fontFace: F, margin: 0, paraSpaceAfter: 6 });

  card(s, 6.82, 1.85, 5.9, 2.2, WHITE);
  s.addText("막아둠", { x: 7.1, y: 2.0, w: 5.4, h: 0.3, fontSize: 12, bold: true, color: AMBER, fontFace: F, margin: 0 });
  s.addText([
    { text: "P2 재개 · P3 실행", options: { breakLine: true, bullet: true } },
    { text: "최종 평가셋(test) 접촉 · M9 실행", options: { breakLine: true, bullet: true } },
    { text: "4B 채택 · 배포 구성 변경 · 영상 외부 반출", options: { bullet: true } },
  ], { x: 7.2, y: 2.35, w: 5.2, h: 1.5, fontSize: 13, color: INK, fontFace: F, margin: 0, paraSpaceAfter: 6 });

  card(s, 0.62, 4.35, 12.1, 1.75, "EFF3F2");
  s.addText("이 기간에 강화한 실행 규율 — 연구 결과 오염 0건, 절차 결함은 전부 코드로 막았다", {
    x: 0.95, y: 4.52, w: 11.4, h: 0.3, fontSize: 12, bold: true, color: TEAL, fontFace: F, margin: 0,
  });
  s.addText([
    { text: "라벨 도구가 캡션·자막을 볼 수 있었다 → 허용 항목만 통과", options: { breakLine: true, bullet: true } },
    { text: "출처 기록 없는 영상이 들어올 수 있었다 → 첫 단계에서 차단 (외부 영상 테스트에서 실제로 걸렸다)", options: { breakLine: true, bullet: true } },
    { text: "배치 진행 여부를 프로세스 생존으로 판단했다 → 완료 표식 + 검증 통과 기준으로 교체", options: { bullet: true } },
  ], { x: 1.05, y: 4.85, w: 11.2, h: 1.1, fontSize: 12, color: INK, fontFace: F, margin: 0, paraSpaceAfter: 5 });

  s.addText("전체 테스트 1,719건 통과 · 작업 트리 정리 완료", {
    x: 0.62, y: 6.3, w: 12.1, h: 0.35, fontSize: 11.5, color: MUTED, fontFace: F, margin: 0,
  });
}

/* ══════════ S15 상의 3건 ══════════ */
{
  const s = darkSlide();
  page--; page++;
  s.addText("상의하고 싶은 것", {
    x: 0.92, y: 0.85, w: 11.5, h: 0.6, fontSize: 30, bold: true, color: WHITE, fontFace: F, margin: 0,
  });
  const qs = [
    ["이번 과정에서는 3B / 4B 우열을 미해결로 남겨도 되는지",
     "결판에는 현재 동결한 설계 기준으로 약 1,500개 라벨과 권리 확인된 영상 300편이 필요하다. 최종 보고서에는 “미해결로 남긴 한계 + 결판에 필요한 설계”로 쓰는 것을 제안한다."],
    ["중단한 P2를 “비용 제약에 의한 HOLD”로 설명해도 되는지",
     "“실패”가 아니라 비용 제약에 의한 중단으로 쓰되, 작성된 20개 라벨은 인용하지 않는다. 이 서술 강도가 적절한지 확인 부탁드린다."],
    ["남은 한 달을 모델 비교보다 시스템·보고서 완성에 쓰는 방향이 맞는지",
     "현재는 최종화 쪽으로 방향을 잡았다. 우선순위가 적절한지가 가장 확인받고 싶은 부분이다."],
  ];
  qs.forEach((q, i) => {
    const y = 1.95 + i * 1.55;
    s.addText(String(i + 1), {
      x: 0.92, y, w: 0.55, h: 0.5, fontSize: 26, bold: true, color: "7FB3B8", fontFace: MONO, margin: 0,
    });
    s.addText(q[0], {
      x: 1.6, y, w: 10.9, h: 0.45, fontSize: 17, bold: true, color: WHITE, fontFace: F, margin: 0,
    });
    s.addText(q[1], {
      x: 1.6, y: y + 0.48, w: 10.9, h: 0.85, fontSize: 12.5, color: "C6D6D8",
      fontFace: F, margin: 0, lineSpacingMultiple: 1.25,
    });
  });
  s.addText("상세 근거 · 원본 수치 : docs/tutor/튜터회의_2026-08-25.md", {
    x: 0.92, y: 6.7, w: 11.5, h: 0.35, fontSize: 11, color: "8FA9AE", fontFace: F, margin: 0,
  });
}

fs.mkdirSync(OUTDIR, { recursive: true });
p.writeFile({ fileName: OUT }).then(() => console.log("wrote " + OUT));
