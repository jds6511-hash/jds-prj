// 국방 AI·SW 프로젝트 중간성과발표회 (2026-08-21) 발표자료 생성기
// 발표 10분 + 질의응답 10분 → 12슬라이드.
// 슬라이드에 평가항목 표기는 넣지 않는다(2026-08-13 피드백). 대응 관계는 발표자 노트로만.
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
  // 오른쪽 채널 칩(x=9.6~)과 상자가 겹치지 않게 폭을 8.7로 끊는다 — 기하 QA 신뢰용
  s.addText(title, { x: M, y: 2.0, w: 8.7, h: 1.6, fontFace: HFONT,
    fontSize: 44, bold: true, color: WHITE, lineSpacing: 52 });
  if (sub) s.addText(sub, { x: M, y: 3.8, w: 8.7, h: 1.2,
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

// 모듈 행 오른쪽에 실제 사용 모델을 적는다. 값은 배포 config.yaml 기준(시연이 도는 설정).
// 교체 예정분은 "→ … 예정"으로 구분해 확정분과 섞이지 않게 한다. [2026-08-13 피드백]
function modelCell(s, x, y, w, lines) {
  s.addText(lines.map(([t, color, bold, size], i) => ({
    text: t,
    options: {
      color, bold: !!bold, fontSize: size || 11,
      breakLine: i < lines.length - 1,
    },
  })), { x, y, w, h: 0.9, fontFace: BFONT, lineSpacing: 15, margin: 0 });
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
  head(s, "문제 — 30분짜리 영상에서 “그 장면”을 어떻게 찾나");
  const items = [
    ["지금은 사람이 직접 돌려본다", "재생·되감기를 반복해 눈으로 찾는다. 영상이 길수록, 편수가 많을수록 선형으로 시간이 늘어난다."],
    ["제목·설명으로는 못 찾는다", "메타데이터는 30분 전체를 한 줄로 요약할 뿐, 그 안의 특정 한 장면을 가리키지 못한다."],
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
  head(s, "왜 AI가 필요한가 — 화면을 글로 바꿔야 한다");
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
  head(s, "전체 구조 — 9개 모듈, 세 단계");
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
    card(s, x, 1.45, 3.75, 3.15);
    s.addShape(pres.ShapeType.roundRect, { x: x + 0.35, y: 1.72, w: 1.35, h: 0.4,
      rectRadius: 0.2, fill: { color: st.color } });
    s.addText(st.mods, { x: x + 0.35, y: 1.72, w: 1.35, h: 0.4, fontFace: BFONT,
      fontSize: 12, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(st.name, { x: x + 0.35, y: 2.25, w: 3.05, h: 0.8, fontFace: HFONT,
      fontSize: 19, bold: true, color: INK, margin: 0 });
    s.addText(st.desc, { x: x + 0.35, y: 3.08, w: 3.05, h: 1.3, fontFace: BFONT,
      fontSize: 14, color: MUTED, lineSpacing: 22, margin: 0 });
    if (i < 2) s.addText("▶", { x: x + 3.82, y: 2.8, w: 0.3, h: 0.4,
      fontFace: BFONT, fontSize: 18, color: MUTED, align: "center", margin: 0 });
  });
  s.addText("색인은 영상마다 한 번만 만든다. 그 뒤로는 질문할 때마다 1초 미만으로 검색된다.",
    { x: M, y: 4.72, w: W - 2 * M, h: 0.4, fontFace: BFONT, fontSize: 15,
      color: INK, margin: 0 });

  // 색인 소요를 묻는 질문이 반복돼 이유와 단축 여지를 함께 싣는다(2026-08-13 피드백)
  card(s, M, 5.2, W - 2 * M, 1.75);
  s.addText("색인이 오래 걸리는 이유", { x: M + 0.35, y: 5.4, w: 5.3, h: 0.35,
    fontFace: HFONT, fontSize: 17, bold: true, color: INK, margin: 0 });
  s.addText("구간마다 장면 설명을 새로 만든다 — 30분 영상이면 약 360구간, 구간당 비전-언어 모델 1회 + 음성 인식.\n노트북(RTX 3060) 실측: 대표 프레임 25분 · 자막·장면 설명 75분 · 벡터 색인 2분 = 약 100분.",
    { x: M + 0.35, y: 5.78, w: 5.3, h: 1.1, fontFace: BFONT, fontSize: 12,
      color: MUTED, lineSpacing: 17, margin: 0 });
  s.addText("줄일 수 있다", { x: M + 6.2, y: 5.4, w: 5.35, h: 0.35,
    fontFace: HFONT, fontSize: 17, bold: true, color: VISION, margin: 0 });
  s.addText("서버 GPU(RTX 4090)에서 장면 설명 2.5초/장 실측 — 같은 작업이 약 4배 빠르다.\n배치 추론·flash-attn은 아직 미적용이라 여지가 더 남아 있다. 기다리는 시간은 색인이 아니라 검색(1초 미만)이다.",
    { x: M + 6.2, y: 5.78, w: 5.35, h: 1.1, fontFace: BFONT, fontSize: 12,
      color: MUTED, lineSpacing: 17, margin: 0 });
  s.addNotes("아키텍처 항목. 색인 소요를 물으면 병목이 M3 한 곳이고 서버·배치로 줄어든다고 답하세요. 100분은 노트북 실측 합계입니다(M2 25 + M3 75 + M4 2).");
}

// ── 5. 모듈 역할 ① ───────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "모듈별 역할 ① — 색인 만들기", "M1 → M4  ·  오른쪽은 실제 사용 모델");
  const mods = [
    ["M1", "영상 자르기",
     "검색이 시각을 지목하려면 단위가 필요하다. 5초 구간으로 자른다 — 3·5·8·10초 비교에서 5초가 최선.", SLATE,
     [["모델 없음", MUTED, true], ["FFmpeg · OpenCV 영상 처리", MUTED, false, 10]]],
    ["M2", "대표 화면 고르기",
     "구간 안 프레임을 차례로 비교해 앞 프레임과 가장 많이 달라진 지점을 고른다(차분 평활 후 최댓값).", SLATE,
     [["모델 없음", MUTED, true], ["OpenCV 차분 + 가우시안 평활", MUTED, false, 10]]],
    ["M3", "말·화면을 글로",
     "음성 인식으로 자막을, 비전-언어 모델로 장면 설명을 만든다. 파이프라인 최대 병목.", VISION,
     [["faster-whisper large-v3", SPEECH, true],
      ["Qwen2.5-VL-3B · 4bit", VISION, true],
      ["→ Qwen3-VL-4B 교체 예정", MUTED, false, 10]]],
    ["M4", "숫자로 색인",
     "두 글을 각각 1024차원 벡터로 바꿔 저장한다. 의미가 가까우면 벡터도 가깝다.", SPEECH,
     [["KURE-v1", SPEECH, true], ["한국어 문장 임베딩 · 1024차원", MUTED, false, 10]]],
  ];
  mods.forEach(([id, t, d, c, ml], i) => {
    const y = 1.70 + i * 1.35;
    card(s, M, y, W - 2 * M, 1.22);
    s.addShape(pres.ShapeType.roundRect, { x: M + 0.3, y: y + 0.31, w: 0.85, h: 0.6,
      rectRadius: 0.12, fill: { color: c } });
    s.addText(id, { x: M + 0.3, y: y + 0.31, w: 0.85, h: 0.6, fontFace: HFONT,
      fontSize: 17, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(t, { x: M + 1.4, y: y + 0.14, w: 2.6, h: 0.38, fontFace: HFONT,
      fontSize: 18, bold: true, color: INK, margin: 0 });
    s.addText(d, { x: M + 1.4, y: y + 0.5, w: 6.9, h: 0.66,
      fontFace: BFONT, fontSize: 12.5, color: MUTED, lineSpacing: 16.5, margin: 0 });
    modelCell(s, M + 8.45, y + 0.2, 3.2, ml);
  });
  s.addNotes("M3이 핵심이자 병목입니다. 쓰는 모델은 음성 인식 faster-whisper large-v3, 장면 설명 Qwen2.5-VL-3B(4bit), 임베딩 KURE-v1입니다. 장면 설명 모델은 독립 표본 확증을 통과한 Qwen3-VL-4B로 교체 예정이고, 오늘 보여드리는 수치는 교체 전 설정입니다.");
}

// ── 6. 모듈 역할 ② ───────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "모듈별 역할 ② — 찾고 보여주기", "M5 → M9  ·  오른쪽은 실제 사용 모델");
  const mods = [
    ["M5", "검색", "질의를 두 채널과 각각 비교해 가중합으로 한 점수를 만든다. 관련 없는 질의에는 경고를 띄운다.", SPEECH,
     [["KURE-v1", SPEECH, true], ["질의도 색인과 같은 임베더로 변환", MUTED, false, 10]]],
    ["M6", "평가", "정답 구간을 얼마나 위에 올렸는지 잰다. MRR·적중률·구간 겹침을 함께 본다.", SLATE,
     [["모델 없음", MUTED, true], ["지표 계산 · 부트스트랩 신뢰구간", MUTED, false, 10]]],
    ["M7", "시연 화면", "영상을 올리고 질문하면 타임라인과 순위가 뜬다. 클릭하면 그 시각으로 이동한다.", SLATE,
     [["모델 없음", MUTED, true], ["Gradio 웹 UI · 검색은 M5 호출", MUTED, false, 10]]],
    ["M8 · M9", "요약 리포트와 채점", "영상 전체를 요약해 근거 구간과 함께 제시하고, 그 요약이 근거에 부합하는지 자동 채점한다.", VISION,
     [["Qwen2.5-7B-Instruct", VISION, true],
      ["요약 생성 + 자동 채점", MUTED, false, 10],
      ["→ 채점자는 14B 교체 예정", MUTED, false, 10]]],
  ];
  mods.forEach(([id, t, d, c, ml], i) => {
    const y = 1.70 + i * 1.35;
    card(s, M, y, W - 2 * M, 1.22);
    s.addShape(pres.ShapeType.roundRect, { x: M + 0.3, y: y + 0.31, w: 1.15, h: 0.6,
      rectRadius: 0.12, fill: { color: c } });
    s.addText(id, { x: M + 0.3, y: y + 0.31, w: 1.15, h: 0.6, fontFace: HFONT,
      fontSize: 15, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(t, { x: M + 1.7, y: y + 0.14, w: 3.2, h: 0.38, fontFace: HFONT,
      fontSize: 18, bold: true, color: INK, margin: 0 });
    s.addText(d, { x: M + 1.7, y: y + 0.5, w: 6.6, h: 0.66,
      fontFace: BFONT, fontSize: 12.5, color: MUTED, lineSpacing: 16.5, margin: 0 });
    modelCell(s, M + 8.45, y + 0.2, 3.2, ml);
  });
  s.addNotes("M8은 군에서 말하는 사후검토(AAR) 리포트에 해당합니다. M8·M9는 Qwen2.5-7B-Instruct 하나를 요약과 채점에 함께 씁니다 — 자기평가 편향이 있어 채점자를 14B로 분리할 예정입니다(게이트 검정에서 7B는 탈락, 14B는 통과).");
}

// ── 7. 데이터 ────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "데이터 — 직접 만들고, 제3자 데이터로 검증했다");
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
  head(s, "성능 — 최종 평가 39건 (튜닝에 쓴 적 없는 데이터)");
  // 지표를 모르는 청중이 있어 MRR 정의를 슬라이드에 싣는다(2026-08-13 피드백)
  s.addShape(pres.ShapeType.roundRect, { x: M, y: 1.22, w: W - 2 * M, h: 0.62,
    rectRadius: 0.08, fill: { color: "E8EDF0" } });
  s.addText("MRR (평균 역순위) — 정답 구간이 검색 결과 몇 번째에 나오는지, 그 순위의 역수를 질의마다 평균한 값. 1위면 1.0 · 2위면 0.5 · 4위면 0.25. 1에 가까울수록 정답을 위에 올린다.",
    { x: M + 0.35, y: 1.22, w: W - 2 * M - 0.7, h: 0.62, fontFace: BFONT,
      fontSize: 13, color: INK, valign: "middle", margin: 0 });
  s.addChart(pres.ChartType.bar, [
    { name: "자막 단독", labels: ["MRR", "1위 적중", "5위 내 적중"], values: [0.649, 0.564, 0.769] },
    { name: "두 채널 융합", labels: ["MRR", "1위 적중", "5위 내 적중"], values: [0.829, 0.769, 0.872] },
  ], {
    x: M, y: 2.0, w: 7.0, h: 3.35, barDir: "col", barGapWidthPct: 60,
    chartColors: [MUTED, VISION], showTitle: false, showLegend: true,
    legendPos: "b", legendFontSize: 12, legendFontFace: BFONT,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11,
    dataLabelFontFace: BFONT, dataLabelColor: INK, dataLabelFormatCode: "0.000",
    valAxisMaxVal: 1.0, valAxisMinVal: 0,
    catAxisLabelColor: INK, catAxisLabelFontSize: 12, catAxisLabelFontFace: BFONT,
    valAxisLabelColor: MUTED, valAxisLabelFontSize: 10,
    valGridLine: { color: "DDE3E7", size: 1 }, catGridLine: { style: "none" },
  });
  card(s, M + 7.4, 2.0, 4.5, 3.35);
  s.addText("질의 유형별 1위 적중", { x: M + 7.7, y: 2.18, w: 3.9, h: 0.4,
    fontFace: HFONT, fontSize: 18, bold: true, color: INK, margin: 0 });
  const types = [["자막형", "말로 찾는 질의", 0.833, SPEECH],
                 ["복합형", "말+화면 함께", 0.857, SLATE],
                 ["장면형", "화면으로만 찾는 질의", 0.615, VISION]];
  types.forEach(([t, d, v, c], i) => {
    const y = 2.68 + i * 0.78;
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
    { x: M + 7.7, y: 4.85, w: 3.9, h: 0.4, fontFace: BFONT, fontSize: 12,
      color: MUTED, margin: 0 });
  s.addText("39건 중 30건을 1위로 맞힌다.  MRR·1위 적중은 통계적으로 유의(95% 신뢰구간이 0을 배제).  5위 내 적중은 표본 39건으로는 아직 유의하지 않아, 평가 규모를 72건으로 확장 중이다.",
    { x: M, y: 5.6, w: W - 2 * M, h: 0.9, fontFace: BFONT, fontSize: 14,
      color: INK, lineSpacing: 22, margin: 0 });
  s.addNotes("유의하지 않은 항목을 먼저 밝히는 것이 방어에 유리합니다. 확장 계획도 같이 말합니다.");
}

// ── 10. 모델 선정 근거 ───────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "모델 선정 근거 — 고를 때와 확인할 때를 분리했다");
  const steps = [
    ["1", "후보 26개 조합 비교", "장면 설명 모델 6종 × 프롬프트 5종을 학습용 데이터에서 비교", SLATE],
    ["2", "제3자 데이터로 확증", "AI Hub 194편·1,086건에서 재측정 → 개선 재현 (+0.038, 신뢰구간이 0 배제)", VISION],
    ["3", "다른 갈래는 닫았다", "음성 인식·프레임 선택·임베딩 모델 — 모두 개선 근거 없음으로 종결", MUTED],
  ];
  steps.forEach(([n, t, d, c], i) => {
    const y = 1.68 + i * 1.2;
    card(s, M, y, W - 2 * M, 1.02);
    s.addShape(pres.ShapeType.ellipse, { x: M + 0.35, y: y + 0.24, w: 0.55, h: 0.55,
      fill: { color: c } });
    s.addText(n, { x: M + 0.35, y: y + 0.24, w: 0.55, h: 0.55, fontFace: HFONT,
      fontSize: 18, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(t, { x: M + 1.15, y: y + 0.15, w: 4.2, h: 0.4, fontFace: HFONT,
      fontSize: 18, bold: true, color: INK, margin: 0 });
    s.addText(d, { x: M + 5.5, y: y + 0.2, w: W - 2 * M - 5.9, h: 0.6,
      fontFace: BFONT, fontSize: 13.5, color: MUTED, valign: "middle", margin: 0 });
  });

  // 후보 실명을 묻는 질문이 나오므로 슬라이드에 싣는다(2026-08-13 피드백)
  card(s, M, 5.3, W - 2 * M, 1.1);
  s.addText("비교한 후보 (전량 기록)", { x: M + 0.35, y: 5.44, w: 5, h: 0.32,
    fontFace: HFONT, fontSize: 16, bold: true, color: INK, margin: 0 });
  s.addText([
    { text: "장면 설명 ", options: { bold: true, color: VISION } },
    { text: "Qwen2.5-VL 3B·7B · Qwen3-VL 4B·8B · VARCO-VISION-2.0 · HyperCLOVAX-SEED-Vision · Kanana-1.5-v",
      options: { color: MUTED, breakLine: true } },
    { text: "임베딩 ", options: { bold: true, color: SPEECH } },
    { text: "KURE-v1(현행) · BGE-m3 계열 3종 · multilingual-e5-large · KoE5 · Qwen3-Embedding · gte-multilingual",
      options: { color: MUTED } },
  ], { x: M + 0.35, y: 5.76, w: W - 2 * M - 0.7, h: 0.55, fontFace: BFONT,
       fontSize: 11.5, lineSpacing: 16, margin: 0 });

  s.addShape(pres.ShapeType.roundRect, { x: M, y: 6.55, w: W - 2 * M, h: 0.62,
    rectRadius: 0.1, fill: { color: SLATE } });
  s.addText("판정 기준은 결과를 보기 전에 코드에 적고 커밋했다 — 결과를 본 뒤 기준을 바꾸는 경로를 구조적으로 없앴다",
    { x: M + 0.4, y: 6.55, w: W - 2 * M - 0.8, h: 0.62, fontFace: BFONT,
      fontSize: 14, color: WHITE, valign: "middle", margin: 0 });
  s.addNotes("모델 선정 근거 배점이 큽니다. 선별과 확증을 분리한 점, 사전 등록한 점을 강조하세요. 최종 채택은 Qwen3-VL-4B입니다. 임베딩은 7개 arm을 한 가족으로 묶어 다중비교 보정했고 통과가 0건입니다.");
}

// (구 11. 방법론 규율 슬라이드는 2026-08-13 피드백으로 삭제.
//  '튜닝 0회'·'사전 등록'은 슬라이드 10 하단 띠와 발표자 노트로 남긴다.)

// ── 11. 군 활용성 ────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "군 적용 가능성");
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

// ── 12. 로드맵 ───────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: SLATE };
  s.addText("남은 기간 로드맵", { x: M, y: 0.6, w: W - 2 * M, h: 0.7,
    fontFace: HFONT, fontSize: 32, bold: true, color: WHITE, margin: 0 });
  s.addText("8월 말 ~ 9월 말", { x: M, y: 1.28, w: W - 2 * M, h: 0.4,
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
