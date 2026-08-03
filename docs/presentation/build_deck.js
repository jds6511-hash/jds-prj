const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.layout = "LAYOUT_WIDE";            // 13.33 x 7.5
p.title = "통합 상황보고서 자동 생성 시스템 (진행상황 발표)";

const W = 13.33, H = 7.5;
const NAVY = "0F2A43", NAVY2 = "16395C", TEAL = "18B7A6", BLUE = "2E7FA6", RED = "C0392B";
const LIGHT = "F5F8FB", INK = "1E2A38", MUTED = "6B7C8E", WHITE = "FFFFFF", LINE = "D9E2EC";
const HF = "맑은 고딕", BF = "맑은 고딕", MONO = "Consolas";

let pageNo = 0;
function footer(s, dark) {
  const c = dark ? "8FB0C6" : MUTED;
  s.addText("통합 상황보고서 자동 생성 시스템 · 진행상황 발표", { x: 0.5, y: H - 0.42, w: 7, h: 0.3, fontSize: 9, color: c, fontFace: BF, align: "left", margin: 0 });
  s.addText(`${pageNo}`, { x: W - 1.0, y: H - 0.42, w: 0.5, h: 0.3, fontSize: 9, color: c, fontFace: BF, align: "right", margin: 0 });
}
function content(titleText, kicker) {
  pageNo++;
  const s = p.addSlide();
  s.background = { color: LIGHT };
  s.addShape(p.shapes.RECTANGLE, { x: 0, y: 0, w: 0.22, h: H, fill: { color: TEAL } });
  if (kicker) s.addText(kicker.toUpperCase(), { x: 0.6, y: 0.42, w: 12, h: 0.3, fontSize: 11, color: TEAL, bold: true, charSpacing: 2, fontFace: BF, margin: 0 });
  s.addText(titleText, { x: 0.58, y: 0.72, w: 12.2, h: 0.75, fontSize: 28, bold: true, color: NAVY, fontFace: HF, margin: 0 });
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
function badge(s, x, y, text, color) {
  s.addShape(p.shapes.RECTANGLE, { x, y, w: 1.05, h: 0.34, fill: { color } });
  s.addText(text, { x, y, w: 1.05, h: 0.34, fontSize: 10.5, bold: true, color: WHITE, align: "center", valign: "middle", fontFace: BF, margin: 0 });
}

/* ─── S1 표지 ─── */
{
  const s = dark();
  s.addShape(p.shapes.RECTANGLE, { x: 0, y: 1.95, w: 0.9, h: 0.09, fill: { color: TEAL } });
  s.addText("음성·영상 멀티모달 LLM을 활용한\n통합 상황보고서 자동 생성 시스템 구축", { x: 0.9, y: 2.15, w: 11.5, h: 1.65, fontSize: 32, bold: true, color: WHITE, fontFace: HF, lineSpacingMultiple: 1.1, margin: 0 });
  s.addText([
    { text: "영상 속 ", options: { color: "CFE0EC" } },
    { text: "말(음성)과 화면(영상)", options: { color: TEAL, bold: true } },
    { text: "을 함께 이해해서, 사람 대신 상황을 정리한 보고서를 쓰는 AI를 만듭니다", options: { color: "CFE0EC" } },
  ], { x: 0.95, y: 4.15, w: 11.5, h: 0.7, fontSize: 15.5, fontFace: BF, lineSpacingMultiple: 1.2, margin: 0 });
  s.addText("진행상황 발표 · 2026-07-31", { x: 0.95, y: 6.5, w: 11.5, h: 0.4, fontSize: 14, bold: true, color: WHITE, fontFace: HF, margin: 0 });
}

/* ─── 실험 슬라이드 공용 부품 ─── */
// 질의 유형별 before→after 비교 카드 (한 장에 3개 나란히)
function typeStat(s, x, y, label, before, after, worse) {
  card(s, x, y, 3.85, 1.62); accentTab(s, x, y, 1.62, worse ? RED : MUTED);
  s.addText(label, { x: x + 0.25, y: y + 0.18, w: 3.4, h: 0.35, fontSize: 13.5, bold: true, color: NAVY, fontFace: HF, margin: 0 });
  s.addText([
    { text: before, options: { color: MUTED, fontSize: 19 } },
    { text: "  →  ", options: { color: MUTED, fontSize: 14 } },
    { text: after, options: { color: worse ? RED : MUTED, fontSize: 27, bold: true } },
  ], { x: x + 0.25, y: y + 0.58, w: 3.4, h: 0.55, valign: "middle", fontFace: MONO, margin: 0 });
  s.addText(worse ? "떨어짐" : "사실상 그대로", { x: x + 0.25, y: y + 1.16, w: 3.4, h: 0.3, fontSize: 11, color: worse ? RED : MUTED, fontFace: BF, margin: 0 });
}
// 점수(MRR)가 무슨 뜻인지 — 숫자가 처음 나오는 장마다 한 줄로 명시
const MRR_NOTE = "점수 = MRR — 정답 장면이 검색 결과 몇 번째에 나오는지. 1등이면 1.0, 2등 0.5, 3등 0.33 (1.0이 만점)";
// 같은 장면을 두 모델이 각각 어떻게 설명했는지 비교
function capRow(s, y, who, text, color) {
  s.addText(who, { x: 0.95, y, w: 1.75, h: 0.4, fontSize: 11.5, bold: true, color, valign: "middle", fontFace: HF, margin: 0 });
  s.addText(text, { x: 2.8, y, w: 9.7, h: 0.4, fontSize: 11.5, color: INK, valign: "middle", fontFace: BF, margin: 0 });
}
function verdict(s, y, h, head, parts) {
  card(s, 0.6, y, 12.15, h, "EEF4F8"); accentTab(s, 0.6, y, h, RED);
  s.addText([{ text: head + "   ", options: { bold: true, color: RED, fontFace: HF } }, ...parts],
    { x: 0.95, y, w: 11.6, h, fontSize: 12.5, valign: "middle", fontFace: BF, lineSpacingMultiple: 1.15, margin: 0 });
}

/* ─── S2 왜 화면 설명 모델을 바꿔보려 했나 ─── */
{
  const s = content("이번 주 한 일 — 왜 '화면 설명' 모델을 바꿔보려 했나", "이번 주 진행");
  s.addText("지금 시스템에서 가장 약한 부분이 어디인지부터 확인하고, 그 부분을 겨냥해 실험했다", { x: 0.6, y: 1.63, w: 12.2, h: 0.35, fontSize: 14, color: MUTED, fontFace: BF, margin: 0 });

  card(s, 0.6, 2.15, 5.9, 2.9); accentTab(s, 0.6, 2.15, 2.9, RED);
  s.addText("약한 부분 — 화면으로 찾는 질문", { x: 0.95, y: 2.28, w: 5.4, h: 0.36, fontSize: 16, bold: true, color: NAVY, fontFace: HF, margin: 0 });
  s.addText("점수 = MRR · 1.0 만점 (1등 1.0, 2등 0.5, 3등 0.33)", { x: 0.95, y: 2.66, w: 5.3, h: 0.26, fontSize: 10.5, italic: true, color: MUTED, fontFace: BF, margin: 0 });
  const rows = [["말로 찾는 질문", "0.79", false], ["둘 다 필요한 질문", "0.79", false], ["화면으로 찾는 질문", "0.49", true]];
  rows.forEach((r, i) => {
    const y = 2.98 + i * 0.54;
    s.addText(r[0], { x: 1.0, y, w: 3.4, h: 0.42, fontSize: 13, color: r[2] ? RED : INK, bold: r[2], valign: "middle", fontFace: BF, margin: 0 });
    s.addText(r[1], { x: 4.5, y, w: 1.7, h: 0.42, fontSize: r[2] ? 22 : 18, bold: true, color: r[2] ? RED : MUTED, align: "right", valign: "middle", fontFace: MONO, margin: 0 });
  });
  s.addText("→ 연습용 영상 기준. 말없이 보여주기만 한 장면이 유독 낮다", { x: 1.0, y: 4.62, w: 5.2, h: 0.3, fontSize: 11.5, italic: true, color: RED, fontFace: BF, margin: 0 });

  card(s, 6.85, 2.15, 5.9, 2.9); accentTab(s, 6.85, 2.15, 2.9, TEAL);
  s.addText("세운 가설과 후보 모델", { x: 7.2, y: 2.32, w: 5.4, h: 0.4, fontSize: 16, bold: true, color: NAVY, fontFace: HF, margin: 0 });
  s.addText([
    { text: "이 질문들은 화면 설명(캡션) 품질에만 의존한다", options: { bullet: true, breakLine: true, bold: true } },
    { text: "→ 눈 역할 모델을 더 좋은 것으로 바꾸면 오를까?", options: { bullet: true, breakLine: true, color: TEAL, bold: true } },
    { text: "후보 ① VARCO-VISION-2.0 — 국산 영상이해 특화 모델", options: { bullet: true, breakLine: true } },
    { text: "후보 ② Qwen3-VL-4B — 같은 회사의 최신 세대 모델", options: { bullet: true } },
  ], { x: 7.25, y: 2.82, w: 5.3, h: 2.1, fontSize: 12.5, color: INK, fontFace: BF, paraSpaceAfter: 9, valign: "top", margin: 0 });

  card(s, 0.6, 5.25, 12.15, 1.15, "EEF4F8"); accentTab(s, 0.6, 5.25, 1.15, BLUE);
  s.addText([
    { text: "실험 규칙   ", options: { bold: true, color: BLUE, fontFace: HF } },
    { text: "두 실험 모두 ", options: { color: INK } },
    { text: "연습용 영상(3개·질문 96개)에서만 비교했고, 채점용 39문항은 건드리지 않았다", options: { color: NAVY, bold: true } },
    { text: ". 기존 화면 설명과 새 화면 설명을 같은 질문·같은 방식으로 나란히 채점해, 순수하게 '설명 품질' 차이만 보이도록 했다.", options: { color: INK } },
  ], { x: 0.95, y: 5.25, w: 11.6, h: 1.15, fontSize: 12.5, valign: "middle", fontFace: BF, lineSpacingMultiple: 1.15, margin: 0 });
}

/* ─── S3 실험 1: VARCO ─── */
{
  const s = content("실험 ① VARCO-VISION-2.0 — 국산 영상이해 특화 모델", "실험 결과");
  s.addText("결과: 기대했던 개선이 없었다 — 우연일 수 있는 차이지만 방향이 마이너스   (연습용 영상 96문항 기준)", { x: 0.6, y: 1.63, w: 12.2, h: 0.35, fontSize: 14, color: MUTED, fontFace: BF, margin: 0 });
  s.addText(MRR_NOTE, { x: 0.6, y: 1.99, w: 12.2, h: 0.26, fontSize: 11.5, italic: true, color: BLUE, fontFace: BF, margin: 0 });

  typeStat(s, 0.6, 2.32, "말로 찾는 질문", "0.79", "0.63", true);
  typeStat(s, 4.75, 2.32, "화면으로 찾는 질문", "0.49", "0.49", false);
  typeStat(s, 8.9, 2.32, "둘 다 필요한 질문", "0.79", "0.77", true);

  card(s, 0.6, 4.1, 12.15, 1.5);
  s.addText("같은 장면을 두 모델이 각각 어떻게 설명했나 (발굴 현장 장면)", { x: 0.95, y: 4.22, w: 11.6, h: 0.3, fontSize: 12.5, bold: true, color: NAVY, fontFace: HF, margin: 0 });
  capRow(s, 4.58, "기존 (Qwen2.5-VL)", "화면에는 토양으로 이루어진 바닥이 보이며, 바닥 위에는 여러 개의 돌멩이들이 놓여 있습니다…", MUTED);
  capRow(s, 5.05, "VARCO", "흙으로 된 들판에서 흰색 선으로 무언가를 표시하고 있는 모습이며, 배경에는 텐트와 산들이 보입니다.", RED);

  verdict(s, 5.76, 0.95, "판단: 기각", [
    { text: "정작 노렸던 '화면으로 찾는 질문'은 0.49 → 0.49로 사실상 그대로", options: { color: NAVY, bold: true } },
    { text: "고, 오히려 다른 유형이 떨어졌다. 설명이 짧고 구조적이라 검색이 기대하는 문장 형태와 어긋난 것으로 보인다. 이미지 축소 등 우리 쪽 설정 문제인지도 따로 확인했지만 원인이 아니었다.", options: { color: INK } },
  ]);
}

/* ─── S4 실험 2: Qwen3-VL ─── */
{
  const s = content("실험 ② Qwen3-VL-4B — 같은 회사의 최신 세대 모델", "실험 결과");
  s.addText("결과: 모든 유형에서 떨어졌다 — 통계적으로도 확실한 하락   (연습용 영상 96문항 기준)", { x: 0.6, y: 1.63, w: 12.2, h: 0.35, fontSize: 14, color: MUTED, fontFace: BF, margin: 0 });
  s.addText(MRR_NOTE, { x: 0.6, y: 1.99, w: 12.2, h: 0.26, fontSize: 11.5, italic: true, color: BLUE, fontFace: BF, margin: 0 });

  typeStat(s, 0.6, 2.32, "말로 찾는 질문", "0.79", "0.62", true);
  typeStat(s, 4.75, 2.32, "화면으로 찾는 질문", "0.49", "0.38", true);
  typeStat(s, 8.9, 2.32, "둘 다 필요한 질문", "0.79", "0.66", true);

  card(s, 0.6, 4.1, 12.15, 1.8);
  s.addText("설명 품질은 좋아 보였지만, 일부에서 같은 단어를 수십 번 반복하는 오작동이 났다", { x: 0.95, y: 4.22, w: 11.6, h: 0.3, fontSize: 12.5, bold: true, color: NAVY, fontFace: HF, margin: 0 });
  capRow(s, 4.58, "기존 (Qwen2.5-VL)", "화면에는 토양으로 이루어진 바닥이 보이며, 바닥 위에는 여러 개의 돌멩이들이 놓여 있습니다…", MUTED);
  capRow(s, 5.0, "Qwen3-VL (정상)", "건조한 흙 위에 돌들이 놓여 있고, 그 위에 흰색 선이 그려져 있는 발굴 현장…", BLUE);
  capRow(s, 5.42, "Qwen3-VL (오작동)", "창문 너머에 희미한 희미한 희미한 희미한 희미한 희미한 희미한 …  (655개 중 22개에서 발생, 기존은 0개)", RED);

  verdict(s, 6.05, 0.85, "판단: 기각", [
    { text: "설명 자체는 오히려 더 정확한 경우도 있었지만", options: { color: NAVY, bold: true } },
    { text: ", 반복 오작동이 섞이면 그 장면은 검색에서 사실상 버려진다. 여기에 문체 차이까지 겹쳐 전체 정확도가 0.67 → 0.54로 떨어졌다.", options: { color: INK } },
  ]);
}

/* ─── S5 두 실험에서 배운 것 ─── */
{
  const s = content("두 실험에서 배운 것", "정리");
  s.addText("'더 좋다고 알려진 모델'로 바꾸는 것만으로는 이 시스템이 좋아지지 않는다", { x: 0.6, y: 1.63, w: 12.2, h: 0.35, fontSize: 14, color: MUTED, fontFace: BF, margin: 0 });

  const lessons = [
    ["1", "순위표 성적 ≠ 우리 작업 성적", "두 후보 모두 일반 성능표에서는 상위권이다. 하지만 우리가 필요한 건 '한 문장 한국어 설명'이라는 아주 좁은 작업이고, 여기서는 밀렸다.", RED],
    ["2", "설명 지시문은 모델마다 다시 맞춰야 한다", "지금 쓰는 설명 지시문은 기존 모델에 맞춰 고른 것이다. 모델을 바꾸면 이것도 다시 맞춰야 하는데, 그대로 이식해서 불리했다.", BLUE],
    ["3", "품질이 좋아도 안정성이 깨지면 손해", "Qwen3-VL은 설명이 더 정확한 경우도 있었지만, 22개에서 난 반복 오작동이 이득을 상쇄했다.", NAVY],
  ];
  lessons.forEach((l, i) => {
    const x = 0.6 + i * 4.15;
    card(s, x, 2.2, 3.85, 2.6); accentTab(s, x, 2.2, 2.6, l[3]);
    s.addShape(p.shapes.OVAL, { x: x + 0.28, y: 2.4, w: 0.6, h: 0.6, fill: { color: l[3] } });
    s.addText(l[0], { x: x + 0.28, y: 2.4, w: 0.6, h: 0.6, fontSize: 18, bold: true, color: WHITE, align: "center", valign: "middle", fontFace: MONO, margin: 0 });
    s.addText(l[1], { x: x + 0.28, y: 3.1, w: 3.3, h: 0.75, fontSize: 13.5, bold: true, color: NAVY, valign: "top", fontFace: HF, margin: 0 });
    s.addText(l[2], { x: x + 0.28, y: 3.88, w: 3.3, h: 0.85, fontSize: 11.5, color: INK, valign: "top", fontFace: BF, margin: 0 });
  });

  card(s, 0.6, 5.05, 12.15, 1.3, "EEF4F8"); accentTab(s, 0.6, 5.05, 1.3, TEAL);
  s.addText([
    { text: "그래서 다음은   ", options: { bold: true, color: TEAL, fontFace: HF } },
    { text: "이번 주 랩실 서버 GPU 사용이 확정됐다. ", options: { color: INK } },
    { text: "① 문체가 바뀔 위험이 없는 같은 계열의 더 큰 모델(Qwen2.5-VL-7B)부터", options: { color: NAVY, bold: true } },
    { text: " 시도하고, ", options: { color: INK } },
    { text: "② 최신 세대(Qwen3-VL)는 설명 지시문까지 그 모델에 맞게 새로 설계한 파이프라인으로", options: { color: NAVY, bold: true } },
    { text: " 별도 시도한다 — 이번에 배운 두 번째·세 번째 교훈을 그대로 반영한 계획이다.", options: { color: INK } },
  ], { x: 0.95, y: 5.05, w: 11.6, h: 1.3, fontSize: 12.5, valign: "middle", fontFace: BF, lineSpacingMultiple: 1.15, margin: 0 });
}

/* ─── S8 상황보고서: 아직 실행 전 ─── */
{
  const s = content("상황보고서 자동 생성 — 아직 실행 전", "현재 상태");
  s.addText([
    { text: "이 연구의 최종 목표지만, ", options: { color: INK } },
    { text: "GPU 한계로 실제 실행은 아직 못 했다", options: { color: RED, bold: true } },
    { text: " — 솔직하게 밝힌다", options: { color: INK } },
  ], { x: 0.6, y: 1.65, w: 12.2, h: 0.4, fontSize: 14.5, fontFace: BF, margin: 0 });

  card(s, 0.6, 2.35, 5.9, 3.6); accentTab(s, 0.6, 2.35, 3.6, RED);
  s.addText("왜 아직 못 했나", { x: 0.95, y: 2.52, w: 5.4, h: 0.4, fontSize: 16, bold: true, color: NAVY, fontFace: HF, margin: 0 });
  s.addText([
    { text: "좋은 보고서를 쓰려면 더 큰 언어모델(LLM)이 필요하다", options: { bullet: true, breakLine: true, bold: true } },
    { text: "지금 쓸 수 있는 GPU는 6GB — 필요한 크기의 모델을 올리면 용량 초과", options: { bullet: true, breakLine: true } },
    { text: "더 작은 모델로 낮춰서 시도해봤지만, 결과 품질이 크게 떨어지는 것을 확인(예시 문장을 베끼는 등)", options: { bullet: true, indentLevel: 1, breakLine: true, color: MUTED } },
    { text: "→ 이번 주 랩실 서버 GPU 사용이 확정돼, 다음 주부터 실행 가능", options: { bullet: true, color: TEAL, bold: true } },
  ], { x: 1.0, y: 3.05, w: 5.3, h: 2.8, fontSize: 12.5, color: INK, fontFace: BF, paraSpaceAfter: 9, valign: "top", margin: 0 });

  card(s, 6.85, 2.35, 5.9, 3.6); accentTab(s, 6.85, 2.35, 3.6, TEAL);
  s.addText("무엇은 이미 준비됐나", { x: 7.2, y: 2.52, w: 5.4, h: 0.4, fontSize: 16, bold: true, color: NAVY, fontFace: HF, margin: 0 });
  s.addText([
    { text: "보고서를 어떻게 쓰게 할지 설계 완료", options: { bullet: true, breakLine: true, bold: true } },
    { text: "모든 문장에 근거(몇 분 몇 초)를 붙이도록 코드 작성 완료", options: { bullet: true, breakLine: true } },
    { text: "완성된 보고서를 자동으로 채점하는 도구도 미리 만들어둠", options: { bullet: true, breakLine: true } },
    { text: "(빠진 내용 없는지 / 근거 없이 지어내지 않았는지)", options: { bullet: true, indentLevel: 1, color: MUTED } },
    { text: "→ 실제로 돌려보는 것만 남았다", options: { bullet: true, color: TEAL, bold: true } },
  ], { x: 7.25, y: 3.05, w: 5.3, h: 2.8, fontSize: 12.5, color: INK, fontFace: BF, paraSpaceAfter: 8, valign: "top", margin: 0 });
}

/* ─── S9 다음 계획 ─── */
{
  const s = content("앞으로 2주 계획", "다음 단계");
  s.addText("랩실 서버 GPU 사용이 확정됐다 — 그동안 GPU 때문에 막혀 있던 항목부터 순서대로 처리한다", { x: 0.6, y: 1.63, w: 12.2, h: 0.35, fontSize: 14.5, color: MUTED, fontFace: BF, margin: 0 });
  const items = [
    ["1주차", "캡션 모델 크기 키우기", "같은 계열의 더 큰 모델(Qwen2.5-VL-7B)을 양자화 없이 올려, 화면 설명 품질과 검색 정확도가 오르는지 확인한다.", TEAL],
    ["1주차", "최신 세대 모델 재도전", "Qwen3-VL을 설명 방식(프롬프트)부터 이 모델에 맞게 다시 설계한 새 파이프라인으로 별도 시도한다.", TEAL],
    ["2주차", "상황보고서 실제 생성", "GPU 한계로 못 하던 2단계를 처음 실행한다 — 큰 언어모델로 근거(시각)를 붙인 보고서를 생성.", NAVY],
    ["2주차", "보고서 품질 검증", "미리 만들어 둔 자동 채점 도구로 평가하고(빠진 내용·지어낸 내용), 일부는 사람이 표본 확인한다.", BLUE],
  ];
  let y = 2.3; const hh = 0.95, gap = 0.13;
  items.forEach(it => {
    card(s, 0.6, y, 12.15, hh); accentTab(s, 0.6, y, hh, it[3]);
    badge(s, 0.9, y + hh / 2 - 0.17, it[0], it[3]);
    s.addText(it[1], { x: 2.1, y: y + 0.1, w: 2.75, h: hh - 0.2, fontSize: 14.5, bold: true, color: NAVY, valign: "middle", fontFace: HF, margin: 0 });
    s.addText(it[2], { x: 5.0, y: y + 0.1, w: 7.5, h: hh - 0.2, fontSize: 12, color: INK, valign: "middle", fontFace: BF, margin: 0 });
    y += hh + gap;
  });
  s.addText("모든 모델 교체 실험은 연습용 영상에서만 비교한 뒤, 확실히 좋아진 경우에만 채점용 평가로 넘어간다.", { x: 0.6, y: y + 0.1, w: 12.15, h: 0.35, fontSize: 12, italic: true, color: MUTED, fontFace: BF, margin: 0 });
}

/* ─── S10 결론 ─── */
{
  const s = dark();
  s.addShape(p.shapes.RECTANGLE, { x: 0.9, y: 1.4, w: 0.9, h: 0.09, fill: { color: TEAL } });
  s.addText("결론", { x: 0.9, y: 1.6, w: 11, h: 0.7, fontSize: 32, bold: true, color: WHITE, fontFace: HF, margin: 0 });
  s.addText([
    { text: "1단계(장면 찾기)는 ", options: { color: "CFE0EC" } },
    { text: "완성하고 성능까지 확인했고,", options: { color: TEAL, bold: true } },
    { text: " 2단계(상황보고서 자동생성)는 설계를 마친 상태다", options: { color: "CFE0EC" } },
  ], { x: 0.95, y: 2.7, w: 11.5, h: 0.9, fontSize: 19, fontFace: BF, lineSpacingMultiple: 1.2, margin: 0 });
  s.addText("랩실 서버 GPU 사용이 확정됐다 — 앞으로 2주간 더 큰 모델로 상황보고서를 실제 생성하고 품질까지 검증한다.", { x: 0.95, y: 3.75, w: 11.5, h: 0.5, fontSize: 14.5, color: "E4EEF5", fontFace: BF, margin: 0 });
  const st = (x, big, lbl, color) => {
    s.addText(big, { x, y: 4.95, w: 3.7, h: 0.7, fontSize: 26, bold: true, color: color || TEAL, align: "center", fontFace: MONO, margin: 0 });
    s.addText(lbl, { x, y: 5.68, w: 3.7, h: 0.6, fontSize: 12, color: "9FBBD0", align: "center", fontFace: BF, margin: 0 });
  };
  st(0.95, "0.65 → 0.83", "1단계 · 검색 정확도 (채점용 39문항)");
  st(4.85, "설계 완료", "2단계 · 상황보고서 생성", "E8B84B");
  st(8.75, "GPU 확보 완료", "2단계 · 2주 내 실행 예정", "E8B84B");
  s.addText("Q & A", { x: 0.95, y: 6.75, w: 11, h: 0.4, fontSize: 15, bold: true, color: "8FB0C6", fontFace: HF, margin: 0 });
}

p.writeFile({ fileName: "docs/presentation/진행상황발표_2026-07-31.pptx" }).then(f => console.log("생성:", f));
