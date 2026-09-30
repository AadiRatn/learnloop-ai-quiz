"""Exercise the real Streamlit app with genuine Colab output, in an isolated DB."""
import json,os,tempfile
from pathlib import Path
from streamlit.testing.v1 import AppTest
from database import Store

ROOT=Path(__file__).parent
def button(app,label):return next(x for x in app.button if x.label==label)
def clean(app):
    assert not app.exception, [x.message for x in app.exception]
    return app

def check_session_isolation(bundle):
    configured_path=os.environ.pop('LEARNLOOP_DB',None)
    try:
        first=clean(AppTest.from_file(str(ROOT/'app.py'),default_timeout=20).run())
        first_path=first.session_state['learnloop_db_path']
        first_store=Store(first_path)
        first_store.save_job(bundle['job'])
        first.run();clean(first)
        assert first.session_state['learnloop_db_path']==first_path

        second=clean(AppTest.from_file(str(ROOT/'app.py'),default_timeout=20).run())
        second_path=second.session_state['learnloop_db_path']
        assert second_path!=first_path
        assert Store(second_path).list('job')==[]
    finally:
        if configured_path is not None:os.environ['LEARNLOOP_DB']=configured_path
        else:os.environ.pop('LEARNLOOP_DB',None)

def main():
    bundle=json.loads((ROOT/'demo_bundle.json').read_text(encoding='utf-8'))
    checks=[]
    check_session_isolation(bundle)
    checks.append('Hosted sessions use separate SQLite databases; reruns retain only the current session data')
    with tempfile.TemporaryDirectory(dir=ROOT) as folder:
        os.environ['LEARNLOOP_DB']=str(Path(folder)/'ui.sqlite3')
        db=Store(os.environ['LEARNLOOP_DB'])
        app=clean(AppTest.from_file(str(ROOT/'app.py'),default_timeout=20).run())
        button(app,'Use sample study notes').click().run();clean(app)
        assert len(app.text_area(key='notes').value)>1000
        button(app,'Create generation job').click().run();clean(app)
        assert len(db.list('job'))==1;checks.append('Prepare: notes -> saved generation job')
        db.save_job(bundle['job']);p=db.import_pack(bundle['job']['job_id'],bundle['result'])
        assert len(p['questions'])==6 and not p['rejected']
        app.radio(key='navigation').set_value('Review').run();clean(app)
        button(app,'Save and approve question').click().run();assert app.error
        checks.append('Review requires explicit confirmation')
        for q in p['questions']:
            app.selectbox(key='review_q').set_value(q['id']).run()
            edits=bundle.get('review_edits',{}).get(q['id'],{})
            for key,label in [('stem','Question'),('explanation','Explanation')]:
                if key in edits:next(x for x in app.text_area if x.label==label).set_value(edits[key])
            if 'options' in edits:
                for i,value in enumerate(edits['options']):next(x for x in app.text_input if x.label==f'Option {i+1}').set_value(value)
            app.checkbox[0].check()
            button(app,'Save and approve question').click().run();clean(app)
        assert all(q['reviewed'] for q in db.get('pack',p['id'])['questions'])
        checks.append('All six genuine model questions approved through review form')
        app.radio(key='navigation').set_value('Practice').run()
        button(app,'Start quiz').click().run();clean(app)
        a=db.list('attempt')[0]
        visible=' '.join(x.value for x in app.markdown)
        assert all(q['explanation'] not in visible for q in a['questions'])
        assert all(q['quote'] not in visible for q in a['questions'])
        checks.append('Answer explanations and source quotes hidden during quiz')
        button(app,'Submit quiz').click().run();assert app.error and not db.get('attempt',a['id'])['finished']
        checks.append('Unanswered submission blocked')
        for q in a['questions']:
            answer=(q['correct']+1)%4 if q['topic']=='Database fundamentals' else q['correct']
            app.radio(key=a['id']+'_'+q['id']).set_value(answer)
        button(app,'Submit quiz').click().run();clean(app)
        finished=db.get('attempt',a['id']);assert finished['result']['correct']==4
        checks.append('Deliberate database mistakes: 4/6, 66.7%')
        app.radio(key='navigation').set_value('Progress').run();clean(app)
        assert any('Database fundamentals' in x.value for x in app.markdown)
        assert len(app.dataframe)>=2;checks.append('Progress shows topic breakdown, revision advice and history')
        next(x for x in app.checkbox if x.label=='Review latest answers').check().run();clean(app)
        checks.append('Progress answer review renders without nested layout errors')
        app=clean(AppTest.from_file(str(ROOT/'app.py'),default_timeout=20).run())
        app.radio(key='navigation').set_value('Practice').run()
        next(x for x in app.radio if x.label=='Practice mode').set_value('Weak topics').run()
        button(app,'Start quiz').click().run();clean(app)
        revision=db.list('attempt')[0];assert len(revision['questions'])==2
        assert all(q['topic']=='Database fundamentals' for q in revision['questions'])
        for q in revision['questions']:app.radio(key=revision['id']+'_'+q['id']).set_value(q['correct'])
        button(app,'Submit quiz').click().run();clean(app)
        assert db.get('attempt',revision['id'])['result']['percent']==100
        checks.append('New UI session retains history; targeted revision contains two database questions and scores 2/2')
        os.environ['LEARNLOOP_DB']=str(Path(folder)/'fresh_demo.sqlite3')
        fresh=clean(AppTest.from_file(str(ROOT/'app.py'),default_timeout=20).run())
        button(fresh,'Load verified demo').click().run();clean(fresh)
        demo=Store(os.environ['LEARNLOOP_DB']).list('pack')[0]
        assert len(demo['questions'])==6 and all(q['reviewed'] for q in demo['questions'])
        assert demo['questions'][0]['options'][3]=='frozenset'
        checks.append('Fresh installation loads the real demo with all manual review edits')
        report={'checks':checks,'passed':len(checks),'attempts':list(reversed(db.list('attempt'))),'scope':'Scripted UI actions with reviewed actual Colab questions; repeated-question score is not evidence of learning improvement.'}
        ROOT.joinpath('verification').mkdir(exist_ok=True)
        ROOT.joinpath('verification/ui_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({'passed':len(checks),'checks':checks},indent=2))
    os.environ.pop('LEARNLOOP_DB',None)

if __name__=='__main__':main()
