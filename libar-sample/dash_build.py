# -*- coding: utf-8 -*-
"""사서 PC용 점검 대시보드 생성기 — 서버 0원 원칙 그대로.

드라이브 수신함에서 내려받은 libar_report_*.zip 폴더를 읽어
①SQLite(libar_dash.sqlite) 적재 ②자립형 HTML 대시보드(libar_dash.html) 생성.

사용:  py -3.12 dash_build.py <리포트 zip 폴더> [--out 출력폴더]
검증:  py -3.12 dash_build.py --selfcheck <260724 리포트 폴더>
       (07-25 수기 전수 분석과 동일해야 함: 유니크 사진 10·권 254·플래그 12)

스키마 두 세대를 모두 읽는다: report.json(단일 사진) / summary.json(사진 점검 묶음).
같은 사진의 중복 내보내기(내용 동일 zip)는 권 시퀀스 지문으로 제거 — 부풀림 방지.
"""
import argparse, html, json, os, sqlite3, sys, zipfile
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')


def iter_photos(zip_path):
    """zip 안의 (사진라벨, 일시, 기기, books[]) — 스키마 두 세대 공통화."""
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if not name.endswith('.json'):
                continue
            d = json.loads(z.read(name).decode('utf-8'))
            if 'books' in d:                       # report.json: 사진 1장
                yield 'single', d.get('date', ''), d.get('device', ''), d['books']
            else:                                  # summary.json: 사진 여러 장
                for it in d.get('items', []):
                    yield it.get('file', '?'), it.get('time') or d.get('date', ''), \
                          d.get('device', ''), it.get('books', [])


def load(folder, db_path):
    con = sqlite3.connect(db_path)
    con.executescript("""
      DROP TABLE IF EXISTS books; DROP TABLE IF EXISTS photos;
      CREATE TABLE photos(id INTEGER PRIMARY KEY, zip TEXT, photo TEXT, date TEXT,
                          device TEXT, n INTEGER);
      CREATE TABLE books(photo_id INTEGER REFERENCES photos(id), pos INTEGER,
                         call TEXT, title TEXT, mis INTEGER, resolved INTEGER,
                         band INTEGER, how TEXT);
    """)
    seen, dup = set(), 0
    zips = sorted(p for p in os.listdir(folder) if p.startswith('libar_report') and p.endswith('.zip'))
    for zp in zips:
        for photo, date, device, books in iter_photos(os.path.join(folder, zp)):
            fp = tuple(b.get('call') for b in books)       # 권 시퀀스 지문 = 같은 사진 판별
            if fp in seen:
                dup += 1
                continue
            seen.add(fp)
            cur = con.execute("INSERT INTO photos(zip,photo,date,device,n) VALUES(?,?,?,?,?)",
                              (zp, photo, date, device, len(books)))
            con.executemany(
                "INSERT INTO books VALUES(?,?,?,?,?,?,?,?)",
                [(cur.lastrowid, i, b.get('call'), b.get('title'),
                  1 if b.get('mis') else 0, 1 if b.get('resolved') else 0,
                  b.get('band'), b.get('how')) for i, b in enumerate(books)])
    con.commit()
    return con, len(zips), dup


def hundred(call):
    """청구기호 → KDC 백단위 구간(000~900). 파싱 불가는 '기타'."""
    try:
        return f"{int(float(call.split('-')[0].lstrip('가-힣A-Z')) // 100) * 100:03d}"
    except (ValueError, AttributeError, IndexError):
        return '기타'


def build_html(con, out_path, n_zips, n_dup):
    q = lambda sql, *a: con.execute(sql, a).fetchall()
    n_photos, n_books = q("SELECT COUNT(*), COALESCE(SUM(n),0) FROM photos")[0]
    n_mis, n_done = q("SELECT COALESCE(SUM(mis),0), COALESCE(SUM(resolved),0) FROM books")[0]
    days = q("SELECT substr(date,1,10) d, COUNT(*), SUM(n), SUM((SELECT SUM(mis) FROM books WHERE photo_id=p.id)) "
             "FROM photos p GROUP BY d ORDER BY d")
    by_sec = defaultdict(lambda: [0, 0])
    for call, mis in q("SELECT call, mis FROM books WHERE call IS NOT NULL"):
        s = by_sec[hundred(call)]
        s[0] += 1
        s[1] += mis
    mis_rows = q("SELECT substr(p.date,1,10), b.call, b.title, b.resolved FROM books b "
                 "JOIN photos p ON p.id=b.photo_id WHERE b.mis=1 ORDER BY p.date DESC")
    sessions = q("SELECT substr(date,1,16), zip, photo, n, "
                 "(SELECT SUM(mis) FROM books WHERE photo_id=p.id) FROM photos p ORDER BY date DESC")

    e = html.escape
    def bar_rows(items, vmax):
        return ''.join(
            f"<tr><td>{e(k)}</td><td class='bar'><div style='width:{v / vmax * 100:.0f}%'></div></td>"
            f"<td class='num'>{v}</td><td class='num red'>{m or ''}</td></tr>"
            for k, v, m in items)

    secs = sorted(by_sec.items())
    sec_rows = bar_rows([(k, v[0], v[1]) for k, v in secs], max(v[0] for v in by_sec.values()) or 1)
    day_rows = bar_rows([(d, bn or 0, m or 0) for d, _, bn, m in days], max((bn or 0) for _, _, bn, _ in days) or 1)
    mis_html = ''.join(f"<tr><td>{e(d)}</td><td class='mono'>{e(c or '')}</td><td>{e(t or '')}</td>"
                       f"<td>{'✅' if r else '미조치'}</td></tr>" for d, c, t, r in mis_rows)
    ses_html = ''.join(f"<tr><td>{e(d.replace('T', ' '))}</td><td class='mono'>{e(z)}·{e(ph)}</td>"
                       f"<td class='num'>{n}</td><td class='num red'>{m or ''}</td></tr>"
                       for d, z, ph, n, m in sessions)

    page = f"""<!doctype html><html lang=ko><meta charset=utf-8>
<title>LibAR 점검 대시보드</title>
<style>
 body{{background:#141a14;color:#e8f0e6;font:14px/1.6 'Malgun Gothic',sans-serif;max-width:860px;margin:24px auto;padding:0 16px}}
 h1{{font-size:20px}} h2{{font-size:15px;margin:28px 0 8px;color:#9fb39c}}
 .kpi{{display:flex;gap:10px;flex-wrap:wrap}}
 .kpi div{{flex:1;min-width:120px;background:#1d241d;border:1px solid #2a332a;border-radius:12px;padding:12px;text-align:center}}
 .kpi b{{display:block;font-size:26px}} .kpi span{{font-size:12px;color:#9fb39c}}
 .kpi .red b{{color:#ff6b64}} .kpi .green b{{color:#4be277}}
 table{{width:100%;border-collapse:collapse}} td{{padding:4px 8px;border-bottom:1px solid #222b22;vertical-align:top}}
 td:first-child,td:last-child{{white-space:nowrap}}
 .bar{{width:45%}} .bar div{{background:#4be277;height:10px;border-radius:5px;min-width:2px}}
 .num{{text-align:right;white-space:nowrap}} .red{{color:#ff6b64}} .mono{{font-family:Consolas,monospace;font-size:12px}}
 footer{{margin:32px 0;color:#5a675a;font-size:12px}}
</style>
<h1>📚 LibAR 서가 점검 대시보드</h1>
<div class=kpi>
 <div class=green><b>{n_books:,}</b><span>확인 권수(연)</span></div>
 <div><b>{n_photos}</b><span>점검 사진</span></div>
 <div class=red><b>{n_mis}</b><span>오배열 플래그</span></div>
 <div class=green><b>{n_done}</b><span>조치 완료</span></div>
</div>
<h2>분류대별 점검량 · <span class=red>오배열</span></h2><table>{sec_rows}</table>
<h2>일자별 점검량 · <span class=red>오배열</span></h2><table>{day_rows}</table>
<h2>오배열 책 목록</h2>
<table><tr><td>일자</td><td>청구기호</td><td>서명</td><td>조치</td></tr>{mis_html or '<tr><td colspan=4>없음</td></tr>'}</table>
<h2>점검 세션 (최신순)</h2>
<table><tr><td>일시(UTC)</td><td>리포트</td><td class=num>권</td><td class=num>플래그</td></tr>{ses_html}</table>
<footer>리포트 zip {n_zips}개 적재 · 중복 내보내기 {n_dup}장 제거 · 생성기 dash_build.py — 전 과정 오프라인</footer>
</html>"""
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(page)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('--out', default=None, help='출력 폴더 (기본: 입력 폴더)')
    ap.add_argument('--selfcheck', action='store_true', help='260724 코퍼스 수기 분석과 대조')
    a = ap.parse_args()
    out = a.out or a.folder
    db = os.path.join(out, 'libar_dash.sqlite')
    con, n_zips, n_dup = load(a.folder, db)
    build_html(con, os.path.join(out, 'libar_dash.html'), n_zips, n_dup)
    n_photos, n_books = con.execute("SELECT COUNT(*), SUM(n) FROM photos").fetchone()
    n_mis = con.execute("SELECT SUM(mis) FROM books").fetchone()[0]
    print(f"zip {n_zips}개 → 유니크 사진 {n_photos}장(중복 {n_dup} 제거) · {n_books}권 · 플래그 {n_mis}건")
    print(f"→ {db}\n→ {os.path.join(out, 'libar_dash.html')}")
    if a.selfcheck:                                # 07-25 수기 전수 분석 = 정답지
        assert (n_photos, n_books, n_mis) == (10, 254, 12), f"수기 분석 불일치: {n_photos},{n_books},{n_mis}"
        print("SELFCHECK PASS — 수기 전수 분석(10장·254권·12건)과 일치")


if __name__ == '__main__':
    main()
