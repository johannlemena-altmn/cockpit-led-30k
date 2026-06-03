# -*- coding: utf-8 -*-
import csv, statistics, re
from collections import defaultdict, Counter
from datetime import date

CSV="data/pixelcrm-LED-export_20260603.csv"
OUT="Dashboard_LED_MVP.html"

def num(s):
    if not s: return None
    s=s.strip().replace("\xa0","").replace(" ","").replace(",",".")
    try: return float(s)
    except: return None

rows=[]
with open(CSV, encoding="latin-1", newline="") as f:
    for d in csv.DictReader(f, delimiter=";"): rows.append(d)

QTE="Produit Qté"; SIG="Date signature devis"; NUM="Numéro de dossier"
PRIME="Prime CEE opération"; CUMAC="Cumac Opération"; SECT="Secteur d'activité"; RS="Raison Sociale"

doss=defaultdict(lambda:{"led":0,"signed":False,"prime":0,"cumac":0,"sect":"","sig":""})
for d in rows:
    k=d.get(NUM,"").strip()
    if not k: continue
    doss[k]["led"]+=num(d.get(QTE)) or 0
    doss[k]["prime"]+=num(d.get(PRIME)) or 0
    doss[k]["cumac"]+=num(d.get(CUMAC)) or 0
    if d.get(SIG,"").strip(): doss[k]["signed"]=True; doss[k]["sig"]=d.get(SIG).strip()
    if not doss[k]["sect"]: doss[k]["sect"]=(d.get(SECT,"") or "").strip()
D=list(doss.values())
signed=[x for x in D if x["signed"]]
led=[x["led"] for x in signed if x["led"]>0]

total_led_signed=int(sum(led))
n_doss=len(D); n_signed=len(signed)
mean_led=statistics.mean(led); med_led=statistics.median(led)
mn,mx=int(min(led)),int(max(led))
prime_tot=int(sum(x["prime"] for x in signed))
cumac_twhc=sum(x["cumac"] for x in signed)/1e9  # kWhc -> TWhc
objectif=30000
ratio=total_led_signed/objectif

# monthly
bym=defaultdict(float)
for x in signed:
    m=re.match(r"(\d{2})/(\d{2})/(\d{4})",x["sig"])
    if m and x["led"]>0 and 2025<=int(m.group(3))<=2026:
        bym[f"{m.group(3)}-{m.group(2)}"]+=x["led"]
months=[k for k in sorted(bym) if not (k=="2026-12") and bym[k]>=100]
mvals=[int(bym[k]) for k in months]

# histogram
buckets=[("1-9",1,9),("10-19",10,19),("20-29",20,29),("30-49",30,49),("50-99",50,99),("100+",100,10**9)]
hist=[]
for lab,a,b in buckets:
    hist.append((lab,sum(1 for v in led if a<=v<=b)))

# secteur
sec=Counter((x["sect"] or "(vide)") for x in signed).most_common(5)

# recent signed (proxy for least-likely-deposited)
recent=int(bym.get("2026-01",0)+bym.get("2026-02",0))

def bars_v(labels,vals,unit="",color="#2E6FB7",h=170,w=560):
    mx=max(vals) if vals else 1
    n=len(vals); bw=w/n*0.62; gap=w/n
    out=[f'<svg viewBox="0 0 {w} {h+38}" width="100%" style="max-width:100%">']
    for i,(l,v) in enumerate(zip(labels,vals)):
        bh=(v/mx)*h if mx else 0
        x=i*gap+(gap-bw)/2; y=h-bh
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3" fill="{color}"/>')
        out.append(f'<text x="{x+bw/2:.1f}" y="{y-4:.1f}" font-size="10" text-anchor="middle" fill="#1c2530">{v:,}</text>'.replace(","," "))
        out.append(f'<text x="{x+bw/2:.1f}" y="{h+14:.1f}" font-size="9.5" text-anchor="middle" fill="#5b6573">{l}</text>')
    out.append('</svg>')
    return "".join(out)

def bars_h(pairs,color="#E08600",w=560,rowh=26):
    mx=max(v for _,v in pairs) if pairs else 1
    h=len(pairs)*rowh+6; lblw=70; barw=w-lblw-70
    out=[f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:100%">']
    for i,(l,v) in enumerate(pairs):
        y=i*rowh+4; bw=(v/mx)*barw if mx else 0
        out.append(f'<text x="0" y="{y+15}" font-size="11" fill="#1c2530">{l}</text>')
        out.append(f'<rect x="{lblw}" y="{y+4}" width="{bw:.1f}" height="15" rx="3" fill="{color}"/>')
        out.append(f'<text x="{lblw+bw+6:.1f}" y="{y+15}" font-size="10.5" fill="#5b6573">{v:,}</text>'.replace(","," "))
    out.append('</svg>')
    return "".join(out)

mlabels=[m[2:] for m in months]  # YY-MM -> MM? keep YYYY-MM short
mlabels=[m.replace("2025-","").replace("2026-","") for m in months]
mlabels=[{"01":"jan","02":"fév","03":"mar","04":"avr","05":"mai","06":"juin","07":"juil","08":"aoû","09":"sep","10":"oct","11":"nov","12":"déc"}.get(x,x) for x in mlabels]
mlabels=[f"{lab}'{m[2:4]}" for lab,m in zip(mlabels,months)]

html=f"""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard LED — MVP</title>
<style>
:root{{--navy:#1F3A5F;--blue:#2E6FB7;--amber:#E08600;--green:#2E7D32;--red:#C0392B;--ink:#1c2530;--muted:#5b6573;--line:#dfe5ee;--soft:#eef3fb;--bg:#f6f8fc;}}
*{{box-sizing:border-box}}body{{font-family:-apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:var(--ink);margin:0;background:var(--bg);line-height:1.5}}
.wrap{{max-width:980px;margin:0 auto;padding:24px 26px 60px}}
.hero{{background:linear-gradient(135deg,var(--navy),#2b5180);color:#fff;border-radius:14px;padding:20px 24px}}
.hero .k{{font-size:11px;letter-spacing:.15em;text-transform:uppercase;opacity:.8}}
.hero h1{{margin:6px 0 2px;font-size:24px}}.hero .s{{opacity:.9;font-size:12.5px}}
.kpis{{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-top:16px}}
.kpi{{background:#fff;border:1px solid var(--line);border-radius:11px;padding:11px 12px;box-shadow:0 1px 3px rgba(20,30,50,.05)}}
.kpi b{{display:block;font-size:21px;line-height:1;color:var(--navy)}}.kpi span{{font-size:10.5px;color:var(--muted)}}
.kpi.hl{{background:var(--navy);border:none}}.kpi.hl b,.kpi.hl span{{color:#fff}}
.kpi.hl b{{color:#ffd79a}}
.punch{{background:#e7f5e9;border:1px solid #b6dfbd;border-left:5px solid var(--green);border-radius:11px;padding:13px 16px;margin:16px 0}}
.punch b{{color:var(--green)}}
.card{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:15px 17px;margin:13px 0;box-shadow:0 1px 3px rgba(20,30,50,.04)}}
h2{{font-size:14px;color:var(--navy);margin:0 0 4px}}
.sub{{font-size:11.5px;color:var(--muted);margin:0 0 10px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:13px}}
.warn{{background:#fff7ec;border:1px solid #f4d6a6;border-left:5px solid var(--amber);border-radius:11px;padding:13px 16px}}
.warn h2{{color:#9a5b00}}
ul{{margin:6px 0;padding-left:18px}}li{{margin:3px 0;font-size:13px}}
.tag{{display:inline-block;background:var(--soft);color:var(--blue);font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:20px;margin-right:5px}}
.foot{{margin-top:22px;font-size:11px;color:var(--muted);text-align:center}}
@media(max-width:760px){{.kpis{{grid-template-columns:repeat(2,1fr)}}.grid2{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">

<div class="hero">
  <div class="k">Énergie Responsable · Opération LED (BAT-EQ-127)</div>
  <h1>Dashboard LED — MVP (données réelles)</h1>
  <div class="s">Source : export Pixel CRM du {date.today().strftime('%d/%m/%Y')} · {len(rows):,} lignes · {n_doss:,} dossiers</div>
</div>

<div class="kpis">
  <div class="kpi hl"><b>{total_led_signed:,}</b><span>LED signées (cumulé)</span></div>
  <div class="kpi"><b>×{ratio:.1f}</b><span>vs objectif 30 000</span></div>
  <div class="kpi"><b>{n_signed:,}</b><span>dossiers signés</span></div>
  <div class="kpi"><b>{mean_led:.0f}</b><span>LED/dossier (moy.)</span></div>
  <div class="kpi"><b>{prime_tot/1e6:.1f} M€</b><span>prime CEE signée</span></div>
  <div class="kpi"><b>{cumac_twhc:.1f} TWhc</b><span>cumac signé</span></div>
</div>

<div class="punch">
  <b>Le stock n'est pas le problème.</b> Vous avez <b>{total_led_signed:,} LED déjà signées</b> — soit <b>~{ratio:.1f}× l'objectif mensuel de 30 000</b>.
  Rien que les signatures de jan.–fév. 2026 (~{recent:,} LED) couvrent déjà le mois. Le levier des 30 000, c'est donc le <b>débit de traitement</b> et la <b>pose</b>, pas la vente.
</div>

<div class="card">
  <h2>LED signées par mois</h2>
  <p class="sub">Dynamique du stock signé — le pic oct.–déc. 2025 = le backlog à écouler.</p>
  {bars_v(mlabels,mvals)}
</div>

<div class="grid2">
  <div class="card">
    <h2>Profondeur — LED par dossier</h2>
    <p class="sub">Médiane {med_led:.0f} · moyenne {mean_led:.0f} · min {mn} · max {mx}. Nb de dossiers signés par tranche :</p>
    {bars_h(hist, color="#2E6FB7")}
  </div>
  <div class="card">
    <h2>Secteur d'activité</h2>
    <p class="sub">Quasi exclusivement « Entrepôts » (cohérent fiche BAT-EQ-127).</p>
    {bars_h([(s[:16],n) for s,n in sec])}
  </div>
</div>

<div class="warn">
  <h2>⚠ Ce qu'il reste à brancher pour rendre le dashboard « activable chaque jour »</h2>
  <p class="sub" style="color:#9a5b00">Ce modèle d'export (« eq 127 pour liste ») ne contient pas tout. Pour la version finale il me faut 3 champs :</p>
  <ul>
    <li><span class="tag">manquant</span><b>Statut / N° de dépôt</b> → pour isoler « signé mais <u>non encore déposé</u> » (le vrai reste-à-faire) et bâtir le <b>funnel</b> Commercial → Technique → Contrôle → Valorisation.</li>
    <li><span class="tag">manquant</span><b>% de pose réelle</b> (ou date de pose) → pour piloter le fameux 60–75% et déclencher les <b>relances</b>.</li>
    <li><span class="tag">manquant</span><b>Responsable / pôle</b> → pour les <b>vues par pôle et par manager</b> (charge, débit, blocages par personne).</li>
  </ul>
  <p style="font-size:12.5px;margin:6px 0 0">→ On les récupère soit via un <b>2ᵉ modèle d'export</b> contenant statut+dépôt+pose, soit en <b>segmentant la recherche par statut</b> (je peux le faire). 15 min et le dashboard devient quotidien.</p>
</div>

<div class="card">
  <h2>Vue manager / multi-pôles (cible)</h2>
  <p class="sub">Une fois les 3 champs branchés, chaque pôle/manager a sa lecture en un coup d'œil :</p>
  <ul>
    <li><b>Pôle Contrôle</b> : files « à contrôler / en contrôle / à corriger », débit/jour, top dossiers du jour.</li>
    <li><b>Pôle Valorisation/Dépôt</b> : « prêts à déposer », N° de lot, burn-up vs 1 500/j.</li>
    <li><b>Pôle Commercial/Pose</b> : dossiers &lt; seuil de pose, liste de relance, délais.</li>
    <li><b>Manager</b> : 1 écran = avancement 30k, complétude moyenne, blocages par motif, charge par personne.</li>
  </ul>
  <p style="font-size:12.5px;margin:6px 0 0">Le cockpit Excel (onglets DASHBOARD/PIPELINE) est déjà conçu pour ça : filtres par statut/responsable + burn-up. On le branche sur ces données.</p>
</div>

<div class="foot">MVP de validation — Énergie Responsable · à confirmer (visu + usage) avant de figer la version quotidienne · données copiées depuis Pixel CRM, aucun original modifié</div>
</div></body></html>"""

html=re.sub(r'(\d),(?=\d{3}\b)', '\\1 ', html)
html=re.sub(r'(\d),(?=\d{3}\b)', '\\1 ', html)
with open(OUT,"w",encoding="utf-8") as f: f.write(html)
print("OK ->",OUT,"| LED signees:",total_led_signed,"| ratio:",round(ratio,1))