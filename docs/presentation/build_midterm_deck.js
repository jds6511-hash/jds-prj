// 국방 AI·SW 프로젝트 중간성과발표회 (2026-08-21) 발표자료 생성기
// 발표 10분 + 질의응답 10분 → 15슬라이드.
// 슬라이드에 평가항목 표기는 넣지 않는다(2026-08-13 피드백). 대응 관계는 발표자 노트로만.
// 2026-08-20 개정: 후보 모델을 "교체 예정"으로 쓰지 않는다(부호 역전 미해결),
// 최종 평가는 39건이다(72건 아님), M8 절단 문제는 조치됐고 남은 문제는 사건 입도다.
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

  // 분할 설계를 묻는 질문이 반복돼(왜 시간 단위인가 / 왜 5초인가) 근거를 슬라이드에 싣는다.
  // 5초 표는 ablation_plan_draft 1-6-1 재검증(thr=0 통일, dev 96질의) 값 그대로.
  card(s, M, 5.15, 6.0, 1.85);
  s.addText("왜 행동 단위가 아니라 시간 단위인가", { x: M + 0.32, y: 5.33, w: 5.4, h: 0.32,
    fontFace: HFONT, fontSize: 16, bold: true, color: INK, margin: 0 });
  s.addText([
    { text: "검색은 “몇 분 몇 초”를 지목해야 한다 — 고정 격자면 구간 번호 × 5초가 곧 시각이다", options: { bullet: true, breakLine: true } },
    { text: "행동 단위 분할은 학습이 필요하고(범위 밖), 학습 없는 샷 분할은 고정 카메라 브이로그에서 거의 안 잘려 한 구간이 수 분이 된다", options: { bullet: true, breakLine: true } },
    { text: "정답 라벨을 초 단위로 만들어 두면 길이를 바꿔도 다시 라벨링하지 않는다. 행동 단위면 모델이 바뀔 때마다 단위가 흔들려 이전 평가와 비교가 끊긴다", options: { bullet: true } },
  ], { x: M + 0.32, y: 5.68, w: 5.4, h: 1.2, fontFace: BFONT, fontSize: 10.5,
       color: MUTED, lineSpacing: 13.5, paraSpaceAfter: 4, margin: 0 });

  card(s, M + 6.25, 5.15, 5.65, 1.85);
  s.addText("왜 하필 5초인가 — 직접 재봤다", { x: M + 6.57, y: 5.33, w: 5.0, h: 0.32,
    fontFace: HFONT, fontSize: 16, bold: true, color: VISION, margin: 0 });
  const segRows = [["길이", "MRR", "5위 내", "장면형"],
                   ["3초", "0.631", "0.773", "0.559"],
                   ["5초 (현행)", "0.655", "0.818", "0.570"],
                   ["10초", "0.561", "0.682", "0.384"]];
  segRows.forEach((r, ri) => {
    const y = 5.62 + ri * 0.245;
    const head0 = ri === 0;
    const best = ri === 2;
    r.forEach((cellText, ci) => {
      s.addText(cellText, {
        x: M + 6.57 + [0, 1.5, 2.55, 3.6][ci], y, w: ci === 0 ? 1.45 : 1.0, h: 0.27,
        fontFace: BFONT, fontSize: head0 ? 10 : 11.5,
        bold: head0 || best, color: head0 ? MUTED : (best ? VISION : INK),
        align: ci === 0 ? "left" : "right", margin: 0 });
    });
  });
  s.addText("학습용 96질의 · 세 지표 전부 5초가 최고. 빌려온 값을 본 데이터에서 재확인했다.",
    { x: M + 6.57, y: 6.66, w: 5.0, h: 0.26, fontFace: BFONT, fontSize: 9,
      color: MUTED, margin: 0 });
  s.addNotes("아키텍처 항목. 분할은 M1의 설계 결정이고 두 질문이 반복됩니다. 시간 단위인 이유는 (1) 검색이 시각을 지목해야 한다 (2) 행동 단위는 학습이 필요해 범위 밖이고 비학습 샷 분할은 브이로그에서 안 잘린다 (3) 초 단위 라벨을 원본으로 두면 길이를 바꿔도 재라벨링이 없다 — 실제로 3/5/10초 ablation을 재라벨링 없이 돌렸습니다. 5초는 dev 96에서 MRR·hit@5·장면형 전부 최고였고, 10초는 자막형만 최고(0.786)라 세그먼트가 길수록 자막 문맥이 온전해진다는 부수 발견이 있었습니다. 색인 소요를 물으면: 병목은 M3 한 곳이고 노트북 실측 약 100분(M2 25 + M3 75 + M4 2), 서버 4090에서 장면 설명 2.5초/장으로 약 4배 빠릅니다. 배치·flash-attn은 아직 미적용이라 여지가 더 있고, 색인은 영상당 1회이며 사용자가 기다리는 것은 검색(1초 미만)입니다.");
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
      ["후보 Qwen3-VL-4B는 검증 중", MUTED, false, 10]]],
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
  s.addNotes("M3이 핵심이자 병목입니다. 쓰는 모델은 음성 인식 faster-whisper large-v3, 장면 설명 Qwen2.5-VL-3B(4bit), 임베딩 KURE-v1입니다. 오늘 수치는 전부 이 설정입니다. 장면 설명 후보 Qwen3-VL-4B는 제3자 데이터에서는 우세했지만 프롬프트를 고정한 대조에서 부호가 뒤집혀 아직 채택하지 않았습니다 — 자세한 근거는 뒤 슬라이드에 있습니다.");
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
      ["채점자 14B는 게이트 통과·대기", MUTED, false, 10]]],
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
  s.addNotes("M8은 군에서 말하는 사후검토(AAR) 리포트에 해당합니다. M8·M9는 Qwen2.5-7B-Instruct 하나를 요약과 채점에 함께 씁니다 — 자기평가 편향이 있어 채점자를 14B로 분리합니다(정답을 아는 60문항 게이트에서 7B 0.550 탈락, 14B 0.767 통과, 통과선 0.75). 다만 M9는 최종평가 데이터에 접촉하는 단계라 실행 자체를 승인 전까지 보류하고 있습니다.");
}

// ── 7. M8 현재 상태 ─────────────────────────────────────────────────
// 2026-08-13 발표에서 쓴 예시(2026-08-06 panibottle 산출물)는 **더 이상 현재 상태가
// 아니다.** 그 뒤로 리포트 입력 정제·구조화 map·코드 병합·토큰 상한 상향이 들어갔고,
// 2026-08-18 서버 예비 실행(dev 3편, validator PASS)에서 절단 양상이 재현되지 않았다.
// 수치는 docs/probes/_scratch/m8_pilot_report_0818d.json + 재분석_M8pilot_2026-08-18.md.
// 판정이 아니다 — 영상 2편 사례 진단이고 신뢰구간이 없다.
{
  const s = pres.addSlide();
  head(s, "M8 현재 상태 — 절단은 닫혔고, 사건이 너무 굵다",
    "2026-08-18 서버 예비 실행 · 학습용 영상 3편 · Qwen2.5-7B-Instruct · 판정이 아니라 사례 진단(신뢰구간 없음)");

  card(s, M, 1.65, 7.35, 4.6);
  s.addText("2주 전 발표와 달라진 것", { x: M + 0.35, y: 1.85, w: 6.6, h: 0.35,
    fontFace: HFONT, fontSize: 18, bold: true, color: INK, margin: 0 });
  const changed = [
    ["그때 (8월 6일 산출물)", "리포트 뒤 2/3가 사라졌다. 262구간 중 87까지만 남았다. 출력은 구간을 1:1로 훑는 문장 나열이었다.", MUTED],
    ["원인", "장면 설명에 섞인 한자 두 글자에서 리포트 모델이 중국어로 전환하며 생성을 끝냈다. 토큰 상한 문제가 아니었다(상한의 1/5에서 멈췄다).", SLATE],
    ["조치", "리포트 입력에서 잔여 한자를 제거하고, 구간 요약을 구조화된 사건 목록으로 받아 병합은 코드가 한다. 토큰 상한도 올렸다.", SPEECH],
    ["지금", "출력이 문장 나열이 아니라 사건 단위다 — 사건마다 시간 구간 + 근거 구간이 붙는다. 잘린 꼬리는 3편 모두 0건이고 타임라인을 87~96% 덮는다.", VISION],
  ];
  changed.forEach(([t, d, c], i) => {
    const y = 2.30 + i * 1.05;
    s.addShape(pres.ShapeType.roundRect, { x: M + 0.35, y, w: 0.34, h: 0.34,
      rectRadius: 0.17, fill: { color: c } });
    s.addText(String(i + 1), { x: M + 0.35, y, w: 0.34, h: 0.34, fontFace: BFONT,
      fontSize: 11, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(t, { x: M + 0.79, y: y + 0.02, w: 6.1, h: 0.3, fontFace: BFONT,
      fontSize: 13, bold: true, color: INK, margin: 0 });
    s.addText(d, { x: M + 0.79, y: y + 0.34, w: 6.15, h: 0.6, fontFace: BFONT,
      fontSize: 11.5, color: MUTED, lineSpacing: 14.5, margin: 0 });
  });

  card(s, M + 7.55, 1.65, 4.35, 4.6);
  s.addText("남은 문제 — 측정값", { x: M + 7.85, y: 1.85, w: 3.7, h: 0.35,
    fontFace: HFONT, fontSize: 18, bold: true, color: INK, margin: 0 });
  const left = [
    ["사람보다 사건이 적다", "같은 영상을 사람이 22개 사건으로 적었는데 모델은 12개, 다른 영상은 31개 대 8개다. 한 사건이 5분(60구간)을 덮은 경우도 있다.", VISION],
    ["그래서 시간이 안 맞는다", "사람 사건과의 겹침 평균 0.164. 3할 이상 겹친 것이 30%, 절반 이상은 15%다.", VISION],
    ["판정은 아니다", "영상 2편 사례라 신뢰구간을 내지 않았다. 다음은 사건을 하나씩 열어 실패 유형만 센다(여러 사건을 묶은 것인지).", SLATE],
  ];
  left.forEach(([t, d, c], i) => {
    const y = 2.3 + i * 1.32;
    s.addShape(pres.ShapeType.roundRect, { x: M + 7.85, y, w: 0.34, h: 0.34,
      rectRadius: 0.17, fill: { color: c } });
    s.addText(String(i + 1), { x: M + 7.85, y, w: 0.34, h: 0.34, fontFace: BFONT,
      fontSize: 11, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(t, { x: M + 8.29, y: y + 0.02, w: 3.25, h: 0.3, fontFace: BFONT,
      fontSize: 13, bold: true, color: INK, margin: 0 });
    s.addText(d, { x: M + 7.85, y: y + 0.42, w: 3.7, h: 0.85, fontFace: BFONT,
      fontSize: 11, color: MUTED, lineSpacing: 14, margin: 0 });
  });

  s.addShape(pres.ShapeType.roundRect, { x: M, y: 6.45, w: W - 2 * M, h: 0.62,
    rectRadius: 0.1, fill: { color: "E8EDF0" } });
  s.addText("오늘 시연 화면에는 M8·M9가 없다(7B는 노트북 6GB에 올라가지 않는다). 자동 채점(M9)은 최종 평가 데이터에 접촉하는 단계라 승인 전까지 실행하지 않는다.",
    { x: M + 0.35, y: 6.45, w: W - 2 * M - 0.7, h: 0.62, fontFace: BFONT,
      fontSize: 12.5, color: INK, valign: "middle", margin: 0 });
  s.addNotes("이 슬라이드는 지난 발표 이후 바뀐 부분입니다. 8월 6일 예시로 보여드린 '뒤 2/3 절단'은 원인을 규명해 조치했고, 8월 18일 서버 예비 실행에서는 3편 모두 타임라인을 87~96% 덮었습니다 — 그 양상은 재현되지 않았습니다. 대신 다른 문제가 드러났습니다: 사건 입도가 사람 기준보다 2~4배 굵습니다(22 대 12, 31 대 8). 그래서 시간 정렬이 0.164로 낮습니다. 다만 이건 판정이 아니라 영상 2편 사례 진단이고 신뢰구간을 내지 않았습니다. '위치를 못 맞춘다'가 아니라 '여러 사건을 하나로 묶는다'가 우선 가설이고, 다음 단계는 사건을 하나씩 열어 실패 유형 빈도만 세는 것입니다. 채점자 수치를 묻거든: 정답을 아는 60문항 게이트에서 7B 0.550 탈락, kanana-8B 0.417 탈락, 14B 0.767 통과(통과선 0.75). 탈락한 계측기의 점수는 인용하지 않습니다.");
}

// ── 8. 데이터 ────────────────────────────────────────────────────────
// 수치 출처: work/*/segments.json 전수 집계(11편 2,568구간),
// data/queries/queries.jsonl(dev 96 / test 39, 영상 단위 분리),
// docs/probes/_scratch/aihub_external_eval.json(194편 1,086질의).
// **최종 평가는 39건이다.** 33건이 추가로 준비돼 있으나 여는 것 자체가 별도 승인
// 사안이라 아직 열지 않았다 — "72건"으로 쓰지 않는다.
{
  const s = pres.addSlide();
  head(s, "데이터 — 직접 만들고, 우리가 만들지 않은 데이터로 검증했다");
  const stats = [
    ["11편", "한국어 영상", "여행·요리·테크·농장·도예·등산·문화유산", SLATE],
    ["2,568", "5초 구간", "구간마다 자막 + 장면 설명", SLATE],
    ["135건", "우리가 만든 평가 질의", "학습용 96 · 최종 평가 39", SPEECH],
    ["1,086건", "제3자 라벨 검증 질의", "AI Hub 공개 데이터 194편", VISION],
  ];
  stats.forEach(([n, t, d, c], i) => {
    const x = M + i * 3.02;
    card(s, x, 1.42, 2.75, 1.5);
    s.addText(n, { x: x + 0.2, y: 1.52, w: 2.35, h: 0.6, fontFace: HFONT,
      fontSize: 30, bold: true, color: c, margin: 0 });
    s.addText(t, { x: x + 0.2, y: 2.12, w: 2.35, h: 0.3, fontFace: BFONT,
      fontSize: 12.5, bold: true, color: INK, margin: 0 });
    s.addText(d, { x: x + 0.2, y: 2.42, w: 2.35, h: 0.45, fontFace: BFONT,
      fontSize: 10, color: MUTED, lineSpacing: 12.5, margin: 0 });
  });

  const COLW = 3.83, GAP = 0.2;
  const cols = [
    ["학습용·최종 평가 분리 기준", SPEECH, [
      "영상 단위로 갈랐다 — 같은 영상의 질의가 양쪽에 섞이면 튜닝이 답을 미리 본 것과 같다. 코드가 로드할 때 겹침을 검사한다",
      "학습용 3편 96건에서 모든 튜닝·모델 선택을 했고, 최종 평가 4편 39건은 확정 설정으로만 돌렸다",
      "질의 유형(자막형·장면형·복합형) 비율을 두 쪽에서 비슷하게 맞췄다",
      "39건은 튜닝에 쓴 적이 0회다. 33건이 더 준비돼 있지만 여는 것 자체가 별도 승인 사안이라 아직 열지 않았다",
    ]],
    ["제3자 데이터 검증 방법", VISION, [
      "AI Hub 「비디오 장면 설명문 생성」 공개 검증셋 — 영상·질의·정답을 전부 우리가 아닌 곳에서 만들었다. 194편 1,086질의",
      "확정 설정에 학습용에서 고른 α만 주입해 1회 실행했다. 재탐색·재튜닝 없음, 판정 규칙은 실행 전에 코드에 적어 뒀다",
      "결과 — 자막 단독 MRR 0.411 → 두 채널 0.469, 차이 +0.058 신뢰구간 [0.035, 0.082]로 유의",
      "한계도 같이 쓴다 — 60초 클립·12구간이라 무작위로 찍어도 0.44가 나온다. 절대값 비교는 못 하고 “방향이 같다”까지만 쓴다",
    ]],
    ["전처리·라벨링에서 지킨 규칙", SLATE, [
      "정답은 프레임 실물만 보고 정한다. 시스템이 만든 자막·장면 설명은 라벨 작업 도구에 아예 전달되지 않는다 — 구간 번호·시각·프레임만 통과시키고 코드가 나머지를 막는다",
      "검색 결과를 본 뒤 정답을 고르거나 고치지 않는다",
      "깨진 장면 설명은 사람이 눈으로 고르지 않고, 자동 판정에 걸린 것만 다시 만든다",
      "음성 인식이 조용한 구간에 만들어내는 환각 문구는 규칙으로 자동 제거한다",
    ]],
  ];
  cols.forEach(([title, c, items], i) => {
    const x = M + i * (COLW + GAP);
    card(s, x, 3.08, COLW, 3.75);
    s.addShape(pres.ShapeType.roundRect, { x: x + 0.28, y: 3.28, w: 0.3, h: 0.3,
      rectRadius: 0.15, fill: { color: c } });
    s.addText(title, { x: x + 0.68, y: 3.26, w: COLW - 0.95, h: 0.34,
      fontFace: HFONT, fontSize: 15.5, bold: true, color: INK, margin: 0 });
    s.addText(items.map((t, ii) => ({
      text: t,
      options: { bullet: true, breakLine: ii < items.length - 1 },
    })), { x: x + 0.28, y: 3.7, w: COLW - 0.56, h: 3.0, fontFace: BFONT,
      fontSize: 10.5, color: INK, lineSpacing: 13.5, paraSpaceAfter: 7, margin: 0 });
  });
  s.addNotes("데이터 항목입니다. 세 가지를 말하세요. 첫째, 학습용과 최종 평가는 영상 단위로 갈랐습니다 — 질의 단위로 나누면 같은 영상의 다른 질의로 튜닝한 셈이 되어 누수입니다. 코드가 로드할 때 dev/test에 같은 영상이 없는지 검사합니다. 최종 평가 39건은 튜닝 0회이고, 33건을 더 만들어 뒀지만 여는 것 자체가 되돌릴 수 없는 결정이라 아직 열지 않았습니다. 둘째, 외부 검증은 우리가 만들지 않은 데이터입니다. 확정 설정 그대로 1회만 돌렸고 판정 규칙을 미리 코드에 적었습니다. 유의하게 좋았지만 60초 클립이라 무작위 기저가 0.44로 높아서 절대값은 인용하지 않고 방향성 근거로만 씁니다 — 이 한계를 먼저 밝히는 것이 방어에 유리합니다. 셋째, 라벨링에서 시스템 출력을 보지 않는 것은 관행이 아니라 도구가 막습니다. 라벨 도구는 구간 번호·시각·프레임만 받고, 캡션·자막이 새면 예외를 던집니다.");
}

// ── 9. 핵심 사례 ─────────────────────────────────────────────────────
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

// ── 10. 성능 ──────────────────────────────────────────────────────────
// 그래프는 하나만 둔다. 이전 판은 왼쪽 전체 집계와 오른쪽 유형별 표를 나란히 놓아
// 같은 지표가 두 값으로 읽혔다(유형별을 건수로 가중하면 전체와 일치하지만, 슬라이드
// 에서는 혼동만 남는다). 유형 얘기는 문장 한 줄로 남긴다. [2026-08-20 피드백]
// 수치 출처: results/eval_test.json (n=39, α=0.5, static_threshold=0).
{
  const s = pres.addSlide();
  head(s, "성능 — 최종 평가 39건 (튜닝에 쓴 적 없는 데이터)");
  s.addShape(pres.ShapeType.roundRect, { x: M, y: 1.22, w: W - 2 * M, h: 0.62,
    rectRadius: 0.08, fill: { color: "E8EDF0" } });
  s.addText("MRR (평균 역순위) — 정답 구간이 검색 결과 몇 번째에 나오는지, 그 순위의 역수를 질의마다 평균한 값. 1위면 1.0 · 2위면 0.5 · 4위면 0.25. 1에 가까울수록 정답을 위에 올린다.",
    { x: M + 0.35, y: 1.22, w: W - 2 * M - 0.7, h: 0.62, fontFace: BFONT,
      fontSize: 13, color: INK, valign: "middle", margin: 0 });
  s.addChart(pres.ChartType.bar, [
    { name: "자막 단독", labels: ["MRR", "1위 적중", "5위 내 적중"], values: [0.649, 0.564, 0.769] },
    { name: "두 채널 융합", labels: ["MRR", "1위 적중", "5위 내 적중"], values: [0.829, 0.769, 0.872] },
  ], {
    x: M, y: 2.0, w: 7.6, h: 3.6, barDir: "col", barGapWidthPct: 60,
    chartColors: [MUTED, VISION], showTitle: false, showLegend: true,
    legendPos: "b", legendFontSize: 12, legendFontFace: BFONT,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 12,
    dataLabelFontFace: BFONT, dataLabelColor: INK, dataLabelFormatCode: "0.000",
    valAxisMaxVal: 1.0, valAxisMinVal: 0,
    catAxisLabelColor: INK, catAxisLabelFontSize: 13, catAxisLabelFontFace: BFONT,
    valAxisLabelColor: MUTED, valAxisLabelFontSize: 10,
    valGridLine: { color: "DDE3E7", size: 1 }, catGridLine: { style: "none" },
  });

  card(s, M + 8.0, 2.0, 3.9, 3.6);
  s.addText("이 그래프가 말하는 것", { x: M + 8.3, y: 2.2, w: 3.3, h: 0.35,
    fontFace: HFONT, fontSize: 17, bold: true, color: INK, margin: 0 });
  s.addText([
    { text: "39건 중 30건을 1위로 맞힌다. 자막 단독이면 22건이다", options: { bullet: true, breakLine: true } },
    { text: "MRR과 1위 적중은 통계적으로 유의하다 (신뢰구간이 0을 배제)", options: { bullet: true, breakLine: true } },
    { text: "5위 내 적중은 39건 표본으로는 아직 유의하지 않다 — 먼저 밝혀 둔다", options: { bullet: true, breakLine: true } },
    { text: "말로 언급되지 않는 “장면형” 13건은 자막 단독으로 1위 적중이 0건이었고, 두 채널에서 8건이 됐다", options: { bullet: true } },
  ], { x: M + 8.3, y: 2.68, w: 3.3, h: 2.7, fontFace: BFONT, fontSize: 12,
       color: INK, lineSpacing: 15.5, paraSpaceAfter: 9, margin: 0 });

  s.addText("확정 설정으로 한 번만 돌린 결과다. 이 39건으로 무엇을 고르거나 고친 적은 없다. 표본을 33건 더 준비했지만, 여는 것 자체가 되돌릴 수 없는 결정이라 별도 승인 전까지 열지 않는다.",
    { x: M, y: 5.85, w: W - 2 * M, h: 0.9, fontFace: BFONT, fontSize: 14,
      color: INK, lineSpacing: 22, margin: 0 });
  s.addNotes("유의하지 않은 항목(5위 내 적중)을 먼저 밝히는 것이 방어에 유리합니다. 마지막 문장이 중요합니다 — 표본을 늘리면 유의해질 수 있지만, 최종 평가 데이터를 다시 여는 것은 그 자체로 별도 결정이라 지금은 열지 않았습니다. 장면형 13건이 자막 단독으로 1위 0건이었다는 사실이 두 채널 설계의 근거입니다. 유형별 수치를 더 물으면: 두 채널에서 자막형 0.833 · 복합형 0.857 · 장면형 0.615이고, 건수로 가중하면 전체 0.769와 일치합니다.");
}

// ── 11. 캡션 모델 선정 ────────────────────────────────────────────────
// 수치는 전부 결과 파일에서 그대로 옮겼다(기억으로 쓰지 않는다):
//   dev 스윕      docs/probes/_scratch/caption_sweep.json (dev 96, 캡션 단독 α=0.0)
//   제3자 확증    docs/probes/_scratch/aihub_confirm_bf16matched.json (1,086질의)
//   부호 역전     docs/재분석_부호역전_2026-08-18.md §0 (프롬프트 P0 고정 대조)
// **4B는 채택 상태가 아니다.** "교체 예정"으로 쓰지 않는다. [2026-08-20]
{
  const s = pres.addSlide();
  head(s, "장면 설명 모델 — 무엇과 비교했고, 왜 아직 안 바꿨나",
    "학습용 96질의에서 후보 6종·26개 조합. 장면 설명 채널만 단독으로 재서 융합에 희석되지 않게 했다. 최종 평가 데이터는 쓰지 않았다.");
  s.addChart(pres.ChartType.bar, [{
    name: "장면 설명 채널 단독 MRR",
    labels: ["Kanana-3B (생성 실패)", "Qwen3-VL-4B · 현행 프롬프트",
             "Qwen2.5-VL-7B", "Qwen2.5-VL-3B 4bit · 현행 배포",
             "VARCO-VISION-2.0-1.7B", "Qwen3-VL-8B", "Qwen3-VL-4B · 프롬프트 변경"],
    values: [0.028, 0.369, 0.457, 0.461, 0.504, 0.525, 0.552],
  }], {
    x: M, y: 1.75, w: 7.15, h: 4.15, barDir: "bar", barGapWidthPct: 45,
    chartColors: [SPEECH], showTitle: false, showLegend: false,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11,
    dataLabelFontFace: BFONT, dataLabelColor: INK, dataLabelFormatCode: "0.000",
    valAxisMaxVal: 0.62, valAxisMinVal: 0,
    catAxisLabelColor: INK, catAxisLabelFontSize: 10.5, catAxisLabelFontFace: BFONT,
    valAxisLabelColor: MUTED, valAxisLabelFontSize: 9,
    valGridLine: { color: "DDE3E7", size: 1 }, catGridLine: { style: "none" },
  });

  card(s, M + 7.35, 1.6, 4.55, 4.4);
  s.addText("판정은 세 단계였다", { x: M + 7.65, y: 1.78, w: 3.9, h: 0.35,
    fontFace: HFONT, fontSize: 17, bold: true, color: INK, margin: 0 });
  const steps = [
    ["① 학습용에서 고른다", "프롬프트까지 함께 바꾸면 Qwen3-VL-4B가 0.552로 최고다(현행 0.461). 문장이 잘리는 비율도 현행 15.0%에서 0.15%로 낮다.", SPEECH],
    ["② 제3자 데이터로 확증", "AI Hub 1,086질의에서 같은 비교를 다시 했다 — 장면 설명 단독 +0.038 신뢰구간 [0.013, 0.061] 유의. 단, 두 채널 융합 지표에서는 +0.019 [−0.002, +0.040]로 유의하지 않다.", VISION],
    ["③ 그런데 부호가 뒤집혔다", "프롬프트를 현행으로 고정하고 모델만 바꾸면 방향이 반대다 — 제3자 데이터 +0.031(후보 우세) 대 학습용 96건 −0.090(현행 우세).", "B5544A"],
  ];
  steps.forEach(([t, d, c], i) => {
    const y = 2.2 + i * 1.13;
    s.addText(t, { x: M + 7.65, y, w: 3.9, h: 0.3, fontFace: BFONT, fontSize: 13,
      bold: true, color: c, margin: 0 });
    s.addText(d, { x: M + 7.65, y: y + 0.31, w: 3.9, h: 0.8, fontFace: BFONT,
      fontSize: 10.5, color: MUTED, lineSpacing: 13.5, margin: 0 });
  });
  s.addShape(pres.ShapeType.roundRect, { x: M + 7.65, y: 5.55, w: 3.9, h: 0.35,
    rectRadius: 0.17, fill: { color: SLATE } });
  s.addText("그래서 현행 3B 유지 · 후보는 보류", { x: M + 7.65, y: 5.55, w: 3.9, h: 0.35,
    fontFace: BFONT, fontSize: 11.5, bold: true, color: WHITE,
    align: "center", valign: "middle", margin: 0 });

  s.addText("두 표본은 서로를 대신하지 못한다 — 학습용은 영상 3편, 제3자 데이터는 60초 클립(질의당 후보 12개)이다. 어느 쪽이 맞는지는 새로 확보한 장편 35편·질의 315건으로 다시 확증한 뒤 결정한다.",
    { x: M, y: 6.05, w: W - 2 * M, h: 0.85, fontFace: BFONT, fontSize: 13.5,
      color: INK, lineSpacing: 20, margin: 0 });
  s.addNotes("배점이 큰 슬라이드입니다. 핵심은 '고르는 데이터'와 '확인하는 데이터'를 분리했다는 것, 그리고 유리한 결과가 나왔는데도 채택하지 않았다는 것입니다. ①에서 후보가 이겼고 ②에서 제3자 데이터로도 재현됐지만, ③ 프롬프트를 고정해 모델만 바꾼 대조에서는 두 표본의 부호가 반대였습니다(+0.031 대 −0.090). 배제한 설명도 말할 수 있습니다: 양자화 차이 아님(+0.009), 모델 가중치 스냅샷 동일, 프롬프트 해시 동일, 자막 채널은 세 arm 전부 0.4144로 동일, 융합 가중치 전 구간에서 현행 우세. 남은 유력 차이는 표본 구조입니다 — 제3자 데이터는 질의당 후보가 12개뿐이라 캡션 품질 차이가 순위에 반영될 여지가 좁습니다. 다만 이건 가설이고 확정하지 않았습니다. 그래서 장편 35편·315질의를 새로 확보했고, 규모·표본·질의 배정을 결과를 보기 전에 문서로 고정했습니다.");
}

// ── 12. 캡션 실물 ────────────────────────────────────────────────────
// 학습용 영상 gwaktube_soviet_apartment의 실제 프레임과 실제 캡션. 두 모델 캡션을
// 같은 서버·같은 실행(caption_sweep)에서 생성한 값으로 나란히 둔다 — 환경 차이가
// 아니라 모델 차이를 보여주기 위한 조건이다. 문장은 편집하지 않았다.
{
  const s = pres.addSlide();
  head(s, "장면 설명은 이렇게 쓰인다 — 학습용 영상의 실제 캡션",
    "프레임은 그대로, 문장은 앞부분만 옮겼다(뒤는 …로 줄였다). 두 모델을 같은 서버·같은 실행에서 생성해 나란히 놓았다.");

  const EX = [
    { x: M, frame: "../../work/gwaktube_soviet_apartment/frames/seg_0006.jpg",
      tag: "구간 #6 · 0:30~0:35", sub: "자막 없음 — 이 5초 동안 아무도 말하지 않는다",
      subColor: SPEECH,
      lines: [
        ["현행 3B", "여성은 푸른색 코트를 입고 금발 머리를 묶고 있으며, 파란색 바지를 입고 있습니다. …"],
        ["후보 4B", "파란색 벽돌 건물 앞에서 녹색 재킷을 입은 여성이 길을 걷고 있다. …"],
      ],
      note: "자막이 비어 있어도 이 문장이 벡터가 되어 “길을 걷는 여성” 같은 질의에 걸린다. 현행 모델은 재킷 색과 머리색을 틀렸다(실물은 청록 재킷·검은 머리)." },
    { x: M + 6.05, frame: "../../work/gwaktube_soviet_apartment/frames/seg_0055.jpg",
      tag: "구간 #55 · 4:35~4:40", sub: "자막: “기름으로 이빨 뿌렸는데도 밥이 없네요 …”",
      subColor: MUTED,
      lines: [
        ["현행 3B", "한 남성이 흰색 티셔츠를 입고 검은색 뚜껑의 작은 플라스틱 병을 들고 있다. …"],
        ["후보 4B", "一头卷发的男子穿着白色T恤，站在厨房里，右手拿着一瓶深色液体 …"],
      ],
      note: "후보가 한국어를 벗어났다 — 이런 캡션은 한국어 질의에 걸리지 않는다. 전면 이탈은 자동 판정기가 잡지만 한자 두 글자는 놓친다(재현율 0.08 실측)." },
  ];
  EX.forEach((e) => {
    card(s, e.x, 1.62, 5.55, 5.2);
    s.addText(e.tag, { x: e.x + 0.28, y: 1.76, w: 5.0, h: 0.26, fontFace: BFONT,
      fontSize: 11, bold: true, color: MUTED, margin: 0 });
    s.addImage({ path: e.frame, x: e.x + 0.28, y: 2.04, w: 4.62, h: 2.60 });
    s.addText(e.sub, { x: e.x + 0.28, y: 4.72, w: 5.0, h: 0.28, fontFace: BFONT,
      fontSize: 10.5, bold: true, color: e.subColor, margin: 0 });
    e.lines.forEach(([who, text], i) => {
      const y = 5.06 + i * 0.6;
      s.addShape(pres.ShapeType.roundRect, { x: e.x + 0.28, y, w: 0.88, h: 0.25,
        rectRadius: 0.12, fill: { color: i === 0 ? VISION : "8FA3B0" } });
      s.addText(who, { x: e.x + 0.28, y, w: 0.88, h: 0.25, fontFace: BFONT,
        fontSize: 9, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
      s.addText(text, { x: e.x + 1.22, y: y - 0.05, w: 4.05, h: 0.58, fontFace: BFONT,
        fontSize: 9.5, color: INK, lineSpacing: 12, margin: 0 });
    });
    s.addText(e.note, { x: e.x + 0.28, y: 6.24, w: 5.0, h: 0.5, fontFace: BFONT,
      fontSize: 9.5, color: MUTED, lineSpacing: 12, margin: 0 });
  });
  s.addNotes("왼쪽은 무발화 구간입니다 — 자막이 없으니 장면 설명 없이는 검색할 방법이 없습니다. 오른쪽은 후보 모델의 언어 이탈 실례입니다. 캡션은 사람이 손으로 고치지 않습니다. 자동 판정에 걸린 것만 다시 생성합니다 — 내용을 보고 고르면 그 순간 평가가 오염되기 때문입니다. 다만 현행 판정기의 재현율이 8%로 측정돼(정밀도 0.986), 판정기 자체를 다시 설계하는 것이 별도 과제로 올라와 있습니다. 개별 사례로 모델 우열을 주장하지는 않습니다 — 우열은 앞 슬라이드의 표본 수치로만 말합니다.");
}

// ── 13. 그 외 선정 근거 ──────────────────────────────────────────────
// (구 방법론 규율 슬라이드는 2026-08-13 피드백으로 삭제. 사전 등록·튜닝 0회는
//  성능 슬라이드 하단 문장과 발표자 노트로 남긴다.)
// 수치 출처: _scratch/embedder_sweep_select_r2.json · _scratch/judge_gate_models.json
//   results/alpha_search_dev.json · _scratch/aihub_env_check.json
{
  const s = pres.addSlide();
  head(s, "나머지 선택도 같은 방식으로 정했다",
    "고를 때는 학습용 96건, 확인할 때는 제3자 데이터. 판정 기준은 전부 결과를 보기 전에 커밋했다.");
  const rows = [
    ["임베딩 모델", "KURE-v1 유지",
     "후보 7종 — BGE-m3 계열 3종 / multilingual-e5-large / KoE5 / Qwen3-Embedding / gte-multilingual",
     "AI Hub 562건 · 7개를 한 가족으로 다중비교 보정 후 통과 0건. 최선인 bge-m3도 +0.0135 신뢰구간 [−0.005, +0.032]",
     "현행 유지", SLATE],
    ["융합 가중치", "말 : 화면 = 0.5 : 0.5",
     "학습용 96건에서 11개 지점을 훑었다. 점추정 최적은 0.4다",
     "쌍체 차이 신뢰구간으로 동률 집합 {0.2, 0.4, 0.5} → 사전에 정한 규칙(동률이면 자막 쪽)에 따라 0.5",
     "확정", SPEECH],
    ["요약 채점 모델", "7B → 14B",
     "정답을 아는 60문항으로 채점자를 먼저 시험했다 — 통과선 0.75",
     "정답률: 7B 0.550 탈락 · Kanana-8B 0.417 탈락 · 14B 0.767 통과. 탈락한 채점자의 점수는 인용하지 않는다",
     "게이트 통과", VISION],
    ["생성 환경(노트북/서버)", "차이 없다고 볼 근거 없음",
     "학습용 96건에서 −0.088로 보였던 효과를 독립 표본에서 다시 쟀다",
     "AI Hub 562건 −0.0046 신뢰구간 [−0.027, +0.017] → 재현 실패. 6GB 제약을 근거로 쓰던 판단을 스스로 철회했다",
     "기각", MUTED],
  ];
  rows.forEach(([t, sub, why, num, verdict, c], i) => {
    const y = 1.72 + i * 1.24;
    card(s, M, y, W - 2 * M, 1.14);
    s.addText(t, { x: M + 0.3, y: y + 0.18, w: 2.45, h: 0.32, fontFace: HFONT,
      fontSize: 15, bold: true, color: INK, margin: 0 });
    s.addText(sub, { x: M + 0.3, y: y + 0.52, w: 2.45, h: 0.45, fontFace: BFONT,
      fontSize: 11, bold: true, color: c, lineSpacing: 13, margin: 0 });
    s.addText(why, { x: M + 2.95, y: y + 0.16, w: 6.8, h: 0.34, fontFace: BFONT,
      fontSize: 11, color: MUTED, margin: 0 });
    s.addText(num, { x: M + 2.95, y: y + 0.5, w: 6.8, h: 0.56, fontFace: BFONT,
      fontSize: 12, color: INK, lineSpacing: 14.5, margin: 0 });
    s.addShape(pres.ShapeType.roundRect, { x: M + 10.0, y: y + 0.38, w: 1.55, h: 0.38,
      rectRadius: 0.19, fill: { color: c } });
    s.addText(verdict, { x: M + 10.0, y: y + 0.38, w: 1.55, h: 0.38, fontFace: BFONT,
      fontSize: 11, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
  });
  s.addText("네 줄 모두 “후보가 이기면 바꾼다”가 아니라 “미리 정한 기준을 넘으면 바꾼다”로 판정했다. 마지막 줄은 우리가 믿던 값이 독립 표본에서 재현되지 않아 스스로 철회한 경우다.",
    { x: M, y: 6.75, w: W - 2 * M, h: 0.5, fontFace: BFONT, fontSize: 13.5,
      color: SLATE, margin: 0 });
  s.addNotes("융합 가중치는 점추정이 아니라 신뢰구간 동률 집합과 사전 규칙으로 골랐습니다 — 점추정만 보면 0.4였습니다. 임베딩은 후보 7개를 한 가족으로 묶어 다중비교를 보정했고 통과가 0건이라 현행을 유지했습니다. 채점 모델은 게이트를 통과했지만, 그 채점을 실제로 돌리는 단계(M9)는 최종 평가 데이터에 접촉하므로 승인 전까지 실행하지 않습니다. 마지막 줄을 강조하세요 — 유리한 결론을 스스로 기각한 사례입니다.");
}

// ── 14. 군 활용성 ────────────────────────────────────────────────────
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

// ── 15. 로드맵 ───────────────────────────────────────────────────────
// **"모델 교체 완료"로 쓰지 않는다.** 부호 역전이 미해결이고, 신규 표본 확증이
// 선행 조건이다. 최종 평가 데이터 확장(33건)도 별도 승인 사안이다. [2026-08-20]
{
  const s = pres.addSlide();
  s.background = { color: SLATE };
  s.addText("남은 기간 로드맵", { x: M, y: 0.6, w: W - 2 * M, h: 0.7,
    fontFace: HFONT, fontSize: 32, bold: true, color: WHITE, margin: 0 });
  s.addText("8월 말 ~ 9월 말", { x: M, y: 1.28, w: W - 2 * M, h: 0.4,
    fontFace: BFONT, fontSize: 14, color: "8FA3B0", margin: 0 });
  const plan = [
    ["8월 말", "장면 설명 모델 판정", "새로 확보한 장편 35편·질의 315건으로 후보와 현행을 같은 조건에서 다시 재고 결정한다. 표본·질의 배정은 이미 문서로 고정했다", VISION, "확증 대기"],
    ["9월 중", "회의록 생성·평가", "회의 음성에서 화자별 발언을 정리해 회의록을 만들고 자동 채점한다", SPEECH, "설계 완료"],
    ["9월 말", "최종 정리", "요약 리포트의 사건 입도 개선, 성능 보고서·재현 절차·시연 패키지 마무리", "8FA3B0", "예정"],
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
  s.addText("판정 기준·표본·질의 배정은 모두 결과를 보기 전에 문서로 고정했다. 최종 평가 데이터를 다시 여는 일은 그 자체로 별도 결정으로 분리해 뒀다.",
    { x: M, y: 6.5, w: W - 2 * M, h: 0.5, fontFace: BFONT, fontSize: 14,
      color: "8FA3B0", margin: 0 });
  s.addNotes("남은 기간 계획 배점입니다. 8월 말 항목을 '교체 완료'라고 말하지 마세요 — 판정이 남았습니다. 새 표본 35편은 이미 확보했고(파일 해시까지 고정), 질의 315건의 유형 배정과 판정 기준을 결과를 보기 전에 커밋했습니다. 이 확증이 어느 방향으로 나오든 그 결과를 따릅니다. 최종 평가 39건에 33건을 더하는 것은 성능 수치를 좋게 만들려는 확장이 아니라 별도 결정으로 떼어 놨습니다.");
}

// 출력은 스크립트와 같은 폴더로 — 실행 위치에 따라 경로가 달라지지 않게 한다
const path = require("path");
pres.writeFile({ fileName: path.join(__dirname, "중간성과발표_2026-08-21.pptx") })
  .then(f => console.log("작성 완료:", f));
