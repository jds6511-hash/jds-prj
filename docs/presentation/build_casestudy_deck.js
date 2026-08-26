/* 캡션 → 검색 케이스 스터디 덱 — 2026-08-26
 *
 * 원본: docs/tutor/캡션검색_케이스스터디_1페이지.md (요약)
 *       docs/finalization/CAPTION_RETRIEVAL_CASESTUDY_RESULTS_2026-08-25.md (상세)
 *       docs/finalization/CAPTION_RETRIEVAL_CASESTUDY_TABLE.md (15질의 전체표)
 * 수치는 전부 위 동결 산출물에서 인용한다. 새로 계산하지 않는다.
 *
 * 출력이 docs/tutor/_local/ 인 이유: 원본 영상 프레임을 embed한다.
 * 프레임은 저장소 비포함 정책 대상이고 _local/ 과 *.pptx 는 .gitignore 대상이다.
 *
 * 색 규약은 2026-08-25 튜터 덱과 같다 — TEAL=3B(현행) · AMBER=4B(후보).
 * 같은 튜터가 연속으로 보는 자료라 모델↔색 대응을 바꾸지 않는다.
 *
 * 실행:  node docs/presentation/build_casestudy_deck.js
 */
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "../..");
const FRAMES = path.join(ROOT, "runs/casestudy_caption_retrieval/cs_20260825/frames_for_discussion");
const OUTDIR = path.join(ROOT, "docs/tutor/_local");
const OUT = path.join(OUTDIR, "캡션검색_케이스스터디.pptx");

const frame = (n) => {
  const f = path.join(FRAMES, n);
  if (!fs.existsSync(f)) throw new Error("프레임 없음: " + f);
  return f;
};

const p = new pptxgen();
p.layout = "LAYOUT_WIDE";
p.title = "캡션 → 검색 케이스 스터디 (2026-08-26)";

const W = 13.33, H = 7.5;
const INK = "12343B";
const PAPER = "F7F7F4";
const TEAL = "2C6E75";        // 3B (현행)
const TEAL_BG = "E8F0F0";
const AMBER = "B45309";       // 4B (후보)
const AMBER_BG = "F6EDE2";
const MUTED = "6B7280";
const LINE = "DCDCD6";
const WHITE = "FFFFFF";
const F = "맑은 고딕";
const MONO = "Consolas";

let page = 0;

function foot(s, dark) {
  const c = dark ? "8FA9AE" : MUTED;
  s.addText("캡션 → 검색 케이스 스터디 · 영상 1편 · 장면 5 · 질의 15 · 정성 사례 연구", {
    x: 0.62, y: H - 0.44, w: 9, h: 0.3, fontSize: 9, color: c, fontFace: F, margin: 0,
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
    x: 0.6, y: 0.7, w: 12.1, h: 0.66, fontSize: 26, bold: true,
    color: INK, fontFace: F, margin: 0,
  });
  s.addShape(p.shapes.LINE, {
    x: 0.62, y: 1.45, w: 12.1, h: 0, line: { color: LINE, width: 1 },
  });
  foot(s, false);
  return s;
}

function darkSlide() {
  page++;
  const s = p.addSlide();
  s.background = { color: INK };
  foot(s, true);
  return s;
}

/* 모델 카드 — 라벨 칩 + 옅은 배경. 가장자리 줄은 쓰지 않는다. */
function armCard(s, arm, x, y, w, h, body, opts) {
  const o = opts || {};
  const is3b = arm === "3B";
  const fill = is3b ? TEAL_BG : AMBER_BG;
  const key = is3b ? TEAL : AMBER;
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: x, y: y, w: w, h: h, fill: { color: fill }, rectRadius: 0.06,
    line: { color: fill },
  });
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: x + 0.22, y: y + 0.2, w: 0.86, h: 0.3,
    fill: { color: key }, rectRadius: 0.05, line: { color: key },
  });
  s.addText(arm, {
    x: x + 0.22, y: y + 0.2, w: 0.86, h: 0.3, fontSize: 12, bold: true,
    color: WHITE, align: "center", valign: "middle", fontFace: F, margin: 0,
  });
  if (o.tag) {
    s.addText(o.tag, {
      x: x + 1.2, y: y + 0.2, w: w - 1.5, h: 0.3, fontSize: 11, bold: true,
      color: key, valign: "middle", fontFace: F, margin: 0,
    });
  }
  s.addText(body, {
    x: x + 0.22, y: y + 0.6, w: w - 0.44, h: h - 0.8,
    fontSize: o.size || 12.5, color: INK, fontFace: F, lineSpacing: 19, margin: 0,
  });
}

/* 순위 배지 — 숫자를 크게, 단위를 작게. */
function rank(s, x, y, w, value, arm, win) {
  const key = arm === "3B" ? TEAL : AMBER;
  s.addText(
    [{ text: String(value), options: { fontSize: win ? 30 : 22, bold: true, color: win ? key : MUTED } },
     { text: "위", options: { fontSize: 12, color: MUTED } }],
    { x: x, y: y, w: w, h: 0.6, align: "center", valign: "middle", fontFace: MONO, margin: 0 }
  );
}

/* ---------------------------------------------------------------- 1 */
{
  const s = darkSlide();
  s.addText("케이스 스터디 · 2026-08-26", {
    x: 0.9, y: 1.9, w: 11, h: 0.3, fontSize: 12, bold: true,
    color: "8FA9AE", charSpacing: 2, fontFace: F, margin: 0,
  });
  s.addText("같은 화면을 두 모델이 다르게 설명하면\n검색 결과가 달라지는가", {
    x: 0.88, y: 2.4, w: 11.4, h: 1.7, fontSize: 34, bold: true,
    color: WHITE, fontFace: F, lineSpacing: 46, margin: 0,
  });
  s.addText("달라진다. 다만 한 모델이 항상 유리하지는 않았다.", {
    x: 0.9, y: 4.25, w: 11, h: 0.4, fontSize: 17, color: "C9D8DA", fontFace: F, margin: 0,
  });
  s.addShape(p.shapes.LINE, {
    x: 0.92, y: 4.95, w: 3.2, h: 0, line: { color: "3E5F68", width: 2 },
  });
  s.addText("영상 1편 · 장면 5개 · 질의 15개의 정성 사례 연구다.\n성능 추정 · 모델 우열 · 채택 근거가 아니다.", {
    x: 0.9, y: 5.25, w: 9, h: 0.8, fontSize: 13, color: "8FA9AE",
    fontFace: F, lineSpacing: 22, margin: 0,
  });
}

/* ---------------------------------------------------------------- 2 */
{
  const s = slide("설계", "결과를 보기 전에 동결했다");
  const rows = [
    ["영상", "요리·일상 브이로그 1편 · 32분 52초", "5초씩 395구간"],
    ["장면", "시간을 5등분해 각 구간의 첫 장면", "프레임만 보고 골랐다"],
    ["질의", "장면당 3개 — 사물 · 행동 · 맥락", "총 15개"],
    ["작성 시점", "캡션과 검색 결과를 열기 전", "동결 후 바꾸지 않았다"],
    ["대조", "같은 프레임 · 같은 노트북 · 같은 프롬프트 · 같은 4bit", "모델만 3B ↔ 4B"],
    ["검색", "캡션만 사용 (자막 채널 끔)", "후보 395구간 전체"],
  ];
  let y = 1.78;
  rows.forEach((r, i) => {
    if (i % 2 === 0) {
      s.addShape(p.shapes.RECTANGLE, {
        x: 0.62, y: y - 0.06, w: 12.1, h: 0.74, fill: { color: "EFEFEA" }, line: { color: "EFEFEA" },
      });
    }
    s.addText(r[0], {
      x: 0.85, y: y, w: 1.7, h: 0.6, fontSize: 13, bold: true, color: TEAL,
      valign: "middle", fontFace: F, margin: 0,
    });
    s.addText(r[1], {
      x: 2.7, y: y, w: 6.5, h: 0.6, fontSize: 13.5, color: INK,
      valign: "middle", fontFace: F, margin: 0,
    });
    s.addText(r[2], {
      x: 9.4, y: y, w: 3.2, h: 0.6, fontSize: 12, color: MUTED,
      valign: "middle", fontFace: F, margin: 0,
    });
    y += 0.74;
  });
  s.addText("동결한 것은 장면·질의다. 결과가 재미없어도 바꾸지 않는다는 뜻이고, 실제로 바꾸지 않았다.", {
    x: 0.85, y: 6.45, w: 11.6, h: 0.4, fontSize: 12.5, italic: true,
    color: MUTED, fontFace: F, margin: 0,
  });
}

/* ---------------------------------------------------------------- 3 */
{
  const s = slide("대표 사례 · scene02", "같은 프레임 한 장, 두 모델이 고른 것이 달랐다");
  s.addImage({ path: frame("seg0079_00395s.jpg"), x: 0.62, y: 1.75, w: 5.7, h: 3.21 });
  s.addText("6:35~6:40 · 창고형 매장을 위에서 내려다본 화면", {
    x: 0.62, y: 5.02, w: 5.7, h: 0.3, fontSize: 10.5, color: MUTED, fontFace: F, margin: 0,
  });
  s.addText("파란 COSTCO 배너 · 유리문 냉장 진열장 · 적재된 상자와 팔레트", {
    x: 0.62, y: 5.3, w: 5.7, h: 0.5, fontSize: 11.5, color: INK,
    fontFace: F, lineSpacing: 17, margin: 0,
  });
  armCard(s, "3B", 6.65, 1.75, 6.05, 1.85,
    "화면의 배너 문구를 중심으로 —\n“‘COSTCO’와 함께 한국어로 된 메시지”, “‘Join Now!’”, 트럭 이미지",
    { tag: "배너 문구를 골랐다" });
  armCard(s, "4B", 6.65, 3.78, 6.05, 1.55,
    "냉장 진열대를 중심으로 —\n“코스트코 내부의 냉장고 진열대와 주변 상품들”",
    { tag: "냉장 진열대를 골랐다" });
  s.addText("어느 쪽도 화면을 잘못 본 것이 아니다.\n같은 화면에서 무엇을 남길지가 갈렸을 뿐이다.", {
    x: 6.65, y: 5.5, w: 6.05, h: 0.7, fontSize: 13, bold: true, color: INK,
    fontFace: F, lineSpacing: 21, margin: 0,
  });
}

/* ---------------------------------------------------------------- 4 */
{
  const s = slide("대표 사례 · scene02", "그 선택이 1위를 뒤집는다");
  const head = [
    ["같은 장면을 겨냥한 검색어", 0.85, 6.2],
    ["3B", 7.35, 1.5],
    ["4B", 9.05, 1.5],
    ["그 arm이 1위로 올린 장면", 10.6, 2.1],
  ];
  head.forEach((h) => {
    s.addText(h[0], {
      x: h[1], y: 1.78, w: h[2], h: 0.32, fontSize: 11, bold: true, color: MUTED,
      align: h[0] === "3B" || h[0] === "4B" ? "center" : "left", fontFace: F, margin: 0,
    });
  });
  const qs = [
    ["대형 마트 안에 걸린\n파란 광고 배너", 1, 15, "3B", "정답 장면", "seg 90 · 다른 매장"],
    ["냉장 진열장과 쌓인 상자가 있는\n창고형 매장 내부", 18, 1, "4B", "seg 80 · 옆 구간", "정답 장면"],
  ];
  let y = 2.25;
  qs.forEach((q) => {
    s.addShape(p.shapes.RECTANGLE, {
      x: 0.62, y: y, w: 12.1, h: 1.42, fill: { color: WHITE }, line: { color: LINE },
    });
    s.addText(q[0], {
      x: 0.85, y: y + 0.1, w: 6.2, h: 1.22, fontSize: 14, color: INK,
      valign: "middle", fontFace: F, lineSpacing: 21, margin: 0,
    });
    rank(s, 7.35, y + 0.4, 1.5, q[1], "3B", q[3] === "3B");
    rank(s, 9.05, y + 0.4, 1.5, q[2], "4B", q[3] === "4B");
    s.addText(
      [{ text: "3B → " + q[4], options: { color: TEAL } },
       { text: "\n4B → " + q[5], options: { color: AMBER } }],
      { x: 10.6, y: y + 0.1, w: 2.1, h: 1.22, fontSize: 11, valign: "middle",
        fontFace: F, lineSpacing: 17, margin: 0 }
    );
    y += 1.6;
  });
  s.addText("배너를 묻는 질의는 3B가, 진열대를 묻는 질의는 4B가 정답을 1위로 올렸다.\n모델이 화면을 맞게 보느냐보다, 같은 화면에서 무엇을 캡션에 남겼는지가 순위에 직접 전달됐다.", {
    x: 0.85, y: 5.62, w: 11.6, h: 0.8, fontSize: 13.5, bold: true, color: INK,
    fontFace: F, lineSpacing: 22, margin: 0,
  });
  s.addText("부수 관측 — 3B가 배너 글자를 그대로 옮겨 적은 것은 프롬프트가 금지한 동작이다. 결과적으로 텍스트 질의에 유리했지만 품질 우위로 읽지 않는다.", {
    x: 0.85, y: 6.5, w: 11.6, h: 0.4, fontSize: 11.5, italic: true, color: MUTED,
    fontFace: F, margin: 0,
  });
}

/* ---------------------------------------------------------------- 5 */
{
  const s = slide("scene01", "정답이 아니라 다른 장면이 1위가 됐을 때");
  s.addText("정답 장면 · 0:00~0:05", {
    x: 0.62, y: 1.72, w: 5.9, h: 0.3, fontSize: 11, bold: true, color: INK, fontFace: F, margin: 0,
  });
  s.addImage({ path: frame("seg0000_00000s.jpg"), x: 0.62, y: 2.05, w: 5.9, h: 3.32 });
  s.addText("3B가 이 장면에 쓴 캡션 — “노란색 그릇에 담긴 노란색 소스가 보입니다…”\n팬 · 기름 · 새우 · 튀기다 가 하나도 없다", {
    x: 0.62, y: 5.45, w: 5.9, h: 0.75, fontSize: 11.5, color: TEAL,
    fontFace: F, lineSpacing: 18, margin: 0,
  });
  s.addText("3B가 1위로 올린 장면 · 15:40", {
    x: 6.82, y: 1.72, w: 5.9, h: 0.3, fontSize: 11, bold: true, color: INK, fontFace: F, margin: 0,
  });
  s.addImage({ path: frame("seg0188_00940s.jpg"), x: 6.82, y: 2.05, w: 5.9, h: 3.32 });
  s.addText("“두 개의 새우가 보입니다 … ‘이대로 기름에 튀기듯 구워주면 끝!’”\n검색어의 “새우” · “기름에 튀기”와 직접 겹친다", {
    x: 6.82, y: 5.45, w: 5.9, h: 0.75, fontSize: 11.5, color: MUTED,
    fontFace: F, lineSpacing: 18, margin: 0,
  });
  s.addText("정답을 못 찾은 이유를 “검색 실패”로 끝내지 않고, 정답 캡션에서 무엇이 빠졌고 오답 1위 캡션에는 무엇이 있었는지까지 되짚을 수 있었다.", {
    x: 0.62, y: 6.32, w: 12.1, h: 0.5, fontSize: 13, bold: true, color: INK,
    fontFace: F, lineSpacing: 20, margin: 0,
  });
}

/* ---------------------------------------------------------------- 6 */
{
  const s = slide("scene05", "화면에 없는 것을 적으면 정답이 밀려난다");
  s.addImage({ path: frame("seg0316_01580s.jpg"), x: 0.62, y: 1.75, w: 5.7, h: 3.21 });
  s.addText("26:20~26:25 · 재봉틀 작업대에서 손이 남색 물방울 무늬 천을 잡고 있다", {
    x: 0.62, y: 5.05, w: 5.7, h: 0.5, fontSize: 10.5, color: MUTED,
    fontFace: F, lineSpacing: 16, margin: 0,
  });
  armCard(s, "3B", 6.65, 1.75, 6.05, 1.6,
    "“여성의 손이 검은색 패턴이 있는 티셔츠를 들어올리고 있습니다. 배경에는 수영장이 보이며…”",
    { tag: "세 질의 모두 148~181위" });
  armCard(s, "4B", 6.65, 3.5, 6.05, 1.6,
    "“손이 다크 브루 이브닝 패턴의 천을 들고 있으며, 배경에는 직조기와 커트 툴이 놓인 작업대가 보입니다”",
    { tag: "9 · 22 · 34위" });
  s.addText("천을 “티셔츠”로, 작업대를 “수영장”으로 적으니 질의의 천 · 재봉틀 · 작업대와 겹치는 표현이 남지 않았다.", {
    x: 0.62, y: 5.72, w: 12.1, h: 0.4, fontSize: 13.5, bold: true, color: INK,
    fontFace: F, margin: 0,
  });
  s.addText("4B도 완벽하지 않다 — “다크 브루 이브닝 패턴”은 의미가 불명한 문구이고, 1위도 아니었다(유사한 재봉 장면이 영상에 여러 개 있다).", {
    x: 0.62, y: 6.2, w: 12.1, h: 0.4, fontSize: 12, color: MUTED,
    fontFace: F, margin: 0,
  });
}

/* ---------------------------------------------------------------- 7 */
{
  const s = slide("정리", "타율 차이는 어디서 나는가");
  const items = [
    ["정답 정보를 생략하거나 잘못 부르면", "그 이름을 가진 다른 장면이 1위가 된다", "s01 · s04 · s05"],
    ["화면에 없는 것을 적으면", "정답과 겹치는 표현의 비중이 낮아진다", "s05 “수영장”"],
    ["같은 프레임에서 다른 요소를 고르면", "질의가 무엇을 묻느냐에 따라 1위가 뒤집힌다", "s02"],
    ["다른 장면 캡션이 질의 표현과 축자로 겹치면", "정답을 눌러 버린다", "s04 뚜껑 질의"],
    ["짧아서 배경어가 없으면", "맥락을 묻는 질의에 불리하다", "s03 4B 170위"],
    ["길다고 유리하지도 않다", "오인이 섞이면 더 나쁘다", "s05 3B 181위"],
  ];
  let y = 1.75;
  items.forEach((it) => {
    s.addShape(p.shapes.RECTANGLE, {
      x: 0.62, y: y, w: 12.1, h: 0.7, fill: { color: WHITE }, line: { color: LINE },
    });
    s.addText(it[0], {
      x: 0.88, y: y, w: 4.9, h: 0.7, fontSize: 13, bold: true, color: INK,
      valign: "middle", fontFace: F, margin: 0,
    });
    s.addText(it[1], {
      x: 5.9, y: y, w: 5.1, h: 0.7, fontSize: 12.5, color: MUTED,
      valign: "middle", fontFace: F, margin: 0,
    });
    s.addText(it[2], {
      x: 11.1, y: y, w: 1.5, h: 0.7, fontSize: 10.5, color: TEAL,
      align: "right", valign: "middle", fontFace: F, margin: 0,
    });
    y += 0.8;
  });
  s.addText("전부 “~했을 가능성이 있다” 수준이다. 인과를 확정하지 않는다.", {
    x: 0.88, y: 6.62, w: 11.6, h: 0.35, fontSize: 12, italic: true, color: MUTED,
    fontFace: F, margin: 0,
  });
}

/* ---------------------------------------------------------------- 8 */
{
  const s = slide("숫자", "보여주되 과장하지 않는다");
  s.addShape(p.shapes.RECTANGLE, {
    x: 0.62, y: 1.75, w: 12.1, h: 1.5, fill: { color: WHITE }, line: { color: LINE },
  });
  s.addText("Top-1 적중", {
    x: 0.9, y: 1.95, w: 3.4, h: 0.35, fontSize: 13, bold: true, color: INK, fontFace: F, margin: 0,
  });
  s.addText("먼저 볼 것 — 1위를 맞힌 횟수는 두 모델이 같다", {
    x: 0.9, y: 2.35, w: 5.2, h: 0.6, fontSize: 12.5, color: MUTED,
    fontFace: F, lineSpacing: 18, margin: 0,
  });
  s.addText([{ text: "2", options: { fontSize: 40, bold: true, color: TEAL } },
             { text: " / 15", options: { fontSize: 16, color: MUTED } }],
    { x: 6.4, y: 2.0, w: 2.6, h: 1.0, align: "center", valign: "middle", fontFace: MONO, margin: 0 });
  s.addText("3B", { x: 6.4, y: 2.85, w: 2.6, h: 0.3, fontSize: 11, bold: true,
                    color: TEAL, align: "center", fontFace: F, margin: 0 });
  s.addText([{ text: "2", options: { fontSize: 40, bold: true, color: AMBER } },
             { text: " / 15", options: { fontSize: 16, color: MUTED } }],
    { x: 9.4, y: 2.0, w: 2.6, h: 1.0, align: "center", valign: "middle", fontFace: MONO, margin: 0 });
  s.addText("4B", { x: 9.4, y: 2.85, w: 2.6, h: 0.3, fontSize: 11, bold: true,
                    color: AMBER, align: "center", fontFace: F, margin: 0 });

  const rows = [
    ["정답 순위가 더 높았던 질의", "4 / 15", "11 / 15"],
    ["정답 순위 중위수", "31위", "10위"],
    ["평균 캡션 길이", "128.5자", "76.4자"],
  ];
  let y = 3.5;
  rows.forEach((r) => {
    s.addShape(p.shapes.RECTANGLE, {
      x: 0.62, y: y, w: 12.1, h: 0.72, fill: { color: "EFEFEA" }, line: { color: "EFEFEA" },
    });
    s.addText(r[0], {
      x: 0.9, y: y, w: 5.2, h: 0.72, fontSize: 13, color: INK,
      valign: "middle", fontFace: F, margin: 0,
    });
    s.addText(r[1], {
      x: 6.4, y: y, w: 2.6, h: 0.72, fontSize: 16, bold: true, color: TEAL,
      align: "center", valign: "middle", fontFace: MONO, margin: 0,
    });
    s.addText(r[2], {
      x: 9.4, y: y, w: 2.6, h: 0.72, fontSize: 16, bold: true, color: AMBER,
      align: "center", valign: "middle", fontFace: MONO, margin: 0,
    });
    y += 0.82;
  });
  s.addText("Top-1만 보면 둘 다 2/15로 같다. 순위를 비교하면 15개 중 11개에서 4B 쪽이 더 높았고 중위수도 31위 대 10위였다.\n상위 1건만 세면 보이지 않는 차이가 있다는 관측이고, 어느 모델이 낫다는 결론이 아니다.", {
    x: 0.9, y: 6.15, w: 11.6, h: 0.8, fontSize: 12.5, color: INK,
    fontFace: F, lineSpacing: 20, margin: 0,
  });
}

/* ---------------------------------------------------------------- 9 */
{
  const s = slide("경계", "이 자료로 말할 수 있는 것 / 없는 것");
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: 0.62, y: 1.8, w: 5.95, h: 2.95, fill: { color: TEAL_BG }, rectRadius: 0.06,
    line: { color: TEAL_BG },
  });
  s.addText("말할 수 있다", {
    x: 0.95, y: 2.05, w: 5.3, h: 0.4, fontSize: 15, bold: true, color: TEAL, fontFace: F, margin: 0,
  });
  s.addText([
    { text: "캡션이 무엇을 골라 묘사하느냐가 검색 순위에 전달된다", options: { bullet: true, breakLine: true } },
    { text: "정답을 못 찾았을 때 원인을 캡션 수준까지 되짚을 수 있다", options: { bullet: true, breakLine: true } },
    { text: "한 모델이 항상 유리하지는 않다", options: { bullet: true } },
  ], {
    x: 0.95, y: 2.6, w: 5.3, h: 2.4, fontSize: 13.5, color: INK, valign: "top",
    fontFace: F, lineSpacing: 22, paraSpaceAfter: 10, margin: 0,
  });

  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: 6.77, y: 1.8, w: 5.95, h: 2.95, fill: { color: "EDEAE6" }, rectRadius: 0.06,
    line: { color: "EDEAE6" },
  });
  s.addText("말할 수 없다", {
    x: 7.1, y: 2.05, w: 5.3, h: 0.4, fontSize: 15, bold: true, color: "8A5A2B", fontFace: F, margin: 0,
  });
  s.addText([
    { text: "모델 우열", options: { bullet: true, breakLine: true } },
    { text: "성능 추정 · 벤치마크", options: { bullet: true, breakLine: true } },
    { text: "통계적 유의성", options: { bullet: true, breakLine: true } },
    { text: "4B 채택 근거", options: { bullet: true } },
  ], {
    x: 7.1, y: 2.6, w: 5.3, h: 2.4, fontSize: 13.5, color: INK, valign: "top",
    fontFace: F, lineSpacing: 22, paraSpaceAfter: 10, margin: 0,
  });
  s.addText("영상 1편 · 장면 5개 · 질의 15개", {
    x: 7.1, y: 4.32, w: 5.3, h: 0.3, fontSize: 11.5, italic: true, color: MUTED, fontFace: F, margin: 0,
  });

  s.addText("한계 하나 더 — 두 모델을 같은 조건에서 새로 생성해 맞췄지만, 두 실행의 저장소 상태가 완전히 같았다는 것까지는 입증하지 못했다(생성 코드·설정 경로에는 차이가 없음을 확인했다).", {
    x: 0.62, y: 5.15, w: 12.1, h: 0.7, fontSize: 12.5, color: MUTED,
    fontFace: F, lineSpacing: 20, margin: 0,
  });
}

/* ---------------------------------------------------------------- 10 */
{
  const s = darkSlide();
  s.addText("결론", {
    x: 0.9, y: 1.6, w: 11, h: 0.3, fontSize: 12, bold: true,
    color: "8FA9AE", charSpacing: 2, fontFace: F, margin: 0,
  });
  s.addText("캡션이 무엇을 적느냐는 검색 순위까지 전달된다.\n그러나 이 사례로 모델 우열을 말할 수는 없다.", {
    x: 0.88, y: 2.05, w: 11.4, h: 1.3, fontSize: 26, bold: true,
    color: WHITE, fontFace: F, lineSpacing: 38, margin: 0,
  });
  const box = [
    ["배포", "Qwen2.5-VL-3B 유지"],
    ["Qwen3-VL-4B", "후보이며 채택 아님"],
    ["과학적 우열", "미해결"],
  ];
  let x = 0.9;
  box.forEach((b) => {
    s.addShape(p.shapes.ROUNDED_RECTANGLE, {
      x: x, y: 3.75, w: 3.83, h: 1.25, fill: { color: "1B4650" }, rectRadius: 0.06,
      line: { color: "2C6E75" },
    });
    s.addText(b[0], {
      x: x + 0.3, y: 3.95, w: 3.3, h: 0.3, fontSize: 11, bold: true,
      color: "8FA9AE", fontFace: F, margin: 0,
    });
    s.addText(b[1], {
      x: x + 0.3, y: 4.28, w: 3.3, h: 0.5, fontSize: 15, bold: true,
      color: WHITE, fontFace: F, margin: 0,
    });
    x += 4.02;
  });
  s.addText("이 케이스 스터디는 그 판단을 바꾸지 않는다.", {
    x: 0.92, y: 5.35, w: 11, h: 0.4, fontSize: 14, color: "C9D8DA", fontFace: F, margin: 0,
  });
  s.addText("상세  docs/finalization/CAPTION_RETRIEVAL_CASESTUDY_RESULTS_2026-08-25.md\n15질의 전체표  docs/finalization/CAPTION_RETRIEVAL_CASESTUDY_TABLE.md", {
    x: 0.9, y: 5.95, w: 11, h: 0.7, fontSize: 11, color: "6E8B92",
    fontFace: MONO, lineSpacing: 18, margin: 0,
  });
}

fs.mkdirSync(OUTDIR, { recursive: true });
p.writeFile({ fileName: OUT }).then(() => console.log("wrote " + OUT));
