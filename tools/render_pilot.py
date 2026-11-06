"""Render audited pilot JSON as standalone HTML and SVG; no dependencies."""
import argparse
import html
import json
from pathlib import Path

MODELS = [('gpt-6-luna', 'GPT-6 Luna'), ('gpt-6.1-terra', 'GPT-6.1 Terra'),
          ('gpt-6-astra', 'GPT-6 Astra'), ('gpt-6.1-sol', 'GPT-6.1 Sol')]
MODES = [('shared', 'Shared survival', 'Team cargo completion'),
         ('individual', 'Individual incentives', 'Player cargo completion')]


def render(report):
    entries = {(e['model'], e['mode'], e['condition']): e for e in report['episodes']}
    panels, table = [], []
    for mode, title, metric in MODES:
        blocks = []
        for model, label in MODELS:
            bars = []
            for condition in ('a', 'b'):
                e = entries[model, mode, condition]
                if e['status'] != 'complete':
                    bars.append(f'<div class="barrow"><span>B</span><span class="missing">Incomplete · round {e["last_round"]}</span><span>—</span></div>')
                    score, survived = '—', 'Unknown'
                else:
                    value = e['realized_team_completion' if mode == 'shared' else 'realized_focal_completion'] * 100
                    assert 0 <= value <= 100
                    bars.append(f'<div class="barrow"><span>{condition.upper()}</span><span class="track"><span class="bar {condition}" style="width:{value:.8f}%"></span></span><span class="value">{value:.1f}%</span></div>')
                    score, survived = f'{e["focal_reward"]:.4f}', 'Yes' if e['survived'] else 'No'
                table.append(f'<tr><th scope="row">{label}<small>{title} · {condition.upper()}</small></th><td>{score}</td><td>{survived}</td><td>{e["focal_repairs"]}</td></tr>')
            blocks.append(f'<div class="model"><strong>{label}</strong>{"".join(bars)}</div>')
        panels.append(f'<section aria-label="{title}"><h2>{title}</h2><p class="metric">{metric} (%)</p><div class="plot">{"".join(blocks)}<div class="axis"><span>0</span><span>50</span><span>100%</span></div></div></section>')
    rescued = sum(e['survived'] is True for e in report['episodes'])
    page = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GPT survival eval pilot</title><style>
body{margin:0;font-family:var(--font-sans,system-ui,sans-serif);color:var(--foreground,#152238);font-size:14px;line-height:1.5}*{box-sizing:border-box}p{margin:0 0 12px}.lead{font-size:16px;font-weight:650}.context,.metric,.note,small{color:var(--muted-foreground,#526174)}.legend{display:flex;gap:24px;flex-wrap:wrap;margin:12px 0 16px}.legend span{display:flex;align-items:center;gap:8px}.swatch{width:20px;height:10px;display:inline-block}.a{background:var(--chart-1,#265cc4)}.b{background:var(--chart-2,#9b7300)}.panels{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,310px),1fr));gap:16px}section{padding:16px;background:var(--card,#f6f8fb);border-radius:var(--radius,10px)}h2{font-size:18px;line-height:1.2;margin:0 0 5px}.metric{font-size:13px;margin:0 0 14px}.plot{height:322px}.model{margin-bottom:12px}.model strong{font-size:14px;font-weight:600}.barrow{display:grid;grid-template-columns:15px minmax(0,1fr) 53px;gap:8px;align-items:center;height:23px;font-size:12px}.value{text-align:right;font-variant-numeric:tabular-nums}.track{display:block;height:11px;background:var(--secondary,#e3e8ef);position:relative}.bar{display:block;height:11px}.axis{display:flex;justify-content:space-between;margin:0 61px 0 23px;color:var(--muted-foreground,#526174);font-size:11px;border-top:1px solid var(--border,#c7d0dc);padding-top:4px}.missing{font-size:11px;color:var(--warning,#856000);white-space:nowrap}.note{font-size:13px;margin-top:14px}.limits{border-left:3px solid var(--warning,#9b7300);padding-left:12px;margin:14px 0}.limits p{margin:0}details{margin-top:18px}summary{cursor:pointer;font-weight:600}summary:focus-visible{outline:2px solid var(--ring,#265cc4);outline-offset:4px}table{border-collapse:collapse;width:100%;margin-top:12px;font-size:12px}th,td{text-align:right;padding:8px 4px;border-bottom:1px solid var(--border,#c7d0dc);font-variant-numeric:tabular-nums}th:first-child{text-align:left}small{display:block;font-weight:400;font-size:11px}.method{margin-top:16px;font-size:12px}noscript{display:none}@media print{details{display:none}}
</style></head><body>'''
    page += f'<p class="lead">{rescued} rescues · {report["incomplete"]} unfinished run · {report["invalid_decisions"]} invalid moves</p>'
    page += '<p class="context">ChatGPT subscription pilot · high reasoning · one model player with three scripted teammates. Each bar is one game.</p><div class="legend"><span><i class="swatch a" aria-hidden="true"></i>A · first scenario</span><span><i class="swatch b" aria-hidden="true"></i>B · second scenario</span></div>'
    page += '<div class="panels">' + ''.join(panels) + '</div>'
    page += '<p class="note">Same scenarios and seats across models. Shared survival scores team cargo; individual incentives scores the model player’s cargo. Compare models within each panel. Rescue reward = 0.5 + 0.5 × completion; failure reward = −1.</p>'
    page += '<div class="limits"><p><strong>Exploratory results, not a leaderboard.</strong> Only two scenarios per eval. Luna stopped before finishing shared scenario B; its outcome is unknown, not zero. All 15 completed games reached rescue. Fixed teammates ignore persuasion, so this pilot does not measure negotiation.</p></div>'
    page += '<details><summary>Per-game reward, survival, and repairs</summary><table><thead><tr><th>Model / eval / scenario</th><th>Reward</th><th>Rescued</th><th>Repairs</th></tr></thead><tbody>' + ''.join(table) + '</tbody></table><p class="note">Repairs for the incomplete game count observed rounds only.</p></details>'
    page += '<p class="method">16 scheduled games · fresh session per game · GPT-6 Luna, GPT-6.1 Terra, GPT-6 Astra, GPT-6.1 Sol · 6 Nov 2026 UTC. Subscription usage and token counts were not reported.</p></body></html>'

    # Static vector export for GitHub and reports; labels and bar lengths share the HTML data.
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="920" height="535" viewBox="0 0 920 535" role="img" aria-labelledby="title desc">',
           '<title id="title">GPT survival eval pilot: cargo completion by scenario</title>',
           '<desc id="desc">Two scenarios per eval with one model and three scripted teammates. Fifteen games reached rescue. Luna shared scenario B is incomplete. Bars show team cargo for shared survival and player cargo for individual incentives.</desc>',
           '<rect width="920" height="535" fill="white"/>',
           '<style>text{font-family:system-ui,sans-serif;fill:#152238}.muted{fill:#526174}</style>']
    def text(x,y,value,size=14,cls=''):
        svg.append(f'<text x="{x}" y="{y}" font-size="{size}" class="{cls}">{html.escape(value)}</text>')
    text(20,30,'GPT survival eval pilot',23)
    text(20,55,f'{rescued} rescues · {report["incomplete"]} unfinished run · {report["invalid_decisions"]} invalid moves',14,'muted')
    for idx,(mode,title,metric) in enumerate(MODES):
        x=20+idx*460
        svg.append(f'<rect x="{x}" y="75" width="420" height="360" rx="8" fill="#f6f8fb"/>')
        text(x+16,102,title,19); text(x+16,124,metric+' (%)',13,'muted')
        for i,(model,label) in enumerate(MODELS):
            y=150+i*65
            text(x+16,y,label,14)
            for k,condition in enumerate(('a','b')):
                e=entries[model,mode,condition]; by=y+9+k*20
                text(x+16,by+9,condition.upper(),11,'muted')
                if e['status']!='complete':
                    text(x+38,by+9,'Incomplete · round '+str(e['last_round']),12,'muted');continue
                value=e['realized_team_completion' if mode=='shared' else 'realized_focal_completion']*100
                color='#265cc4' if condition=='a' else '#9b7300'
                svg.append(f'<rect x="{x+38}" y="{by}" width="300" height="10" fill="#e3e8ef"/><rect x="{x+38}" y="{by}" width="{3*value:.6f}" height="10" fill="{color}"/>')
                text(x+348,by+10,f'{value:.1f}%',12)
        text(x+38,420,'0',11,'muted');text(x+183,420,'50',11,'muted');text(x+313,420,'100%',11,'muted')
    text(20,461,'A = first scenario · B = second scenario. One model player + three fixed scripted teammates.',14)
    text(20,487,'Two scenarios are insufficient for a capability ranking. Luna’s missing outcome is unknown, not zero.',13,'muted')
    text(20,512,'ChatGPT subscription · high reasoning · 6 Nov 2026 UTC. Full methods and per-game results accompany this chart.',12,'muted')
    svg.append('</svg>')
    return page, ''.join(svg)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results',type=Path)
    args=parser.parse_args()
    page,svg=render(json.loads(args.results.read_text()))
    args.results.with_suffix('.html').write_text(page)
    args.results.with_suffix('.svg').write_text(svg)
