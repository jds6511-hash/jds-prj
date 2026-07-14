const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.layout = "LAYOUT_WIDE";            // 13.33 x 7.5
p.title = "영상에서 원하는 장면, 말로 찾기 (중간발표)";

const W = 13.33, H = 7.5;
const NAVY = "0F2A43", NAVY2 = "16395C", TEAL = "18B7A6", BLUE = "2E7FA6", RED = "C0392B";
const LIGHT = "F5F8FB", INK = "1E2A38", MUTED = "6B7C8E", WHITE = "FFFFFF", LINE = "D9E2EC";
const HF = "맑은 고딕", BF = "맑은 고딕", MONO = "Consolas";

let pageNo = 0;
function footer(s, dark) {
  const c = dark ? "8FB0C6" : MUTED;
  s.addText("영상 장면 검색 · 중간발표", { x: 0.5, y: H - 0.42, w: 6, h: 0.3, fontSize: 9, color: c, fontFace: BF, align: "left", margin: 0 });
  s.addText(`${pageNo}`, { x: W - 1.0, y: H - 0.42, w: 0.5, h: 0.3, fontSize: 9, color: c, fontFace: BF, align: "right", margin: 0 });
}
function content(titleText, kicker) {
  pageNo++;
  const s = p.addSlide();
  s.background = { color: LIGHT };
  s.addShape(p.shapes.RECTANGLE, { x: 0, y: 0, w: 0.22, h: H, fill: { color: TEAL } });
  if (kicker) s.addText(kicker.toUpperCase(), { x: 0.6, y: 0.42, w: 12, h: 0.3, fontSize: 11, color: TEAL, bold: true, charSpacing: 2, fontFace: BF, margin: 0 });
  s.addText(titleText, { x: 0.58, y: 0.72, w: 12.2, h: 0.75, fontSize: 30, bold: true, color: NAVY, fontFace: HF, margin: 0 });
  footer(s, false);
  return s;
}
function dark() {
  pageNo++;
  const s = p.addSlide();
  s.background = { color: NAVY };
  s.addShape(p.shapes.RECTANGLE, { x: 0, y: 0, w: W, h: 0.12, fill: { color: TEAL } });
  return s;
}
function card(s, x, y, w, h, fill) {
  s.addShape(p.shapes.RECTANGLE, { x, y, w, h, fill: { color: fill || WHITE }, line: { color: LINE, width: 1 }, shadow: { type: "outer", color: "0F2A43", blur: 7, offset: 2, angle: 135, opacity: 0.10 } });
}
function accentTab(s, x, y, h, color) {
  s.addShape(p.shapes.RECTANGLE, { x, y, w: 0.09, h, fill: { color: color || TEAL } });
}

/* ─── S1 표지 ─── */
{
  const s = dark();
  s.addShape(p.shapes.RECTANGLE, { x: 0, y: 2.35, w: 0.9, h: 0.09, fill: { color: TEAL } });
  s.addText("영상에서 원하는 장면,\n말로 찾기", { x: 0.9, y: 2.55, w: 11.5, h: 1.7, fontSize: 42, bold: true, color: WHITE, fontFace: HF, lineSpacingMultiple: 1.05, margin: 0 });
  s.addText([
    { text: "자막만 검색하면 놓치는 장면을, ", options: { color: "CFE0EC" } },
    { text: "화면 설명을 더해", options: { color: TEAL, bold: true } },
    { text: " 찾아냅니다", options: { color: "CFE0EC" } },
  ], { x: 0.95, y: 4.45, w: 11.5, h: 0.5, fontSize: 17, fontFace: BF, margin: 0 });
  s.addText([
    { text: "중간발표", options: { bold: true, color: WHITE } },
  ], { x: 0.95, y: 6.35, w: 11.5, h: 0.4, fontSize: 14, fontFace: BF, margin: 0 });
}

/* ─── S2 문제 ─── */
{
  const s = content("긴 영상에서 '그 장면'을 어떻게 찾을까?", "문제");
  s.addText([
    { text: "예)  ", options: { bold: true, color: TEAL } },
    { text: "30분짜리 요리 영상에서 '새우 굽는 장면'만 다시 보고 싶다", options: { color: INK } },
  ], { x: 0.6, y: 1.7, w: 12.2, h: 0.4, fontSize: 15, fontFace: BF, margin: 0 });

  card(s, 0.6, 2.35, 5.9, 3.9);
  accentTab(s, 0.6, 2.35, 3.9, RED);
  s.addText("지금까지 — 자막만으로 검색", { x: 0.9, y: 2.6, w: 5.4, h: 0.4, fontSize: 17, bold: true, color: NAVY, fontFace: HF, margin: 0 });
  s.addText([
    { text: "화면에는 나오지만 아무도 말하지 않은 장면은 못 찾는다", options: { bullet: true, breakLine: true, bold: true } },
    { text: "예: 조용히 새우 굽는 장면, 마트 진열대", options: { bullet: true, indentLevel: 1, breakLine: true, color: MUTED } },
    { text: "실제 검색의 약 1/3이 이런 '보여주기만 한' 장면", options: { bullet: true, breakLine: true } },
    { text: "결국 사람이 영상을 직접 돌려봐야 한다", options: { bullet: true } },
  ], { x: 0.95, y: 3.15, w: 5.3, h: 2.9, fontSize: 13.5, color: INK, fontFace: BF, paraSpaceAfter: 8, valign: "top", margin: 0 });

  card(s, 6.85, 2.35, 5.9, 3.9);
  accentTab(s, 6.85, 2.35, 3.9, TEAL);
  s.addText("본 연구 — 화면 설명을 더한다", { x: 7.15, y: 2.6, w: 5.4, h: 0.4, fontSize: 17, bold: true, color: NAVY, fontFace: HF, margin: 0 });
  s.addText([
    { text: "AI가 각 장면을 보고 '무엇이 보이는지' 한 문장으로 기록", options: { bullet: true, breakLine: true, bold: true } },
    { text: "말한 것(자막) + 보이는 것(설명)을 함께 검색", options: { bullet: true, breakLine: true } },
    { text: "→ 말없이 보여주기만 한 장면도 찾을 수 있다", options: { bullet: true, breakLine: true, color: TEAL, bold: true } },
    { text: "덤: 영상 전체를 요약한 리포트도 자동 생성", options: { bullet: true, indentLevel: 1, color: MUTED } },
  ], { x: 7.2, y: 3.15, w: 5.3, h: 2.9, fontSize: 13.5, color: INK, fontFace: BF, paraSpaceAfter: 8, valign: "top", margin: 0 });
}

/* ─── S3 핵심 아이디어 ─── */
{
  const s = content("핵심 아이디어: 말한 것 + 보이는 것", "아이디어");
  s.addText("한 장면을 두 가지 글로 표현해 두고, 질문과 가장 비슷한 장면을 찾는다", { x: 0.6, y: 1.68, w: 12.2, h: 0.4, fontSize: 15, italic: true, color: BLUE, fontFace: BF, margin: 0 });
  const cols = [
    ["말한 것", "자막", "사람이 말한 내용을\n음성 인식으로 받아쓰기", TEAL],
    ["보이는 것", "화면 설명", "AI가 화면을 보고\n한 문장으로 설명", TEAL],
    ["질문", "검색어", "사용자가 입력한\n찾고 싶은 장면", BLUE],
  ];
  cols.forEach((c, i) => {
    const x = 0.6 + i * 4.13;
    card(s, x, 2.4, 3.9, 2.55);
    s.addShape(p.shapes.RECTANGLE, { x, y: 2.4, w: 3.9, h: 0.6, fill: { color: c[3] } });
    s.addText(c[0], { x, y: 2.4, w: 3.9, h: 0.6, fontSize: 17, bold: true, color: WHITE, align: "center", valign: "middle", fontFace: HF, margin: 0 });
    s.addText([{ text: c[1], options: { bold: true, breakLine: true, color: NAVY, fontSize: 15 } }, { text: c[2], options: { color: MUTED } }], { x: x + 0.2, y: 3.2, w: 3.5, h: 1.55, fontSize: 13, align: "center", valign: "middle", fontFace: BF, paraSpaceAfter: 8, margin: 0 });
  });
  card(s, 0.6, 5.3, 12.15, 1.0, "EEF4F8");
  s.addText([
    { text: "핵심   ", options: { bold: true, color: TEAL, fontFace: HF } },
    { text: "새로 학습시키지 않고 공개된 무료 AI 모델만 조합 — ", options: { color: INK } },
    { text: "작은 GPU(6GB) 한 대에서 동작", options: { color: NAVY, bold: true } },
    { text: "한다.", options: { color: INK } },
  ], { x: 0.9, y: 5.3, w: 11.6, h: 1.0, fontSize: 14, align: "left", valign: "middle", fontFace: BF, margin: 0 });
}

/* ─── S4 동작 방식 ─── */
{
  const s = content("어떻게 동작하나", "동작 방식");
  s.addText("영상 하나를 넣으면, 4단계를 거쳐 원하는 장면의 시각을 돌려준다", { x: 0.6, y: 1.68, w: 12.2, h: 0.4, fontSize: 14.5, color: MUTED, fontFace: BF, margin: 0 });
  const steps = [
    ["1", "영상을 조각낸다", "5초 단위로 나눠\n장면 단위를 만든다"],
    ["2", "글로 바꾼다", "조각마다 말한 것(자막)과\n보이는 것(설명)을 기록"],
    ["3", "질문과 비교한다", "질문과 각 조각이\n얼마나 비슷한지 계산"],
    ["4", "장면을 돌려준다", "가장 비슷한 순서로\n'몇 분 몇 초'와 함께 제시"],
  ];
  const bw = 2.85, gap = 0.29, x0 = 0.6, y0 = 2.45;
  steps.forEach((st, i) => {
    const x = x0 + i * (bw + gap);
    card(s, x, y0, bw, 2.35);
    s.addShape(p.shapes.OVAL, { x: x + bw / 2 - 0.4, y: y0 + 0.3, w: 0.8, h: 0.8, fill: { color: NAVY } });
    s.addText(st[0], { x: x + bw / 2 - 0.4, y: y0 + 0.3, w: 0.8, h: 0.8, fontSize: 24, bold: true, color: TEAL, align: "center", valign: "middle", fontFace: MONO, margin: 0 });
    s.addText(st[1], { x, y: y0 + 1.2, w: bw, h: 0.4, fontSize: 15.5, bold: true, color: NAVY, align: "center", fontFace: HF, margin: 0 });
    s.addText(st[2], { x: x + 0.15, y: y0 + 1.62, w: bw - 0.3, h: 0.65, fontSize: 12, color: MUTED, align: "center", fontFace: BF, margin: 0 });
    if (i < steps.length - 1) s.addText("▶", { x: x + bw - 0.02, y: y0, w: gap + 0.04, h: 2.35, fontSize: 13, color: TEAL, align: "center", valign: "middle", margin: 0 });
  });
  card(s, 0.6, 5.35, 12.15, 1.0, "EEF4F8");
  s.addText([
    { text: "사용한 공개 모델   ", options: { bold: true, color: BLUE, fontFace: HF } },
    { text: "음성 인식 Whisper   ·   화면 설명 Qwen2.5-VL   ·   유사도 비교 KURE", options: { color: INK } },
    { text: "     — 전부 무료·오픈소스", options: { color: MUTED } },
  ], { x: 0.9, y: 5.35, w: 11.6, h: 1.0, fontSize: 13.5, valign: "middle", fontFace: BF, margin: 0 });
}

/* ─── S5 평가 방법 ─── */
{
  const s = content("어떻게 성능을 쟀나", "평가 방법");
  card(s, 0.6, 1.8, 5.9, 4.3); accentTab(s, 0.6, 1.8, 4.3, TEAL);
  s.addText("문제지 만들기", { x: 0.95, y: 2.0, w: 5.4, h: 0.4, fontSize: 16.5, bold: true, color: NAVY, fontFace: HF, margin: 0 });
  s.addText([
    { text: "영상 7개 · 질문 135개", options: { bullet: true, breakLine: true, bold: true } },
    { text: "정답은 사람이 화면을 직접 보고 표시", options: { bullet: true, breakLine: true } },
    { text: "자막 글자를 믿지 않고 프레임 실물로 확인", options: { bullet: true, indentLevel: 1, breakLine: true, color: MUTED } },
    { text: "질문을 세 종류로 나눠 집계:", options: { bullet: true, breakLine: true } },
    { text: "말로 찾는 것 / 화면으로 찾는 것 / 둘 다", options: { bullet: true, indentLevel: 1, color: MUTED } },
  ], { x: 1.0, y: 2.55, w: 5.2, h: 3.5, fontSize: 13.5, color: INK, fontFace: BF, paraSpaceAfter: 9, valign: "top", margin: 0 });

  card(s, 6.85, 1.8, 5.9, 4.3); accentTab(s, 6.85, 1.8, 4.3, BLUE);
  s.addText("공정하게 채점하기", { x: 7.2, y: 2.0, w: 5.4, h: 0.4, fontSize: 16.5, bold: true, color: NAVY, fontFace: HF, margin: 0 });
  s.addText([
    { text: "연습용 영상과 채점용 영상을 분리", options: { bullet: true, breakLine: true, bold: true } },
    { text: "설정은 연습용에서만 맞춘다", options: { bullet: true, breakLine: true } },
    { text: "설정을 확정한 뒤, 채점용 39문항으로 딱 한 번 평가", options: { bullet: true, breakLine: true } },
    { text: "→ 시험 문제를 미리 보고 맞추는 일이 없음", options: { bullet: true, indentLevel: 1, color: TEAL, bold: true } },
  ], { x: 7.25, y: 2.55, w: 5.2, h: 2.9, fontSize: 13.5, color: INK, fontFace: BF, paraSpaceAfter: 9, valign: "top", margin: 0 });
  card(s, 6.85, 5.05, 5.9, 1.05, "EEF4F8");
  s.addText([
    { text: "점수 읽는 법   ", options: { bold: true, color: BLUE, fontFace: HF } },
    { text: "정답을 위에 보여줄수록 높은 점수 (1점 만점)", options: { color: INK } },
  ], { x: 7.1, y: 5.05, w: 5.5, h: 1.05, fontSize: 12.5, align: "left", valign: "middle", fontFace: BF, margin: 0 });
}

/* ─── S6 핵심 결과 ─── */
{
  const s = content("결과: 검색 정확도가 크게 올랐다", "결과");
  const stat = (x, lbl, base, prop, sub) => {
    card(s, x, 1.8, 3.85, 2.05);
    s.addText(lbl, { x, y: 1.95, w: 3.85, h: 0.35, fontSize: 14, bold: true, color: MUTED, align: "center", fontFace: HF, margin: 0 });
    s.addText([{ text: base + "  ", options: { color: MUTED, fontSize: 17 } }, { text: "→ " + prop, options: { color: NAVY, fontSize: 30, bold: true } }], { x, y: 2.4, w: 3.85, h: 0.7, align: "center", valign: "middle", fontFace: MONO, margin: 0 });
    s.addText(sub, { x, y: 3.25, w: 3.85, h: 0.5, fontSize: 11, color: TEAL, align: "center", fontFace: BF, margin: 0 });
  };
  stat(0.6, "전체 정확도", "0.65", "0.83", "확실히 좋아짐");
  stat(4.7, "첫 결과가 정답일 확률", "0.56", "0.77", "확실히 좋아짐");
  stat(8.8, "보여주기만 한 장면", "0.17", "0.72", "가장 큰 개선");

  s.addChart(p.charts.BAR, [
    { name: "지금까지 (자막만)", labels: ["말 위주 질문", "화면 위주 질문", "둘 다", "전체"], values: [0.958, 0.174, 0.825, 0.649] },
    { name: "본 연구 (자막+화면)", labels: ["말 위주 질문", "화면 위주 질문", "둘 다", "전체"], values: [0.880, 0.718, 0.887, 0.829] },
  ], {
    x: 0.6, y: 4.1, w: 12.15, h: 2.6, barDir: "col",
    chartColors: [MUTED, TEAL], showLegend: true, legendPos: "t", legendColor: INK, legendFontFace: BF,
    chartArea: { fill: { color: LIGHT } }, showValue: true, dataLabelPosition: "outEnd", dataLabelColor: INK, dataLabelFontSize: 10, dataLabelFormatCode: "0.00",
    catAxisLabelColor: INK, catAxisLabelFontFace: BF, catAxisLabelFontSize: 12,
    valAxisLabelColor: MUTED, valAxisHidden: false, valGridLine: { color: "E2E8F0", size: 0.5 }, valAxisMaxVal: 1, valAxisMinVal: 0,
  });
  s.addText("* 채점용 39문항 기준. 작은 규모라 일부 지표는 '확실히 좋아졌다'까지만 말하고 과장하지 않음", { x: 0.6, y: 6.72, w: 12.2, h: 0.3, fontSize: 10.5, color: MUTED, italic: true, fontFace: BF, margin: 0 });
}

/* ─── S7 결과 해석 ─── */
{
  const s = content("이 결과가 의미하는 것", "해석");
  const items = [
    ["못 찾던 장면을 찾는다", "자막만으로는 원리상 찾을 수 없던 '보여주기만 한 장면'(전체 질문의 1/3)을 이제 찾아낸다. 0.17 → 0.72로 가장 크게 좋아진 부분.", TEAL],
    ["잘하던 것을 안 망친다", "자막이 이미 잘 찾던 질문도 거의 그대로 유지된다(0.96 → 0.88). 화면 설명을 더해도 손해가 거의 없는 '균형점'을 찾았다는 것이 핵심.", NAVY],
    ["우연이 아니다", "여행·요리·홍보·테크 4개 영상 모두 비슷하게 좋아졌다. 특정 영상에서만 잘 되는 것이 아니라 고르게 통한다.", BLUE],
  ];
  let y = 1.9; const hh = 1.45;
  items.forEach(it => {
    card(s, 0.6, y, 12.15, hh); accentTab(s, 0.6, y, hh, it[2]);
    s.addText(it[0], { x: 0.95, y: y + 0.14, w: 3.7, h: hh - 0.25, fontSize: 16, bold: true, color: NAVY, valign: "middle", fontFace: HF, margin: 0 });
    s.addText(it[1], { x: 4.75, y: y + 0.14, w: 7.8, h: hh - 0.25, fontSize: 13.5, color: INK, valign: "middle", fontFace: BF, margin: 0 });
    y += hh + 0.2;
  });
}

/* ─── S8 한계 ─── */
{
  const s = content("솔직한 한계", "한계");
  s.addText("실제로 써 보며 찾아낸 약점 — 원인과 해결책까지 확인했다", { x: 0.6, y: 1.68, w: 12.2, h: 0.35, fontSize: 14, italic: true, color: BLUE, fontFace: BF, margin: 0 });
  const box = (x, t, b) => {
    card(s, x, 2.15, 5.9, 2.6);
    s.addText(t, { x: x + 0.28, y: 2.32, w: 5.5, h: 0.4, fontSize: 15.5, bold: true, color: NAVY, fontFace: HF, margin: 0 });
    s.addText(b, { x: x + 0.3, y: 2.85, w: 5.4, h: 1.75, fontSize: 12.5, color: INK, fontFace: BF, valign: "top", paraSpaceAfter: 6, margin: 0 });
  };
  box(0.6, "① 같은 뜻, 다른 단어", [
    { text: "'초밥'으로 검색하면 화면 설명이 '스시'인 장면을 놓칠 수 있다", options: { bullet: true, breakLine: true } },
    { text: "해결: 검색어에 비슷한 말을 함께 넣어주면 복구됨(확인함)", options: { bullet: true, bold: true, color: TEAL } },
  ]);
  box(6.85, "② 말했지만 안 보이는 것", [
    { text: "자막엔 '다진 마늘'이 있어도 마늘 다지는 장면 자체는 없을 때 헷갈린다", options: { bullet: true, breakLine: true } },
    { text: "해결: 화면으로 다시 확인하는 단계 추가 (더 큰 모델 필요)", options: { bullet: true, bold: true, color: TEAL } },
  ]);
  card(s, 0.6, 5.05, 12.15, 1.15, "EEF4F8"); accentTab(s, 0.6, 5.05, 1.15, RED);
  s.addText([
    { text: "정직성   ", options: { bold: true, color: RED, fontFace: HF } },
    { text: "테스트 규모가 작아(39문항) 결과를 부풀리지 않았고, 틀린 사례도 숨기지 않고 그대로 공개한다.", options: { color: INK } },
  ], { x: 0.95, y: 5.05, w: 11.6, h: 1.15, fontSize: 13.5, valign: "middle", fontFace: BF, margin: 0 });
}

/* ─── S9 덤: 요약 리포트 ─── */
{
  const s = content("덤: 영상 요약 리포트 자동 생성", "확장 기능");
  s.addText("같은 검색 기능을 재활용해, 영상 전체를 요약한 보고서를 자동으로 만든다", { x: 0.6, y: 1.68, w: 12.2, h: 0.4, fontSize: 14.5, color: MUTED, fontFace: BF, margin: 0 });
  card(s, 0.6, 2.35, 5.9, 2.6); accentTab(s, 0.6, 2.35, 2.6, TEAL);
  s.addText("무엇을 만드나", { x: 0.95, y: 2.52, w: 5.4, h: 0.4, fontSize: 15.5, bold: true, color: NAVY, fontFace: HF, margin: 0 });
  s.addText([
    { text: "영상 내용을 정리한 요약 리포트", options: { bullet: true, breakLine: true } },
    { text: "모든 문장에 출처(몇 분 몇 초)를 붙인다", options: { bullet: true, breakLine: true } },
    { text: "→ 근거 없이 지어내는 것을 방지", options: { bullet: true, indentLevel: 1, color: TEAL, bold: true } },
  ], { x: 1.0, y: 3.05, w: 5.3, h: 1.85, fontSize: 13, color: INK, fontFace: BF, paraSpaceAfter: 7, valign: "top", margin: 0 });

  card(s, 6.85, 2.35, 5.9, 2.6); accentTab(s, 6.85, 2.35, 2.6, BLUE);
  s.addText("품질을 어떻게 믿나", { x: 7.2, y: 2.52, w: 5.4, h: 0.4, fontSize: 15.5, bold: true, color: NAVY, fontFace: HF, margin: 0 });
  s.addText([
    { text: "별도 검사기가 두 가지를 점검:", options: { bullet: true, breakLine: true } },
    { text: "중요한 내용을 빠뜨렸나", options: { bullet: true, indentLevel: 1, breakLine: true, color: MUTED } },
    { text: "없는 내용을 지어냈나", options: { bullet: true, indentLevel: 1, breakLine: true, color: MUTED } },
    { text: "리포트를 쓴 AI와 다른 AI가 검사(제 자랑 방지)", options: { bullet: true } },
  ], { x: 7.25, y: 3.05, w: 5.3, h: 1.85, fontSize: 13, color: INK, fontFace: BF, paraSpaceAfter: 6, valign: "top", margin: 0 });

  card(s, 0.6, 5.1, 12.15, 1.1, "EEF4F8"); accentTab(s, 0.6, 5.1, 1.1, RED);
  s.addText([
    { text: "현재 상태   ", options: { bold: true, color: RED, fontFace: HF } },
    { text: "설계·구현·기본 검증 완료. 큰 모델 실행은 서버 GPU 확보를 기다리는 중.", options: { color: INK } },
  ], { x: 0.95, y: 5.1, w: 11.6, h: 1.1, fontSize: 13.5, valign: "middle", fontFace: BF, margin: 0 });
}

/* ─── S10 결론 ─── */
{
  const s = dark();
  s.addShape(p.shapes.RECTANGLE, { x: 0.9, y: 1.5, w: 0.9, h: 0.09, fill: { color: TEAL } });
  s.addText("결론", { x: 0.9, y: 1.7, w: 11, h: 0.7, fontSize: 34, bold: true, color: WHITE, fontFace: HF, margin: 0 });
  s.addText([
    { text: "화면 설명을 더해 ", options: { color: "CFE0EC" } },
    { text: "못 찾던 장면(전체의 1/3)을 찾으면서,", options: { color: TEAL, bold: true } },
    { text: " 기존 강점은 지켰다", options: { color: "CFE0EC" } },
  ], { x: 0.95, y: 2.8, w: 11.5, h: 0.9, fontSize: 21, fontFace: BF, lineSpacingMultiple: 1.15, margin: 0 });
  s.addText("큰 수치를 좇기보다, 작은 규모에서도 믿을 수 있게 '주장한 것만 정확히' 검증했다.", { x: 0.95, y: 3.9, w: 11.5, h: 0.5, fontSize: 15, color: "E4EEF5", fontFace: BF, margin: 0 });
  const st = (x, big, lbl) => {
    s.addText(big, { x, y: 5.05, w: 3.7, h: 0.7, fontSize: 28, bold: true, color: TEAL, align: "center", fontFace: MONO, margin: 0 });
    s.addText(lbl, { x, y: 5.8, w: 3.7, h: 0.4, fontSize: 12.5, color: "9FBBD0", align: "center", fontFace: BF, margin: 0 });
  };
  st(0.95, "0.65 → 0.83", "전체 검색 정확도");
  st(4.85, "0.17 → 0.72", "보여주기만 한 장면");
  st(8.75, "6GB GPU", "개인 PC 수준에서 동작");
  s.addText("Q & A", { x: 0.95, y: 6.65, w: 11, h: 0.4, fontSize: 15, bold: true, color: "8FB0C6", fontFace: HF, margin: 0 });
}

p.writeFile({ fileName: "docs/presentation/중간발표_2026-07-13.pptx" }).then(f => console.log("생성:", f));
