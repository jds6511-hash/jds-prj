/* 주간 진행 발표 2026-08-28 — 이번 주 진행 / 막힌 부분 / 향후 일정
 * 스타일은 build_deck.js(진행상황발표)와 동일하게 유지한다. */
const path = require("path");
const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.layout = "LAYOUT_WIDE";
p.title = "통합 상황보고서 자동 생성 시스템 (주간 진행 발표 2026-08-28)";

const W = 13.33, H = 7.5;
const NAVY = "0F2A43", TEAL = "18B7A6", BLUE = "2E7FA6", RED = "C0392B",
      AMBER = "B8860B";
const LIGHT = "F5F8FB", INK = "1E2A38", MUTED = "6B7C8E", WHITE = "FFFFFF",
      LINE = "D9E2EC";
const HF = "맑은 고딕", BF = "맑은 고딕", MONO = "Consolas";

let pageNo = 0;
function footer(s, dark) {
  const c = dark ? "8FB0C6" : MUTED;
  s.addText("통합 상황보고서 자동 생성 시스템 · 주간 진행 발표 2026-08-28",
    { x: 0.5, y: H - 0.42, w: 8, h: 0.3, fontSize: 9, color: c, fontFace: BF, margin: 0 });
  s.addText(`${pageNo}`, { x: W - 1.0, y: H - 0.42, w: 0.5, h: 0.3, fontSize: 9,
    color: c, fontFace: BF, align: "right", margin: 0 });
}
function content(titleText, kicker) {
  pageNo++;
  const s = p.addSlide();
  s.background = { color: LIGHT };
  s.addShape(p.shapes.RECTANGLE, { x: 0, y: 0, w: 0.22, h: H, fill: { color: TEAL } });
  if (kicker) s.addText(kicker, { x: 0.6, y: 0.40, w: 12, h: 0.3, fontSize: 11,
    color: TEAL, bold: true, charSpacing: 2, fontFace: BF, margin: 0 });
  s.addText(titleText, { x: 0.58, y: 0.70, w: 12.2, h: 0.72, fontSize: 27, bold: true,
    color: NAVY, fontFace: HF, margin: 0 });
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
  s.addShape(p.shapes.RECTANGLE, { x, y, w, h, fill: { color: fill || WHITE },
    line: { color: LINE, width: 1 },
    shadow: { type: "outer", color: "0F2A43", blur: 7, offset: 2, angle: 135, opacity: 0.10 } });
}
function tab(s, x, y, h, color) {
  s.addShape(p.shapes.RECTANGLE, { x, y, w: 0.09, h, fill: { color: color || TEAL } });
}
function mono(s, x, y, w, h, text, size, color) {
  s.addText(text, { x, y, w, h, fontSize: size || 11, color: color || INK,
    fontFace: MONO, lineSpacingMultiple: 1.22, margin: 0 });
}
/* 지표 카드 — 값 하나 + 라벨 + 판정 */
function stat(s, x, y, w, label, value, verdictText, color) {
  card(s, x, y, w, 1.5); tab(s, x, y, 1.5, color);
  s.addText(label, { x: x + 0.22, y: y + 0.14, w: w - 0.4, h: 0.32, fontSize: 12,
    bold: true, color: NAVY, fontFace: HF, margin: 0 });
  s.addText(value, { x: x + 0.22, y: y + 0.5, w: w - 0.4, h: 0.5, fontSize: 24,
    bold: true, color, fontFace: MONO, margin: 0 });
  s.addText(verdictText, { x: x + 0.22, y: y + 1.06, w: w - 0.4, h: 0.32,
    fontSize: 10.5, color: MUTED, fontFace: BF, margin: 0 });
}
/* 한 줄 항목 (번호 + 제목 + 설명) */
function row(s, y, no, head, body, color) {
  s.addShape(p.shapes.OVAL, { x: 0.62, y, w: 0.42, h: 0.42, fill: { color: color || TEAL } });
  s.addText(no, { x: 0.62, y, w: 0.42, h: 0.42, fontSize: 12, bold: true, color: WHITE,
    align: "center", valign: "middle", fontFace: BF, margin: 0 });
  s.addText(head, { x: 1.2, y: y - 0.02, w: 3.3, h: 0.46, fontSize: 13, bold: true,
    color: NAVY, valign: "middle", fontFace: HF, margin: 0 });
  s.addText(body, { x: 4.5, y: y - 0.02, w: 8.2, h: 0.46, fontSize: 12, color: INK,
    valign: "middle", fontFace: BF, margin: 0 });
}

/* ─── 1 표지 ─── */
{
  const s = dark();
  s.addShape(p.shapes.RECTANGLE, { x: 0, y: 1.95, w: 0.9, h: 0.09, fill: { color: TEAL } });
  s.addText("음성·영상 멀티모달 LLM을 활용한\n통합 상황보고서 자동 생성 시스템",
    { x: 0.9, y: 2.15, w: 11.5, h: 1.5, fontSize: 30, bold: true, color: WHITE,
      fontFace: HF, lineSpacingMultiple: 1.1, margin: 0 });
  s.addText([
    { text: "이번 주는 ", options: { color: "CFE0EC" } },
    { text: "M8(상황보고서 생성) 판정 사이클을 끝까지 돌렸습니다", options: { color: TEAL, bold: true } },
    { text: " — 결과는 기준 미달이고, 그 사실과 원인을 그대로 보고합니다", options: { color: "CFE0EC" } },
  ], { x: 0.95, y: 3.95, w: 11.5, h: 0.8, fontSize: 15, fontFace: BF,
       lineSpacingMultiple: 1.2, margin: 0 });
  mono(s, 0.95, 5.0, 11.5, 1.0,
    "커밋 66건 (8/25~)   ·   테스트 2,227건 통과   ·   판정 표본 8편 · 2,075구간   ·   사람 정답 68건",
    12, "9FC3D6");
  s.addText("주간 진행 발표 · 2026-08-28", { x: 0.95, y: 6.5, w: 11.5, h: 0.4,
    fontSize: 14, bold: true, color: WHITE, fontFace: HF, margin: 0 });
}

/* ─── 2 한 장 요약 ─── */
{
  const s = content("이번 주 결론 — 절차는 닫았고, 성능은 기준에 못 미쳤습니다", "요약");
  card(s, 0.6, 1.62, 12.15, 1.35, "EEF7F6"); tab(s, 0.6, 1.62, 1.35, TEAL);
  s.addText([
    { text: "닫힌 것   ", options: { bold: true, color: TEAL, fontFace: HF } },
    { text: "판정에 필요한 모든 것을 결과를 보기 전에 고정했습니다. 표본 8편·사람 정답 68건·관문 기준·채점 코드 " },
    { text: "전부 해시로 동결", options: { bold: true } },
    { text: " → 그 다음에 처음으로 생성·채점했습니다. \"결과를 보고 기준을 맞췄다\"는 의심을 반박할 근거가 파일로 남았습니다." },
  ], { x: 1.0, y: 1.62, w: 11.5, h: 1.35, fontSize: 12.5, color: INK, valign: "middle",
       fontFace: BF, lineSpacingMultiple: 1.2, margin: 0 });

  card(s, 0.6, 3.12, 12.15, 1.35, "FBEEEC"); tab(s, 0.6, 3.12, 1.35, RED);
  s.addText([
    { text: "못 넘은 것   ", options: { bold: true, color: RED, fontFace: HF } },
    { text: "세 관문이 모두 미달입니다. 원인은 " },
    { text: "\"사건을 어느 크기로 자를지\"가 사람 기준과 안 맞는 것", options: { bold: true } },
    { text: "이었습니다. 짧은 사건은 큰 사건에 삼켜지고, 긴 사건은 여러 조각으로 쪼개집니다. 개선을 2회 시도했지만 필요한 수준까지 수렴시키지 못했고, 원래 정상이던 영상에서 회귀가 나왔습니다." },
  ], { x: 1.0, y: 3.12, w: 11.5, h: 1.35, fontSize: 12.5, color: INK, valign: "middle",
       fontFace: BF, lineSpacingMultiple: 1.2, margin: 0 });

  card(s, 0.6, 4.62, 12.15, 1.35, "FFF8E7"); tab(s, 0.6, 4.62, 1.35, AMBER);
  s.addText([
    { text: "결정   ", options: { bold: true, color: AMBER, fontFace: HF } },
    { text: "개발 반복 상한(2회)에 도달해 추가 튜닝을 멈췄습니다. " },
    { text: "M8 미달을 최종 결과로 확정", options: { bold: true } },
    { text: "하고, 후속 가설은 향후과제로 이관합니다. " },
    { text: "M9(품질 채점)는 HOLD", options: { bold: true } },
    { text: " — 합격 기준이 설계에 없어 지금 열지 않습니다." },
  ], { x: 1.0, y: 4.62, w: 11.5, h: 1.35, fontSize: 12.5, color: INK, valign: "middle",
       fontFace: BF, lineSpacingMultiple: 1.2, margin: 0 });

  s.addText("숫자를 좋게 만드는 것보다, 어떤 숫자가 나와도 그것이 참임을 보일 수 있게 만드는 데 이번 주를 썼습니다.",
    { x: 0.6, y: 6.15, w: 12.15, h: 0.4, fontSize: 12, italic: true, color: MUTED,
      fontFace: BF, margin: 0 });
}

/* ─── 3 이번 주 진행 순서 ─── */
{
  const s = content("이번 주 진행 — 순서를 바꿀 수 없게 만든 9단계", "진행 내용");
  s.addText("각 단계는 앞 단계의 산출물 해시를 확인해야 시작됩니다. 코드가 순서를 강제합니다.",
    { x: 0.6, y: 1.52, w: 12.15, h: 0.3, fontSize: 11.5, color: MUTED, fontFace: BF, margin: 0 });
  const items = [
    ["1", "방법론 결정", "판정 기준·역할 6건(D1~D6) 확정. \"평가 완료\"와 \"기준 통과\"를 분리해 기록"],
    ["2", "표본 규칙 동결", "영상을 고르는 규칙을 후보를 보기 전에 커밋 (되돌리기 불가)"],
    ["3", "표본 8편 확정", "후보 조회 120건 → 자격 62편 → 해시 순서로 신규 2편 결정"],
    ["4", "사람 정답 작성", "8편 68건. 화면만 보고 작성 — 캡션·자막·검색 결과는 도구가 차단"],
    ["5", "정답 동결", "영상별 해시 + 전체 해시 1개. 이후 수정하면 채점기가 거부"],
    ["6", "관문 기준 동결", "세 관문의 계산 방법을 결과 0건 시점에 확정 (§C1·C2·C3)"],
    ["7", "채점기 동결", "관문별 함수 소스 해시 + 테스트 결과까지 기록"],
    ["8", "공식 생성", "서버 GPU에서 8편 생성 (7B 모델). 중간 내용 열람 없음"],
    ["9", "판정·실패 분해", "세 관문 채점 → 원인 분해 → 개선 2회 시도"],
  ];
  items.forEach((it, i) => row(s, 1.95 + i * 0.53, it[0], it[1], it[2],
    i >= 7 ? BLUE : TEAL));
  s.addText("8단계 이전에는 생성 결과를 한 번도 보지 않았습니다 — 사람 정답이 모델 출력에 끌려가는 것을 막기 위해서입니다.",
    { x: 0.6, y: 6.72, w: 12.15, h: 0.3, fontSize: 11, color: MUTED, fontFace: BF, margin: 0 });
}

/* ─── 4 판정 결과 ─── */
{
  const s = content("판정 결과 — 세 관문 모두 기준 미달", "결과");
  stat(s, 0.6, 1.62, 3.9, "C1  치명적 실패 영상 수", "4 / 8", "기준 0편 · 미달", RED);
  stat(s, 4.7, 1.62, 3.9, "C2  사건 시간 정합 (중앙값)", "0.331", "기준 0.70 이상 · 미달", RED);
  stat(s, 8.8, 1.62, 3.95, "C3  문장 수 ÷ 정답 사건 수", "최대 7.00", "기준 2.0 이하 · 미달", RED);

  card(s, 0.6, 3.35, 12.15, 1.5);
  s.addText("세 관문이 각각 무엇을 보는가", { x: 0.95, y: 3.48, w: 11.5, h: 0.3,
    fontSize: 12.5, bold: true, color: NAVY, fontFace: HF, margin: 0 });
  mono(s, 0.95, 3.85, 11.5, 0.95,
    "C1   보고서가 아예 망가졌는가        다른 언어로 이탈 · 중간에 끊김 · 같은 문장 반복\n" +
    "C2   사건을 같은 시간대에 잡았는가    사람이 적은 사건과 시간 범위가 얼마나 겹치는가 (0~1)\n" +
    "C3   너무 잘게 쪼개 쓰지 않았는가     정답 사건 하나를 두 문장 넘게 쓰지 않는다", 11);

  card(s, 0.6, 5.05, 12.15, 1.25, "EEF4F8"); tab(s, 0.6, 5.05, 1.25, BLUE);
  s.addText([
    { text: "기준을 고치지 않았습니다.   ", options: { bold: true, color: BLUE, fontFace: HF } },
    { text: "0.70·2.0에 외부 근거가 없다는 사실은 사전등록에 이미 적혀 있고, \"결과가 나빠도 임계를 고치지 않는다\"도 함께 적혀 있었습니다. 그대로 지켰습니다. 평가는 " },
    { text: "완료(COMPLETE)", options: { bold: true } },
    { text: ", 채택은 " },
    { text: "미달(FAIL)", options: { bold: true, color: RED } },
    { text: "로 분리해 기록했습니다." },
  ], { x: 1.0, y: 5.05, w: 11.5, h: 1.25, fontSize: 12, color: INK, valign: "middle",
       fontFace: BF, lineSpacingMultiple: 1.2, margin: 0 });
}

/* ─── 5 표본을 어떻게 골랐나 ─── */
{
  const s = content("표본 8편 — 결과와 무관하게 골랐다는 것을 증명하는 방식", "방법");
  const steps = [
    ["규칙 먼저 커밋", "후보를 한 편도 보기 전에\n선정 규칙·자격 조건을 커밋", TEAL],
    ["후보 조회", "고정한 검색어 6개로 120건\n제목·길이 등 정보만 (내용 안 봄)", TEAL],
    ["자격 심사 → 62편", "길이·언어 등 13개 조건\n채널 47개로 분산", TEAL],
    ["후보 풀 해시 동결", "62편 목록 자체를 해시\n이후 추가·제외 불가", BLUE],
    ["해시 순서로 2편 선정", "고정 문자열 + 영상 ID를\n해시해 정렬 → 앞에서 2편", BLUE],
  ];
  steps.forEach((st, i) => {
    const x = 0.6 + i * 2.47;
    card(s, x, 1.7, 2.3, 2.0); tab(s, x, 1.7, 2.0, st[2]);
    s.addText(`${i + 1}`, { x: x + 0.2, y: 1.82, w: 0.4, h: 0.3, fontSize: 12,
      bold: true, color: st[2], fontFace: MONO, margin: 0 });
    s.addText(st[0], { x: x + 0.2, y: 2.14, w: 1.95, h: 0.6, fontSize: 12.5, bold: true,
      color: NAVY, fontFace: HF, lineSpacingMultiple: 1.1, margin: 0 });
    s.addText(st[1], { x: x + 0.2, y: 2.78, w: 1.95, h: 0.85, fontSize: 10.5,
      color: MUTED, fontFace: BF, lineSpacingMultiple: 1.15, margin: 0 });
    if (i < 4) s.addText("→", { x: x + 2.3, y: 2.5, w: 0.2, h: 0.4, fontSize: 14,
      color: LINE, align: "center", fontFace: BF, margin: 0 });
  });
  card(s, 0.6, 4.0, 12.15, 1.15, "EEF7F6"); tab(s, 0.6, 4.0, 1.15, TEAL);
  s.addText([
    { text: "핵심   ", options: { bold: true, color: TEAL, fontFace: HF } },
    { text: "\"2편을 먼저 고르고 규칙을 나중에 적는\" 순서를 원천적으로 막았습니다. 후보 풀을 먼저 해시로 얼린 뒤에 선정 계산을 돌리기 때문에, 결과가 마음에 안 들어도 표본을 바꿀 수 없습니다." },
  ], { x: 1.0, y: 4.0, w: 11.5, h: 1.15, fontSize: 12, color: INK, valign: "middle",
       fontFace: BF, lineSpacingMultiple: 1.2, margin: 0 });

  card(s, 0.6, 5.3, 12.15, 1.05);
  s.addText([
    { text: "교체 규칙도 미리 못박았습니다.   ", options: { bold: true, color: NAVY, fontFace: HF } },
    { text: "허용 사유는 기술적 실패·권리 문제·자동 품질검사 실패뿐입니다. 실제로 \"사건이 적어 보인다\"는 이유로 한 편을 빼려 했지만 금지 목록 1번이라 " },
    { text: "1건으로 기록하고 8편을 유지", options: { bold: true } },
    { text: "했습니다." },
  ], { x: 1.0, y: 5.3, w: 11.5, h: 1.05, fontSize: 11.5, color: INK, valign: "middle",
       fontFace: BF, lineSpacingMultiple: 1.15, margin: 0 });
}

/* ─── 6 사람 정답 ─── */
{
  const s = content("사람 정답 68건 — 눈으로만 보고 작성, 차단은 도구가", "방법");
  card(s, 0.6, 1.62, 5.95, 2.35);
  s.addText("보이는 것 / 막는 것", { x: 0.95, y: 1.75, w: 5.3, h: 0.3, fontSize: 12.5,
    bold: true, color: NAVY, fontFace: HF, margin: 0 });
  mono(s, 0.95, 2.12, 5.4, 1.7,
    "보임   프레임 이미지 · 구간 번호 · 시각\n" +
    "       무음 영상 재생\n\n" +
    "막힘   AI 캡션 · 음성인식 자막\n" +
    "       검색 결과 · 점수 · 순위\n" +
    "       M8 보고서 · 예비 실행 수치", 11);
  card(s, 6.8, 1.62, 5.95, 2.35);
  s.addText("어떻게 막았나", { x: 7.15, y: 1.75, w: 5.3, h: 0.3, fontSize: 12.5,
    bold: true, color: NAVY, fontFace: HF, margin: 0 });
  s.addText("관행이 아니라 코드로 막았습니다. 구간 파일에서 허용 항목(번호·시작·끝·대표 프레임)만 통과시키는 필터를 거치게 하고, 작성 도구가 그 필터 밖 필드를 아예 메모리에 올리지 못하게 했습니다. 작성이 끝난 뒤 산출물 559개 파일·3,485조각을 대조해 유출 0건을 확인했습니다.",
    { x: 7.15, y: 2.1, w: 5.3, h: 1.75, fontSize: 11.5, color: INK, valign: "top",
      fontFace: BF, lineSpacingMultiple: 1.18, margin: 0 });

  card(s, 0.6, 4.15, 12.15, 1.3);
  s.addText("작성 결과", { x: 0.95, y: 4.26, w: 5, h: 0.3, fontSize: 12.5, bold: true,
    color: NAVY, fontFace: HF, margin: 0 });
  mono(s, 0.95, 4.6, 11.5, 0.75,
    "영상 8편 · 사건 68건 · 판단 불가 0건 · 구간 겹침 0건 · 검증 4종 전부 통과\n" +
    "클릭 2회로 범위를 잡고 한 줄만 적는 전용 화면을 만들어, 2,075구간을 손으로 타이핑하지 않게 했습니다", 11);

  card(s, 0.6, 5.6, 12.15, 0.95, "EEF4F8"); tab(s, 0.6, 5.6, 0.95, BLUE);
  s.addText([
    { text: "동결 후 수정 시도는 차단됩니다.   ", options: { bold: true, color: BLUE, fontFace: HF } },
    { text: "정답 파일을 고치면 해시가 달라져 채점기가 \"동결 이후 변경됨\"으로 실행을 거부합니다. 실제로 한 줄을 넣어 거부되는 것을 확인했습니다." },
  ], { x: 1.0, y: 5.6, w: 11.5, h: 0.95, fontSize: 11.5, color: INK, valign: "middle",
       fontFace: BF, margin: 0 });
}

/* ─── 7 실패 원인 ─── */
{
  const s = content("왜 미달인가 — 사건을 자르는 크기가 사람 기준과 다릅니다", "원인");
  card(s, 0.6, 1.62, 5.95, 2.15, "FBEEEC"); tab(s, 0.6, 1.62, 2.15, RED);
  s.addText("① 짧은 사건이 사라진다", { x: 0.95, y: 1.74, w: 5.3, h: 0.32,
    fontSize: 13, bold: true, color: RED, fontFace: HF, margin: 0 });
  mono(s, 0.95, 2.12, 5.4, 0.75,
    "못 찾은 정답 사건   22 / 68\n" +
    "그 길이 중앙값       6구간(30초)\n" +
    "찾은 사건 중앙값    24구간(120초)", 11);
  s.addText("사라진 것: 인트로 · 출근길 · 퇴근 · 아웃트로 · 이동 — 짧은 전환 장면이 조직적으로 빠집니다.",
    { x: 0.95, y: 2.95, w: 5.4, h: 0.7, fontSize: 11, color: INK, fontFace: BF,
      lineSpacingMultiple: 1.15, margin: 0 });

  card(s, 6.8, 1.62, 5.95, 2.15, "FBEEEC"); tab(s, 6.8, 1.62, 2.15, RED);
  s.addText("② 긴 사건이 쪼개진다", { x: 7.15, y: 1.74, w: 5.3, h: 0.32,
    fontSize: 13, bold: true, color: RED, fontFace: HF, margin: 0 });
  mono(s, 7.15, 2.12, 5.4, 0.75,
    "생성한 사건            93건\n" +
    "정답과 짝이 안 맞는 것  47건 (51%)\n" +
    "한 정답에 몰린 조각     최대 7건", 11);
  s.addText("예: 105구간짜리 '등산' 하나에 코스 설명·버스 안내·대피소 도착이 각각 별개 사건으로 붙습니다.",
    { x: 7.15, y: 2.95, w: 5.4, h: 0.7, fontSize: 11, color: INK, fontFace: BF,
      lineSpacingMultiple: 1.15, margin: 0 });

  card(s, 0.6, 3.95, 12.15, 1.15, "EEF4F8"); tab(s, 0.6, 3.95, 1.15, BLUE);
  s.addText([
    { text: "이 둘은 같은 원인의 양쪽입니다.   ", options: { bold: true, color: BLUE, fontFace: HF } },
    { text: "\"어느 단위를 하나의 사건으로 볼지\"가 안 맞으면, 어떤 영상에서는 덜 뽑고 어떤 영상에서는 과하게 쪼갭니다. 같은 파이프라인에서 두 현상이 동시에 나온 것이 그 증거입니다." },
  ], { x: 1.0, y: 3.95, w: 11.5, h: 1.15, fontSize: 12, color: INK, valign: "middle",
       fontFace: BF, lineSpacingMultiple: 1.2, margin: 0 });

  card(s, 0.6, 5.25, 12.15, 1.2);
  s.addText("부수적으로 확인된 것", { x: 0.95, y: 5.36, w: 5, h: 0.3, fontSize: 12.5,
    bold: true, color: NAVY, fontFace: HF, margin: 0 });
  mono(s, 0.95, 5.7, 11.5, 0.65,
    "· 후보가 검증에서 거부된 11건 중 7건이 '못 찾은 정답'과 같은 시간대였습니다 (인과 증명은 아님)\n" +
    "· 한 영상은 앞 절반의 후보가 전부 거부되고 재생성도 실패해 그 구간이 비었습니다", 11);
}

/* ─── 8 개선 시도 ─── */
{
  const s = content("개선 2회 시도 — 필요한 수준까지 수렴시키지 못했습니다", "개선");
  s.addText("아래 수치는 이미 결과를 본 8편에서 재실행한 개발용 점수입니다. 성능 검증(확증)이 아닙니다.",
    { x: 0.6, y: 1.5, w: 12.15, h: 0.3, fontSize: 11, color: MUTED, italic: true,
      fontFace: BF, margin: 0 });
  card(s, 0.6, 1.9, 12.15, 2.3);
  mono(s, 0.9, 2.02, 11.6, 2.05,
    "지표                        공식(기준선)    1차 개선    2차 개선     바람직\n" +
    "─────────────────────────────────────────────────────────────────────────\n" +
    "못 찾은 정답 사건 (68건 중)         22          10          10        낮을수록\n" +
    "생성 사건 수                       93         219         134        비슷하게\n" +
    "정답과 안 맞는 생성 사건           47         161          76        낮을수록\n" +
    "시간 정합 (중앙값)             0.3311      0.3892      0.4498        높을수록\n" +
    "쪼갬 정도 (최댓값)               7.00       16.00       13.00        낮을수록\n" +
    "새로 생긴 치명적 실패               —          1편         1편        0이어야", 11.5);

  card(s, 0.6, 4.4, 5.95, 1.05, "EEF7F6"); tab(s, 0.6, 4.4, 1.05, TEAL);
  s.addText([
    { text: "된 것   ", options: { bold: true, color: TEAL, fontFace: HF } },
    { text: "짧은 사건 회수(22→10)와 시간 정합(0.33→0.45)은 확실히 좋아졌습니다." },
  ], { x: 0.95, y: 4.4, w: 5.4, h: 1.05, fontSize: 11.5, color: INK, valign: "middle",
       fontFace: BF, lineSpacingMultiple: 1.15, margin: 0 });
  card(s, 6.8, 4.4, 5.95, 1.05, "FBEEEC"); tab(s, 6.8, 4.4, 1.05, RED);
  s.addText([
    { text: "안 된 것   ", options: { bold: true, color: RED, fontFace: HF } },
    { text: "쪼갬이 기준선보다 나빠졌고(7.00→13.00), 같은 문장 반복이라는 새 실패가 생겼습니다. 원래 정상이던 영상까지 나빠진 회귀도 있습니다." },
  ], { x: 7.15, y: 4.4, w: 5.4, h: 1.05, fontSize: 11.5, color: INK, valign: "middle",
       fontFace: BF, lineSpacingMultiple: 1.15, margin: 0 });

  card(s, 0.6, 5.65, 12.15, 1.0, "FFF8E7"); tab(s, 0.6, 5.65, 1.0, AMBER);
  s.addText([
    { text: "합격 기준을 실행 전에 못박아 뒀습니다.   ", options: { bold: true, color: AMBER, fontFace: HF } },
    { text: "6개 조건 중 2개만 통과 → 개발 반복 상한(2회) 도달로 중단했습니다. 기준을 결과에 맞춰 고치지 않았습니다." },
  ], { x: 1.0, y: 5.65, w: 11.5, h: 1.0, fontSize: 11.5, color: INK, valign: "middle",
       fontFace: BF, margin: 0 });
}

/* ─── 9 막힌 부분 ─── */
{
  const s = content("막힌 부분 — 5가지", "현안");
  const blocks = [
    ["M8 품질이 기준 미달", RED,
     "세 관문 모두 미달. 개선 2회로도 기준선을 넘지 못했고, 2차에서는 원래 정상이던 영상이 나빠지는 회귀가 관찰됐습니다. 지금 상태로는 \"보고서를 자동으로 쓴다\"를 성능으로 주장할 수 없습니다."],
    ["사건 단위 정의 자체의 한계", RED,
     "긴 활동 안의 세부 단계를 표현할 자리가 현재 출력 형식에 없습니다. 모델이 그걸 적으려면 별개 사건으로 만들 수밖에 없습니다. 근본 해결은 출력 구조 2층화인데, 채점·후속 문서 생성까지 연쇄 변경이라 이번엔 보류했습니다."],
    ["판정 표본을 다 썼음", AMBER,
     "8편은 결과를 본 순간 소진됐습니다. 고친 버전을 같은 8편으로 다시 재서 \"좋아졌다\"고 말할 수 없어, 새 8편과 새 사람 정답이 필요합니다."],
    ["채점기 결함 1건 (기록만)", AMBER,
     "중간 청크가 빈 것을 \"생성이 끊겼다\"로 세는 구현이 문구보다 넓게 작동합니다. 과거 판정은 그대로 두고 다음 판정에만 적용하는 수정안을 문서로 남겼습니다."],
    ["M9(품질 채점)은 대기", BLUE,
     "M9는 코드가 test 자료를 직접 열기 때문에 실행 자체가 되돌릴 수 없는 접촉입니다. M8이 미달인 상태에서 열 것인지가 결정 사항입니다."],
  ];
  let y = 1.62;
  blocks.forEach((b) => {
    const h = b[2].length > 110 ? 1.12 : 0.9;
    card(s, 0.6, y, 12.15, h); tab(s, 0.6, y, h, b[1]);
    s.addText(b[0], { x: 0.95, y: y + 0.1, w: 3.4, h: 0.4, fontSize: 12.5, bold: true,
      color: b[1], fontFace: HF, margin: 0 });
    s.addText(b[2], { x: 4.4, y: y + 0.08, w: 7.9, h: h - 0.16, fontSize: 11.5,
      color: INK, fontFace: BF, lineSpacingMultiple: 1.15, margin: 0 });
    y += h + 0.12;
  });
}

/* ─── 10 말할 수 있는 것 / 없는 것 ─── */
{
  const s = content("지금 말할 수 있는 것과 없는 것", "경계");
  card(s, 0.6, 1.62, 5.95, 2.55, "EEF7F6"); tab(s, 0.6, 1.62, 2.55, TEAL);
  s.addText("말할 수 있다", { x: 0.95, y: 1.75, w: 5.3, h: 0.35, fontSize: 14,
    bold: true, color: TEAL, fontFace: HF, margin: 0 });
  s.addText([
    "· 검색(M1~M7)은 확정 구성으로 평가가 끝났습니다",
    "· M8 평가를 규정대로 완료했습니다 (COMPLETE)",
    "· 미달의 원인을 사건 단위로 분해해 재현 가능한 파일로 남겼습니다",
    "· 표본·정답·기준·채점기를 결과 전에 동결했고 대조로 증명됩니다",
    "· 사람 정답 작성이 모델 출력을 보지 않았음을 도구로 강제했습니다",
  ].join("\n"), { x: 0.95, y: 2.2, w: 5.4, h: 1.95, fontSize: 11.5, color: INK,
    valign: "top", fontFace: BF, lineSpacingMultiple: 1.35, margin: 0 });

  card(s, 6.8, 1.62, 5.95, 2.55, "FBEEEC"); tab(s, 6.8, 1.62, 2.55, RED);
  s.addText("말할 수 없다", { x: 7.15, y: 1.75, w: 5.3, h: 0.35, fontSize: 14,
    bold: true, color: RED, fontFace: HF, margin: 0 });
  s.addText([
    "· \"보고서 자동 생성이 기준을 만족한다\" — 미달입니다",
    "· \"개선안이 효과가 있었다\" — 소진된 표본의 개발 점수입니다",
    "· \"C1을 좁게 보면 통과다\" — 나머지 두 관문이 미달입니다",
    "· \"표본이 한국어 영상 전체를 대표한다\" — 8편입니다",
    "· M9 품질(근거 충실도)에 대한 어떤 수치도 아직 없습니다",
  ].join("\n"), { x: 7.15, y: 2.2, w: 5.4, h: 1.95, fontSize: 11.5, color: INK,
    valign: "top", fontFace: BF, lineSpacingMultiple: 1.35, margin: 0 });

  card(s, 0.6, 4.45, 12.15, 1.15, "EEF4F8"); tab(s, 0.6, 4.45, 1.15, BLUE);
  s.addText([
    { text: "이 구분이 이번 주의 실제 산출물입니다.   ", options: { bold: true, color: BLUE, fontFace: HF } },
    { text: "미달이라는 결과보다, 미달을 미달이라고 말할 수 있는 상태를 만든 것이 남습니다. 기준을 결과에 맞춰 옮겼다면 이 구분선 자체가 없어집니다." },
  ], { x: 1.0, y: 4.45, w: 11.5, h: 1.15, fontSize: 12, color: INK, valign: "middle",
       fontFace: BF, lineSpacingMultiple: 1.2, margin: 0 });

  card(s, 0.6, 5.85, 12.15, 0.85);
  s.addText([
    { text: "근거 위치   ", options: { bold: true, color: NAVY, fontFace: HF } },
    { text: "판정 결과 · 실패 분해 · 개선 2회 기록 · 관문 기준 · 동결 해시 — 전부 docs/finalization/ 에 파일로 있습니다", options: { color: INK } },
  ], { x: 1.0, y: 5.85, w: 11.5, h: 0.85, fontSize: 11, valign: "middle",
       fontFace: BF, margin: 0 });
}

/* ─── 11 향후 추진 일정 ─── */
{
  const s = content("향후 추진 일정", "계획");
  card(s, 0.6, 1.55, 12.15, 1.25, "FFF8E7"); tab(s, 0.6, 1.55, 1.25, AMBER);
  s.addText([
    { text: "결정됨 (2026-08-28)   ", options: { bold: true, color: AMBER, fontFace: HF } },
    { text: "①  M8 acceptance FAIL을 최종 결과로 확정 — 추가 redesign 종료    " },
    { text: "③  후속 가설(출력 구조 2층화 등)은 향후과제로 이관    " },
    { text: "②  M9는 HOLD — test 개방 조건이 충족되지 않았습니다" },
  ], { x: 1.0, y: 1.55, w: 11.5, h: 1.25, fontSize: 12, color: INK, valign: "middle",
       fontFace: BF, lineSpacingMultiple: 1.25, margin: 0 });

  const plan = [
    ["8/29 ~ 8/30", "종결 문서 확정", "M8 종결 기록 · 한계·향후과제 반영 · 최종 보고서 문구 고정", TEAL],
    ["9/1 주", "최종 보고서 작성", "M1~M7 결과 + M8 실패와 원인. 기준을 움직이지 않았다는 근거 정리", TEAL],
    ["9/2 주", "산출물·시연 점검", "검색 시연 시나리오 · 문서 지도 · 재현 절차 확인", TEAL],
    ["9/3 주", "발표 준비", "결과·한계·향후과제 발표본 확정. M9는 조건 충족 전까지 미실행", TEAL],
    ["향후과제", "이번 범위에서 제외", "출력 구조 2층화 · 선택적 고재현율 추출 · 새 8편 확증 · test 39→72 확장", MUTED],
  ];
  let y = 2.95;
  plan.forEach((r) => {
    card(s, 0.6, y, 12.15, 0.68); tab(s, 0.6, y, 0.68, r[3]);
    s.addText(r[0], { x: 0.95, y, w: 1.85, h: 0.68, fontSize: 11.5, bold: true,
      color: r[3] === MUTED ? MUTED : NAVY, valign: "middle", fontFace: MONO, margin: 0 });
    s.addText(r[1], { x: 2.9, y, w: 3.1, h: 0.68, fontSize: 12, bold: true, color: NAVY,
      valign: "middle", fontFace: HF, margin: 0 });
    s.addText(r[2], { x: 6.1, y, w: 6.4, h: 0.68, fontSize: 11, color: INK,
      valign: "middle", fontFace: BF, margin: 0 });
    y += 0.75;
  });
  s.addText("M9를 열려면 (a) FAIL 상태 개방 여부 결정 (b) 합격 기준·해석 규칙 동결이 선행합니다 — 그 자체가 별도 승인 사건입니다.",
    { x: 0.6, y: 6.68, w: 12.15, h: 0.3, fontSize: 10.5, color: MUTED, fontFace: BF, margin: 0 });
}

/* ─── 12 마무리 ─── */
{
  const s = dark();
  s.addShape(p.shapes.RECTANGLE, { x: 0, y: 2.2, w: 0.9, h: 0.09, fill: { color: TEAL } });
  s.addText("이번 주 남은 것", { x: 0.9, y: 2.45, w: 11.5, h: 0.6, fontSize: 26,
    bold: true, color: WHITE, fontFace: HF, margin: 0 });
  s.addText([
    { text: "M8은 기준에 못 미쳤습니다. ", options: { color: WHITE, bold: true } },
    { text: "그러나 그 판정이 ", options: { color: "CFE0EC" } },
    { text: "결과를 보기 전에 정해진 기준으로 나왔다는 것", options: { color: TEAL, bold: true } },
    { text: "을 파일과 해시로 보일 수 있습니다. 실패를 실패로 기록할 수 있는 상태가 이번 주의 결과물입니다.", options: { color: "CFE0EC" } },
  ], { x: 0.95, y: 3.35, w: 11.4, h: 1.2, fontSize: 15, fontFace: BF,
       lineSpacingMultiple: 1.3, margin: 0 });
  mono(s, 0.95, 4.85, 11.4, 1.0,
    "동결 기록   표본 해시 · 정답 해시 · 관문 기준 · 채점기 함수 해시 · 테스트 결과\n" +
    "다음 결정   ① 한계로 확정   ② 미달 유지하고 M9 수행   ③ 범위 재정의", 12);
  footer(s, true);
}

p.writeFile({ fileName: path.join(__dirname, "주간진행발표_2026-08-28.pptx") })
  .then((f) => console.log("작성:", f));
