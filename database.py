"""SQLite persistence with immutable attempt snapshots and idempotent submissions."""
import json,sqlite3,uuid
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
from quiz_core import import_generated,validate_question,grade,weak_topics

class Store:
    def __init__(self,path):
        self.path=str(path);Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, data TEXT NOT NULL, created TEXT NOT NULL, PRIMARY KEY(kind,id))')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=15)
        try:
            with db:yield db
        finally:db.close()
    def put(self,kind,id,data,replace=False):
        with self.connect() as db:
            verb='INSERT OR REPLACE' if replace else 'INSERT'
            db.execute(f'{verb} INTO records VALUES(?,?,?,?)',(kind,id,json.dumps(data),datetime.now(timezone.utc).isoformat()))
    def get(self,kind,id):
        with self.connect() as db: row=db.execute('SELECT data FROM records WHERE kind=? AND id=?',(kind,id)).fetchone()
        if not row: raise ValueError('Record not found.')
        return json.loads(row[0])
    def list(self,kind):
        with self.connect() as db: rows=db.execute('SELECT data FROM records WHERE kind=? ORDER BY created DESC',(kind,)).fetchall()
        return [json.loads(r[0]) for r in rows]
    def save_job(self,job):self.put('job',job['job_id'],job)
    def import_pack(self,jobid,result):
        job=self.get('job',jobid);pack=import_generated(job,result)
        try:self.put('pack',pack['id'],pack)
        except sqlite3.IntegrityError:raise ValueError('This job was already imported. Open its question pack.')
        return pack
    def review(self,packid,qid,changes):
        pack=self.get('pack',packid);q=next((q for q in pack['questions'] if q['id']==qid),None)
        if q is None:raise ValueError('Question not found.')
        source=next(s for s in pack['sources'] if s['id']==q['source_id'])
        clean=validate_question(changes,source)
        if any(x['id']!=qid and x['stem'].strip().casefold()==clean['stem'].strip().casefold() for x in pack['questions']):raise ValueError('Question duplicates another stem.')
        q.update(clean,reviewed=True);pack['version']+=1
        self.put('pack',packid,pack,replace=True)
        return pack
    def start_attempt(self,packid,mode='Full pack'):
        pack=self.get('pack',packid);questions=[q for q in pack['questions'] if q['reviewed']]
        if mode=='Weak topics':
            previous=sorted([a for a in self.list('attempt') if a.get('finished') and a['pack_id']==packid],key=lambda a:a['finished_at'],reverse=True)
            if not previous:raise ValueError('Complete a full quiz first.')
            weak=weak_topics(previous[0]['result'])
            questions=[q for q in questions if q['topic'] in weak]
            if not questions:raise ValueError('No weak topics in the latest attempt. Try a full quiz or create fresh questions.')
        if not questions:raise ValueError('Review and approve questions before starting.')
        attempt={'id':uuid.uuid4().hex,'pack_id':packid,'pack_version':pack['version'],'title':pack['title'],'questions':questions,'sources':pack['sources'],'mode':mode,'finished':False,'started':datetime.now(timezone.utc).isoformat()}
        self.put('attempt',attempt['id'],attempt);return attempt
    def finish(self,id,answers):
        # Transaction prevents double-click/retry from creating or changing a result.
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT data FROM records WHERE kind='attempt' AND id=?",(id,)).fetchone()
            if not row:raise ValueError('Attempt not found.')
            attempt=json.loads(row[0])
            if attempt['finished']:return attempt
            attempt.update(result=grade(attempt['questions'],answers),finished=True,finished_at=datetime.now(timezone.utc).isoformat())
            db.execute("UPDATE records SET data=? WHERE kind='attempt' AND id=?",(json.dumps(attempt),id))
        return attempt
