'use strict';
const $ = id => document.getElementById(id);
const money = value => new Intl.NumberFormat('uk-UA', {minimumFractionDigits: 2, maximumFractionDigits: 2}).format(value) + ' грн';
const date = value => new Intl.DateTimeFormat('uk-UA', {dateStyle: 'short', timeStyle: 'short', timeZone: 'Europe/Kyiv'}).format(new Date(value));
let pendingDraft = null;
function node(tag, value, className) { const el = document.createElement(tag); if (value !== undefined) el.textContent = value; if (className) el.className = className; return el; }
function clearResult() {
  $('result').hidden = true;
  $('confirmation').hidden = true; pendingDraft = null;
  $('calls').replaceChildren(); $('trace').open = false;
  $('model-state').textContent = 'Розпізнавання потреб'; $('mcp-state').textContent = 'Товари, ціни, залишки';
  $('rules-state').textContent = 'Кількість і бюджет'; $('evidence-note').textContent = 'Очікується нова перевірка.';
  window.demoReport = null;
}
function render(report, recorded = false) {
  clearResult();
  if (!report.ok) { $('status').textContent = report.error || 'Перевірку не завершено.'; $('status').className = 'error'; return; }
  if (report.phase === 'needs_confirmation') {
    pendingDraft = report;
    $('confirmation').hidden = false;
    $('draft-items').textContent = report.plan.items.map(item => `${({potato:'Картопля',chicken:'Куряче філе',eggs:'Курячі яйця'})[item.kind]}: ${item.quantity} ${item.unit === 'kg' ? 'кг' : 'шт'}`).join(' · ');
    $('draft-budget').textContent = `Бюджет: ${money(report.plan.budget)}`;
    $('status').textContent = 'Пані Одарка опрацювала запит. Спочатку звірте кількість і бюджет.';
    $('model-state').textContent = `${report.model.model} · ${(report.model.ms/1000).toFixed(1)} с · очікує підтвердження`;
    return;
  }
  if (!report.branch || !report.slot || !report.result || !Array.isArray(report.result.rows) || !Array.isArray(report.calls) || !Number.isFinite(report.result.total)) throw new Error('Malformed evidence');
  window.demoReport = report;
  $('request').value = report.request;
  $('result').hidden = false; $('status').className = '';
  $('status').textContent = recorded ? 'Запис попередньої перевірки. Поточні ціни не оновлювалися.' : 'План підготовлено за відповіддю Сільпо. Перед купівлею потрібна перевірка Олени.';
  $('mode').textContent = recorded ? 'ЗАПИС ПЕРЕВІРКИ' : 'ЩОЙНО ПЕРЕВІРЕНО';
  $('context').textContent = `${report.branch.city}, ${report.branch.address} · ${date(report.at)} · Самовивіз ${date(report.slot.start)}`;
  $('parsed').textContent = 'Розпізнано: ' + report.plan.items.map(item => `${({potato:'картопля',chicken:'філе',eggs:'яйця'})[item.kind]} ${item.quantity} ${item.unit === 'kg' ? 'кг' : 'шт'}`).join(' · ');
  $('products').replaceChildren();
  for (const row of report.result.rows) {
    const product = node('article', undefined, 'product');
    const chosen = row.selected;
    const image = chosen?.image ? node('img') : node('span', row.label.slice(0,1), 'missing-image');
    if (chosen?.image) { image.src = chosen.image; image.alt = chosen.name; image.referrerPolicy = 'no-referrer'; }
    product.append(image);
    const description = node('div');
    description.append(node('h3', chosen?.name || row.label));
    description.append(node('p', chosen ? `${chosen.requested} ${chosen.unit} · ${money(chosen.price)} / ${chosen.price_unit}` : 'Сумісного товару в отриманій вибірці немає.'));
    description.append(node('p', `Перевірено ${row.checked} · придатних ${row.compatible}`));
    product.append(description);
    const price = node('div', chosen ? money(chosen.cost) : 'Немає', 'price');
    price.append(node('small', chosen ? 'за потрібний обсяг' : 'підтвердження'));
    product.append(price); $('products').append(product);
  }
  const r = report.result;
  $('total-label').textContent = r.decision === 'incomplete' ? 'Лише знайдені позиції' : 'Орієнтовна вартість';
  $('total').textContent = money(r.total); $('budget').textContent = money(r.budget);
  $('balance-label').textContent = r.remaining >= 0 ? 'Залишається' : 'Перевищення';
  $('balance').textContent = money(Math.abs(r.remaining));
  $('verdict').className = r.decision === 'within_budget' ? 'verdict' : 'verdict warn';
  $('verdict').textContent = report.plan_confirmation === 'explicit_operator_confirmation' ? ({within_budget:'Підтверджену кількість збережено. План вкладається в бюджет.',over_budget:'План перевищує підтверджений бюджет. Потрібне рішення покупчині.',incomplete:'План неповний. Відсутні позиції потребують уточнення.'})[r.decision] : 'Попередня проба: розпізнаний план потребує звірки з початковим запитом.';
  $('model-state').textContent = `${report.model.model} · ${(report.model.ms/1000).toFixed(1)} с · запит опрацьовано`;
  $('mcp-state').textContent = `${report.calls.length} підтверджених викликів читання`;
  $('rules-state').textContent = r.decision === 'within_budget' ? 'Кількість і бюджет перевірено' : 'Потрібна увага покупчині';
  $('evidence-note').textContent = 'Модель розпізнала запит. Джерело надало ціни. Код виконав розрахунок.';
  for (const call of report.calls) {
    const p = node('p'); p.append(node('strong', call.tool), node('br'), node('span', `${call.ms} мс · ${call.response_sha256.slice(0,16)}`)); $('calls').append(p);
  }
}
async function load(recorded, confirmed = null) {
  clearResult(); $('status').className = '';
  document.body.setAttribute('aria-busy', 'true'); $('run').disabled = $('recording').disabled = $('request').disabled = $('confirm').disabled = true;
  $('status').textContent = recorded ? 'Завантаження запису…' : confirmed ? 'Пані Одарка перевіряє каталог Сільпо за підтвердженими потребами…' : 'Пані Одарка розпізнає потреби покупчині…';
  try {
    const body = confirmed ? {draft_id:confirmed.draft_id, confirmed_plan:confirmed.plan} : {text:$('request').value};
    const response = recorded ? await fetch('agent-demo-recording.json', {cache:'no-store'}) : await fetch('/api/agent-demo', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(180000)});
    if (!response.ok) throw new Error('unavailable');
    render(await response.json(), recorded);
  } catch { clearResult(); $('status').textContent = 'Перевірка недоступна. Умовні дані не підставляються.'; $('status').className = 'error'; }
  finally { document.body.setAttribute('aria-busy','false'); $('run').disabled = $('recording').disabled = $('request').disabled = $('confirm').disabled = false; }
}
$('run').addEventListener('click', () => load(false));
$('recording').addEventListener('click', () => load(true));
$('confirm').addEventListener('click', () => { if(pendingDraft) load(false, pendingDraft); });
$('request').addEventListener('input', () => { clearResult(); $('status').textContent = 'Запит змінено. Попередній результат скасовано.'; $('status').className = ''; });
window.renderDemo = render;
lucide.createIcons();

// Same original motanka geometry as the approved weave V4.
const ctx = $('odarka-mark').getContext('2d');
let drawCrown=()=>{};
window.odarkaCrownReady=false;
import('./odarka-crown.js').then(module=>{drawCrown=module.drawOdarkaCrown;window.odarkaCrownReady=true;drawMark();});
function drawMark(now=0){
ctx.save();ctx.clearRect(0,0,120,140);
const phase=matchMedia('(prefers-reduced-motion: reduce)').matches?0:now/1000*Math.PI*2/3.8;
ctx.translate(60,70+3*Math.sin(phase));ctx.rotate(.025*Math.sin(phase*.5));
const scale=.92*(1+.045*Math.sin(phase));ctx.scale(scale,scale);ctx.translate(-60,-70);
ctx.shadowColor='rgba(25,102,117,.42)';ctx.shadowBlur=10+6*Math.sin(phase);
ctx.translate(60,70); ctx.fillStyle='#196675'; ctx.beginPath();ctx.moveTo(0,-56);
ctx.bezierCurveTo(-42,-56,-46,-17,-27,13);ctx.bezierCurveTo(-45,20,-47,39,-41,50);
ctx.bezierCurveTo(-17,42,-11,28,0,28);ctx.bezierCurveTo(11,28,17,42,41,50);
ctx.bezierCurveTo(47,39,45,20,27,13);ctx.bezierCurveTo(46,-17,42,-56,0,-56);ctx.fill();
ctx.shadowBlur=0;ctx.fillStyle='#fbfcfd';ctx.beginPath();ctx.ellipse(0,-19,24,31,0,0,Math.PI*2);ctx.fill();ctx.lineCap='round';
[[-25,-27,-10,-20,10,-20,25,-27],[-24,-22,-9,-15,9,-15,24,-22],[-3,-45,-4,-20,-1,0,0,13],[3,-45,4,-20,1,0,0,13]].forEach((p,i)=>{ctx.strokeStyle=i<2?'#196675':'#b77816';ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(p[0],p[1]);ctx.bezierCurveTo(...p.slice(2));ctx.stroke();});
for(const side of [-1,1])for(let i=0;i<2;i++){ctx.strokeStyle='#fbfcfd';ctx.lineWidth=1.8;ctx.beginPath();ctx.moveTo(side*(31+i*5),15+i*9);ctx.bezierCurveTo(side*26,22+i*9,side*18,29+i*7,side*(8+i*7),33+i*6);ctx.stroke();}
drawCrown(ctx);ctx.restore();}
function tickMark(now){if(!document.hidden)drawMark(now);requestAnimationFrame(tickMark);}
drawMark();requestAnimationFrame(tickMark);
