"""Portable question-generation worker, injected into a Colab notebook."""
import hashlib,json,time,re

def job_digest(job):
    return hashlib.sha256(json.dumps({k:v for k,v in job.items() if k!='sha256'},sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def generate_pack(job,generate,model_id):
    if not isinstance(job,dict) or job.get('version')!=1 or job.get('sha256')!=job_digest(job):raise ValueError('Invalid LearnLoop job or checksum.')
    if not isinstance(job.get('system'),str) or len(json.dumps(job))>200000:raise ValueError('Invalid prompt or oversized job.')
    sources=job.get('sources');items=job.get('items')
    if not isinstance(sources,list) or not 1<=len(sources)<=30 or not isinstance(items,list) or not 3<=len(items)<=12:raise ValueError('Invalid sources or question count.')
    sources={s['id']:s for s in sources};previous=[];records=[];used={}
    for item in items:
        source=sources[item['source_id']]
        facts=[s.strip() for s in re.split(r'(?<=[.!?])\s+',source['text']) if len(s.strip())>=20]
        turn=used.get(source['id'],0);used[source['id']]=turn+1
        target=facts[turn%len(facts)] if facts else source['text']
        prompt='TARGET FACT: '+target+'\nWrite one '+job['difficulty'].lower()+' question asking WHICH TERM fits this description. Use the exact subject phrase of the sentence as the correct answer. Provide EXACTLY FOUR options, each a short term (not a sentence). Copy the TARGET FACT as the quote. Explain the answer. For application style, use a short scenario.'
        messages=[{'role':'system','content':job['system']},{'role':'user','content':json.dumps(prompt,ensure_ascii=False)}]
        started=time.perf_counter();raw=generate(messages)
        records.append({'id':item['id'],'raw':raw,'seconds':round(time.perf_counter()-started,2),'messages':messages})
        try:
            obj=json.loads(raw.strip().removeprefix('```json').removesuffix('```').strip())
            if isinstance(obj.get('stem'),str):previous.append(obj['stem'])
        except (ValueError,AttributeError):pass
        print(item['id']+' generated',flush=True)
    return {'job_id':job['job_id'],'sha256':job['sha256'],'model':model_id,'records':records}
