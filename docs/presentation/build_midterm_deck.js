// 국방 AI·SW 프로젝트 중간성과발표회 (2026-08-21) 발표자료 생성기
// 평가표 6항목(문제정의10·데이터10·기술구현15·프로젝트관리5·군활용성5·발표력5)에 대응.
// 발표 10분 + 질의응답 10분 → 13슬라이드.
const pptxgen = require("pptxgenjs");

// ── 팔레트: 두 채널이 주제이므로 채널마다 고유색을 주고 그 외에는 절제한다 ──
const SLATE = "1F2A33";   // 지배색(60~70%) — 표지·섹션·마무리 배경
const PAPER = "F4F6F7";   // 본문 배경
const SPEECH = "3E7CB1";  // 채널 A: 발화(자막)
const VISION = "D98C3F";  // 채널 B: 화면(장면 설명)
const MUTED = "6B7A85";
const INK = "16202A";
const WHITE = "FFFFFF";

const HFONT = "Cambria";   // 제목 — 안전 목록 세리프
const BFONT = "Calibri";   // 본문 — 안전 목록 산세리프

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";           // 13.3 x 7.5 인치
pres.author = "국방 AI·SW 프로젝트 과정";
pres.title = "한국어 영상 모먼트 검색";

const W = 13.3, H = 7.5, M = 0.7;

// ── 공통 헬퍼 ────────────────────────────────────────────────────────
function titleSlide(s, kicker, title, sub) {
  s.background = { color: SLATE };
  s.addText(kicker, { x: M, y: 1.5, w: W - 2 * M, h: 0.4, fontFace: BFONT,
    fontSize: 14, color: VISION, charSpacing: 3, bold: true });
  s.addText(title, { x: M, y: 2.0, w: W - 2 * M, h: 1.6, fontFace: HFONT,
    fontSize: 44, bold: true, color: WHITE, lineSpacing: 52 });
  if (sub) s.addText(sub, { x: M, y: 3.8, w: W - 2 * M - 1.5, h: 1.2,
    fontFace: BFONT, fontSize: 17, color: "AEBDC7", lineSpacing: 28 });
}

function head(s, title, note) {
  s.background = { color: PAPER };
  s.addText(title, { x: M, y: 0.42, w: W - 2 * M, h: 0.80, fontFace: HFONT,
    fontSize: 32, bold: true, color: INK, margin: 0 });
  if (note) s.addText(note, { x: M, y: 1.22, w: W - 2 * M, h: 0.38,
    fontFace: BFONT, fontSize: 14, color: MUTED, margin: 0 });
}

function card(s, x, y, w, h, fill) {
  s.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.08,
    fill: { color: fill || WHITE },
    shadow: { type: "outer", color: "9AA8B2", blur: 8, offset: 1, angle: 90, opacity: 0.25 } });
}

function chip(s, x, y, label, color) {
  s.addShape(pres.ShapeType.roundRect, { x, y, w: 1.05, h: 0.32, rectRadius: 0.16,
    fill: { color } });
  s.addText(label, { x, y, w: 1.05, h: 0.32, fontFace: BFONT, fontSize: 11,
    bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
}

// ── 1. 표지 ──────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  titleSlide(s, "국방 AI·SW 프로젝트 과정 · 중간성과발표",
    "말이 없는 장면도 찾아내는\n한국어 영상 모먼트 검색",
    "영상 속 “그 장면”을 한국어 문장으로 검색한다.\n발화(자막)와 화면(장면 설명) 두 채널을 함께 색인해, 아무도 말하지 않은 순간까지 찾는다.");
  s.addText("2026. 8. 21.", { x: M, y: 6.3, w: 4, h: 0.4, fontFace: BFONT,
    fontSize: 13, color: MUTED });
  // 두 채널 모티프 — 표지에서 먼저 보여주고 이후 슬라이드에서 반복한다
  s.addShape(pres.ShapeType.roundRect, { x: 9.6, y: 2.2, w: 3.0, h: 0.5,
    rectRadius: 0.1, fill: { color: SPEECH } });
  s.addText("발화 채널", { x: 9.6, y: 2.2, w: 3.0, h: 0.5, fontFace: BFONT,
    fontSize: 13, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
  s.addShape(pres.ShapeType.roundRect, { x: 9.6, y: 2.85, w: 3.0, h: 0.5,
    rectRadius: 0.1, fill: { color: VISION } });
  s.addText("화면 채널", { x: 9.6, y: 2.85, w: 3.0, h: 0.5, fontFace: BFONT,
    fontSize: 13, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
  s.addText("두 채널을 하나의 점수로 융합", { x: 9.6, y: 3.5, w: 3.0, h: 0.4,
    fontFace: BFONT, fontSize: 12, color: "AEBDC7", align: "center", margin: 0 });
  s.addNotes("인사 후 한 문장으로: 영상에서 특정 순간을 한국어 문장으로 찾는 시스템입니다. 핵심은 말과 화면을 따로 색인해 합친다는 점입니다.");
}

// ── 2. 문제 정의 ─────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "문제 — 30분짜리 영상에서 “그 장면”을 어떻게 찾나",
    "평가항목: 문제 정의 및 기획성");
  const items = [
    ["지금은 사람이 직접 돌려본다", "재생·되감기를 반복해 눈으로 찾는다. 영상이 길수록, 편수가 많을수록 선형으로 시간이 늘어난다."],
    ["제목·설명으로는 못 찾는다", "메타데이터는 영상 전체를 요약할 뿐, 12분 30초의 한 장면을 가리키지 못한다."],
    ["자막 검색만으로는 절반만 찾는다", "말로 언급되지 않는 장면이 많다. 간판·표정·행동은 자막에 없다."],
  ];
  items.forEach(([t, d], i) => {
    const y = 1.75 + i * 1.55;
    card(s, M, y, W - 2 * M, 1.3);
    s.addShape(pres.ShapeType.ellipse, { x: M + 0.35, y: y + 0.38, w: 0.55, h: 0.55,
      fill: { color: i === 2 ? VISION : SLATE } });
    s.addText(String(i + 1), { x: M + 0.35, y: y + 0.38, w: 0.55, h: 0.55,
      fontFace: HFONT, fontSize: 18, bold: true, color: WHITE,
      align: "center", valign: "middle", margin: 0 });
    s.addText(t, { x: M + 1.15, y: y + 0.18, w: W - 2 * M - 1.6, h: 0.45,
      fontFace: HFONT, fontSize: 20, bold: true, color: INK, margin: 0 });
    s.addText(d, { x: M + 1.15, y: y + 0.63, w: W - 2 * M - 1.6, h: 0.55,
      fontFace: BFONT, fontSize: 14, color: MUTED, margin: 0 });
  });
  s.addText("→ 우리가 푸는 문제: 한국어 문장 하나로 영상 속 정확한 시각 구간을 찾아준다",
    { x: M, y: 6.5, w: W - 2 * M, h: 0.45, fontFace: BFONT, fontSize: 16,
      bold: true, color: SLATE, margin: 0 });
  s.addNotes("세 번째가 이 프로젝트의 출발점입니다. 자막만 쓰면 말하지 않은 장면을 놓칩니다.");
}

// ── 3. 왜 AI인가 ─────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "왜 AI가 필요한가 — 화면을 글로 바꿔야 한다",
    "평가항목: 문제 정의 및 기획성 (AI 도입 타당성)");
  card(s, M, 1.8, 5.9, 3.4);
  s.addText("규칙 기반으로 안 되는 이유", { x: M + 0.4, y: 2.05, w: 5.1, h: 0.4,
    fontFace: HFONT, fontSize: 19, bold: true, color: INK, margin: 0 });
  s.addText([
    { text: "장면은 픽셀이지 텍스트가 아니다 — 검색하려면 언어로 바꿔야 한다", options: { bullet: true, breakLine: true } },
    { text: "질의와 캡션이 다른 단어를 써도 통해야 한다 (초밥 ↔ 스시)", options: { bullet: true, breakLine: true } },
    { text: "한국어 구어체·발화 겹침을 다뤄야 한다", options: { bullet: true } },
  ], { x: M + 0.4, y: 2.55, w: 5.1, h: 2.3, fontFace: BFONT, fontSize: 14,
       color: INK, paraSpaceAfter: 10, margin: 0 });

  card(s, M + 6.3, 1.8, 5.9, 3.4);
  s.addText("그래서 쓰는 AI 세 가지", { x: M + 6.7, y: 2.05, w: 5.1, h: 0.4,
    fontFace: HFONT, fontSize: 19, bold: true, color: INK, margin: 0 });
  const ai = [
    ["음성 인식", "말 → 자막", SPEECH],
    ["비전-언어 모델", "화면 → 한국어 장면 설명", VISION],
    ["문장 임베딩", "의미가 비슷하면 가깝게", SLATE],
  ];
  ai.forEach(([n, d, c], i) => {
    const y = 2.6 + i * 0.78;
    s.addShape(pres.ShapeType.roundRect, { x: M + 6.7, y, w: 1.9, h: 0.5,
      rectRadius: 0.1, fill: { color: c } });
    s.addText(n, { x: M + 6.7, y, w: 1.9, h: 0.5, fontFace: BFONT, fontSize: 12.5,
      bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(d, { x: M + 8.75, y: y + 0.05, w: 3.1, h: 0.42, fontFace: BFONT,
      fontSize: 13.5, color: INK, valign: "middle", margin: 0 });
  });

  s.addShape(pres.ShapeType.roundRect, { x: M, y: 5.5, w: W - 2 * M, h: 1.15,
    rectRadius: 0.1, fill: { color: SLATE } });
  s.addText("핵심 설계 — 말과 화면을 따로 색인한 뒤 하나의 점수로 합친다. 한쪽이 비어도 다른 쪽이 찾는다.",
    { x: M + 0.4, y: 5.5, w: W - 2 * M - 0.8, h: 1.15, fontFace: BFONT,
      fontSize: 16, color: WHITE, valign: "middle", margin: 0 });
  s.addNotes("AI 도입 타당성 질문에 대비. 규칙으로는 픽셀을 언어로 못 바꿉니다.");
}

// ── 4. 파이프라인 전체 ───────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "전체 구조 — 9개 모듈, 세 단계",
    "평가항목: 기술구현 및 방법론 (아키텍처)");
  const stages = [
    { name: "① 영상을 잘게 나눈다", mods: "M1 · M2", color: SLATE,
      desc: "5초 단위로 자르고\n구간마다 대표 화면 1장 선택" },
    { name: "② 두 채널로 글을 만든다", mods: "M3 · M4", color: VISION,
      desc: "말 → 자막 / 화면 → 장면 설명\n각각 숫자 벡터로 색인" },
    { name: "③ 찾고 보여준다", mods: "M5 ~ M9", color: SPEECH,
      desc: "질의와 비교해 순위 매김\n웹 화면 · 요약 리포트" },
  ];
  stages.forEach((st, i) => {
    const x = M + i * 4.15;
    card(s, x, 1.85, 3.75, 3.3);
    s.addShape(pres.ShapeType.roundRect, { x: x + 0.35, y: 2.15, w: 1.35, h: 0.4,
      rectRadius: 0.2, fill: { color: st.color } });
    s.addText(st.mods, { x: x + 0.35, y: 2.15, w: 1.35, h: 0.4, fontFace: BFONT,
      fontSize: 12, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(st.name, { x: x + 0.35, y: 2.7, w: 3.05, h: 0.8, fontFace: HFONT,
      fontSize: 19, bold: true, color: INK, margin: 0 });
    s.addText(st.desc, { x: x + 0.35, y: 3.55, w: 3.05, h: 1.3, fontFace: BFONT,
      fontSize: 14, color: MUTED, lineSpacing: 22, margin: 0 });
    if (i < 2) s.addText("▶", { x: x + 3.82, y: 3.2, w: 0.3, h: 0.4,
      fontFace: BFONT, fontSize: 18, color: MUTED, align: "center", margin: 0 });
  });
  s.addText("색인은 영상마다 한 번만 만든다. 그 뒤로는 질문할 때마다 즉시 검색된다.",
    { x: M, y: 5.5, w: W - 2 * M, h: 0.4, fontFace: BFONT, fontSize: 15,
      color: INK, margin: 0 });
  s.addText("30분 영상 기준 색인 약 75분 · 검색 응답 1초 미만",
    { x: M, y: 5.95, w: W - 2 * M, h: 0.4, fontFace: BFONT, fontSize: 14,
      color: MUTED, margin: 0 });
  s.addNotes("여기서 큰 그림만 잡고 다음 두 장에서 모듈별로 풉니다.");
}

// ── 5. 모듈 역할 ① ───────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "모듈별 역할 ① — 색인 만들기", "M1 → M4");
  const mods = [
    ["M1", "영상 자르기", "5초 단위로 구간을 나눈다. 3·5·8·10초를 비교해 5초가 가장 좋았다.", SLATE],
    ["M2", "대표 화면 고르기", "구간마다 가장 대표적인 프레임 1장을 뽑는다. 움직임이 큰 순간을 우선한다.", SLATE],
    ["M3", "말·화면을 글로", "음성 인식으로 자막을, 비전-언어 모델로 장면 설명을 만든다.", VISION],
    ["M4", "숫자로 색인", "두 글을 각각 1024차원 벡터로 바꿔 저장한다. 의미가 가까우면 벡터도 가깝다.", SPEECH],
  ];
  mods.forEach(([id, t, d, c], i) => {
    const y = 1.8 + i * 1.22;
    card(s, M, y, W - 2 * M, 1.05);
    s.addShape(pres.ShapeType.roundRect, { x: M + 0.3, y: y + 0.22, w: 0.85, h: 0.6,
      rectRadius: 0.12, fill: { color: c } });
    s.addText(id, { x: M + 0.3, y: y + 0.22, w: 0.85, h: 0.6, fontFace: HFONT,
      fontSize: 17, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(t, { x: M + 1.4, y: y + 0.15, w: 2.6, h: 0.4, fontFace: HFONT,
      fontSize: 18, bold: true, color: INK, margin: 0 });
    s.addText(d, { x: M + 1.4, y: y + 0.55, w: W - 2 * M - 1.8, h: 0.4,
      fontFace: BFONT, fontSize: 13.5, color: MUTED, margin: 0 });
  });
  s.addNotes("M3이 이 프로젝트의 핵심이자 병목입니다. 다음 장에서 검색과 활용을 봅니다.");
}

// ── 6. 모듈 역할 ② ───────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "모듈별 역할 ② — 찾고 보여주기", "M5 → M9");
  const mods = [
    ["M5", "검색", "질의를 두 채널과 각각 비교해 가중합으로 한 점수를 만든다. 관련 없는 질의에는 경고를 띄운다.", SPEECH],
    ["M6", "평가", "정답 구간을 얼마나 위에 올렸는지 잰다. MRR·적중률·구간 겹침을 함께 본다.", SLATE],
    ["M7", "시연 화면", "영상을 올리고 질문하면 타임라인과 순위가 뜬다. 클릭하면 그 시각으로 이동한다.", SLATE],
    ["M8 · M9", "요약 리포트와 채점", "영상 전체를 요약해 근거 구간과 함께 제시하고, 그 요약이 실제 근거에 부합하는지 자동 채점한다.", VISION],
  ];
  mods.forEach(([id, t, d, c], i) => {
    const y = 1.8 + i * 1.22;
    card(s, M, y, W - 2 * M, 1.05);
    s.addShape(pres.ShapeType.roundRect, { x: M + 0.3, y: y + 0.22, w: 1.15, h: 0.6,
      rectRadius: 0.12, fill: { color: c } });
    s.addText(id, { x: M + 0.3, y: y + 0.22, w: 1.15, h: 0.6, fontFace: HFONT,
      fontSize: 15, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(t, { x: M + 1.7, y: y + 0.15, w: 3.2, h: 0.4, fontFace: HFONT,
      fontSize: 18, bold: true, color: INK, margin: 0 });
    s.addText(d, { x: M + 1.7, y: y + 0.55, w: W - 2 * M - 2.1, h: 0.4,
      fontFace: BFONT, fontSize: 13.5, color: MUTED, margin: 0 });
  });
  s.addNotes("M8은 군에서 말하는 사후검토(AAR) 리포트에 해당합니다. 뒤에서 다시 언급합니다.");
}

// ── 7. 데이터 ────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "데이터 — 직접 만들고, 제3자 데이터로 검증했다",
    "평가항목: 데이터 수집 및 전처리");
  const stats = [
    ["10편", "한국어 영상", "여행·요리·테크·홍보·농장·도예·등산"],
    ["2,173", "5초 구간", "구간마다 자막 + 장면 설명"],
    ["168건", "평가 질의", "학습용 96 · 최종평가용 72"],
    ["1,086건", "외부 검증 질의", "AI Hub 공개 데이터 194편"],
  ];
  stats.forEach(([n, t, d], i) => {
    const x = M + i * 3.06;
    card(s, x, 1.8, 2.75, 2.0);
    s.addText(n, { x: x + 0.2, y: 2.0, w: 2.35, h: 0.75, fontFace: HFONT,
      fontSize: 34, bold: true, color: i === 3 ? VISION : SLATE, margin: 0 });
    s.addText(t, { x: x + 0.2, y: 2.75, w: 2.35, h: 0.35, fontFace: BFONT,
      fontSize: 14, bold: true, color: INK, margin: 0 });
    s.addText(d, { x: x + 0.2, y: 3.1, w: 2.35, h: 0.6, fontFace: BFONT,
      fontSize: 11.5, color: MUTED, margin: 0 });
  });
  card(s, M, 4.05, W - 2 * M, 2.35);
  s.addText("전처리와 라벨링에서 지킨 규칙", { x: M + 0.4, y: 4.25, w: 11, h: 0.4,
    fontFace: HFONT, fontSize: 19, bold: true, color: INK, margin: 0 });
  s.addText([
    { text: "정답 라벨은 프레임 실물을 직접 보고 만든다 — 시스템이 만든 자막·장면 설명을 보고 정하지 않는다 (자기 답안 채점 방지)", options: { bullet: true, breakLine: true } },
    { text: "검색 결과를 본 뒤 정답을 고르거나 고치지 않는다", options: { bullet: true, breakLine: true } },
    { text: "깨진 장면 설명은 사람이 고르지 않고 자동 판정으로만 재생성한다 (선택 편향 차단)", options: { bullet: true, breakLine: true } },
    { text: "음성 인식이 무발화 구간에 만들어내는 환각 문구는 규칙으로 자동 제거한다", options: { bullet: true } },
  ], { x: M + 0.4, y: 4.7, w: 11.4, h: 1.6, fontFace: BFONT, fontSize: 13.5,
       color: INK, paraSpaceAfter: 7, margin: 0 });
  s.addNotes("라벨을 시스템 출력으로 만들면 평가가 무의미해집니다. 그래서 프레임 실물만 봅니다.");
}

// ── 8. 핵심 사례 ─────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: SLATE };
  s.addText("두 채널이 필요한 이유 — 한 사례", { x: M, y: 0.6, w: W - 2 * M, h: 0.7,
    fontFace: HFONT, fontSize: 32, bold: true, color: WHITE, margin: 0 });
  s.addText("최종 평가 질의 중 실제 사례", { x: M, y: 1.28, w: W - 2 * M, h: 0.4,
    fontFace: BFONT, fontSize: 14, color: "8FA3B0", margin: 0 });

  s.addShape(pres.ShapeType.roundRect, { x: M, y: 1.95, w: W - 2 * M, h: 0.95,
    rectRadius: 0.1, fill: { color: "2C3B46" } });
  s.addText("“ 'HONG KONG'이라는 간판이 걸린 옷가게 거리 장면 ”",
    { x: M + 0.4, y: 1.95, w: W - 2 * M - 0.8, h: 0.95, fontFace: HFONT,
      fontSize: 24, bold: true, color: WHITE, valign: "middle", margin: 0 });

  const rows = [
    ["발화 채널만 사용", "204위", "아무도 이 간판을 말하지 않는다. 자막에 단서가 없다.", SPEECH],
    ["두 채널 융합", "1위", "장면 설명이 간판 글자를 포착해 바로 찾아낸다.", VISION],
  ];
  rows.forEach(([t, r, d, c], i) => {
    const y = 3.2 + i * 1.45;
    s.addShape(pres.ShapeType.roundRect, { x: M, y, w: W - 2 * M, h: 1.2,
      rectRadius: 0.1, fill: { color: i === 1 ? "35485A" : "273540" } });
    s.addShape(pres.ShapeType.roundRect, { x: M + 0.35, y: y + 0.32, w: 2.4, h: 0.56,
      rectRadius: 0.1, fill: { color: c } });
    s.addText(t, { x: M + 0.35, y: y + 0.32, w: 2.4, h: 0.56, fontFace: BFONT,
      fontSize: 13, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(r, { x: M + 3.0, y: y + 0.2, w: 2.0, h: 0.8, fontFace: HFONT,
      fontSize: 36, bold: true, color: i === 1 ? VISION : "8FA3B0",
      valign: "middle", margin: 0 });
    s.addText(d, { x: M + 5.2, y: y + 0.2, w: 6.5, h: 0.8, fontFace: BFONT,
      fontSize: 15, color: "D5DEE4", valign: "middle", margin: 0 });
  });
  s.addText("말로 언급되지 않는 장면 — 여기서 두 채널의 차이가 가장 크게 벌어진다.",
    { x: M, y: 6.35, w: W - 2 * M, h: 0.5, fontFace: BFONT, fontSize: 15,
      color: "AEBDC7", margin: 0 });
  s.addNotes("시연에서도 이 질의를 보여줍니다. 발표의 핵심 장면입니다.");
}

// ── 9. 성능 ──────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "성능 — 최종 평가 39건 (튜닝에 쓴 적 없는 데이터)",
    "평가항목: 기술구현 및 방법론 (진척도 및 성능)");
  s.addChart(pres.ChartType.bar, [
    { name: "자막 단독", labels: ["MRR", "1위 적중", "5위 내 적중"], values: [0.649, 0.564, 0.769] },
    { name: "두 채널 융합", labels: ["MRR", "1위 적중", "5위 내 적중"], values: [0.829, 0.769, 0.872] },
  ], {
    x: M, y: 1.75, w: 7.0, h: 3.5, barDir: "col", barGapWidthPct: 60,
    chartColors: [MUTED, VISION], showTitle: false, showLegend: true,
    legendPos: "b", legendFontSize: 12, legendFontFace: BFONT,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11,
    dataLabelFontFace: BFONT, dataLabelColor: INK, dataLabelFormatCode: "0.000",
    valAxisMaxVal: 1.0, valAxisMinVal: 0,
    catAxisLabelColor: INK, catAxisLabelFontSize: 12, catAxisLabelFontFace: BFONT,
    valAxisLabelColor: MUTED, valAxisLabelFontSize: 10,
    valGridLine: { color: "DDE3E7", size: 1 }, catGridLine: { style: "none" },
  });
  card(s, M + 7.4, 1.75, 4.5, 3.5);
  s.addText("질의 유형별 1위 적중", { x: M + 7.7, y: 1.95, w: 3.9, h: 0.4,
    fontFace: HFONT, fontSize: 18, bold: true, color: INK, margin: 0 });
  const types = [["자막형", "말로 찾는 질의", 0.833, SPEECH],
                 ["복합형", "말+화면 함께", 0.857, SLATE],
                 ["장면형", "화면으로만 찾는 질의", 0.615, VISION]];
  types.forEach(([t, d, v, c], i) => {
    const y = 2.5 + i * 0.85;
    s.addText(t, { x: M + 7.7, y, w: 1.3, h: 0.32, fontFace: BFONT, fontSize: 14,
      bold: true, color: INK, margin: 0 });
    s.addText(d, { x: M + 7.7, y: y + 0.3, w: 2.3, h: 0.3, fontFace: BFONT,
      fontSize: 10.5, color: MUTED, margin: 0 });
    s.addShape(pres.ShapeType.roundRect, { x: M + 10.05, y: y + 0.02, w: 1.55 * v, h: 0.3,
      rectRadius: 0.06, fill: { color: c } });
    s.addText(v.toFixed(3), { x: M + 9.05, y, w: 0.95, h: 0.32, fontFace: BFONT,
      fontSize: 13, bold: true, color: c, align: "right", margin: 0 });
  });
  s.addText("장면형이 가장 낮다 — 남은 개선 여지가 여기 있다.",
    { x: M + 7.7, y: 4.7, w: 3.9, h: 0.55, fontFace: BFONT, fontSize: 12,
      color: MUTED, margin: 0 });
  s.addText("39건 중 30건을 1위로 맞힌다.  MRR·1위 적중은 통계적으로 유의(95% 신뢰구간이 0을 배제).  5위 내 적중은 표본 39건으로는 아직 유의하지 않아, 평가 규모를 72건으로 확장 중이다.",
    { x: M, y: 5.55, w: W - 2 * M, h: 0.9, fontFace: BFONT, fontSize: 14,
      color: INK, lineSpacing: 22, margin: 0 });
  s.addNotes("유의하지 않은 항목을 먼저 밝히는 것이 방어에 유리합니다. 확장 계획도 같이 말합니다.");
}

// ── 10. 모델 선정 근거 ───────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "모델 선정 근거 — 고를 때와 확인할 때를 분리했다",
    "평가항목: 기술구현 및 방법론 (모델 선정의 논리적 근거)");
  const steps = [
    ["1", "후보 26개 조합 비교", "장면 설명 모델 6종 × 프롬프트 5종을 학습용 데이터에서 비교", SLATE],
    ["2", "제3자 데이터로 확증", "AI Hub 194편·1,086건에서 재측정 → 개선 재현 (+0.038, 신뢰구간이 0 배제)", VISION],
    ["3", "다른 갈래는 닫았다", "음성 인식·프레임 선택·임베딩 모델 7종 — 모두 개선 근거 없음으로 종결", MUTED],
  ];
  steps.forEach(([n, t, d, c], i) => {
    const y = 1.8 + i * 1.28;
    card(s, M, y, W - 2 * M, 1.1);
    s.addShape(pres.ShapeType.ellipse, { x: M + 0.35, y: y + 0.28, w: 0.55, h: 0.55,
      fill: { color: c } });
    s.addText(n, { x: M + 0.35, y: y + 0.28, w: 0.55, h: 0.55, fontFace: HFONT,
      fontSize: 18, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(t, { x: M + 1.15, y: y + 0.18, w: 4.2, h: 0.4, fontFace: HFONT,
      fontSize: 18, bold: true, color: INK, margin: 0 });
    s.addText(d, { x: M + 5.5, y: y + 0.25, w: W - 2 * M - 5.9, h: 0.6,
      fontFace: BFONT, fontSize: 13.5, color: MUTED, valign: "middle", margin: 0 });
  });
  s.addShape(pres.ShapeType.roundRect, { x: M, y: 5.75, w: W - 2 * M, h: 1.1,
    rectRadius: 0.1, fill: { color: SLATE } });
  s.addText("모든 판정 기준을 결과를 보기 전에 코드에 적고 커밋했다 — 결과를 본 뒤 기준을 바꾸는 것을 구조적으로 차단",
    { x: M + 0.4, y: 5.75, w: W - 2 * M - 0.8, h: 1.1, fontFace: BFONT,
      fontSize: 15.5, color: WHITE, valign: "middle", margin: 0 });
  s.addNotes("모델 선정 근거 배점이 큽니다. 선별과 확증을 분리한 점, 사전 등록한 점을 강조하세요.");
}

// ── 11. 방법론 규율 ──────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "차별점 — 성능보다 “믿을 수 있는가”에 투자했다",
    "질의응답 대비");
  const disc = [
    ["최종 평가 데이터로 튜닝한 적 0회", "설정을 고르는 데는 학습용 96건만 썼다. 최종 평가는 확정된 설정으로만 접촉한다."],
    ["판정 기준을 결과보다 먼저 고정", "실험마다 성공/실패 규칙을 미리 커밋한다. 사후에 기준을 맞추는 경로를 없앴다."],
    ["평가 도구 자체를 먼저 검정", "지표가 못 재는 것을 “차이 없음”으로 쓰지 않기 위해, 정답을 아는 문항으로 계측기를 먼저 시험한다."],
    ["부정적 결과도 그대로 남긴다", "개선을 못 찾은 갈래(음성 인식·임베딩·프레임)를 근거와 함께 종결로 기록한다."],
  ];
  disc.forEach(([t, d], i) => {
    const x = M + (i % 2) * 6.15;
    const y = 1.85 + Math.floor(i / 2) * 2.3;
    card(s, x, y, 5.75, 2.0);
    s.addShape(pres.ShapeType.roundRect, { x: x + 0.35, y: y + 0.3, w: 0.42, h: 0.42,
      rectRadius: 0.21, fill: { color: i % 2 === 0 ? VISION : SPEECH } });
    s.addText(t, { x: x + 0.95, y: y + 0.28, w: 4.5, h: 0.75, fontFace: HFONT,
      fontSize: 17, bold: true, color: INK, margin: 0 });
    s.addText(d, { x: x + 0.35, y: y + 1.1, w: 5.05, h: 0.75, fontFace: BFONT,
      fontSize: 13, color: MUTED, lineSpacing: 19, margin: 0 });
  });
  s.addText("연구 결과가 재현 가능하고 방어 가능해야 실무에 옮길 수 있다.",
    { x: M, y: 6.55, w: W - 2 * M, h: 0.4, fontFace: BFONT, fontSize: 15,
      bold: true, color: SLATE, margin: 0 });
  s.addNotes("평가위원이 방법론을 물으면 여기로 옵니다. 튜닝 0회가 가장 강한 카드입니다.");
}

// ── 12. 군 활용성 ────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "군 적용 가능성", "평가항목: 군 활용성");
  const uses = [
    ["사후검토(AAR) 지원", "훈련·연습 영상에서 특정 상황을 문장으로 찾아 되짚는다. 요약 리포트 모듈이 근거 구간과 함께 초안을 만든다.", VISION],
    ["무발화 영상 검색", "감시·정찰 영상처럼 말이 거의 없는 자료에서도 화면 채널만으로 검색된다. 자막 검색이 무력한 영역이다.", SPEECH],
    ["교육·교범 영상 탐색", "긴 교육 영상에서 필요한 절차 구간을 문장으로 바로 찾는다.", SLATE],
  ];
  uses.forEach(([t, d, c], i) => {
    const y = 1.8 + i * 1.5;
    card(s, M, y, W - 2 * M, 1.3);
    s.addShape(pres.ShapeType.roundRect, { x: M + 0.35, y: y + 0.35, w: 0.6, h: 0.6,
      rectRadius: 0.12, fill: { color: c } });
    s.addText(String(i + 1), { x: M + 0.35, y: y + 0.35, w: 0.6, h: 0.6,
      fontFace: HFONT, fontSize: 18, bold: true, color: WHITE,
      align: "center", valign: "middle", margin: 0 });
    s.addText(t, { x: M + 1.2, y: y + 0.2, w: 4.3, h: 0.45, fontFace: HFONT,
      fontSize: 19, bold: true, color: INK, margin: 0 });
    s.addText(d, { x: M + 1.2, y: y + 0.65, w: W - 2 * M - 1.7, h: 0.55,
      fontFace: BFONT, fontSize: 13.5, color: MUTED, margin: 0 });
  });
  s.addShape(pres.ShapeType.roundRect, { x: M, y: 6.35, w: W - 2 * M, h: 0.7,
    rectRadius: 0.1, fill: { color: "E8EDF0" } });
  s.addText("전제: 현재 실험은 공개 한국어 영상으로 수행했다. 군 자료 적용에는 폐쇄망 구동과 도메인 재검증이 필요하다.",
    { x: M + 0.35, y: 6.35, w: W - 2 * M - 0.7, h: 0.7, fontFace: BFONT,
      fontSize: 12.5, color: INK, valign: "middle", margin: 0 });
  s.addNotes("과장하지 않는 것이 중요합니다. 마지막 전제 문장을 반드시 말하세요.");
}

// ── 13. 로드맵 ───────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: SLATE };
  s.addText("남은 기간 로드맵", { x: M, y: 0.6, w: W - 2 * M, h: 0.7,
    fontFace: HFONT, fontSize: 32, bold: true, color: WHITE, margin: 0 });
  s.addText("평가항목: 프로젝트 관리", { x: M, y: 1.28, w: W - 2 * M, h: 0.4,
    fontFace: BFONT, fontSize: 14, color: "8FA3B0", margin: 0 });
  const plan = [
    ["8월 말", "장면 설명 모델 교체 완료", "제3자 데이터에서 확증한 모델로 전환하고, 확장된 72건에서 최종 재평가", VISION, "진행 중"],
    ["9월 중", "회의록 생성·평가", "회의 음성에서 화자별 발언을 정리해 회의록을 만들고 자동 채점", SPEECH, "설계 완료"],
    ["9월 말", "최종 정리", "성능 보고서·재현 절차·시연 패키지 마무리", "8FA3B0", "예정"],
  ];
  plan.forEach(([when, t, d, c, st], i) => {
    const y = 2.0 + i * 1.45;
    s.addShape(pres.ShapeType.roundRect, { x: M, y, w: W - 2 * M, h: 1.2,
      rectRadius: 0.1, fill: { color: "2C3B46" } });
    s.addText(when, { x: M + 0.4, y: y + 0.15, w: 1.6, h: 0.45, fontFace: HFONT,
      fontSize: 19, bold: true, color: c, margin: 0 });
    s.addShape(pres.ShapeType.roundRect, { x: M + 0.4, y: y + 0.68, w: 1.2, h: 0.32,
      rectRadius: 0.16, fill: { color: c } });
    s.addText(st, { x: M + 0.4, y: y + 0.68, w: 1.2, h: 0.32, fontFace: BFONT,
      fontSize: 10.5, bold: true, color: i === 2 ? INK : WHITE,
      align: "center", valign: "middle", margin: 0 });
    s.addText(t, { x: M + 2.3, y: y + 0.18, w: 9.2, h: 0.45, fontFace: HFONT,
      fontSize: 20, bold: true, color: WHITE, margin: 0 });
    s.addText(d, { x: M + 2.3, y: y + 0.65, w: 9.2, h: 0.45, fontFace: BFONT,
      fontSize: 13.5, color: "AEBDC7", margin: 0 });
  });
  s.addText("모든 재평가 절차는 결과를 보기 전에 문서로 고정했다 — 일정과 판정 기준이 함께 확정된 상태다.",
    { x: M, y: 6.5, w: W - 2 * M, h: 0.5, fontFace: BFONT, fontSize: 14,
      color: "8FA3B0", margin: 0 });
  s.addNotes("남은 기간 계획 배점. 진행 중/설계 완료 상태를 명확히 말하세요.");
}

// 출력은 스크립트와 같은 폴더로 — 실행 위치에 따라 경로가 달라지지 않게 한다
const path = require("path");
pres.writeFile({ fileName: path.join(__dirname, "중간성과발표_2026-08-21.pptx") })
  .then(f => console.log("작성 완료:", f));
