/* 최종발표 초안 v4 — 평가표(문제정의·데이터·기술구현·프로젝트관리·군활용성) 정렬,
 * 슬라이드 3 분리(구조/화면모델근거/임베딩모델근거), 데이터·군활용성 슬라이드 신설,
 * 한계 슬라이드 삭제, test 39건 관련 수치는 여전히 사용하지 않는다.
 * 수치 출처: results/alpha_search_dev.json, archive/ablation/results_bge/alpha_search_dev.json,
 *            archive/ablation/results_seg3·seg5ref·seg10/alpha_search_dev.json,
 *            docs/DESIGN_SPEC.md(raw_sub_max/raw_cap_max 예시, α 탐색 tie-break),
 *            data/queries/queries.jsonl, config.yaml,
 *            docs/presentation/중간성과발표_2026-08-21.pptx(화면설명 3B/4B 실제 캡션·프레임, 군 활용성 문구 재인용),
 *            runs/wvr_video_overview_preview_v1/video_overview_v1_record.json */
const path = require("path");
const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.layout = "LAYOUT_WIDE";
p.title = "말이 없는 장면도 찾아내는 한국어 영상 모먼트 검색 (최종발표 초안)";

const W = 13.33, H = 7.5;
const NAVY = "0F2A43", TEAL = "18B7A6", BLUE = "2E7FA6", RED = "C0392B",
      AMBER = "B8860B", GREEN = "1E8449";
const LIGHT = "F5F8FB", INK = "1E2A38", MUTED = "6B7C8E", WHITE = "FFFFFF",
      LINE = "D9E2EC";
const HF = "맑은 고딕", BF = "맑은 고딕", MONO = "Consolas";
const ASSET = (name) => path.join(__dirname, "assets", name);

let pageNo = 0;
function footer(s, isDark) {
  const c = isDark ? "8FB0C6" : MUTED;
  s.addText("말이 없는 장면도 찾아내는 한국어 영상 모먼트 검색 · 최종발표",
    { x: 0.5, y: H - 0.42, w: 8, h: 0.3, fontSize: 9, color: c, fontFace: BF, margin: 0 });
  s.addText(String(pageNo), { x: W - 1.0, y: H - 0.42, w: 0.5, h: 0.3, fontSize: 9,
    color: c, fontFace: BF, align: "right", margin: 0 });
}
function content(titleText, kicker) {
  pageNo++;
  const s = p.addSlide();
  s.background = { color: LIGHT };
  s.addShape(p.shapes.RECTANGLE, { x: 0, y: 0, w: 0.22, h: H, fill: { color: TEAL } });
  if (kicker) s.addText(kicker, { x: 0.6, y: 0.40, w: 12, h: 0.3, fontSize: 11,
    color: TEAL, bold: true, charSpacing: 1, fontFace: BF, margin: 0 });
  s.addText(titleText, { x: 0.58, y: 0.70, w: 12.2, h: 0.72, fontSize: 25, bold: true,
    color: NAVY, fontFace: HF, margin: 0 });
  footer(s, false);
  return s;
}
function darkSlide() {
  pageNo++;
  const s = p.addSlide();
  s.background = { color: NAVY };
  s.addShape(p.shapes.RECTANGLE, { x: 0, y: 0, w: W, h: 0.12, fill: { color: TEAL } });
  return s;
}
function card(s, x, y, w, h, fill) {
  s.addShape(p.shapes.RECTANGLE, { x, y, w, h, fill: { color: fill || WHITE },
    line: { color: LINE, width: 1 },
    shadow: { type: "outer", color: "0F2A43", blur: 7, offset: 2, angle: 135, opacity: 0.10 } });
}
function tab(s, x, y, h, color) {
  s.addShape(p.shapes.RECTANGLE, { x, y, w: 0.09, h, fill: { color: color || TEAL } });
}
function mono(s, x, y, w, h, text, size, color) {
  s.addText(text, { x, y, w, h, fontSize: size || 11, color: color || INK,
    valign: "top", fontFace: MONO, lineSpacingMultiple: 1.22, margin: 0 });
}
function body(s, x, y, w, h, text, size, color) {
  s.addText(text, { x, y, w, h, fontSize: size || 12.5, color: color || INK,
    valign: "top", fontFace: BF, lineSpacingMultiple: 1.3, margin: 0 });
}
function stat(s, x, y, w, label, value, note, color) {
  card(s, x, y, w, 1.5); tab(s, x, y, 1.5, color);
  s.addText(label, { x: x + 0.22, y: y + 0.14, w: w - 0.4, h: 0.32, fontSize: 12,
    bold: true, color: NAVY, fontFace: HF, margin: 0 });
  s.addText(value, { x: x + 0.22, y: y + 0.5, w: w - 0.4, h: 0.5, fontSize: 20,
    bold: true, color, fontFace: MONO, margin: 0 });
  s.addText(note, { x: x + 0.22, y: y + 1.06, w: w - 0.4, h: 0.4, fontSize: 10.5, color: MUTED,
    fontFace: BF, margin: 0 });
}
function row(s, y, no, headText, bodyText, color, h) {
  const hh = h || 0.42;
  s.addShape(p.shapes.OVAL, { x: 0.62, y, w: hh, h: hh, fill: { color: color || TEAL } });
  s.addText(no, { x: 0.62, y, w: hh, h: hh, fontSize: 12, bold: true, color: WHITE,
    align: "center", valign: "middle", fontFace: BF, margin: 0 });
  s.addText(headText, { x: 1.2, y: y - 0.02, w: 3.4, h: hh + 0.04, fontSize: 13, bold: true,
    color: NAVY, valign: "middle", fontFace: HF, margin: 0 });
  s.addText(bodyText, { x: 4.6, y: y - 0.02, w: 8.1, h: hh + 0.04, fontSize: 12, color: INK,
    valign: "middle", fontFace: BF, margin: 0 });
}
function hdr(t) { return { text: t, options: { bold: true, color: WHITE, fill: { color: NAVY } } }; }
function tableAt(s, x, y, w, rows, colW, opts) {
  s.addTable(rows, {
    x, y, w, colW,
    border: { type: "solid", color: LINE, pt: 1 },
    fontFace: BF, fontSize: (opts && opts.fontSize) || 12, color: INK,
    valign: "middle", align: "center", rowH: (opts && opts.rowH) || 0.42,
    fill: { color: WHITE },
  });
}

/* ─── 1 표지 ─── */
{
  const s = darkSlide();
  s.addText("국방 AI·SW 프로젝트 과정 · 최종발표", { x: 0.95, y: 1.35, w: 11, h: 0.35,
    fontSize: 13, color: "8FB0C6", fontFace: BF, charSpacing: 1, margin: 0 });
  s.addShape(p.shapes.RECTANGLE, { x: 0, y: 1.95, w: 0.9, h: 0.09, fill: { color: TEAL } });
  s.addText("말이 없는 장면도 찾아내는\n한국어 영상 모먼트 검색",
    { x: 0.9, y: 2.15, w: 11.5, h: 1.7, fontSize: 34, bold: true, color: WHITE,
      fontFace: HF, lineSpacingMultiple: 1.15, margin: 0 });
  s.addText("2026. 9. 11.   ·   정대석", { x: 0.95, y: 6.55, w: 8, h: 0.4,
    fontSize: 13, color: "8FB0C6", fontFace: BF, margin: 0 });
  footer(s, true);
}

/* ─── 2 프로젝트 목표 ─── */
{
  const s = content("프로젝트 목표", "01  목표");
  card(s, 0.6, 1.62, 12.15, 1.15, "E8F6F4");
  tab(s, 0.6, 1.62, 1.15, TEAL);
  s.addText("긴 영상에서 원하는 장면을 자연어로 빠르게 검색하고,\n영상 전체 내용을 요약한 보고서까지 생성하는 시스템",
    { x: 0.95, y: 1.75, w: 11.6, h: 0.95, fontSize: 19, bold: true, color: NAVY,
      fontFace: HF, lineSpacingMultiple: 1.18, margin: 0 });

  card(s, 0.6, 3.05, 5.95, 2.85); tab(s, 0.6, 3.05, 2.85, BLUE);
  s.addText("영상 검색", { x: 0.95, y: 3.22, w: 5.3, h: 0.4, fontSize: 17,
    bold: true, color: BLUE, fontFace: HF, margin: 0 });
  s.addText("찾 기", { x: 0.95, y: 3.68, w: 5.3, h: 0.35, fontSize: 13, bold: true,
    color: MUTED, charSpacing: 3, fontFace: BF, margin: 0 });
  body(s, 0.95, 4.14, 5.3, 1.65,
    "이미 무엇을 찾을지 아는 사용자가 한국어 문장으로\n질문하면, 영상 속에서 가장 관련 있는 장면을\n순서대로 보여준다.\n\n일치하는 장면이 없으면 \"해당 장면 없음\"이라고\n알려준다 — 억지로 답을 만들지 않는다.", 12);

  card(s, 6.8, 3.05, 5.95, 2.85); tab(s, 6.8, 3.05, 2.85, AMBER);
  s.addText("전체 영상 보고서", { x: 7.15, y: 3.22, w: 5.3, h: 0.4, fontSize: 17,
    bold: true, color: AMBER, fontFace: HF, margin: 0 });
  s.addText("전체 이해", { x: 7.15, y: 3.68, w: 5.3, h: 0.35, fontSize: 13, bold: true,
    color: MUTED, charSpacing: 3, fontFace: BF, margin: 0 });
  body(s, 7.15, 4.14, 5.3, 1.65,
    "무엇을 찾을지 아직 모르는 사용자가\n영상 전체 흐름을 한 문단으로 먼저 본다.\n\n출력 = Overview(개요 요약) → Analysis(상세 분석) → Conclusion(결론)", 12);

  s.addText("검색은 질문이 있을 때, 보고서는 질문이 없을 때 쓰는 기능이다 — 두 기능은 서로의 대체재가 아니라 짝이다.",
    { x: 0.62, y: 6.15, w: 12.1, h: 0.35, fontSize: 12.5, color: MUTED, fontFace: BF, margin: 0 });
}

/* ─── (구)3 전체 구조 슬라이드 삭제됨 ─── */

/* ─── (구)4 데이터 슬라이드 삭제됨 ─── */

/* ─── 5 검색 문제 정의 (모델선택 근거는 파이프라인 설명 뒤로 이동) ─── */
{
  const s = content("영상 검색 — 왜 필요한가", "02  영상 검색 · 문제정의");
  row(s, 1.72, "1", "수작업 탐색", "긴 영상에서 원하는 장면 찾기는 지금도 타임라인을 직접 긁는 작업이다", BLUE);
  row(s, 2.34, "2", "시간 비용", "40분 영상 하나를 훑는 데 실시간에 가까운 시간이 든다", BLUE);
  row(s, 2.96, "3", "자막의 구멍", "자막(말)만 검색하면 \"말하지 않고 보여주기만 한 장면\"을 원리적으로 놓친다 — 간판·표정·행동은 자막에 없다", RED);

  card(s, 0.6, 3.85, 12.15, 1.55, "E8F6F4"); tab(s, 0.6, 3.85, 1.55, TEAL);
  s.addText("우리가 푸는 문제", { x: 0.95, y: 4.02, w: 11.5, h: 0.35, fontSize: 14, bold: true,
    color: TEAL, fontFace: HF, margin: 0 });
  body(s, 0.95, 4.42, 11.5, 0.9,
    "한국어 문장 하나로, 영상 속 정확한 시각 구간을 찾아준다.\n말한 것과 보이는 것을 모두 검색 대상으로 만들어, 자막만으로는 못 찾던 장면까지 찾는다.", 14);
}

/* ─── 6 검색 파이프라인 (M1~M7 모듈 대응 명시) ─── */
{
  const s = content("영상 검색은 어떻게 동작하는가", "03  영상 검색 · 원리");
  card(s, 0.6, 1.6, 7.65, 4.95);
  mono(s, 0.88, 1.8, 7.2, 4.6,
    "영상\n" +
    "  │  [M1] 5초 구간으로 자르고\n" +
    "  │  [M2] 구간마다 대표 화면 1장 선택\n" +
    "  ├── 소리   → 음성 인식        → 자막 문장   [M3]\n" +
    "  └── 화면   → 화면 이해 모델   → 장면 설명   [M3]\n" +
    "  │\n" +
    "  │  [M4] 두 문장을 각각 숫자 벡터로 바꿔 저장\n" +
    "  ▼\n" +
    "저장소 (영상마다 한 번만 생성)\n" +
    "  ▲\n" +
    "  │   질문 문장도 같은 방식으로 벡터로 바꿔 비교\n" +
    "사용자 질문\n" +
    "  │  [M5] 자막·화면 점수의 기준을 맞춘 뒤\n" +
    "  │       같은 비중으로 더한다 (자막 50% : 화면 50%)\n" +
    "  │       점수가 너무 낮으면 \"관련 장면 없음\"\n" +
    "  ▼\n" +
    "관련 구간 순서대로 + 근거(자막·설명·화면)", 11.5);

  const modRows = [
    [hdr("모듈"), hdr("하는 일")],
    ["M1", { text: "영상을 5초 구간으로 자른다", options: { align: "left" } }],
    ["M2", { text: "구간마다 대표 화면 1장을 고른다", options: { align: "left" } }],
    ["M3", { text: "소리→자막, 화면→장면 설명을 만든다", options: { align: "left" } }],
    ["M4", { text: "두 문장을 벡터로 바꿔 저장한다", options: { align: "left" } }],
    ["M5", { text: "질문과 비교해 점수를 합치고 순위를 매긴다", options: { align: "left" } }],
    ["M7", { text: "웹 화면으로 보여준다 (시연 UI)", options: { align: "left" } }],
    [{ text: "M6", options: { color: MUTED } },
     { text: "정확도 채점 (검색할 때는 안 돌아감)", options: { align: "left", color: MUTED, italic: true } }],
  ];
  tableAt(s, 8.5, 1.6, 4.25, modRows, [0.85, 3.4], { fontSize: 11, rowH: 0.58 });
  card(s, 8.5, 6.35, 4.25, 0.62, "F0F5FA");
  s.addText("M1~M5 · M7 = 실제 검색 흐름\nM6 = 개발 중 정확도 확인용(오프라인)",
    { x: 8.7, y: 6.42, w: 3.9, h: 0.48, fontSize: 10, bold: true, color: NAVY,
      fontFace: BF, lineSpacingMultiple: 1.15, margin: 0 });
}

/* ─── 6-1 모듈 상세 ① — M1~M5, M7이 주고받는 것 ─── */
{
  const s = content("모듈 상세 ① — 각 모듈이 주고받는 것", "03-1  영상 검색 · 모듈");
  const rows = [
    [hdr("모듈"), hdr("입력"), hdr("처리"), hdr("출력")],
    ["M1", "원본 영상", "5초 단위로 자른다", "구간 목록(시작·끝 시각)"],
    ["M2", "구간 안 프레임들", "앞 프레임과 가장 많이 달라지는 순간을 고른다", "대표 프레임 1장"],
    ["M3", "대표 프레임 + 음성", "화면 → 장면 설명 문장, 소리 → 자막 문장", "자막 문장 · 장면 설명 문장"],
    ["M4", "자막·장면 설명 문장", "임베딩 모델로 숫자 벡터로 바꾼다", "저장된 벡터 색인"],
    ["M5", "질문 + 벡터 색인", "질문도 벡터로 바꿔 유사도 비교 → 기준 맞춰 합산", "순위 매긴 결과 목록"],
    ["M7", "영상 + 사용자 질문", "M5를 호출하고 결과를 화면에 그린다", "웹 화면(검색창·결과·재생)"],
  ];
  tableAt(s, 0.6, 1.65, 12.15, rows, [1.0, 2.6, 6.05, 2.5], { fontSize: 11.5, rowH: 0.72 });
  card(s, 0.6, 6.55, 12.15, 0.55, "F0F5FA");
  s.addText("위 여섯 모듈이 실제 검색이 도는 경로다. M6은 이 경로에 들어가지 않는다 — 개발 중에만 따로 돌려 정확도를 채점한다(다음 장).",
    { x: 0.88, y: 6.63, w: 11.65, h: 0.4, fontSize: 11.5, bold: true, color: NAVY,
      fontFace: BF, valign: "middle", margin: 0 });
}

/* ─── 6-2 모듈 상세 ② — M6(평가)는 어떻게 하는가 (쉽고 간략하게) ─── */
{
  const s = content("M6 — 검색이 잘 맞는지 채점하는 모듈", "03-2  영상 검색 · 모듈");
  s.addShape(p.shapes.RECTANGLE, { x: 9.35, y: 0.72, w: 3.4, h: 0.42, fill: { color: MUTED } });
  s.addText("사용자 검색 때는 실행 안 됨", { x: 9.35, y: 0.72, w: 3.4, h: 0.42, fontSize: 11,
    bold: true, color: WHITE, align: "center", valign: "middle", fontFace: BF, margin: 0 });
  s.addText("검색 기능 자체가 아니라, 개발 중에 \"이 검색이 실제로 맞는가\"를 확인하려고 따로 돌리는 채점 도구다.",
    { x: 0.62, y: 1.5, w: 12.1, h: 0.32, fontSize: 12, color: MUTED, fontFace: BF, margin: 0 });

  function item(y, no, title, txt, color) {
    const hh = 1.1;
    card(s, 0.6, y, 12.15, hh); tab(s, 0.6, y, hh, color);
    s.addShape(p.shapes.OVAL, { x: 0.85, y: y + (hh - 0.42) / 2, w: 0.42, h: 0.42, fill: { color } });
    s.addText(no, { x: 0.85, y: y + (hh - 0.42) / 2, w: 0.42, h: 0.42, fontSize: 14, bold: true,
      color: WHITE, align: "center", valign: "middle", fontFace: BF, margin: 0 });
    s.addText(title, { x: 1.5, y: y + 0.14, w: 3.2, h: hh - 0.28, fontSize: 14, bold: true,
      color: NAVY, valign: "middle", fontFace: HF, lineSpacingMultiple: 1.15, margin: 0 });
    body(s, 4.9, y + 0.14, 7.6, hh - 0.28, txt, 12.5, INK);
  }
  item(2.0, "1", "몇 등으로\n찾았나 확인", "질문마다 정답 구간이 검색 결과 몇 번째에 나왔는지 본다", TEAL);
  item(3.15, "2", "점수로\n바꾼다", "1위면 1점, 2위면 0.5점… 이런 식으로 등수를 점수로 바꿔 평균 낸다", TEAL);
  item(4.3, "3", "두 방식을\n비교한다", "자막만 썼을 때와 자막+화면을 함께 썼을 때, 같은 질문으로 점수를 비교한다", BLUE);
  item(5.45, "4", "진짜 차이인지\n확인한다", "질문을 여러 번 다시 섞어 봐도 점수 차이가 그대로면, 우연이 아니라 진짜 개선이라고 본다", AMBER);

  card(s, 0.6, 6.63, 12.15, 0.38, "E8F6F4");
  s.addText("정리 — 정답과 검색 결과를 대조해 점수를 매기고, 그 점수 차이가 우연이 아닌지 확인하는 모듈이다.",
    { x: 0.88, y: 6.67, w: 11.65, h: 0.3, fontSize: 11, bold: true, color: NAVY,
      fontFace: BF, valign: "middle", margin: 0 });
}

/* ─── 7 왜 이 화면 설명 모델을 골랐나 (실제 프레임 + 실제 캡션 비교, 파이프라인 설명 뒤로 이동) ─── */
{
  const s = content("화면 설명 모델 — 같은 장면, 다른 설명", "04  모델 선택 근거 ①");
  s.addText("실제 학습용 영상에서 두 모델을 같은 서버·같은 조건으로 나란히 실행한 결과",
    { x: 0.62, y: 1.48, w: 12.1, h: 0.3, fontSize: 11, color: MUTED, fontFace: BF, margin: 0 });

  // column 1
  const cx1 = 0.6, cx2 = 6.83, cw = 5.9;
  s.addImage({ path: ASSET("frame_seg06_gwaktube.jpg"), x: cx1, y: 1.85, w: 4.6, h: 2.59 });
  s.addText("구간 #6 · 0:30~0:35 · 자막 없음(무발화 구간)", { x: cx1, y: 4.48, w: cw, h: 0.28,
    fontSize: 10.5, bold: true, color: MUTED, fontFace: BF, margin: 0 });
  card(s, cx1, 4.78, cw, 0.72, "F0F5FA"); tab(s, cx1, 4.78, 0.72, TEAL);
  s.addText([{ text: "지금 쓰는 모델(3B)  ", options: { bold: true, color: TEAL } },
    { text: "여성은 푸른색 코트를 입고 금발 머리를 묶고 있으며, 파란색 바지를 입고 있습니다…", options: { color: INK } }],
    { x: cx1 + 0.15, y: 4.86, w: cw - 0.3, h: 0.58, fontSize: 10.5, fontFace: BF,
      valign: "middle", lineSpacingMultiple: 1.15, margin: 0 });
  card(s, cx1, 5.55, cw, 0.72, "FDF6E9"); tab(s, cx1, 5.55, 0.72, AMBER);
  s.addText([{ text: "후보 모델(4B)  ", options: { bold: true, color: AMBER } },
    { text: "파란색 벽돌 건물 앞에서 녹색 재킷을 입은 여성이 길을 걷고 있다…", options: { color: INK } }],
    { x: cx1 + 0.15, y: 5.63, w: cw - 0.3, h: 0.58, fontSize: 10.5, fontFace: BF,
      valign: "middle", lineSpacingMultiple: 1.15, margin: 0 });
  s.addText("실제로는 청록 재킷·검은 머리 — 3B가 색과 머리 모두 틀렸고, 4B가 더 정확했다.",
    { x: cx1, y: 6.32, w: cw, h: 0.4, fontSize: 10.5, bold: true, color: GREEN, fontFace: BF, margin: 0 });

  // column 2
  s.addImage({ path: ASSET("frame_seg55_gwaktube.jpg"), x: cx2, y: 1.85, w: 4.6, h: 2.59 });
  s.addText("구간 #55 · 4:35~4:40 · 자막: \"기름으로 이빨 뿌렸는데도 밥이 없네요…\"", { x: cx2, y: 4.48, w: cw, h: 0.28,
    fontSize: 10.5, bold: true, color: MUTED, fontFace: BF, margin: 0 });
  card(s, cx2, 4.78, cw, 0.72, "F0F5FA"); tab(s, cx2, 4.78, 0.72, TEAL);
  s.addText([{ text: "지금 쓰는 모델(3B)  ", options: { bold: true, color: TEAL } },
    { text: "한 남성이 흰색 티셔츠를 입고 검은색 뚜껑의 작은 플라스틱 병을 들고 있다…", options: { color: INK } }],
    { x: cx2 + 0.15, y: 4.86, w: cw - 0.3, h: 0.58, fontSize: 10.5, fontFace: BF,
      valign: "middle", lineSpacingMultiple: 1.15, margin: 0 });
  card(s, cx2, 5.55, cw, 0.72, "FBF3F2"); tab(s, cx2, 5.55, 0.72, RED);
  s.addText([{ text: "후보 모델(4B)  ", options: { bold: true, color: RED } },
    { text: "一头卷发的男子穿着白色T恤，站在厨房里，右手拿着一瓶深色液体…  (중국어로 이탈)", options: { color: INK } }],
    { x: cx2 + 0.15, y: 5.63, w: cw - 0.3, h: 0.58, fontSize: 10.5, fontFace: BF,
      valign: "middle", lineSpacingMultiple: 1.15, margin: 0 });
  s.addText("4B가 한국어를 벗어났다 — 이런 설명은 한국어 질문에 걸리지 않는다.",
    { x: cx2, y: 6.32, w: cw, h: 0.4, fontSize: 10.5, bold: true, color: RED, fontFace: BF, margin: 0 });

  card(s, 0.6, 6.85, 12.15, 0.5, "F0F5FA");
  s.addText("① 사례는 후보가 더 정확했지만, ② 사례처럼 언어 자체를 벗어나는 오류를 자동 필터가 다 잡지 못한다(두 글자만 섞이면 검출률 0.08) — 그래서 아직 교체하지 않았다.",
    { x: 0.88, y: 6.9, w: 11.65, h: 0.4, fontSize: 10.5, bold: true, color: NAVY, fontFace: BF, valign: "middle", margin: 0 });
}

/* ─── 8 왜 이 임베딩 모델을 골랐나 (파이프라인 설명 뒤로 이동) ─── */
{
  const s = content("문장 임베딩 모델 — 왜 KURE-v1을 쓰는가", "05  모델 선택 근거 ②");
  body(s, 0.62, 1.52, 12.1, 0.55,
    "문장을 숫자로 바꾸는 모델. 비교한 후보 7종 — BGE-M3 계열 3종 · multilingual-e5-large · KoE5 · Qwen3-Embedding · gte-multilingual", 12);

  const rows2 = [
    [hdr("비교 조건"), hdr("KURE-v1"), hdr("BGE-M3"), hdr("해석")],
    ["화면 설명 채널만 따로 쟀을 때", { text: "0.55", options: { bold: true, color: GREEN } }, "0.44",
      { text: "격차가 가장 크게 드러남", options: { align: "left" } }],
    ["실제 배포 비중(자막+화면 함께)", { text: "0.67", options: { bold: true, color: GREEN } }, "0.64",
      { text: "그대로 써도 KURE가 앞섬", options: { align: "left" } }],
  ];
  tableAt(s, 0.6, 2.2, 12.15, rows2, [3.6, 2.2, 2.2, 4.15], { fontSize: 12, rowH: 0.55 });
  s.addText("숫자는 MRR(정답을 얼마나 위로 올리는지, 1에 가까울수록 좋음) · 학습용 데이터 96건 기준",
    { x: 0.62, y: 3.95, w: 12.1, h: 0.3, fontSize: 10.5, color: MUTED, fontFace: BF, margin: 0 });

  card(s, 0.6, 4.4, 12.15, 1.55, "F0F5FA"); tab(s, 0.6, 4.4, 1.55, TEAL);
  s.addText("외부 데이터로 다시 확인", { x: 0.95, y: 4.54, w: 11.4, h: 0.32, fontSize: 13, bold: true,
    color: TEAL, fontFace: HF, margin: 0 });
  body(s, 0.95, 4.9, 11.4, 0.98,
    "우리가 만들지 않은 AI Hub 공개데이터 562건에서 후보 7종을 KURE-v1과 다시 비교했다. 비교가 여러 번이라 통계 기준을 더 엄격하게 적용했더니, 7종 전부 의미 있는 개선을 보이지 못했다(가장 나은 후보도 개선 폭이 불확실했다) → KURE-v1 유지.", 11);

  card(s, 0.6, 6.1, 12.15, 0.85, "E8F6F4"); tab(s, 0.6, 6.1, 0.85, TEAL);
  s.addText("처음 고를 때 뚜렷하게 앞섰고, 나중에 외부 데이터로 다시 확인했을 때도 흔들리지 않았다.",
    { x: 0.95, y: 6.24, w: 11.6, h: 0.55, fontSize: 12.5, bold: true, color: NAVY, fontFace: HF,
      valign: "middle", margin: 0 });
}

/* ─── (구)9 검색 정확도 슬라이드 삭제됨 ─── */

/* ─── (구)10 검색 결과 슬라이드 삭제됨 ─── */

/* ─── 9 데모 — 실제 검색 화면 ─── */
{
  const s = content("검색 데모 — 실제 화면", "06  영상 검색 · 데모");
  const iw = 6.9, ih = 4.31; // 1600x1000 원본 비율(1.6:1) 유지
  const ix = (W - iw) / 2;
  s.addImage({ path: ASSET("ui_search_screenshot.png"), x: ix, y: 1.5, w: iw, h: ih });
  s.addShape(p.shapes.RECTANGLE, { x: ix, y: 1.5, w: iw, h: ih, fill: { type: "none" },
    line: { color: LINE, width: 1 } });

  const legend = [
    ["①", "질문 입력창 — \"새우전을 부치는 장면\"처럼 한국어 문장을 그대로 넣는다", BLUE],
    ["②", "순위별 결과 — 정답 후보마다 자막 근거와 화면 설명 근거가 함께 뜬다", TEAL],
    ["③", "채널별 일치도 그래프 — 자막·화면 각각의 점수를 시간대별로 보여준다", AMBER],
    ["④", "영상 재생기 — 결과를 클릭하면 그 순간부터 바로 재생된다", GREEN],
  ];
  const lw = 5.95;
  for (let i = 0; i < legend.length; i++) {
    const [no, txt, c] = legend[i];
    const lx = 0.6 + (i % 2) * (lw + 0.25);
    const row_y = 6.02 + Math.floor(i / 2) * 0.48;
    s.addText(no, { x: lx, y: row_y, w: 0.3, h: 0.42, fontSize: 12, bold: true, color: c,
      fontFace: BF, valign: "top", margin: 0 });
    s.addText(txt, { x: lx + 0.3, y: row_y, w: lw - 0.3, h: 0.42, fontSize: 10, color: INK,
      fontFace: BF, valign: "top", lineSpacingMultiple: 1.1, margin: 0 });
  }
}

/* ─── 12 보고서 문제 정의 ─── */
{
  const s = content("전체 영상 보고서 — 왜 추가했나", "07  전체 보고서 · 문제정의");
  card(s, 0.6, 1.68, 12.15, 1.3, "FDF6E9"); tab(s, 0.6, 1.68, 1.3, AMBER);
  s.addText("검색은 \"원하는 부분 찾기\"에는 좋지만, 영상 전체가 어떤 내용인지 한눈에 이해하기는 어렵다.\n질문을 던지려면 이미 무엇을 찾을지 알고 있어야 한다.",
    { x: 0.95, y: 1.88, w: 11.6, h: 0.95, fontSize: 15, bold: true, color: NAVY,
      fontFace: HF, lineSpacingMultiple: 1.2, margin: 0 });

  card(s, 0.6, 3.3, 12.15, 1.6);
  mono(s, 0.95, 3.6, 11.6, 1.1,
    "영상  →  전체 흐름 파악  →  Overview(개요 요약)  →  Analysis(상세 분석)  →  Conclusion(결론)  →  Report(보고서)\n" +
    "                            ─────────────    ─────────    ──────────     ────────\n" +
    "                              구현 완료         진행 중        미착수         미착수", 13.5);

  card(s, 0.6, 5.2, 12.15, 1.25, "F0F5FA");
  body(s, 0.95, 5.42, 11.6, 0.95,
    "검색은 사용자가 질문을 갖고 있을 때 동작한다. 보고서는 질문 자체를 만들어 준다.\n" +
    "두 기능은 경쟁 관계가 아니라 진입 경로가 다른 것이다 — 이 관계는 통합 장에서 닫는다.", 12.5);
}

/* ─── 13 왜 나눠 분석했는가 (48초·24초 근거 추가) ─── */
{
  const s = content("왜 영상을 나눠서 분석했는가", "08  전체 보고서 · 설계");
  card(s, 0.6, 1.55, 5.95, 1.35, "FBF3F2"); tab(s, 0.6, 1.55, 1.35, RED);
  s.addText("① GPU 메모리 한계", { x: 0.95, y: 1.66, w: 5.3, h: 0.32, fontSize: 14, bold: true,
    color: RED, fontFace: HF, margin: 0 });
  body(s, 0.95, 2.0, 5.3, 0.85,
    "40분짜리 영상은 프레임 수가 너무 많아\n한 번에 전부 넣을 수 없다.", 11.5);

  card(s, 6.8, 1.55, 5.95, 1.35, "FBF3F2"); tab(s, 6.8, 1.55, 1.35, RED);
  s.addText("② 길수록 품질이 떨어진다", { x: 7.15, y: 1.66, w: 5.3, h: 0.32, fontSize: 14,
    bold: true, color: RED, fontFace: HF, margin: 0 });
  body(s, 7.15, 2.0, 5.3, 0.85,
    "한 번에 넣는 분량이 길수록 중간 내용을\n놓치고 출력 품질이 떨어진다.", 11.5);

  card(s, 0.6, 3.05, 12.15, 1.7);
  mono(s, 0.95, 3.22, 11.6, 1.4,
    "영상\n" +
    "  →  48초씩 겹치게(24초씩) 나눈다 — 구간마다 2초 간격으로 화면 24장을 넣는다\n" +
    "  →  화면 이해 모델이 구간을 직접 보고 큰 활동만 요약 → 시간 순서대로 정리\n" +
    "  →  같은 모델이 전체 영상 Overview로 합성 (짧은 요약 / 자세한 요약)", 12);

  card(s, 0.6, 4.9, 12.15, 1.1, "F0F5FA"); tab(s, 0.6, 4.9, 1.1, AMBER);
  s.addText("왜 48초 · 24초인가", { x: 0.95, y: 5.0, w: 11.4, h: 0.3, fontSize: 12.5, bold: true,
    color: AMBER, fontFace: HF, margin: 0 });
  body(s, 0.95, 5.32, 11.4, 0.62,
    "24초 overlap은 window 길이의 절반이다 — 모든 순간이 서로 다른 구간에서 최소 두 번 관찰되어, 활동이 경계에서 통째로 잘리는 것을 막는다. window 길이(48초)는 GPU가 한 번에 무리 없이 처리할 수 있는 화면 수(24장)에 맞춘 값이다 — 다른 길이와의 정식 비교는 아직 진행 전이다.", 10.5);

  card(s, 0.6, 6.15, 5.95, 0.72, "E8F6F4"); tab(s, 0.6, 6.15, 0.72, TEAL);
  s.addText("영상을 직접 본다 — 검색용 색인을 재사용하지 않는다",
    { x: 0.95, y: 6.27, w: 5.4, h: 0.48, fontSize: 11.5, bold: true, color: NAVY,
      fontFace: BF, margin: 0 });
  card(s, 6.8, 6.15, 5.95, 0.72, "E8F6F4"); tab(s, 6.8, 6.15, 0.72, TEAL);
  s.addText("모델 하나가 관찰과 요약을 모두 한다 — 별도 모델 없음",
    { x: 7.15, y: 6.27, w: 5.4, h: 0.48, fontSize: 11.5, bold: true, color: NAVY,
      fontFace: BF, margin: 0 });
}

/* ─── 14 실제 Overview 결과 (V2 동기화 대기) ─── */
{
  const s = content("실제 Overview 결과", "09  전체 보고서 · 출력");
  s.addShape(p.shapes.RECTANGLE, { x: 9.6, y: 0.75, w: 3.15, h: 0.42,
    fill: { color: AMBER } });
  s.addText("최신 결과 반영 전 자리표시자", { x: 9.6, y: 0.75, w: 3.15, h: 0.42, fontSize: 11,
    bold: true, color: WHITE, align: "center", valign: "middle", fontFace: BF, margin: 0 });

  s.addText("자리표시자 — 초기 실행의 실제 출력 (40분 영상 중 앞 10분 구간, 화면 이해 모델이 직접 관찰)",
    { x: 0.62, y: 1.5, w: 12.1, h: 0.3, fontSize: 11.5, color: MUTED, fontFace: BF, margin: 0 });
  card(s, 0.6, 1.86, 12.15, 1.75, "F0F5FA"); tab(s, 0.6, 1.86, 1.75, TEAL);
  s.addText("주방에서 다양한 감자 요리와 커리 우동을 준비하고, 아침 식사 메뉴를 바꾸며 반복적으로 요리 활동을 진행한 후, 병원 퇴원 후 외출을 시작해 동대문 시장에서 김밥을 제작하고 식사를 하며 일상의 흐름을 이어간다. 이후 직장 시간에 옷 수선을 하며, 아침 식사와 출근 준비를 마치고 선물 포장 및 시장 방문 계획을 세우며 하루를 마무리한다.",
    { x: 0.95, y: 2.04, w: 11.6, h: 1.45, fontSize: 14, color: INK, italic: true,
      fontFace: BF, lineSpacingMultiple: 1.25, margin: 0 });

  card(s, 0.6, 3.78, 5.95, 0.85, "E8F6F4"); tab(s, 0.6, 3.78, 0.85, GREEN);
  s.addText("된 것 — 활동 전환의 순서가 잡힌다", { x: 0.95, y: 3.96, w: 5.4, h: 0.5,
    fontSize: 13, bold: true, color: GREEN, fontFace: HF, margin: 0 });
  card(s, 6.8, 3.78, 5.95, 0.85, "FBF3F2"); tab(s, 6.8, 3.78, 0.85, RED);
  s.addText("안 된 것 — 아직 발표에 쓸 품질이 아니다", { x: 7.15, y: 3.96, w: 5.4, h: 0.5,
    fontSize: 13, bold: true, color: RED, fontFace: HF, margin: 0 });

  s.addText("현재 개선 중인 점", { x: 0.62, y: 4.82, w: 6, h: 0.32, fontSize: 14,
    bold: true, color: NAVY, fontFace: HF, margin: 0 });
  const fixes = [
    ["지나치게 세부적인 활동 표현", "구간 단위 동작이 전체 요약 문장에 그대로 올라온다"],
    ["모호한 활동 분류", "비슷한 활동이 하나로 뭉개지거나 과하게 구체화된다"],
    ["불확실성 표현 부재", "근거가 약한 구간도 단정적으로 서술한다"],
    ["자연스러운 문장화", "활동 나열에 가깝고 이야기로서의 연결이 약하다"],
  ];
  let y = 5.2;
  for (const [k, v] of fixes) {
    s.addShape(p.shapes.RECTANGLE, { x: 0.62, y: y + 0.1, w: 0.1, h: 0.1, fill: { color: RED } });
    s.addText(k, { x: 0.88, y: y - 0.02, w: 3.7, h: 0.32, fontSize: 12, bold: true,
      color: NAVY, valign: "middle", fontFace: BF, margin: 0 });
    s.addText(v, { x: 4.6, y: y - 0.02, w: 8.1, h: 0.32, fontSize: 11.5, color: INK,
      valign: "middle", fontFace: BF, margin: 0 });
    y += 0.36;
  }
  s.addText("경로가 동작하는 것과 품질이 확보된 것은 다르다 — 후자는 아직이다.",
    { x: 0.62, y: 6.68, w: 12.1, h: 0.3, fontSize: 12, bold: true, color: MUTED,
      fontFace: BF, margin: 0 });
}

/* ─── 15 통합 ─── */
{
  const s = content("검색과 보고서가 어떻게 연결되는가", "10  통합");
  card(s, 0.6, 1.68, 12.15, 2.6);
  mono(s, 0.95, 1.92, 11.6, 2.2,
    "   영상  ──→  보고서 생성  ──→  주요 주장\n" +
    "                                     │\n" +
    "                                     ▼\n" +
    "                          검색 기능으로 해당 장면 다시 확인\n" +
    "                                     │\n" +
    "                                     ▼\n" +
    "                          근거 구간 + 화면으로 확인", 13.5);

  card(s, 0.6, 4.5, 12.15, 1.05, "E8F6F4"); tab(s, 0.6, 4.5, 1.05, TEAL);
  s.addText("보고서는 영상 전체를 요약하고, 검색은 그 요약이 맞는지 다시 찾아 확인하는 역할을 한다.",
    { x: 0.95, y: 4.7, w: 11.6, h: 0.6, fontSize: 15, bold: true, color: NAVY,
      fontFace: HF, margin: 0 });

  body(s, 0.62, 5.78, 12.1, 1.0,
    "보고서의 결론(\"Overview도 아직 틀린다\")과 검색의 결론(\"검색 근거도 정답이 아니다\")은 같은 문제의 양면이다.\n" +
    "그래서 한쪽 출력을 다른 쪽으로 되짚는 구조가 필요하다 — 두 기능이 따로 노는 게 아닌 이유다.", 12.5);
}

/* ─── 16 군 활용성 ─── */
{
  const s = content("군 활용 가능성", "11  군 활용성");
  const items = [
    ["사후검토(AAR) 지원", "훈련·연습 영상에서 특정 상황을 문장으로 찾아 되짚는다. 요약 리포트가 근거 구간과 함께 초안을 만든다.", BLUE],
    ["무발화 영상 검색", "감시·정찰 영상처럼 말이 거의 없는 자료에서도 화면 채널만으로 검색된다 — 자막 검색이 무력한 영역이다.", TEAL],
    ["교육·교범 영상 탐색", "긴 교육 영상에서 필요한 절차 구간을 문장으로 바로 찾는다.", AMBER],
  ];
  let y = 1.75;
  for (const [k, v, c] of items) {
    card(s, 0.6, y, 12.15, 1.28); tab(s, 0.6, y, 1.28, c);
    s.addText(k, { x: 0.95, y: y + 0.14, w: 3.6, h: 1.0, fontSize: 15, bold: true,
      color: c, valign: "middle", fontFace: HF, margin: 0 });
    body(s, 4.7, y + 0.14, 7.7, 1.0, v, 12.5);
    y += 1.42;
  }
  card(s, 0.6, 6.05, 12.15, 0.85, "F0F5FA"); tab(s, 0.6, 6.05, 0.85, MUTED);
  s.addText("전제 — 현재 실험은 공개 한국어 영상으로 수행했다. 군 자료 적용에는 폐쇄망 구동과 도메인 재검증이 필요하다.",
    { x: 0.95, y: 6.22, w: 11.6, h: 0.5, fontSize: 12, bold: true, color: NAVY, fontFace: BF, margin: 0 });
}

/* ─── 17 결과 / 배운 점 / 향후 ─── */
{
  const s = content("결과 · 배운 점 · 향후", "12  마무리");
  const cols = [
    ["확인한 것", GREEN, [
      "자연어 영상 검색 기능 구축",
      "우리 데이터·외부 데이터 모두에서 성능 개선 확인",
      "말 없는 장면을 찾아내는 능력이 크게 좋아짐",
      "검색 결과를 클릭하면 그 순간으로 바로 이동",
      "영상을 직접 관찰해 전체 요약을 만드는 경로 구현",
    ]],
    ["배운 점", BLUE, [
      "긴 영상은 모델 한 번 호출로 해결되지 않는다 — 나누고 다시 합치는 설계가 본체다",
      "검색과 전체 요약은 목적이 달라 기능을 분리해야 한다",
      "모델 출력은 검증 없이 정답으로 쓸 수 없다 — 장면 설명도, 보고서도",
    ]],
    ["향후", AMBER, [
      "① Overview 품질 개선 (활동 표현 수준·불확실성 표시)",
      "② Analysis / Conclusion 생성",
      "③ 검색 근거와 보고서 주장을 자동으로 연결",
      "④ 최종 문서 형태로 통합",
    ]],
  ];
  let x = 0.6;
  for (const [title, color, lines] of cols) {
    card(s, x, 1.68, 3.92, 4.6); tab(s, x, 1.68, 4.6, color);
    s.addText(title, { x: x + 0.28, y: 1.88, w: 3.4, h: 0.38, fontSize: 16, bold: true,
      color, fontFace: HF, margin: 0 });
    let yy = 2.42;
    for (const l of lines) {
      s.addShape(p.shapes.OVAL, { x: x + 0.3, y: yy + 0.09, w: 0.09, h: 0.09, fill: { color } });
      s.addText(l, { x: x + 0.52, y: yy - 0.04, w: 3.2, h: 0.85, fontSize: 11.5,
        color: INK, valign: "top", fontFace: BF, lineSpacingMultiple: 1.18, margin: 0 });
      yy += 0.26 + Math.ceil(l.length / 20) * 0.2;
    }
    x += 4.12;
  }
  card(s, 0.6, 6.42, 12.15, 0.55, "F0F5FA");
  s.addText("향후 계획은 ①→④ 순서로 진행한다 — 품질 확보 없이 문서 통합으로 넘어가지 않는다.",
    { x: 0.88, y: 6.5, w: 11.65, h: 0.4, fontSize: 12, bold: true, color: NAVY,
      fontFace: BF, valign: "middle", margin: 0 });
}

const OUT_NAME = process.env.WVR_DECK_OUT || "최종발표_초안_2026-09-11.pptx";
p.writeFile({ fileName: path.join(__dirname, OUT_NAME) })
  .then((f) => console.log("작성:", f));
