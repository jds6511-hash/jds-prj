"""[푸시 전 민감값 스캔 — working tree가 아니라 reachable history 전체]

**왜 스크립트로 만드는가.** 여태 즉석 셸 파이프라인으로 했다. 그러면 (1) 매번 패턴이
달라지고, (2) `grep -c ... || echo 0` 류의 출력 왜곡 버그를 다시 만들고
(2026-08-17 실측 2회), (3) "민감값 0건"이 **무엇을 기준으로 0건인지** 사후에 확인할
수 없다. 이 저장소는 공개이므로 그 기준이 기록돼야 한다.

**기본은 reachable history 전수다.** working tree만 보면 과거 커밋에 남은 값을 놓친다.
`--tree-only`로 작업 트리만 볼 수도 있지만, 푸시 판단에는 쓰지 마라.

**허용 예외.** 이미 공개된 커밋에 남아 있어 제거하려면 공개 이력 재작성이 필요한
항목은 `ALLOWLIST`에 blob SHA로 등록한다. 패턴을 지우는 게 아니라 **그 blob만**
면제하므로, 새로 들어오는 값은 계속 잡힌다.

사용:
    python scripts/scan_sensitive.py                  # master reachable 전수
    python scripts/scan_sensitive.py --ref HEAD       # 다른 ref
    python scripts/scan_sensitive.py --range origin/master..master   # 푸시분만
    python scripts/scan_sensitive.py --tree-only      # 작업 트리만 (푸시 판단 금지)

종료 코드: 0 = 적출 없음(허용분 제외), 1 = 적출 있음.
"""
import argparse, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# **이 파일에 실제 값을 적지 마라.** 처음 판본은 서버 계정·랩 호스트명을 리터럴
# 정규식으로 박았는데, 그러면 **스캐너 자신이 민감값을 평문으로 담은 추적 파일**이
# 된다(2026-08-18에 이 스캔이 자기 자신을 적출했다). 실제 값은 gitignore된
# SERVER_LOCAL.md의 자리표시자 표에서 **런타임에 읽는다.**
STRUCTURAL = {
    "ssh_private_key": r"-----BEGIN (?:OPENSSH|RSA|EC|DSA) PRIVATE KEY-----",
    "openai_key": r"\bsk-[A-Za-z0-9_-]{20,}",
    "hf_token": r"\bhf_[A-Za-z0-9]{20,}",
    "github_pat": r"\bgh[pousr]_[A-Za-z0-9]{20,}",
    "slack_token": r"\bxox[baprs]-[A-Za-z0-9-]{10,}",
    "aws_key": r"\bAKIA[0-9A-Z]{16}\b",
    "private_ipv4_kr_univ": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b:?\s*(?:22|2222)\b",
}
LOCAL_SECRETS = ROOT / "SERVER_LOCAL.md"


def load_local_patterns() -> tuple[dict, list[str]]:
    """SERVER_LOCAL.md의 `| \\`<NAME>\\` | 값 |` 표에서 실제 값을 읽어 패턴을 만든다.
    경계(\\b)를 붙이지 않는다 — 밑줄이 단어문자라 `<user>_gpu_server_usage`류가
    `\\b…\\b`에 걸리지 않고, 수동 grep보다 약해진다(2026-08-17 실측)."""
    if not LOCAL_SECRETS.is_file():
        return {}, [f"{LOCAL_SECRETS.name} 없음 — 서버 IP·계정·호스트명 패턴을 "
                    f"검사하지 못했다. 이 실행은 **부분 스캔**이다."]
    pats = {}
    for m in re.finditer(r"^\|\s*`<([A-Z_]+)>`\s*\|\s*(\S+)\s*\|",
                         LOCAL_SECRETS.read_text(encoding="utf-8"), re.M):
        name, val = m.group(1), m.group(2)
        if len(val) >= 4:
            pats[f"local:{name}"] = re.escape(val)
            # 끝자리 숫자를 뗀 접두도 잡는다. 정확값만 보면 호스트명에서 숫자를 뺀
            # **기관·랩 이름 변형**(파일명·식별자에 섞인 형태)을 놓친다 —
            # 실제로 그 형태가 과거 커밋에 남아 있었다(ALLOWLIST 참조).
            stem = re.sub(r"\d+$", "", val)
            if stem != val and len(stem) >= 4:
                pats[f"local:{name}_stem"] = re.escape(stem)
    return pats, ([] if pats else
                  [f"{LOCAL_SECRETS.name}에서 자리표시자 표를 못 읽었다 — 부분 스캔이다."])

# 공개 이력 재작성 없이는 제거 불가한 기존 항목. 신규 유입은 계속 잡힌다.
ALLOWLIST = {
    # docs/작업현황_2026-08-04.md:132 — 로컬 메모리 **파일명**을 가리키는 한 줄.
    # IP·계정·자격증명이 아니고, 랩 이름이 파일명 안에 섞인 형태다(값 자체는 여기
    # 적지 않는다 — 적으면 이 파일이 다시 적출된다). 423889b·5cb1e9c에 이미 공개돼
    # 있고, 제거하려면 이번 세션 이전부터 공개된 커밋을 재작성해야 한다.
    # 2026-08-17 사용자 판단: 유지.
    "1da59d8f6e3b8a9888e3347d6960cb8ac902128d": "메모리 파일명 참조 (작업현황 08-04:132)",
}

_LOCAL, WARNINGS = load_local_patterns()
PATTERNS = {**STRUCTURAL, **_LOCAL}
RX = {k: re.compile(v.encode()) for k, v in PATTERNS.items()}


def _run_text(cmd, stdin: str | None = None) -> str:
    """UTF-8 고정. Windows 기본 인코딩(cp949)으로 두면 한글 경로에서
    UnicodeDecodeError가 **리더 스레드 안에서 삼켜지고** stdout이 빈 문자열로
    돌아온다 — 스캔이 'blob 0개, 적출 0건'으로 거짓 통과한다(2026-08-17 실측)."""
    r = subprocess.run(cmd, cwd=ROOT, input=stdin, capture_output=True,
                       encoding="utf-8", errors="replace")
    return r.stdout


def blobs(ref: str, rng: str | None):
    """대상 ref/range에서 reachable한 blob의 (sha, path)."""
    rev = ["git", "rev-list", "--objects"] + ([rng] if rng else [ref])
    objs = _run_text(rev)
    chk = _run_text(
        ["git", "cat-file", "--batch-check=%(objecttype) %(objectname) %(rest)"], objs)
    for line in chk.splitlines():
        f = line.split(" ", 2)
        if f[0] == "blob":
            yield f[1], (f[2] if len(f) > 2 else "")


def scan_bytes(data: bytes) -> list[str]:
    return [k for k, rx in RX.items() if rx.search(data)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="master")
    ap.add_argument("--range", dest="rng", default=None,
                    help="예: origin/master..master — 푸시될 커밋만")
    ap.add_argument("--tree-only", action="store_true",
                    help="작업 트리만. **푸시 판단에 쓰지 마라**")
    a = ap.parse_args()

    hits, n = [], 0
    if a.tree_only:
        print("작업 트리만 스캔 — 푸시 판단 근거로 쓰지 마라", file=sys.stderr)
        files = _run_text(["git", "ls-files"]).split()
        for rel in files:
            p = ROOT / rel
            if not p.is_file():
                continue
            n += 1
            k = scan_bytes(p.read_bytes())
            if k:
                hits.append(("(tree)", rel, k))
    else:
        for sha, path in blobs(a.ref, a.rng):
            n += 1
            data = subprocess.run(["git", "cat-file", "blob", sha], cwd=ROOT,
                                  capture_output=True).stdout
            k = scan_bytes(data)
            if k:
                hits.append((sha, path, k))

    allowed = [h for h in hits if h[0] in ALLOWLIST]
    blocking = [h for h in hits if h[0] not in ALLOWLIST]

    for w in WARNINGS:
        print("경고:", w, file=sys.stderr)
    scope = ("작업 트리" if a.tree_only else
             f"range {a.rng}" if a.rng else f"ref {a.ref} reachable")
    print(f"스캔 대상: {scope} · blob {n}개 · 패턴 {len(PATTERNS)}개"
          f"{' (부분 스캔)' if WARNINGS else ''}")
    for sha, path, k in allowed:
        print(f"  허용 {sha[:8]} {path} {k} — {ALLOWLIST[sha]}")
    for sha, path, k in blocking:
        print(f"  적출 {sha[:8]} {path} {k}")
    print(f"결과: 적출 {len(blocking)}건 · 허용 {len(allowed)}건")
    # 빈 스캔을 통과로 읽으면 안 된다. range 스캔은 정상적으로 0일 수 있지만
    # ref 전수/트리 스캔이 0이면 파이프라인이 깨진 것이다(위 인코딩 사고).
    if n == 0 and not a.rng:
        print("스캔 대상 blob이 0개다 — 스캔이 실제로 수행되지 않았다. 통과로 읽지 마라.",
              file=sys.stderr)
        return 2
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
