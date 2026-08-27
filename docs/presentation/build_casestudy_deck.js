/* 캡션 → 검색 케이스 스터디 덱 — 2026-08-26 (14장)
 *
 * 구조: 튜터 질문 → 방법 → **장면 5개를 전부 같은 형식으로** → 전체표 → 숫자 → 경로 → 답
 * 장면 카드 6요소 고정: ① 선택한 장면 ② 질문 3개 ③ 3B/4B target 순위
 *                      ④ 다른 장면이 1위면 그 장면 ⑤ target vs top1 캡션 ⑥ 한 줄 해석
 *
 * 원본: docs/finalization/CAPTION_RETRIEVAL_CASESTUDY_TABLE.md   (15질의 순위 전건)
 *       docs/finalization/CAPTION_RETRIEVAL_CASESTUDY_RESULTS_2026-08-25.md (캡션 원문)
 *       docs/tutor/캡션검색_케이스스터디_1페이지.md
 * 질의 문구·순위·캡션은 전부 동결 산출물에서 그대로 가져왔다. 새로 만들거나 계산하지 않았다.
 *
 * 출력이 docs/tutor/_local/ 인 이유: 원본 영상 프레임을 embed한다.
 * 프레임은 저장소 비포함 정책 대상이고 _local/ 과 *.pptx 는 .gitignore 대상이다.
 * 프레임 자체도 미추적이다 — docs/finalization/HISTORY_REWRITE_2026-08-26.md
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
const BAND = "EFEFEA";
const TEAL = "2C6E75";        // 3B (현행)
const TEAL_BG = "E8F0F0";
const AMBER = "B45309";       // 4B (후보)
const MUTED = "6B7280";
const LINE = "DCDCD6";
const WHITE = "FFFFFF";
const F = "맑은 고딕";
const MONO = "Consolas";

let page = 0;

/* 푸터는 그 장의 **표본 범위**를 적는다. 14·15장은 194편 쌍대 분석이라 1편 사례
 * 문구를 그대로 두면 슬라이드와 푸터가 서로 다른 범위를 주장하게 된다. */
const SCOPE_CASE = "캡션 → 검색 케이스 스터디 · 영상 1편 · 장면 5 · 질의 15 · 정성 사례 연구";
const SCOPE_PAIRED = "캡션 서술 방식 · AI Hub 194편 2,328구간 쌍대 기술 분석 · 채택 근거 아님";
const SCOPE_OTHER = "캡션 서술 방식 · 자체 취득 영상 3편 · 구간별 쌍대 비교 · 채택 근거 아님";
/* 원인 장은 사람이 확인한 395구간과 자동 후보 2,328구간을 함께 인용한다 — 둘을 갈라 적는다 */
const SCOPE_CAUSE = "텍스트 처리 감사 · 확인분 395구간 + 자동 후보 2,328구간 · 원인은 해석";
let scope = SCOPE_CASE;

function foot(s, dark) {
  const c = dark ? "8FA9AE" : MUTED;
  s.addText(scope, {
    x: 0.62, y: H - 0.42, w: 9, h: 0.3, fontSize: 9, color: c, fontFace: F, margin: 0,
  });
  s.addText(String(page), {
    x: W - 1.1, y: H - 0.42, w: 0.5, h: 0.3, fontSize: 9, color: c,
    fontFace: F, align: "right", margin: 0,
  });
}

function slide(kicker, title) {
  page++;
  const s = p.addSlide();
  s.background = { color: PAPER };
  if (kicker) {
    s.addText(kicker, {
      x: 0.62, y: 0.38, w: 12, h: 0.28, fontSize: 11, bold: true,
      color: TEAL, charSpacing: 2, fontFace: F, margin: 0,
    });
  }
  s.addText(title, {
    x: 0.6, y: 0.66, w: 12.15, h: 0.62, fontSize: 24, bold: true,
    color: INK, fontFace: F, margin: 0,
  });
  s.addShape(p.shapes.LINE, {
    x: 0.62, y: 1.38, w: 12.1, h: 0, line: { color: LINE, width: 1 },
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

function card(s, x, y, w, h, fill, line) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: x, y: y, w: w, h: h, fill: { color: fill }, rectRadius: 0.05,
    line: { color: line || fill },
  });
}

/* 캡션 카드 — 라벨 + 원문 + 한 줄 진단 */
function capCard(s, x, y, w, h, label, labelColor, body, diag, diagColor, fs) {
  card(s, x, y, w, h, WHITE, LINE);
  s.addText(label, {
    x: x + 0.18, y: y + 0.08, w: w - 0.36, h: 0.26, fontSize: 10, bold: true,
    color: labelColor, fontFace: F, margin: 0,
  });
  s.addText(body, {
    // 카드 3장(3B·4B·1위 장면) 배치에서는 폭이 좁아 본문을 줄인다
    x: x + 0.18, y: y + 0.34, w: w - 0.36, h: h - 0.78, fontSize: fs || 10.5, color: INK,
    fontFace: F, lineSpacing: (fs || 10.5) + 4.5, valign: "top", margin: 0,
  });
  s.addText(diag, {
    x: x + 0.18, y: y + h - 0.42, w: w - 0.36, h: 0.34, fontSize: 10, bold: true,
    color: diagColor, fontFace: F, valign: "middle", margin: 0,
  });
}

/* ============================================================ 장면 카드
 * 5개 장면 전부 같은 틀. 튜터가 장면을 넘기며 바로 비교할 수 있게 한다.
 */
function sceneSlide(d) {
  const s = slide("Scene " + d.n + " · seg " + d.seg + " · " + d.time, d.title);

  /* ① 내가 선택한 장면 */
  s.addImage({ path: frame(d.frame), x: 0.62, y: 1.55, w: 3.9, h: 2.19 });
  s.addText("① 내가 선택한 장면", {
    x: 0.62, y: 3.8, w: 3.9, h: 0.26, fontSize: 10, bold: true, color: TEAL,
    fontFace: F, margin: 0,
  });
  s.addText(d.desc, {
    x: 0.62, y: 4.04, w: 3.9, h: 0.5, fontSize: 10.5, color: INK,
    fontFace: F, lineSpacing: 15, valign: "top", margin: 0,
  });

  /* ② 질문 3개 + ③ target 순위 */
  s.addText("② 캡션·결과를 보기 전에 작성한 질문 3개", {
    x: 4.8, y: 1.5, w: 5.6, h: 0.26, fontSize: 10, bold: true, color: TEAL,
    fontFace: F, margin: 0,
  });
  s.addText("③ 내가 고른 장면의 순위", {
    x: 10.45, y: 1.5, w: 2.3, h: 0.26, fontSize: 10, bold: true, color: TEAL,
    align: "center", fontFace: F, margin: 0,
  });
  ["3B", "4B"].forEach((a, i) => {
    s.addText(a, {
      x: 10.45 + i * 1.16, y: 1.76, w: 1.14, h: 0.24, fontSize: 10.5, bold: true,
      color: i === 0 ? TEAL : AMBER, align: "center", fontFace: F, margin: 0,
    });
  });
  let y = 2.04;
  d.queries.forEach((q, i) => {
    const [text, r3, r4] = q;
    if (i % 2 === 0) {
      s.addShape(p.shapes.RECTANGLE, {
        x: 4.8, y: y, w: 7.92, h: 0.58, fill: { color: BAND }, line: { color: BAND },
      });
    }
    s.addText("Q" + (i + 1) + ".  " + text, {
      // A2에서 Scene01 Q3가 38자로 길어졌다 — 10.5pt여야 한 줄에 들어간다
      x: 4.98, y: y, w: 5.4, h: 0.58, fontSize: 10.5, color: INK,
      valign: "middle", fontFace: F, margin: 0,
    });
    [[r3, TEAL], [r4, AMBER]].forEach((cell, k) => {
      const [rank, col] = cell;
      const win = (k === 0 ? r3 < r4 : r4 < r3);
      const cx = 10.45 + k * 1.16;
      if (rank === 1) {
        card(s, cx + 0.14, y + 0.09, 0.86, 0.4, col, col);
        s.addText("1위", {
          x: cx + 0.14, y: y + 0.09, w: 0.86, h: 0.4, fontSize: 12.5, bold: true,
          color: WHITE, align: "center", valign: "middle", fontFace: F, margin: 0,
        });
      } else {
        s.addText(
          [{ text: String(rank), options: { fontSize: win ? 17 : 14, bold: win, color: win ? col : MUTED } },
           { text: "위", options: { fontSize: 9.5, color: MUTED } }],
          { x: cx, y: y, w: 1.14, h: 0.58, align: "center", valign: "middle",
            fontFace: MONO, margin: 0 }
        );
      }
    });
    y += 0.58;
  });
  s.addText("굵은 값 = 그 질문에서 순위가 더 높았던 쪽 · 색칠 = 내가 고른 장면이 1위 (후보 395구간 중)", {
    x: 4.98, y: 3.84, w: 7.7, h: 0.24, fontSize: 9.5, italic: true, color: MUTED,
    fontFace: F, margin: 0,
  });

  /* ④⑤ 아래 띠 — 대표 사례 하나만 크게 */
  s.addShape(p.shapes.RECTANGLE, {
    x: 0.62, y: 4.6, w: 12.1,
    h: (d.miss && d.miss.altCap) ? 1.9 : 1.74,
    fill: { color: BAND }, line: { color: BAND },
  });
  if (d.compare) {
    s.addText(d.compare.head, {
      x: 0.85, y: 4.7, w: 11.6, h: 0.28, fontSize: 10.5, bold: true, color: INK,
      fontFace: F, margin: 0,
    });
    capCard(s, 0.85, 5.02, 5.75, 1.2, "3B 캡션 — " + d.compare.tag3, TEAL,
            d.compare.cap3, d.compare.diag3, TEAL);
    capCard(s, 6.82, 5.02, 5.68, 1.2, "4B 캡션 — " + d.compare.tag4, AMBER,
            d.compare.cap4, d.compare.diag4, AMBER);
  } else {
    const m = d.miss;
    const col = m.arm === "3B" ? TEAL : AMBER;
    /* 오른쪽 카드가 top1 장면의 캡션이 아닌 경우(같은 장면의 다른 모델 캡션)에는
     * bandHead로 문구를 바꾼다 — 머리글과 카드 내용이 어긋나면 안 된다. */
    s.addText(m.bandHead ||
      ("④ " + m.arm + "에서 내가 고른 장면이 " + m.rank + "위 — 대신 1위가 된 장면과 캡션을 비교한다"), {
      x: 0.85, y: 4.7, w: 11.6, h: 0.28, fontSize: 10.5, bold: true, color: INK,
      fontFace: F, margin: 0,
    });
    if (m.altCap) {
      /* 두 모델이 **같은 장면**을 뭐라고 썼는지 나란히 보여야 한다 — 카드 3장.
       * 그래서 이 분기만 띠·카드가 조금 높고 본문이 9.5pt다. */
      s.addImage({ path: frame(m.top1Frame), x: 0.85, y: 5.02, w: 1.6, h: 0.9 });
      s.addText(m.top1Label, {
        x: 0.85, y: 5.94, w: 2.0, h: 0.2, fontSize: 8, color: MUTED, fontFace: F, margin: 0,
      });
      capCard(s, 2.62, 5.02, 3.24, 1.36, "⑤ 내가 고른 장면의 3B 캡션", TEAL,
              m.targetCap, "✕  " + m.targetMiss, TEAL, 9.5);
      capCard(s, 6.02, 5.02, 3.24, 1.36, m.altLabel || "같은 장면의 4B 캡션", AMBER,
              m.altCap, "✕  " + m.altMiss, AMBER, 9.5);
      capCard(s, 9.42, 5.02, 3.3, 1.36, m.top1CardLabel || "1위가 된 다른 장면의 캡션", MUTED,
              m.top1Cap, "✓  " + m.top1Hit, INK, 9.5);
    } else {
      s.addImage({ path: frame(m.top1Frame), x: 0.85, y: 5.02, w: 1.96, h: 1.1 });
      s.addText(m.top1Label, {
        x: 0.85, y: 6.12, w: 2.2, h: 0.2, fontSize: 8.5, color: MUTED, fontFace: F, margin: 0,
      });
      capCard(s, 3.0, 5.02, 4.72, 1.2, "⑤ 내가 고른 장면의 " + m.arm + " 캡션", col,
              m.targetCap, "✕  " + m.targetMiss, col);
      capCard(s, 7.9, 5.02, 4.6, 1.2, m.top1CardLabel || "1위가 된 다른 장면의 캡션", MUTED,
              m.top1Cap, "✓  " + m.top1Hit, INK);
    }
  }

  /* ⑥ 한 줄 해석 */
  s.addText("⑥  " + d.read, {
    x: 0.62, y: (d.miss && d.miss.altCap) ? 6.6 : 6.46, w: 12.1, h: 0.52,
    fontSize: 12, bold: true, color: INK,
    fontFace: F, lineSpacing: 18, valign: "top", margin: 0,
  });
  return s;
}

/* ---------------------------------------------------------------- 1 표지 */
{
  const s = darkSlide();
  s.addText("케이스 스터디 · 2026-08-26", {
    x: 0.9, y: 1.75, w: 11, h: 0.3, fontSize: 12, bold: true,
    color: "8FA9AE", charSpacing: 2, fontFace: F, margin: 0,
  });
  s.addText("캡션 모델의 설명 차이가\n검색 결과에 어떻게 전달되는가", {
    x: 0.88, y: 2.25, w: 11.4, h: 1.7, fontSize: 33, bold: true,
    color: WHITE, fontFace: F, lineSpacing: 45, margin: 0,
  });
  s.addText("Qwen2.5-VL-3B   vs   Qwen3-VL-4B", {
    x: 0.9, y: 4.15, w: 11, h: 0.35, fontSize: 16, bold: true, color: "C9D8DA",
    fontFace: MONO, margin: 0,
  });
  s.addText("5개 장면 × 장면당 질문 3개 = 15개 질의", {
    x: 0.9, y: 4.55, w: 11, h: 0.35, fontSize: 15, color: "9FB8BC", fontFace: F, margin: 0,
  });
  s.addShape(p.shapes.LINE, {
    x: 0.92, y: 5.2, w: 3.2, h: 0, line: { color: "3E5F68", width: 2 },
  });
  s.addText("같은 장면을 두 모델이 다르게 설명할 때, 그 차이가 실제 검색 순위에도\n나타나는지 확인했다.", {
    x: 0.9, y: 5.45, w: 10, h: 0.8, fontSize: 13.5, color: "8FA9AE",
    fontFace: F, lineSpacing: 22, margin: 0,
  });
}

/* ---------------------------------------------------------------- 2 질문 */
{
  const s = slide("무엇을 확인했나", "튜터 피드백에서 시작한 질문");
  const qs = [
    ["①", "같은 장면을 3B와 4B가 어떻게 다르게 설명하는가?"],
    ["②", "같은 질문을 넣었을 때 내가 선택한 장면이 검색되는가?"],
    ["③", "다른 장면이 1위가 된다면, 그 장면의 캡션에는 무엇이 적혀 있었는가?"],
  ];
  let y = 1.8;
  qs.forEach((q) => {
    card(s, 0.62, y, 12.1, 1.2, WHITE, LINE);
    s.addText(q[0], {
      x: 0.95, y: y, w: 0.8, h: 1.2, fontSize: 28, bold: true, color: TEAL,
      valign: "middle", fontFace: F, margin: 0,
    });
    s.addText(q[1], {
      x: 1.9, y: y, w: 10.5, h: 1.2, fontSize: 17, bold: true, color: INK,
      valign: "middle", fontFace: F, margin: 0,
    });
    y += 1.4;
  });
  card(s, 0.62, 6.1, 12.1, 0.78, TEAL_BG);
  s.addText("목표는 “누가 이겼는가”보다, 캡션의 차이가 검색 결과로 전달되는 과정을 확인하는 것이다.", {
    x: 0.95, y: 6.1, w: 11.5, h: 0.78, fontSize: 13.5, bold: true, color: INK,
    valign: "middle", fontFace: F, margin: 0,
  });
}

/* ---------------------------------------------------------------- 3 방법 */
{
  const s = slide("비교 방법", "결과를 보기 전에 장면과 질문을 먼저 고정했다");
  s.addText([
    { text: "영상 1편을 시간으로 5등분하고, 각 구간에서 장면 1개씩 총 5개를 골랐다.", options: { breakLine: true } },
    { text: "장면을 고를 때는 대표 프레임만 봤다 — 캡션은 열지 않았다.", options: { breakLine: true } },
    { text: "각 장면에 사물 · 행동 · 맥락을 묻는 질문을 3개씩 작성했다.", options: { breakLine: true } },
    { text: "질문은 3B/4B 캡션과 검색 결과를 보기 전에 작성하고 동결했다.", options: { breakLine: true } },
    { text: "같은 질문을 두 모델에 그대로 넣었고, 자막 검색 채널을 끄고 캡션만으로 검색했다.", options: { breakLine: true } },
    { text: "캡션은 5초 구간의 대표 프레임 1장에서 생성된다 — 모델이 구간 전체를 보지 않는다.", options: {} },
  ], {
    x: 0.85, y: 1.58, w: 7.5, h: 2.2, fontSize: 13, color: INK, valign: "top",
    fontFace: F, lineSpacing: 23, margin: 0,
  });
  /* 숫자 카드는 오른쪽 열 폭(8.72~12.72)에 맞춰 2×2로 둔다.
   * 한 줄 4개는 폭 13.33을 넘어 뒤 2장이 슬라이드 밖으로 나갔다. */
  const nums = [["영상", "1편"], ["후보 구간", "395"], ["장면", "5"], ["질문", "15"]];
  nums.forEach((n, i) => {
    const x = 8.72 + (i % 2) * 2.07;
    const y0 = 1.62 + Math.floor(i / 2) * 1.06;
    card(s, x, y0, 1.9, 1.0, WHITE, LINE);
    s.addText(n[1], {
      x: x, y: y0 + 0.08, w: 1.9, h: 0.55, fontSize: 22, bold: true, color: TEAL,
      align: "center", fontFace: MONO, margin: 0,
    });
    s.addText(n[0], {
      x: x, y: y0 + 0.64, w: 1.9, h: 0.26, fontSize: 10.5, color: MUTED,
      align: "center", fontFace: F, margin: 0,
    });
  });
  card(s, 0.62, 3.88, 12.1, 0.72, TEAL_BG);
  s.addText("두 모델에 같게 준 것 — 프레임 · 프롬프트 · 4bit · 후보 풀 395구간.   다른 것은 캡션 모델 하나뿐이다.", {
    x: 0.9, y: 3.88, w: 11.6, h: 0.72, fontSize: 12.5, color: INK,
    valign: "middle", fontFace: F, margin: 0,
  });

  s.addShape(p.shapes.RECTANGLE, {
    x: 0.62, y: 4.78, w: 12.1, h: 1.62, fill: { color: BAND }, line: { color: BAND },
  });
  s.addText("각 질문에서 보는 것은 네 가지뿐이다", {
    x: 0.9, y: 4.9, w: 11.5, h: 0.3, fontSize: 14, bold: true, color: INK, fontFace: F, margin: 0,
  });
  const four = [
    ["①", "내가 고른 장면이\n1위인가"],
    ["②", "1위가 아니면\n몇 위인가"],
    ["③", "1위가 다른 장면이면\n어떤 장면인가"],
    ["④", "두 캡션이 무엇을\n다르게 썼는가"],
  ];
  four.forEach((f, i) => {
    const fx = 0.85 + i * 3.0;
    card(s, fx, 5.24, 2.85, 1.02, WHITE, LINE);
    s.addText(f[0], {
      x: fx + 0.18, y: 5.32, w: 0.5, h: 0.3, fontSize: 15, bold: true, color: TEAL,
      fontFace: F, margin: 0,
    });
    s.addText(f[1], {
      x: fx + 0.18, y: 5.62, w: 2.5, h: 0.58, fontSize: 11.5, color: INK,
      fontFace: F, lineSpacing: 16, valign: "top", margin: 0,
    });
  });
  s.addText("장면 5개를 모두 같은 형식으로 본다 — 좋은 사례만 고르지 않았다.", {
    x: 0.85, y: 6.5, w: 11.8, h: 0.32, fontSize: 12.5, italic: true, color: MUTED,
    fontFace: F, margin: 0,
  });
}

/* ---------------------------------------------------------------- 4 Scene01
 * A2(2026-08-26): 원래 Scene01은 seg0이었으나 대표 프레임 중앙이 인트로 타이틀
 * 로고로 가려져 재지정했다. 제외 기준 E7(오버레이 가림)·E8(장면 중복)을 추가하고
 * 규칙대로 전진해 seg2가 선정됐다. 질의 3개는 사용자가 프레임만 보고 새로 작성했다.
 * 절차·비용: docs/finalization/CAPTION_RETRIEVAL_CASESTUDY_AMENDMENT_A2_2026-08-26.md
 * 순위 출처: runs/casestudy_caption_retrieval/cs_20260826/step6_retrieval_alpha0.json */
sceneSlide({
  n: "01", seg: 2, time: "0:10~0:15",
  title: "두 모델 모두 수동 기구를 “전자”로 읽고, 질의의 핵심 재료를 쓰지 않았다",
  frame: "seg0002_00010s.jpg",
  desc: "주방 조리대에서 투명한 수동 다지기 안의 새우와 마늘을 손으로 눌러 다진다",
  queries: [
    ["다지기 통 안에 재료가 들어있는 장면", 200, 248],
    ["손으로 음식 다지는 기구를 눌러 재료를 다지는 장면", 59, 156],
    ["주방 조리대에서 투명한 다지기 용기에 새우와 마늘을 넣어 손질하는 장면", 93, 107],
  ],
  miss: {
    arm: "3B", rank: 93,
    bandHead: "④ Q3에서 3B는 내가 고른 장면을 93위로 두고 seg171을 1위로 올렸다 — 같은 다지기 작업의 14분 뒤 시점이다",
    top1Frame: "seg0171_00855s.jpg", top1Label: "1위가 된 장면 — seg171 · 14:15",
    targetCap: "“…손가락으로 전자식 주방기구를 조절하고 있습니다. 주방기구 안에는 다양한 재료들이 들어 있습니다.”",
    /* 카드 3장 배치에서 진단 줄은 한 줄만 들어간다 — 두 줄이면 카드 밖으로 넘친다.
     * "수동 기구를 전자로 읽었다"는 제목과 ⑥이 들고 있고, 두 카드 본문에도 그대로 있다. */
    targetMiss: "새우 · 마늘 · 투명 없음",
    /* 4B가 같은 프레임을 뭐라고 썼는지 나란히 둔다 — "두 모델 모두 전자로 읽었다"는
     * 제목이 3B 카드 하나로는 확인되지 않는다. 원문:
     * runs/casestudy_caption_retrieval/cs_20260825/4b_fresh/…/segments.json seg 2 */
    altLabel: "같은 장면의 4B 캡션 — Q3에서 107위",
    altCap: "“흰색과 녹색의 손잡이가 있는 전자 식품 절편기에서 생선 조각이 잘게 썰리되고 있으며, 사람의 손이 기계를 조작하고 있다.”",
    altMiss: "새우를 “생선”으로 · 마늘 없음",
    /* seg171 프레임에는 편집 자막 "청양고추 + 새우 + 마늘 / Cheongyang chili pepper +
     * shrimp + garlic"이 박혀 있고 캡션의 세 단어가 그것과 일치한다. 인과 단정은 하지
     * 않는다 — 자막을 언급하지도, 따옴표를 쓰지도 않은 형태의 유입이다. */
    top1CardLabel: "1위가 된 장면 — 화면 자막 문구와 일치한다",
    top1Cap: "“…투명한 컵에 청양고추와 새우, 그리고 마늘을 넣습니다.”",
    top1Hit: "질의의 투명 · 새우 · 마늘이 그대로 있다",
  },
  read: "두 모델 모두 수동 다지기를 “전자” 기구로 읽고 새우 · 마늘 · 투명을 쓰지 않아 세 질문에서 59~248위로 밀렸다.\n1위 장면 캡션의 “청양고추 · 새우 · 마늘”은 그 프레임에 덧씌운 편집 자막 문구와 그대로 일치한다.",
});

/* ---------------------------------------------------------------- 5 Scene02 */
sceneSlide({
  n: "02", seg: 79, time: "6:35~6:40",
  title: "같은 화면인데 어느 요소를 적었는지에 따라 1위가 뒤집힌다",
  frame: "seg0079_00395s.jpg",
  desc: "창고형 매장을 위에서 내려다본 화면. 파란 COSTCO 배너, 유리문 냉장 진열장, 적재된 상자",
  queries: [
    ["대형 마트 안에 걸린 파란 광고 배너", 1, 15],
    ["매장 안에서 사람이 지나가는 장면", 46, 2],
    ["냉장 진열장과 쌓인 상자가 있는 창고형 매장 내부", 18, 1],
  ],
  compare: {
    head: "⑤ 같은 프레임 한 장을 두 모델이 이렇게 설명했다 — 배너를 묻는 Q1은 3B가 1위, 진열대를 묻는 Q3은 4B가 1위",
    tag3: "장면 속 실제 배너를 골랐다",
    cap3: "“코스트코의 광고가 보입니다. 파란색 배경에 ‘COSTCO’와 함께 한국어로 된 메시지가 있습니다. 아래에는 ‘Join Now!’, 상단에는 트럭 이미지가 있습니다.”",
    diag3: "Q1 배너 1위  ·  Q3 진열대 18위",
    tag4: "냉장 진열대를 골랐다",
    cap4: "“코스트코 내부의 냉장고 진열대와 주변 상품들이 보이는 장면이다.”",
    diag4: "Q3 진열대 1위  ·  Q1 배너 15위",
  },
  /* 배너는 프레임 실물 확인 결과 냉장창고 벽면에 부착된 비닐 배너다 — in-scene text.
   * 편집으로 덧씌운 자막(Scene 01)과 다른 종류이므로 같은 문제로 묶지 않는다. */
  read: "3B는 장면에 실제로 걸려 있는 배너와 그 문구를, 4B는 냉장 진열대와 상품을 중심으로 설명했다.\n같은 화면에서도 어떤 시각 요소를 캡션에 남겼는지가 순위를 갈랐다. 배너 · 간판처럼 장면 속 실제 텍스트는 제외 대상이 아니다.",
});

/* ---------------------------------------------------------------- 6 Scene03 */
sceneSlide({
  n: "03", seg: 158, time: "13:10~13:15",
  title: "짧게 핵심만 쓰면 맥락을 묻는 질문에 불리할 수 있다",
  frame: "seg0158_00790s.jpg",
  desc: "주방에서 흰 티셔츠를 입은 사람이 나무 도마 위 흰색 재료를 식칼로 썬다",
  queries: [
    ["나무 도마 위에 놓인 흰색 재료와 식칼", 59, 40],
    ["칼로 재료를 썰고 있는 손", 52, 20],
    ["주방 조리대에서 재료를 손질하는 사람", 34, 170],
  ],
  miss: {
    arm: "4B", rank: 170,
    bandHead: "④ Q3에서 4B는 내가 고른 장면을 170위로 두고 seg175를 1위로 올렸다 — ⑤ 같은 장면을 두 모델이 어떻게 썼는지 비교한다",
    top1Frame: "seg0175_00875s.jpg", top1Label: "Q3에서 4B의 1위 — seg175 · 14:35",
    targetCap: "“여성이 흰색 셔츠를 입고 나무 식탁 위에서 큰 칼로 흰색 채소를 슬라이스하고 있다.”",
    targetMiss: "칼·흰색·슬라이스는 있지만 주방 · 조리대 같은 배경어가 없다",
    top1CardLabel: "같은 장면의 3B 캡션 — 같은 질문에서 34위",
    top1Cap: "“…그녀는 흰색 티셔츠를 입고 있으며 … 배경에는 주방 가구와 다양한 도구들이 보인다.”",
    top1Hit: "맥락 질문에서는 배경 표현을 쓴 쪽이 앞섰다",
  },
  read: "두 모델 모두 크게 밀린 장면이다 — 32분 요리 영상에 “칼로 썬다”는 장면이 여럿이라 정답이 그 안에서 밀린다.\n다만 Q3에서는 배경어를 쓴 3B가 34위, 짧게 쓴 4B가 170위로 방향이 반대였다.",
});

/* ---------------------------------------------------------------- 7 Scene04 */
sceneSlide({
  n: "04", seg: 237, time: "19:45~19:50",
  title: "다른 장면 캡션이 질문 표현과 더 직접적으로 겹치면 그 장면이 올라온다",
  frame: "seg0237_01185s.jpg",
  desc: "장갑 낀 손이 노란 무쇠 냄비 뚜껑을 들어 올린다. 안에 소스 끼얹은 고기와 다진 파",
  queries: [
    ["노란색 뚜껑이 있는 무쇠 냄비", 1, 3],
    ["냄비 뚜껑을 손으로 들어 올리는 장면", 3, 10],
    ["완성된 조림 요리를 냄비에서 확인하는 장면", 5, 3],
  ],
  miss: {
    arm: "4B", rank: 10,
    top1Frame: "seg0115_00575s.jpg", top1Label: "Q2에서 4B의 1위 — seg115 · 9:35",
    targetCap: "“노란색 도자기 주전자 위에 손으로 뚫린 채로 뚜껑을 들어 올리는 모습이다. 주전자의 안에는 녹색 야채와…”",
    targetMiss: "“뚜껑을 들어 올리는”은 있지만 냄비를 “주전자”로 오인했다",
    top1Cap: "“손이 흰색 플라스틱 용기의 뚜껑을 들어 올리는 모습이다.”",
    top1Hit: "질의의 동작 표현과 거의 축자적으로 겹친다",
  },
  read: "검색기는 화면을 직접 비교하지 않고 캡션 임베딩을 비교한다 — 다른 장면의 문장이 질문과 더 직접적으로 맞으면 그 장면이 올라올 수 있다. 이 장면은 3B가 더 잘 맞았다(1 · 3 · 5위).",
});

/* ---------------------------------------------------------------- 8 Scene05 */
sceneSlide({
  n: "05", seg: 316, time: "26:20~26:25",
  /* 감사(2026-08-26): 프레임에 밝은 흰 작업대 면과 무늬 천이 실재하므로 근거 없는
   * 생성(환각)이 아니라 실제 시각 요소의 오해석이다 — "화면에 없는 것"은 과했다. */
  title: "화면을 잘못 읽으면 그 오인이 검색까지 그대로 전달된다",
  frame: "seg0316_01580s.jpg",
  desc: "재봉틀이 놓인 작업대 앞에서 손이 남색 물방울 무늬 천을 잡고 있다. 왼쪽에 가위",
  queries: [
    ["물방울 무늬가 있는 남색 천", 181, 22],
    ["재봉틀 앞에서 천을 손으로 잡고 있는 장면", 148, 9],
    ["작업대 위에 재봉틀과 가위가 놓인 작업 공간", 175, 34],
  ],
  miss: {
    arm: "3B", rank: 181,
    bandHead: "④ Q1에서 3B는 내가 고른 장면을 181위로 두고 seg372를 1위로 올렸다 — ⑤ 같은 장면을 두 모델이 어떻게 썼는지 비교한다",
    top1Frame: "seg0372_01860s.jpg", top1Label: "Q1에서 3B의 1위 — seg372 · 31:00",
    targetCap: "“여성의 손이 검은색 패턴이 있는 티셔츠를 들어올리고 있습니다. 배경에는 수영장이 보이며, 테이블 위에는 커터가 놓여 있습니다.”",
    targetMiss: "천을 “티셔츠”로, 작업대를 “수영장”으로 적었다",
    top1CardLabel: "같은 장면의 4B 캡션 — 세 질문에서 22 · 9 · 34위",
    top1Cap: "“손이 다크 브루 이브닝 패턴의 천을 들고 있으며, 배경에는 직조기와 커트 툴이 놓인 작업대가 보입니다.”",
    top1Hit: "천 · 작업대를 쓴 쪽이 세 질문 모두 앞섰다",
  },
  read: "필요한 표현이 빠진 것에 더해 잘못 읽은 내용이 캡션에 들어가면, 그 표현도 임베딩에 함께 들어간다.\n세 질문 모두 148~181위로 밀렸다. 다만 4B의 1위도 모두 같은 작업의 이웃 시점이었다.",
});

/* ---------------------------------------------------------------- 9 전체표 */
{
  const s = slide("숨기지 않는다", "15개 질문 전체 결과");
  const rows = [
    ["01", "다지기 통 안에 재료가 들어있는 장면", 200, 248, ""],
    ["", "손으로 음식 다지는 기구를 눌러 재료를 다지는 장면", 59, 156, ""],
    ["", "주방 조리대에서 투명한 다지기 용기에 새우와 마늘을 넣어 손질하는 장면", 93, 107, ""],
    ["02", "대형 마트 안에 걸린 파란 광고 배너", 1, 15, "3B"],
    ["", "매장 안에서 사람이 지나가는 장면", 46, 2, ""],
    ["", "냉장 진열장과 쌓인 상자가 있는 창고형 매장 내부", 18, 1, "4B"],
    ["03", "나무 도마 위에 놓인 흰색 재료와 식칼", 59, 40, ""],
    ["", "칼로 재료를 썰고 있는 손", 52, 20, ""],
    ["", "주방 조리대에서 재료를 손질하는 사람", 34, 170, ""],
    ["04", "노란색 뚜껑이 있는 무쇠 냄비", 1, 3, "3B"],
    ["", "냄비 뚜껑을 손으로 들어 올리는 장면", 3, 10, ""],
    ["", "완성된 조림 요리를 냄비에서 확인하는 장면", 5, 3, ""],
    ["05", "물방울 무늬가 있는 남색 천", 181, 22, ""],
    ["", "재봉틀 앞에서 천을 손으로 잡고 있는 장면", 148, 9, ""],
    ["", "작업대 위에 재봉틀과 가위가 놓인 작업 공간", 175, 34, ""],
  ];
  const head = [["장면", 0.75, 0.75, "left"], ["질문", 1.6, 6.05, "left"],
                ["3B 순위", 7.75, 1.25, "center"], ["4B 순위", 9.05, 1.25, "center"],
                ["더 높은 쪽", 10.35, 1.25, "center"], ["1위 적중", 11.6, 1.15, "center"]];
  head.forEach((h) => {
    s.addText(h[0], {
      x: h[1], y: 1.52, w: h[2], h: 0.26, fontSize: 10, bold: true, color: MUTED,
      align: h[3], fontFace: F, margin: 0,
    });
  });
  let y = 1.84, band = false;
  rows.forEach((r) => {
    if (r[0]) band = !band;
    if (band) {
      s.addShape(p.shapes.RECTANGLE, {
        x: 0.62, y: y, w: 12.1, h: 0.31, fill: { color: BAND }, line: { color: BAND },
      });
    }
    if (r[0]) {
      s.addText(r[0], {
        x: 0.75, y: y, w: 0.75, h: 0.31, fontSize: 11, bold: true, color: TEAL,
        valign: "middle", fontFace: MONO, margin: 0,
      });
    }
    s.addText(r[1], {
      x: 1.6, y: y, w: 6.05, h: 0.31, fontSize: 10.5, color: INK,
      valign: "middle", fontFace: F, margin: 0,
    });
    const better = r[2] < r[3] ? "3B" : (r[3] < r[2] ? "4B" : "");
    [[r[2], TEAL, "3B"], [r[3], AMBER, "4B"]].forEach((c, k) => {
      const win = better === c[2];
      s.addText(String(c[0]), {
        x: 7.75 + k * 1.3, y: y, w: 1.25, h: 0.31, fontSize: win ? 12 : 10.5,
        bold: win, color: win ? c[1] : MUTED, align: "center", valign: "middle",
        fontFace: MONO, margin: 0,
      });
    });
    s.addText(better, {
      x: 10.35, y: y, w: 1.25, h: 0.31, fontSize: 10.5, bold: true,
      color: better === "3B" ? TEAL : AMBER, align: "center", valign: "middle",
      fontFace: F, margin: 0,
    });
    if (r[4]) {
      card(s, 11.87, y + 0.04, 0.6, 0.23, r[4] === "3B" ? TEAL : AMBER);
      s.addText(r[4], {
        x: 11.87, y: y + 0.04, w: 0.6, h: 0.23, fontSize: 9, bold: true, color: WHITE,
        align: "center", valign: "middle", fontFace: F, margin: 0,
      });
    } else {
      s.addText("—", {
        x: 11.6, y: y, w: 1.15, h: 0.31, fontSize: 10.5, color: "C3C3BD",
        align: "center", valign: "middle", fontFace: F, margin: 0,
      });
    }
    y += 0.31;
  });
  card(s, 0.62, 6.58, 12.1, 0.4, TEAL_BG);
  s.addText("내가 고른 장면이 1위였던 질문 — 3B 2건 · 4B 1건 (15개 중). 좋은 사례만 고르지 않았다.", {
    x: 0.9, y: 6.58, w: 11.6, h: 0.4, fontSize: 12, bold: true, color: INK,
    valign: "middle", fontFace: F, margin: 0,
  });
}

/* ---------------------------------------------------------------- 10 숫자 */
{
  const s = slide("숫자", "누가 더 잘 찾았나");
  card(s, 0.62, 1.5, 12.1, 1.5, WHITE, LINE);
  s.addText("① 내가 고른 장면이 1위였던 질문", {
    x: 0.9, y: 1.66, w: 5.6, h: 0.3, fontSize: 14, bold: true, color: INK, fontFace: F, margin: 0,
  });
  s.addText("Top-1 적중이 두 모델 모두 매우 낮다", {
    x: 0.9, y: 2.02, w: 5.6, h: 0.6, fontSize: 13, color: MUTED, fontFace: F, margin: 0,
  });
  [[TEAL, "3B", 6.6, "2"], [AMBER, "4B", 9.6, "1"]].forEach((a) => {
    s.addText([{ text: a[3], options: { fontSize: 38, bold: true, color: a[0] } },
               { text: " / 15", options: { fontSize: 16, color: MUTED } }],
      { x: a[2], y: 1.66, w: 2.6, h: 0.92, align: "center", valign: "middle",
        fontFace: MONO, margin: 0 });
    s.addText(a[1], { x: a[2], y: 2.52, w: 2.6, h: 0.26, fontSize: 11, bold: true,
                      color: a[0], align: "center", fontFace: F, margin: 0 });
  });
  const rows = [
    ["② 내가 고른 장면의 순위가 더 높았던 질문", "7 / 15", "8 / 15"],
    ["③ 내가 고른 장면의 순위 중앙값", "52위", "20위"],
    /* 감사(2026-08-26): 3B 미종결 57건은 공유 토큰 상한(128) 도달분이다.
     * "4B가 원래 짧다"로 읽히지 않게 항목명에 병기한다. */
    ["④ 평균 캡션 길이 (3B는 토큰 상한 절단 포함)", "128.5자", "76.4자"],
  ];
  let y = 3.25;
  rows.forEach((r) => {
    s.addShape(p.shapes.RECTANGLE, {
      x: 0.62, y: y, w: 12.1, h: 0.72, fill: { color: BAND }, line: { color: BAND },
    });
    s.addText(r[0], { x: 0.9, y: y, w: 5.6, h: 0.72, fontSize: 13, color: INK,
                      valign: "middle", fontFace: F, margin: 0 });
    s.addText(r[1], { x: 6.6, y: y, w: 2.6, h: 0.72, fontSize: 16, bold: true, color: TEAL,
                      align: "center", valign: "middle", fontFace: MONO, margin: 0 });
    s.addText(r[2], { x: 9.6, y: y, w: 2.6, h: 0.72, fontSize: 16, bold: true, color: AMBER,
                      align: "center", valign: "middle", fontFace: MONO, margin: 0 });
    y += 0.82;
  });
  card(s, 0.62, 5.8, 12.1, 1.05, TEAL_BG);
  s.addText("Top-1 적중은 두 모델 모두 15개 중 1~2건이다. 이 사례만으로 모델 우열을 말할 수 없다.\n순위가 더 높았던 질문도 8 대 7로 갈렸다 — 한 영상 15개 질문의 사례 분석이고 일반 성능 추정치가 아니다.", {
    x: 0.9, y: 5.92, w: 11.6, h: 0.82, fontSize: 12.5, bold: true, color: INK,
    fontFace: F, lineSpacing: 20, valign: "top", margin: 0,
  });
}

/* ---------------------------------------------------------------- 11 경로 */
{
  const s = slide("정리", "검색 순위 차이가 생기는 경로");
  const items = [
    /* Scene01 재지정(seg2) 후에는 두 모델이 **같은 재료를 같이** 빠뜨렸다 —
     * 모델 차이가 아니라 캡션에 안 쓰면 못 찾는다는 경로다. 순위는 r2 step6 그대로. */
    ["①", "핵심 사물·행동 생략", "두 모델이 같이 빠뜨리면 순위가 같이 밀린다 (59~248위)", "Scene 01"],
    ["②", "같은 장면에서 다른 요소 선택", "3B는 배너, 4B는 진열대 — 질문에 따라 1위가 뒤집힌다", "Scene 02"],
    ["③", "배경·맥락 정보 부족", "짧은 캡션이 사물은 맞혀도 장소·배경 질문에서 밀린다", "Scene 03"],
    ["④", "다른 장면의 더 직접적인 표현", "정답보다 다른 장면 캡션이 질문과 축자로 겹친다", "Scene 01 · 04"],
    /* 4B도 같은 프레임을 잘못 읽었다(새우→"생선") — 4슬라이드 카드와 같은 근거다. */
    ["⑤", "잘못 본 내용이 캡션에 들어감", "기구를 “전자”로 · 새우를 “생선”으로 · 천을 “티셔츠”로", "Scene 01 · 05"],
    /* 프레임 실물에서 overlay subtitle임을 확인한 뒤 추가한 경로다. */
    ["⑥", "편집 자막이 캡션에 들어옴", "영상 위에 덧씌운 자막 문구가 검색어와 직접 겹친다", "Scene 01"],
  ];
  let y = 1.46;
  items.forEach((it) => {
    card(s, 0.62, y, 12.1, 0.72, WHITE, LINE);
    s.addText(it[0], {
      x: 0.9, y: y, w: 0.55, h: 0.72, fontSize: 17, bold: true, color: TEAL,
      valign: "middle", fontFace: F, margin: 0,
    });
    s.addText(it[1], {
      x: 1.55, y: y, w: 4.15, h: 0.72, fontSize: 12.5, bold: true, color: INK,
      valign: "middle", fontFace: F, margin: 0,
    });
    s.addText(it[2], {
      x: 5.85, y: y, w: 5.35, h: 0.72, fontSize: 11.5, color: MUTED,
      valign: "middle", fontFace: F, margin: 0,
    });
    s.addText(it[3], {
      x: 11.3, y: y, w: 1.25, h: 0.72, fontSize: 10.5, bold: true, color: TEAL,
      align: "right", valign: "middle", fontFace: F, margin: 0,
    });
    y += 0.78;
  });
  card(s, 0.62, 6.3, 12.1, 0.62, TEAL_BG);
  s.addText("장면마다 다른 실패 경로가 나왔다. 검색 성능은 “화면을 봤는가”뿐 아니라 “화면에서 무엇을 문장으로 남겼는가”의 영향을 받는다.\n간판 · 배너처럼 장면 속 실제 텍스트는 시각 근거로 보고, 영상 위에 덧씌운 편집 자막과 구분한다.", {
    x: 0.9, y: 6.34, w: 11.6, h: 0.56, fontSize: 11.5, bold: true, color: INK,
    fontFace: F, lineSpacing: 16, valign: "top", margin: 0,
  });
}

/* ---------------------------------------------------------------- 12 Q&A */
{
  const s = slide("답", "튜터 질문에 대한 답");
  const qa = [
    ["같은 질문지를 넣었을 때 내가 고른 장면이 나왔나?",
     "일부는 1위로 나왔지만, 15개 중 Top-1 적중은 3B 2건 · 4B 1건이었다."],
    ["모델별 차이가 있었나?",
     "내가 고른 장면의 순위가 더 높았던 질문은 4B 8개 · 3B 7개로 갈렸다. 이 작은 사례만으로 일반적인 우열을 말할 수는 없다."],
    ["다른 장면이 1위가 됐을 때 그 장면은 왜 올라왔나?",
     "정답 캡션에서 필요한 정보가 빠지거나, 다른 장면 캡션이 질문과 더 직접적인 표현을 가진 경우가 있었다. Scene 01에서는 영상 위에 덧씌운 편집 자막 문구가 그 표현으로 들어왔다."],
    ["그래서 무엇을 확인했나?",
     "캡션 모델이 화면에서 어떤 정보를 골라 문장으로 남기는지가 실제 검색 순위까지 전달된다."],
  ];
  let y = 1.52;
  qa.forEach((r, i) => {
    const last = i === qa.length - 1;
    card(s, 0.62, y, 12.1, 1.24, last ? TEAL_BG : WHITE, last ? TEAL_BG : LINE);
    s.addText("Q", {
      x: 0.9, y: y + 0.13, w: 0.4, h: 0.3, fontSize: 13, bold: true, color: TEAL,
      fontFace: MONO, margin: 0,
    });
    s.addText(r[0], {
      x: 1.35, y: y + 0.11, w: 11.1, h: 0.34, fontSize: 14, bold: true, color: INK,
      fontFace: F, margin: 0,
    });
    s.addText("A", {
      x: 0.9, y: y + 0.57, w: 0.4, h: 0.3, fontSize: 13, bold: true, color: MUTED,
      fontFace: MONO, margin: 0,
    });
    s.addText(r[1], {
      x: 1.35, y: y + 0.53, w: 11.1, h: 0.6, fontSize: 12.5,
      color: INK, bold: last,
      fontFace: F, lineSpacing: 18, valign: "top", margin: 0,
    });
    y += 1.34;
  });
}

/* --------------------------------------------- 13 다른 영상 3편 · 캡션 비교
 * 여기까지는 영상 1편이었다. 이 장에서 처음 다른 영상으로 넘어간다.
 * 쌍 선택은 결정적 규칙이다 — 같은 프레임에서 내용어 겹침이 가장 낮은 쌍을 영상별로
 * 하나씩 뽑고, 두 캡션이 모두 한국어이며 둘 다 40자 이상인 것만 남겼다(언어 이탈·
 * 생성 실패 사례는 15장에서 따로 다루므로 여기서 겹치지 않게 한다).
 * AI Hub 프레임은 반출 권한 문제가 있어 덱에 싣지 않고 자체 취득 영상만 쓴다.
 * 근거: docs/재분석_캡션서술방식_2026-08-27.md */
scope = SCOPE_OTHER;
{
  const s = slide("다른 영상", "같은 프레임을 두 모델은 이렇게 다르게 적었다");
  s.addText("영상 3편 · 각 영상에서 두 캡션의 어휘 겹침이 가장 낮은 구간 하나 (겹침 0.00) · 긴 원문은 가운데를 … 로 줄였다", {
    x: 0.62, y: 1.46, w: 12.1, h: 0.26, fontSize: 11.5, color: MUTED, fontFace: F, margin: 0,
  });

  const EX = [
    {
      label: "곽튜브 · 소비에트 아파트 · seg19",
      img: ROOT + "/work/gwaktube_soviet_apartment/frames/seg_0019.jpg",
      a: "“화면에는 한 남성이 문을 열고 들어와 있는 모습이 보입니다. … 그의 몸짓과 행동에서 긴장감이 느껴집니다. … 화면 하단에는 한국어 자막이 나타나 있습니다.”",
      aDiag: "화면 아래 편집 자막까지 캡션에 들어왔다",
      b: "“문이 열린 상태로, 그 안에서 녹색 상의를 입은 사람이 손으로 문손잡이를 잡고 서 있다.”",
      bDiag: "녹색 상의 · 문손잡이 — 3B가 적지 않은 것",
    },
    {
      label: "헤리티지채널 · 묘 발굴 · seg29",
      img: ROOT + "/work/kheritage_grave_excavation/frames/seg_0029.jpg",
      a: "“검은색 바탕에 흰색 글씨로 ‘Hch’와 ‘문화재청’이라는 텍스트가 있습니다. 화면의 하단에는 ‘문화재청’이라는 텍스트가 있습니다. …”",
      aDiag: "좌상단 로고만 읽고 같은 말을 여섯 번",
      b: "“어두운 톤의 숲길에서 누군가의 다리와 발이 나무 잎과 건조한 풀 사이를 걷고 있는 모습이다.”",
      bDiag: "장면 자체를 잡았다 — 숲길 · 걷는 발",
    },
    {
      label: "플랜디 · 코스트코 호스팅 · seg311",
      img: ROOT + "/work/pland_costco_hosting/frames/seg_0311.jpg",
      a: "“여성은 흑색 패턴이 있는 직물 위에 손을 얹고 있습니다. … 여성의 손에는 반지가 달린 손가락이 보입니다. 배경에는 흰색 테이블 위에 여러 물건들이 놓여 있습니다.”",
      aDiag: "사람 · 반지 · 배경까지 · 기구는 안 적었다",
      b: "“검은색 무늬가 있는 천 위에서 작업하는 손이 삼각형 형태의 자동 가위를 조정하고 있다.”",
      bDiag: "기구를 지목했지만 재봉틀을 “가위”로 오인",
    },
  ];

  let y = 1.78;
  EX.forEach((e) => {
    s.addText(e.label, {
      x: 0.62, y: y, w: 2.6, h: 0.22, fontSize: 9, bold: true, color: TEAL,
      fontFace: F, margin: 0,
    });
    s.addImage({ path: e.img, x: 0.62, y: y + 0.24, w: 2.42, h: 1.36 });
    capCard(s, 3.2, y, 4.68, 1.6, "Qwen2.5-VL-3B", TEAL, e.a, e.aDiag, MUTED, 9);
    capCard(s, 8.04, y, 4.68, 1.6, "Qwen3-VL-4B", "8A5A2B", e.b, e.bDiag, MUTED, 9);
    y += 1.72;
  });
  /* 주석은 상단 부제로 합쳤다 — 셋째 행 이미지 아래에는 푸터까지 여유가 없다 */
}

/* ------------------------------------------- 14 왜 편집 자막이 캡션에 들어오나
 * 13장 사례 둘(gwaktube 자막 · kheritage 로고)이 바로 이 현상이라 이어서 둔다.
 * **실측과 해석을 갈라 적는다** — 유출률·프롬프트 원문·프레임 유형은 측정값이지만,
 * "OCR 신호가 강하다"는 모델 학습에 관한 외부 주장이고 이 프로젝트가 측정한 것이 아니다.
 * 근거: docs/finalization/CAPTION_TEXT_HANDLING_AUDIT_2026-08-26.md (판정 B) */
scope = SCOPE_CAUSE;
{
  const s = slide("원인", "프롬프트는 금지하고 있다 — 그런데도 들어온다");

  /* 프롬프트 원문을 그대로 보여준다. "지시가 없어서"라는 오해를 먼저 닫는다. */
  card(s, 0.62, 1.5, 12.1, 0.92, "F3EFE7", "E0D6C2");
  s.addText("P0 프롬프트 (현행 · 변경 없음)", {
    x: 0.95, y: 1.58, w: 6, h: 0.24, fontSize: 9.5, bold: true, color: "8A5A2B",
    fontFace: F, margin: 0,
  });
  s.addText("“화면에 자막이나 글자가 보이더라도 그 글자를 그대로 옮겨 적지 말고, 인물의 행동과 배경 등 시각적 내용만 묘사하라.”", {
    x: 0.95, y: 1.84, w: 11.5, h: 0.42, fontSize: 12, color: INK,
    fontFace: F, valign: "top", margin: 0,
  });

  s.addText("실측", {
    x: 0.62, y: 2.56, w: 3, h: 0.24, fontSize: 10, bold: true, color: TEAL,
    fontFace: F, charSpacing: 1, margin: 0,
  });
  const meas = [
    ["처리 방식", "프롬프트 지시뿐", "프레임은 원본 그대로 · 픽셀 mask · crop 없음"],
    ["편집 자막 전사", "3B 21건 / 4B 0건", "같은 프레임 395구간 · 사람이 확인한 수"],
    ["화면 글자 언급", "3B 11.1% / 4B 0.3%", "AI Hub 2,328구간 · 자동 후보(overlay 확정 아님)"],
  ];
  let my = 2.84;
  meas.forEach((r) => {
    card(s, 0.62, my, 12.1, 0.56, WHITE, LINE);
    s.addText(r[0], { x: 0.85, y: my + 0.14, w: 2.3, h: 0.28, fontSize: 11.5, bold: true,
                      color: INK, fontFace: F, margin: 0 });
    s.addText(r[1], { x: 3.2, y: my + 0.14, w: 2.9, h: 0.28, fontSize: 12,
                      color: INK, fontFace: MONO, margin: 0 });
    s.addText(r[2], { x: 6.2, y: my + 0.14, w: 6.3, h: 0.28, fontSize: 11,
                      color: MUTED, fontFace: F, margin: 0 });
    my += 0.64;
  });

  s.addText("해석 — 측정한 것이 아니라 위 실측을 설명하는 가설이다", {
    x: 0.62, y: 4.82, w: 8, h: 0.24, fontSize: 10, bold: true, color: "8A5A2B",
    fontFace: F, charSpacing: 1, margin: 0,
  });
  const why = [
    ["글자는 지우기 어려운 신호", "말로 금지해도 픽셀은 그대로 들어간다.\n지시는 출력 단계에서 누르는 시도일 뿐이다"],
    ["글자밖에 없는 구간", "검은 화면에 “DAY 59” · 인트로 로고.\n“묘사하라”와 “적지 마라”가 서로 충돌한다"],
    ["편집 자막과 간판을 못 가른다", "모델에게는 둘 다 픽셀 위의 글자다.\n그래서 지시가 부분적으로만 듣는다"],
  ];
  let wx = 0.62;
  why.forEach((w) => {
    card(s, wx, 5.1, 3.9, 1.36, WHITE, LINE);
    s.addText(w[0], { x: wx + 0.2, y: 5.22, w: 3.5, h: 0.28, fontSize: 11.5, bold: true,
                      color: TEAL, fontFace: F, margin: 0 });
    s.addText(w[1], { x: wx + 0.2, y: 5.54, w: 3.5, h: 0.8, fontSize: 10.5, color: INK,
                      fontFace: F, lineSpacing: 15, valign: "top", margin: 0 });
    wx += 4.1;
  });

  s.addText("더 세게 금지하는 것이 답은 아니다 — 자막형 질의에서는 화면 글자가 도움이 되는 정보다. 억제와 활용이 긴장 관계라 현행 유지 + 한계 명시로 뒀다.", {
    x: 0.62, y: 6.58, w: 12.1, h: 0.3, fontSize: 11, italic: true, color: MUTED,
    fontFace: F, margin: 0,
  });
}

/* ---------------------------------------------------------------- 15 경계 */
scope = SCOPE_CASE;
{
  const s = slide("경계", "말할 수 있는 것 / 말할 수 없는 것");
  card(s, 0.62, 1.52, 5.95, 3.35, TEAL_BG);
  s.addText("말할 수 있다", {
    x: 0.95, y: 1.74, w: 5.3, h: 0.36, fontSize: 15, bold: true, color: TEAL, fontFace: F, margin: 0,
  });
  s.addText([
    { text: "캡션의 정보 선택이 검색 순위에 전달된다", options: { bullet: true, breakLine: true } },
    { text: "정답을 못 찾았을 때 원인을 캡션 수준까지 추적할 수 있다", options: { bullet: true, breakLine: true } },
    { text: "한 모델이 모든 질문에서 항상 유리한 것은 아니다", options: { bullet: true, breakLine: true } },
    { text: "실패 경로가 장면마다 달랐다", options: { bullet: true, breakLine: true } },
    { text: "1위가 된 장면은 모두 같은 사건 · 같은 동작 · 의미가 가까운 장면이었다 — 무관한 장면은 없었다", options: { bullet: true } },
  ], {
    x: 0.95, y: 2.22, w: 5.3, h: 2.5, fontSize: 13, color: INK, valign: "top",
    fontFace: F, lineSpacing: 21, paraSpaceAfter: 9, margin: 0,
  });
  card(s, 6.77, 1.52, 5.95, 3.35, "EDEAE6");
  s.addText("말할 수 없다", {
    x: 7.1, y: 1.74, w: 5.3, h: 0.36, fontSize: 15, bold: true, color: "8A5A2B", fontFace: F, margin: 0,
  });
  s.addText([
    { text: "4B가 일반적으로 더 좋다", options: { bullet: true, breakLine: true } },
    { text: "3B가 일반적으로 더 좋다", options: { bullet: true, breakLine: true } },
    { text: "15개 질의로 성능을 추정할 수 있다", options: { bullet: true, breakLine: true } },
    { text: "이 결과만으로 모델을 교체해야 한다", options: { bullet: true } },
  ], {
    x: 7.1, y: 2.22, w: 5.3, h: 2.5, fontSize: 13, color: INK, valign: "top",
    fontFace: F, lineSpacing: 21, paraSpaceAfter: 9, margin: 0,
  });
  s.addText("영상 1편 · 장면 5개 · 질의 15개의 정성 사례 연구다.", {
    x: 7.1, y: 4.4, w: 5.3, h: 0.3, fontSize: 11.5, italic: true, color: MUTED,
    fontFace: F, margin: 0,
  });
  s.addText("한계 하나 더 — 두 모델을 같은 조건에서 새로 생성해 맞췄지만, 두 실행의 저장소 상태가 완전히 같았다는 것까지는\n입증하지 못했다(생성 코드·설정 경로에는 차이가 없음을 확인했다).", {
    x: 0.62, y: 5.05, w: 12.1, h: 0.7, fontSize: 12, color: MUTED,
    fontFace: F, lineSpacing: 19, valign: "top", margin: 0,
  });
  /* 2026-08-26 텍스트 처리 감사에서 정량화된 채널 비대칭 — 동결 캡션 원문 집계다. */
  card(s, 0.62, 5.85, 12.1, 1.02, "EDEAE6");
  s.addText("한계 둘 — 395구간에서 3B 캡션은 화면에 덧씌운 편집 자막을 21건 옮겨 적었고 4B는 0건이다.\n캡션만으로 검색할 때 이것은 시각 묘사 품질이 아니라 캡션에 들어온 정보 종류의 차이다. 간판 · 배너는 여기 해당하지 않는다.", {
    x: 0.95, y: 5.97, w: 11.5, h: 0.8, fontSize: 12, color: INK,
    fontFace: F, lineSpacing: 19, valign: "top", margin: 0,
  });
}

/* --------------------------------------- 14 서술 방식 — 194편 쌍대 기술 분석
 * 이 슬라이드까지는 영상 1편 사례다. 여기서 처음으로 표본이 194편으로 늘어난다.
 * 성능 비교가 아니라 **캡션에 무엇을 남겼는가**의 기술이므로 문구를 그렇게 고정한다.
 * 근거: docs/재분석_캡션서술방식_2026-08-27.md (AI Hub 2,328쌍) */
scope = SCOPE_PAIRED;
{
  const s = slide("서술 방식", "같은 프레임, 다른 선택 — 194편 2,328구간에서 다시 보면");
  s.addText("저장해 둔 두 모델의 캡션을 같은 프레임끼리 짝지어 비교했다. 새로 생성하지 않았고 검색도 돌리지 않았다.", {
    x: 0.62, y: 1.55, w: 12.1, h: 0.3, fontSize: 12.5, color: MUTED, fontFace: F, margin: 0,
  });

  /* 3열 수치 카드 — 길이 · 겹침 · 화면 글자 */
  const stat = [
    ["캡션 길이 중앙값", "133자  vs  73자", "P0에서 3B가 60자 길다"],
    ["내용어 겹침", "0.13", "같은 화면인데 쓰는 단어가 거의 다르다"],
    ["화면 글자를 언급", "11.1%  vs  0.3%", "네 표본 모두 3B가 높았다"],
  ];
  let sx = 0.62;
  stat.forEach((t) => {
    card(s, sx, 2.0, 3.9, 1.5, WHITE, LINE);
    s.addText(t[0], { x: sx + 0.22, y: 2.14, w: 3.5, h: 0.28, fontSize: 10.5, bold: true,
                      color: TEAL, fontFace: F, margin: 0 });
    s.addText(t[1], { x: sx + 0.22, y: 2.46, w: 3.5, h: 0.42, fontSize: 19, bold: true,
                      color: INK, fontFace: F, margin: 0 });
    s.addText(t[2], { x: sx + 0.22, y: 2.94, w: 3.5, h: 0.46, fontSize: 10.5,
                      color: MUTED, fontFace: F, lineSpacing: 14, valign: "top", margin: 0 });
    sx += 4.09;
  });

  /* 뒤집히는 지점을 같은 슬라이드에 둔다 — 여기가 이 분석의 핵심 절제다 */
  card(s, 0.62, 3.72, 12.1, 1.16, "F3EFE7", "E0D6C2");
  s.addText("다만 길이 우열은 프롬프트에서 뒤집힌다", {
    x: 0.95, y: 3.84, w: 6, h: 0.3, fontSize: 12.5, bold: true, color: INK, fontFace: F, margin: 0,
  });
  s.addText("P0에서는 3B 133자 · 4B 73자였지만, P1에서는 3B 82자 · 4B 97자로 4B가 더 길다.\n따라서 “3B가 더 자세한 모델”이라고 말할 수 없다 — 길이는 모델과 프롬프트가 함께 만든다.", {
    x: 0.95, y: 4.16, w: 11.5, h: 0.66, fontSize: 12, color: INK,
    fontFace: F, lineSpacing: 19, valign: "top", margin: 0,
  });

  /* 실제 쌍 하나 — 숫자보다 이 한 쌍이 설명을 대신한다 */
  s.addText("같은 프레임 (AI Hub)", {
    x: 0.62, y: 5.02, w: 6, h: 0.28, fontSize: 10.5, bold: true, color: TEAL,
    fontFace: F, charSpacing: 1, margin: 0,
  });
  capCard(s, 0.62, 5.34, 6.0, 1.5, "Qwen2.5-VL-3B", TEAL,
          "“여성은 나무로 만든 정원 카페에서 책을 읽고 있습니다. 검은색 상의와 스트라이프 바지를 입고 있으며, 그녀 앞 테이블에는 컵과 종이가 놓여 있습니다.”",
          "옷 · 소품 · 배경까지 적는다", MUTED, 10.5);
  capCard(s, 6.72, 5.34, 6.0, 1.5, "Qwen3-VL-4B", "8A5A2B",
          "“숲 속 목조 휴식처에 앉아 책을 읽는 사람.”",
          "핵심 행위 하나로 압축한다", MUTED, 10.5);
}

/* ------------------------------------------- 15 부작용은 양쪽 다 있고 종류가 다르다
 * "4B는 간결하고 깨끗하다"는 그림을 여기서 깬다. 발표에서 가장 반박당하기 쉬운 지점이라
 * 먼저 인정하고 들어간다. */
{
  const s = slide("부작용", "한쪽이 깨끗한 것이 아니라, 고장 나는 방식이 서로 다르다");
  const rows = [
    ["한자 혼입", "4.1%", "10.3%", "4B가 2배 이상 — P1에서는 2.6% vs 14.7%"],
    ["가나 혼입", "1.9%", "0.04%", "반대로 3B가 높다"],
    ["문장 미완결", "6.6%", "4.5%", "공유 상한 128토큰이 3B를 더 자주 자른다"],
  ];
  s.addText("AI Hub 2,328구간 · P0", {
    x: 0.62, y: 1.55, w: 6, h: 0.28, fontSize: 11, color: MUTED, fontFace: F, margin: 0,
  });
  const head = ["", "Qwen2.5-3B", "Qwen3-4B", ""];
  const cx = [0.62, 3.5, 5.3, 7.1];
  head.forEach((h, i) => {
    if (!h) return;
    s.addText(h, { x: cx[i], y: 1.95, w: 1.7, h: 0.28, fontSize: 10.5, bold: true,
                   color: TEAL, fontFace: F, margin: 0 });
  });
  let ry = 2.32;
  rows.forEach((r) => {
    card(s, 0.62, ry, 12.1, 0.62, WHITE, LINE);
    s.addText(r[0], { x: 0.85, y: ry + 0.16, w: 2.6, h: 0.3, fontSize: 12.5, bold: true,
                      color: INK, fontFace: F, margin: 0 });
    s.addText(r[1], { x: 3.5, y: ry + 0.16, w: 1.7, h: 0.3, fontSize: 13,
                      color: INK, fontFace: MONO, margin: 0 });
    s.addText(r[2], { x: 5.3, y: ry + 0.16, w: 1.7, h: 0.3, fontSize: 13,
                      color: INK, fontFace: MONO, margin: 0 });
    s.addText(r[3], { x: 7.1, y: ry + 0.16, w: 5.4, h: 0.3, fontSize: 11.5,
                      color: MUTED, fontFace: F, margin: 0 });
    ry += 0.74;
  });

  s.addText("실제로 관찰된 실패 사례", {
    x: 0.62, y: 4.66, w: 6, h: 0.28, fontSize: 10.5, bold: true, color: TEAL,
    fontFace: F, charSpacing: 1, margin: 0,
  });
  capCard(s, 0.62, 4.98, 6.0, 1.14, "Qwen2.5-VL-3B", TEAL,
          "캡션 전체를 중국어로 생성 · 같은 표현을 세 번 되풀이한 구간",
          "", MUTED, 11);
  capCard(s, 6.72, 4.98, 6.0, 1.14, "Qwen3-VL-4B", "8A5A2B",
          "영어 명사구를 그대로 남김 — “wooden gazebo 아래에서 책을 읽고 있는 사람”",
          "", MUTED, 11);
  s.addText("사후 기술 분석이다. 재사용 표본이며 모델 채택 근거가 아니다 — 채택 판정은 사전등록된 2×2가 한다.", {
    x: 0.62, y: 6.28, w: 12.1, h: 0.3, fontSize: 11, italic: true, color: MUTED,
    fontFace: F, margin: 0,
  });
}

/* ---------------------------------------------------------------- 16 결론 */
scope = SCOPE_CASE;
{
  const s = darkSlide();
  s.addText("결론", {
    x: 0.9, y: 1.5, w: 11, h: 0.3, fontSize: 12, bold: true,
    color: "8FA9AE", charSpacing: 2, fontFace: F, margin: 0,
  });
  s.addText("캡션 모델의 차이는 문장 표현에서 끝나지 않고\n실제 검색 순위까지 전달된다.", {
    x: 0.88, y: 1.95, w: 11.4, h: 1.3, fontSize: 26, bold: true,
    color: WHITE, fontFace: F, lineSpacing: 38, margin: 0,
  });
  const box = [["배포", "Qwen2.5-VL-3B 유지"], ["Qwen3-VL-4B", "후보이며 채택 아님"],
               ["과학적 우열", "미해결"]];
  let x = 0.9;
  box.forEach((b) => {
    s.addShape(p.shapes.ROUNDED_RECTANGLE, {
      x: x, y: 3.6, w: 3.83, h: 1.2, fill: { color: "1B4650" }, rectRadius: 0.06,
      line: { color: "2C6E75" },
    });
    s.addText(b[0], { x: x + 0.3, y: 3.78, w: 3.3, h: 0.3, fontSize: 11, bold: true,
                      color: "8FA9AE", fontFace: F, margin: 0 });
    s.addText(b[1], { x: x + 0.3, y: 4.1, w: 3.3, h: 0.5, fontSize: 15, bold: true,
                      color: WHITE, fontFace: F, margin: 0 });
    x += 4.02;
  });
  s.addShape(p.shapes.LINE, {
    x: 0.92, y: 5.2, w: 3.2, h: 0, line: { color: "3E5F68", width: 2 },
  });
  s.addText("이번 분석의 가장 중요한 결과는 “어느 모델이 이겼는가”보다,\n왜 검색 결과가 달라지는지를 장면 · 캡션 · 1위가 된 다른 장면까지 추적해 설명할 수 있게 된 것이다.", {
    x: 0.9, y: 5.45, w: 11.4, h: 0.9, fontSize: 14, color: "C9D8DA",
    fontFace: F, lineSpacing: 24, valign: "top", margin: 0,
  });
  s.addText("상세  docs/finalization/CAPTION_RETRIEVAL_CASESTUDY_RESULTS_2026-08-25.md", {
    x: 0.9, y: 6.5, w: 11, h: 0.3, fontSize: 10.5, color: "6E8B92", fontFace: MONO, margin: 0,
  });
}

fs.mkdirSync(OUTDIR, { recursive: true });
p.writeFile({ fileName: OUT }).then(() => console.log("wrote " + OUT + "  (" + page + "장)"));
