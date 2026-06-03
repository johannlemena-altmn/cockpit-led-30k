# -*- coding: utf-8 -*-
import csv, re, json, statistics
from collections import defaultdict
from datetime import date

CSV="data/pixelcrm-LED-export_20260603.csv"
OUT="Dashboard_LED_interactif.html"

def num(s):
    if not s: return None
    s=s.strip().replace("\xa0","").replace(" ","").replace(",",".")
    try: return float(s)
    except: return None

rows=[]
with open(CSV, encoding="latin-1", newline="") as f:
    for d in csv.DictReader(f, delimiter=";"): rows.append(d)

QTE="Produit Qté"; SIG="Date signature devis"; NUM="Numéro de dossier"
PRIME="Prime CEE opération"; SECT="Secteur d'activité"; RS="Raison Sociale"; VILLE="Ville chantier"

doss=defaultdict(lambda:{"led":0,"signed":0,"prime":0,"sect":"","rs":"","ym":"","ville":""})
for d in rows:
    k=d.get(NUM,"").strip()
    if not k: continue
    o=doss[k]
    o["led"]+=num(d.get(QTE)) or 0
    o["prime"]+=num(d.get(PRIME)) or 0
    if d.get(SIG,"").strip():
        o["signed"]=1
        m=re.match(r"(\d{2})/(\d{2})/(\d{4})",d.get(SIG).strip())
        if m and 2025<=int(m.group(3))<=2026: o["ym"]="%s-%s"%(m.group(3),m.group(2))
    if not o["sect"]: o["sect"]=(d.get(SECT,"") or "").strip() or "(vide)"
    if not o["rs"]: o["rs"]=(d.get(RS,"") or "").strip()
    if not o["ville"]: o["ville"]=(d.get(VILLE,"") or "").strip()

recs=[]
for o in doss.values():
    if o["led"]<=0: continue
    recs.append({"l":int(round(o["led"])),"s":o["signed"],"k":o["sect"],
                 "m":o["ym"],"p":int(round(o["prime"])),"n":o["rs"][:38],"v":o["ville"][:22]})

DATA=json.dumps(recs, ensure_ascii=False).replace("</","<\\/")
gen=date.today().strftime("%d/%m/%Y")

html="""<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Dashboard LED — interactif</title>
<style>
:root{--navy:#1F3A5F;--blue:#2E6FB7;--amber:#E08600;--green:#2E7D32;--ink:#1c2530;--muted:#5b6573;--line:#dfe5ee;--soft:#eef3fb;--bg:#f6f8fc}
*{box-sizing:border-box}body{font-family:-apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:var(--ink);margin:0;background:var(--bg)}
.wrap{max-width:1080px;margin:0 auto;padding:22px 24px 60px}
.hero{background:linear-gradient(135deg,var(--navy),#2b5180);color:#fff;border-radius:13px;padding:18px 22px}
.hero h1{margin:4px 0 2px;font-size:22px}.hero .s{opacity:.9;font-size:12px}.hero .k{font-size:10.5px;letter-spacing:.15em;text-transform:uppercase;opacity:.8}
.bar{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;background:#fff;border:1px solid var(--line);border-radius:12px;padding:13px 15px;margin:14px 0}
.fld{display:flex;flex-direction:column;font-size:11px;color:var(--muted);gap:3px}
.fld select,.fld input{font:inherit;font-size:13px;padding:5px 7px;border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--ink)}
.chk{flex-direction:row;align-items:center;gap:6px;font-size:12.5px;color:var(--ink)}
.btn{font:inherit;font-size:12px;padding:6px 12px;border:1px solid var(--blue);background:var(--blue);color:#fff;border-radius:7px;cursor:pointer}
.btn.ghost{background:#fff;color:var(--blue)}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:8px 0 4px}
.kpi{background:#fff;border:1px solid var(--line);border-radius:11px;padding:10px 12px}
.kpi b{display:block;font-size:20px;color:var(--navy)}.kpi span{font-size:10.5px;color:var(--muted)}
.kpi.hl{background:var(--navy)}.kpi.hl b{color:#ffd79a}.kpi.hl span{color:#fff}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:13px;margin-top:13px}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.card h2{font-size:13.5px;color:var(--navy);margin:0 0 8px}
table{width:100%;border-collapse:collapse;font-size:12px}th,td{border-bottom:1px solid var(--line);padding:5px 7px;text-align:left}
th{color:var(--navy);font-size:10.5px;text-transform:uppercase}
td.r,th.r{text-align:right}
.note{background:#fff7ec;border:1px solid #f4d6a6;border-left:4px solid var(--amber);border-radius:10px;padding:10px 13px;font-size:12px;margin-top:13px}
.foot{margin-top:18px;font-size:10.5px;color:var(--muted);text-align:center}
@media(max-width:820px){.kpis{grid-template-columns:repeat(2,1fr)}.grid2{grid-template-columns:1fr}}
</style></head><body><div class="wrap">
<div class="hero"><div class="k">Énergie Responsable · Opération LED (BAT-EQ-127)</div>
<h1>Dashboard LED — interactif</h1><div class="s">Données réelles Pixel CRM (__GEN__) · filtres en direct · prototype local</div></div>

<div class="bar">
  <label class="fld">Secteur<select id="fSect"></select></label>
  <label class="fld">Mois signé — de<select id="fFrom"></select></label>
  <label class="fld">à<select id="fTo"></select></label>
  <label class="fld">LED/dossier ≥ <span id="lblLed">0</span><input id="fLed" type="range" min="0" max="200" value="0" step="5"></label>
  <label class="fld chk"><input id="fSigned" type="checkbox" checked> Signés uniquement</label>
  <button class="btn ghost" id="reset">Réinitialiser</button>
</div>

<div class="kpis">
  <div class="kpi hl"><b id="kLed">–</b><span>LED (somme)</span></div>
  <div class="kpi"><b id="kDoss">–</b><span>dossiers</span></div>
  <div class="kpi"><b id="kMoy">–</b><span>LED/dossier (moy.)</span></div>
  <div class="kpi"><b id="kMed">–</b><span>médiane</span></div>
  <div class="kpi"><b id="kPrime">–</b><span>prime CEE</span></div>
</div>

<div class="grid2">
  <div class="card"><h2>LED par mois de signature</h2><div id="cMonth"></div></div>
  <div class="card"><h2>Répartition par taille (LED/dossier)</h2><div id="cHist"></div></div>
</div>

<div class="card" style="margin-top:13px"><h2>Top 20 dossiers (filtre courant)</h2><div id="cTable"></div></div>

<div class="note"><b>Filtres à venir (données à brancher) :</b> Statut (funnel dépôt), % / date de pose, Responsable / pôle — non présents dans l'export actuel.
Voie fiable : créer un <b>modèle d'export dédié dans Pixel</b> (admin) avec ces colonnes, ou la version BDD + Metabase (cf. plan). On aura alors les vues par pôle/manager et la synchro automatique.</div>

<div class="foot">Prototype interactif local — aucune donnée envoyée, aucun original modifié. Copie de l'export Pixel.</div>
</div>

<script>
const DATA=__DATA__;
const f={sect:"",from:"",to:"",led:0,signed:true};
const months=[...new Set(DATA.filter(d=>d.m).map(d=>d.m))].sort();
const sects=[...new Set(DATA.map(d=>d.k))].sort();
const fr=n=>Math.round(n).toLocaleString("fr-FR");
function opt(el,arr,all){el.innerHTML="<option value=''>"+all+"</option>"+arr.map(x=>`<option value="${x}">${x}</option>`).join("")}
opt(document.getElementById("fSect"),sects,"Tous secteurs");
opt(document.getElementById("fFrom"),months,"début");
opt(document.getElementById("fTo"),months,"fin");
function apply(){return DATA.filter(d=>(!f.signed||d.s)&&(!f.sect||d.k===f.sect)&&d.l>=f.led&&(!f.from||(d.m&&d.m>=f.from))&&(!f.to||(d.m&&d.m<=f.to)))}
function svgBars(pairs,color,unit){if(!pairs.length)return"<div style='color:#5b6573;font-size:12px'>Aucune donnée</div>";
 const w=480,h=160,n=pairs.length,gap=w/n,bw=gap*0.6,mx=Math.max(...pairs.map(p=>p[1]))||1;let s=`<svg viewBox="0 0 ${w} ${h+34}" width="100%">`;
 pairs.forEach((p,i)=>{const bh=p[1]/mx*h,x=i*gap+(gap-bw)/2,y=h-bh;
  s+=`<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="3" fill="${color}"/>`;
  s+=`<text x="${(x+bw/2).toFixed(1)}" y="${(y-3).toFixed(1)}" font-size="9.5" text-anchor="middle" fill="#1c2530">${fr(p[1])}</text>`;
  s+=`<text x="${(x+bw/2).toFixed(1)}" y="${h+13}" font-size="9" text-anchor="middle" fill="#5b6573">${p[0]}</text>`});
 return s+"</svg>"}
function render(){const r=apply();
 const led=r.reduce((a,d)=>a+d.l,0),prime=r.reduce((a,d)=>a+d.p,0);
 const ls=r.map(d=>d.l).sort((a,b)=>a-b);const med=ls.length?ls[Math.floor(ls.length/2)]:0;
 document.getElementById("kLed").textContent=fr(led);
 document.getElementById("kDoss").textContent=fr(r.length);
 document.getElementById("kMoy").textContent=r.length?fr(led/r.length):"–";
 document.getElementById("kMed").textContent=fr(med);
 document.getElementById("kPrime").textContent=(prime/1e6).toFixed(1)+" M€";
 const bm={};r.forEach(d=>{if(d.m)bm[d.m]=(bm[d.m]||0)+d.l});
 const mp=Object.keys(bm).sort().map(k=>[k.slice(2),bm[k]]);
 document.getElementById("cMonth").innerHTML=svgBars(mp,"#2E6FB7");
 const B=[["1-9",1,9],["10-19",10,19],["20-29",20,29],["30-49",30,49],["50-99",50,99],["100+",100,1e9]];
 const hp=B.map(([lab,a,b])=>[lab,r.filter(d=>d.l>=a&&d.l<=b).length]);
 document.getElementById("cHist").innerHTML=svgBars(hp,"#E08600");
 const top=[...r].sort((a,b)=>b.l-a.l).slice(0,20);
 let t="<table><tr><th>Raison sociale</th><th>Ville</th><th>Mois</th><th class='r'>LED</th><th class='r'>Prime</th></tr>";
 top.forEach(d=>{t+=`<tr><td>${d.n||"—"}</td><td>${d.v||""}</td><td>${d.m||"—"}</td><td class='r'>${fr(d.l)}</td><td class='r'>${fr(d.p)} €</td></tr>`});
 document.getElementById("cTable").innerHTML=t+"</table>";
}
document.getElementById("fSect").onchange=e=>{f.sect=e.target.value;render()};
document.getElementById("fFrom").onchange=e=>{f.from=e.target.value;render()};
document.getElementById("fTo").onchange=e=>{f.to=e.target.value;render()};
document.getElementById("fLed").oninput=e=>{f.led=+e.target.value;document.getElementById("lblLed").textContent=e.target.value;render()};
document.getElementById("fSigned").onchange=e=>{f.signed=e.target.checked;render()};
document.getElementById("reset").onclick=()=>{f.sect="";f.from="";f.to="";f.led=0;f.signed=true;
 document.getElementById("fSect").value="";document.getElementById("fFrom").value="";document.getElementById("fTo").value="";
 document.getElementById("fLed").value=0;document.getElementById("lblLed").textContent="0";document.getElementById("fSigned").checked=true;render()};
render();
</script></body></html>"""

html=html.replace("__DATA__",DATA).replace("__GEN__",gen)
with open(OUT,"w",encoding="utf-8") as fo: fo.write(html)
print("OK ->",OUT,"| dossiers:",len(recs))
