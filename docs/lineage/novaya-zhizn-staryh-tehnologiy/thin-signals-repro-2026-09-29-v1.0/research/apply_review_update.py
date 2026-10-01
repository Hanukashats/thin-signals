"""Apply the recorded second-pass market audit once, retaining retired cards."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
def read(name):
    return json.loads((ROOT/name).read_text(encoding='utf-8-sig'))
def write(name, data):
    (ROOT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
update = read('review_update.json')
sources = {s['id']:s for s in read('sources.json')}
for s in update['sources']:
    sources.setdefault(s['id'],s)
write('sources.json',list(sources.values()))
cards = read('candidates.json')
retired = [c for c in cards if c['id'] in update['retire']]
if retired:
    reasons = {
      'T07': ('S58','Обнаружен коммерческий разработчик PYRO-E с финансированием. Для строгого потока требуется сначала отделить свободную реализацию; без этого исключено.'),
      'T08': ('S59','Нановакуумные транзисторы для сложных условий разрабатывала финансируемая компания Radiation Monitoring Devices.'),
      'T12': ('S62','Историческая коммерческая программа BHO и современный пилот Alg4Hyd с промышленным участником: широкое поле не считать свободным.'),
      'T14': ('S60','Уже существует коммерческое предложение TL-Sensor на аномальном эффекте Нернста.'),
      'T15': ('S63','Терморадиационное получение энергии для спутников имеет финансируемый коммерческий консорциум, Phase II 2025.')}
    exclusions=read('exclusions.json')
    for c in retired:
        src,reason=reasons[c['id']]
        c['commercial_status']='funded_business' if c['id']!='T14' else 'commercial'
        c['source_ids'].append(src)
        c['market_findings']=reason
        c['retired_reason']=reason
        exclusions.append({'id':'X'+str(len(exclusions)+1).zfill(2),'candidate_id':c['id'],'name':c['name'],'decision':'exclude','reason':reason,'source_ids':[src]+(['S61'] if c['id']=='T12' else [])})
    exclusions.append({'id':'X14','name':'Магнитные искусственные реснички для лабораторных планшетов','decision':'exclude','reason':'Artic Technologies сообщает о поставляемом MACplate; это уже коммерческая разработка.','source_ids':['S64']})
    write('retired_candidates.json',retired)
    write('exclusions.json',exclusions)
cards=[c for c in cards if c['id'] not in update['retire']]
existing={c['id'] for c in cards}
cards.extend(c for c in update['candidates'] if c['id'] not in existing)
for c in cards:
    c['retracted']=None
    c['system_comparison_status']='proposed'
    c['decisive_test_status']='proposed'
    if c['id']=='T01' and 'S82' not in c['source_ids']:
        c['source_ids'].append('S82')
        c['market_findings']+=' Найден US9243624B2; государственная confirmatory license не равна исключительной коммерческой лицензии.'
    if c['id']=='T03' and 'S81' not in c['source_ids']:
        c['source_ids'].append('S81')
        c['risk']+=' Известны ограничения концентрированных редокс-электролитов; нужны контроль коррозии и материальный баланс электродов.'
    if c['id']=='T04' and 'S83' not in c['source_ids']:
        c['source_ids'].append('S83')
        c['market_findings']+=' Найден исследовательский проект NASA по EWOD-конденсации; это не доказательство промышленной лицензии.'
write('candidates.json',cards)
model=read('model.json')
model['stream']='resurrection'
write('model.json',model)
print('Retained',len(cards),'candidates;',len(sources),'sources')
