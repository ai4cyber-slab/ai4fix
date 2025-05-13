import argparse, html, xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileStat:
    lines_tot: int = 0
    lines_cov: int = 0
    br_tot   : int = 0
    br_cov   : int = 0

def pct(cov, tot): return 0.0 if tot == 0 else round(100*cov/tot, 2)

def parse_cond(cond_attr, hit):
    """Return (covered_branches, total_branches) for one <line> element."""
    if not cond_attr or "(" not in cond_attr:
        return (1 if hit else 0), 1
    cov, tot = map(int, cond_attr.split("(")[1].split(")")[0].split("/"))
    return cov, tot

def line_fully_covered(ln_el):
    """fully covered only if every branch is hit."""
    hit   = int(ln_el.attrib["hits"]) > 0
    if not ln_el.attrib.get("branch") == "true":
        return hit
    cov, tot = parse_cond(ln_el.attrib.get("condition-coverage"), hit)
    return hit and cov == tot


def parse_report(path):
    totals = dict(lines=0, lines_cov=0, branches=0, branches_cov=0)
    hits   = defaultdict(dict)
    stats  = defaultdict(FileStat)

    root = ET.parse(path).getroot()
    for cls in root.findall(".//class"):
        fname = cls.attrib["filename"]
        st    = stats[fname]

        for ln_el in cls.findall(".//line"):
            ln    = int(ln_el.attrib["number"])
            hit   = int(ln_el.attrib["hits"]) > 0
            br    = ln_el.attrib.get("branch") == "true"
            full  = line_fully_covered(ln_el)

            # line counters
            totals['lines']  += 1
            st.lines_tot     += 1
            if full:
                totals['lines_cov'] += 1
                st.lines_cov        += 1
            hits[fname][ln] = full

            # branch counters (overall stats only)
            if br:
                cov, tot = parse_cond(ln_el.attrib.get("condition-coverage"), hit)
                totals['branches']     += tot
                totals['branches_cov'] += cov
                st.br_tot              += tot
                st.br_cov              += cov
        stats[fname] = st
    return totals, hits, stats

# ──────────────── diff helpers ─────────────
def changed_lines(pre_hits, post_hits):
    gain, lost = defaultdict(set), defaultdict(set)
    for f in set(pre_hits) | set(post_hits):
        pre, post = pre_hits.get(f, {}), post_hits.get(f, {})
        for ln in set(pre) | set(post):
            if pre.get(ln, False) != post.get(ln, False):
                (gain if post.get(ln, False) else lost)[f].add(ln)
    return gain, lost


def per_file_rows(pre_stats, post_stats, gain, lost):
    """Return rows only for files whose coverage changed."""
    changed_files = set(gain) | set(lost)

    rows = []
    for f in changed_files:
        a, b = pre_stats.get(f, FileStat()), post_stats.get(f, FileStat())
        lp, lq = pct(a.lines_cov, a.lines_tot), pct(b.lines_cov, b.lines_tot)
        ld = round(lq - lp, 2)

        bp = bq = bd = None
        if a.br_tot or b.br_tot:
            bp = pct(a.br_cov, a.br_tot) if a.br_tot else 0.0
            bq = pct(b.br_cov, b.br_tot) if b.br_tot else 0.0
            bd = round(bq - bp, 2)

        rows.append((f, lp, lq, ld, bp, bq, bd))

    # sort by biggest line-coverage delta, then branch delta
    return sorted(rows, key=lambda r: (r[3], (r[6] or 0)), reverse=True)



CSS = """
<style>
body{font-family:Segoe UI,Roboto,Arial,sans-serif;margin:1.4rem}
h1,h2,h3{margin-top:1.2em}
table{border-collapse:collapse;margin-bottom:1.6rem;font-size:0.9rem}
th,td{border:1px solid #ddd;padding:4px 8px;text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}
.code{border:1px solid #ddd;background:#fafafa;margin-bottom:2rem;overflow:auto}
.ln{color:#888;padding-right:8px;border-right:1px solid #ddd}
.covergain{background:#e6ffe6}
.mono{font-family:monospace;font-size:0.85rem;white-space:pre}
a{color:#0645ad;text-decoration:none}
a:hover{text-decoration:underline}
.deltaplus  { color: #006400; font-weight: bold; }
</style>
"""

E = lambda s: html.escape(s, quote=False)

def shorten(p, w=70):
    p=str(p)
    return p if len(p)<=w else p[:w//2-1]+"…"+p[-(w-w//2-2):]

def render_source(fname, gain, lost):
    try:
        lines=open(fname,encoding='utf-8',errors='ignore').read().splitlines()
    except FileNotFoundError:
        return f"<p><em>source unavailable – {E(fname)}</em></p>"
    html_lines=[]
    for i,l in enumerate(lines,1):
        cls="covergain" if i in gain else "" 
        html_lines.append(f'<span class="ln">{i:>4}</span>'
                          f'<span class="mono {cls}">{E(l)}</span>')
    return '<div class="code"><div class="mono">\n'+"\n".join(html_lines)+"\n</div></div>"

# HTML report
HEAD = "<!doctype html><html><head><meta charset=utf-8><title>Coverage diff</title>"+CSS+"</head><body>"
TAIL = "</body></html>"

def write_html(pre_tot, post_tot, rows, gain, lost, outfile):
    with open(outfile,"w",encoding="utf-8") as out:
        w=out.write
        w(HEAD); w('<a id="top"></a><h1>Coverage diff report</h1>')

        # overall table
        lp,lq = pct(pre_tot['lines_cov'],pre_tot['lines']), pct(post_tot['lines_cov'],post_tot['lines'])
        ld=round(lq-lp,2)
        br_avail = bool(pre_tot['branches'] or post_tot['branches'])
        w("<h2>Overall</h2><table><tr><th></th><th>Pre%</th><th>Post%</th><th>Δ</th></tr>")
        w(f"<tr><td>Lines</td><td>{lp:.2f}%</td><td>{lq:.2f}%</td><td>{ld:+.2f}</td></tr>")
        if br_avail:
            bp=pct(pre_tot['branches_cov'],pre_tot['branches'])
            bq=pct(post_tot['branches_cov'],post_tot['branches'])
            bd=round(bq-bp,2)
            w(f"<tr><td>Branches</td><td>{bp:.2f}%</td><td>{bq:.2f}%</td><td>{bd:+.2f}</td></tr>")
        else:
            w("<tr><td>Branches</td><td colspan=3>N/A</td></tr>")
        w("</table>")

        # per-file table
        w("<h2>Per-file coverage</h2><table>")
        w("<tr><th>File</th><th>Line&nbsp;pre%</th><th>Line&nbsp;post%</th><th>Δ</th>"
          "<th>Branch&nbsp;pre%</th><th>Branch&nbsp;post%</th><th>Δ</th></tr>")
        for idx,(f,lp,lq,ld,bp,bq,bd) in enumerate(rows):
            fid=f"file{idx}"
            bp_s, bq_s = (f"{bp:.2f}%" if bp is not None else "N/A",
                          f"{bq:.2f}%" if bq is not None else "N/A")
            bd_s = f"{bd:+.2f}" if bd is not None else "N/A"
            # choose classes based on delta sign
            ld_class = "deltaplus" if ld > 0 else ""
            bd_class = "deltaplus" if bd and bd > 0 else ""

            # wrap deltas in spans
            ld_span = f'<span class="{ld_class}">{ld:+.2f}</span>'
            bd_span = f'<span class="{bd_class}">{bd:+.2f}</span>' if bd is not None else "N/A"

            w(f'<tr><td><a href="#{fid}">{E(shorten(f))}</a></td>'
            f'<td>{lp:.2f}%</td><td>{lq:.2f}%</td><td>{ld_span}</td>'
            f'<td>{bp_s}</td><td>{bq_s}</td><td>{bd_span}</td></tr>')
        w("</table>")

        w("<p><span class='covergain'>&nbsp;&nbsp;</span> coverage increased</p>")

        # code blocks
        for idx,(f,_,_,_,_,_,_) in enumerate(rows):
            fid=f"file{idx}"
            w(f'<h3 id="{fid}">{E(f)}</h3>')
            w(render_source(f, gain.get(f,set()), lost.get(f,set())))
            w('<p style="text-align:right"><a href="#top">back ↑</a></p>')

        w(TAIL)



def generate_report(pre_path, post_path, out_path):
    pre_tot, pre_hits, pre_stats   = parse_report(pre_path)
    post_tot, post_hits, post_stats = parse_report(post_path)

    gain, lost = changed_lines(pre_hits, post_hits)
    rows = per_file_rows(pre_stats, post_stats, gain, lost)


    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    write_html(pre_tot, post_tot, rows, gain, lost, out_path)
    print("HTML diff written to", out_path)

if __name__ == "__main__":
    generate_report(None, None, None)
