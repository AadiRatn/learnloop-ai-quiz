"""LearnLoop local Streamlit UI. Run: streamlit run app.py"""
import html,json,os,tempfile,uuid
from pathlib import Path
import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from database import Store
from quiz_core import parse_notes,parse_pdf,make_job,weak_topics

ROOT=Path(__file__).parent
st.set_page_config(page_title='LearnLoop | Study with evidence',page_icon='◉',layout='wide')
if 'learnloop_db_path' not in st.session_state:
    # Keep the existing SQLite workflow, but isolate public visitors from each other.
    # LEARNLOOP_DB remains available for local development and automated checks.
    st.session_state['learnloop_db_path']=os.environ.get(
        'LEARNLOOP_DB', str(Path(tempfile.gettempdir())/f'learnloop-{uuid.uuid4().hex}.sqlite3')
    )
store=Store(st.session_state['learnloop_db_path'])
st.markdown('''<style>
.stApp{background:#f7f8fb}h1,h2,h3{letter-spacing:-.03em;color:#203a4f}h1{font-size:2.8rem!important}
[data-testid="stSidebar"]{background:#eaf0f5}[data-testid="stMetric"]{background:white;border:1px solid #e3e9f0;border-radius:14px;padding:18px}
[data-testid="stForm"]{background:white;border:1px solid #e1e7ef;border-radius:14px;padding:22px}
.hero{background:#173b55;color:#fff;padding:30px 34px;border-radius:18px;margin:0 0 24px}.hero h2{color:white;margin:4px 0;font-size:2rem}.hero p{color:#b7cedd;margin:5px 0}.eyebrow{font-size:11px;letter-spacing:2px;color:#70d5c1}
.source{border-left:3px solid #3ea996;background:#eef7f4;padding:12px 18px;margin:12px 0;color:#365c52}
</style>''',unsafe_allow_html=True)
with st.sidebar:
    st.title('◉ LearnLoop')
    st.caption('STUDY → PRACTICE → REFLECT')
    page=st.radio('Workspace',['Prepare','Review','Practice','Progress'],key='navigation')
    st.divider()
    st.caption('Your study session · SQLite storage')
    st.caption('Groq generates question packs. Quizzes and scoring run locally without additional model calls.')
    if (ROOT/'demo_bundle.json').exists() and st.button('Load verified demo',use_container_width=True):
        bundle=json.loads((ROOT/'demo_bundle.json').read_text(encoding='utf-8'))
        ids={p['id'] for p in store.list('pack')}
        if bundle['job']['job_id'] not in ids:
            if bundle['job']['job_id'] not in {j['job_id'] for j in store.list('job')}:store.save_job(bundle['job'])
            p=store.import_pack(bundle['job']['job_id'],bundle['result'])
            for q in p['questions']:
                if q['id'] in bundle['reviewed_ids']:store.review(p['id'],q['id'],{**q,**bundle.get('review_edits',{}).get(q['id'],{})})
        st.session_state['notice']='Loaded a previously generated, reviewed demo pack. This is not a new model call.'
        st.rerun()
    st.caption('Learning-gap indicators are based on quiz performance, not a diagnosis of ability.')

if st.session_state.get('notice'):st.success(st.session_state.pop('notice'))

def select_pack(key):
    packs=store.list('pack')
    if not packs:st.info('Prepare and import a question pack, or load the verified demo.');st.stop()
    mapping={p['id']:p for p in packs}
    selected=st.selectbox('Question pack',list(mapping),format_func=lambda id:mapping[id]['title'],key=key)
    return mapping[selected]

def show_result(attempt):
    r=attempt['result']
    a,b,c=st.columns(3);a.metric('Score',f'{r["percent"]}%');b.metric('Correct answers',f'{r["correct"]}/{r["total"]}');c.metric('Topics to revise',len(weak_topics(r)))
    st.caption('Scored locally against the reviewed answer key. No model graded this attempt.')
    for row in r['answers']:
        with st.expander(('✓ ' if row['correct'] else '↻ ')+row['stem']):
            st.write('Your answer:',row['selected']);st.write('Correct answer:',row['expected']);st.write(row['explanation'])
            source=next(s for s in attempt['sources'] if s['id']==row['source_id'])
            st.caption(f'{source["document"]} · {source["topic"]}'+(f' · PDF page {source["page"]}' if source['page'] else ''))
            st.markdown('<div class="source">'+html.escape(row['quote'])+'</div>',unsafe_allow_html=True)

if page=='Prepare':
    st.markdown('<div class="hero"><span class="eyebrow">MAKE YOUR NEXT STUDY SESSION COUNT</span><h2>Turn your notes into practice.</h2><p>Generate once. Review the evidence. Learn at your own pace.</p></div>',unsafe_allow_html=True)
    a,b,c=st.columns(3)
    a.metric('Question packs',len(store.list('pack')));b.metric('Reviewed questions',sum(q['reviewed'] for p in store.list('pack') for q in p['questions']));c.metric('Completed attempts',sum(a['finished'] for a in store.list('attempt')))
    st.subheader('1. Prepare your study material')
    if st.button('Use sample study notes'):
        st.session_state['notes']=ROOT.joinpath('sample_notes.md').read_text(encoding='utf-8');st.rerun()
    title=st.text_input('Pack title',value='My study practice',max_chars=100,key='new_title')
    notes=st.text_area('Study notes',height=230,key='notes',placeholder='Use ## Topic headings to organize your notes. Paste explanatory material under each heading.')
    uploaded=st.file_uploader('Or upload a text-based PDF',type=['pdf'],key='notes_pdf')
    st.caption('An uploaded PDF takes precedence over pasted text. Topic headings in pasted notes give more useful topic-level feedback. Uploaded PDFs retain page numbers.')
    x,y=st.columns(2);count=x.slider('Questions to generate',3,12,6);difficulty=y.selectbox('Question style',['Recall','Application'])
    if st.button('Create generation job',type='primary'):
        try:
            sources=parse_pdf(uploaded.getvalue(),uploaded.name) if uploaded else parse_notes(notes,title)
            job=make_job(sources,title,count,difficulty);store.save_job(job)
            st.session_state['last_job']=job['job_id'];st.success('Job saved. Generate questions below.')
        except ValueError as exc:st.error(str(exc))
    jobs=store.list('job')
    if jobs:
        mapping={j['job_id']:j for j in jobs}
        selected=st.selectbox('Saved generation job',list(mapping),format_func=lambda id:mapping[id]['title']+' · '+id[:6],key='import_job')
        job=mapping[selected]
        st.caption(f'{len(job["items"])} questions requested · {len(job["sources"])} source passages. The exported job contains your notes.')
        
        st.subheader('2. Generate Questions Instantly')
        try:
            groq_api_key = st.secrets.get("GROQ_API_KEY", "")
        except StreamlitSecretNotFoundError:
            groq_api_key = ""
        if not groq_api_key:
            st.warning("🔒 API key not found. When deploying to Streamlit Cloud, add your Groq API key to the App Secrets. For local testing, add it to `.streamlit/secrets.toml`.")
        
        if st.button('Generate Questions via Groq API', type='primary', disabled=not groq_api_key):
            generation_stage = 'Groq API request'
            with st.spinner("Generating questions live using Qwen..."):
                try:
                    from quiz_core import generate_live
                    result = generate_live(job, groq_api_key)
                    generation_stage = 'response validation and import'
                    pack=store.import_pack(selected,result)
                    st.success(f'Imported {len(pack["questions"])} draft questions; {len(pack["rejected"])} rejected. Open Review to check and approve them.')
                except Exception as exc:
                    # Keep request text, user notes, credentials, and provider messages
                    # out of the UI and logs. Preserve only a safe error category.
                    cause = exc.__cause__ or exc.__context__
                    diagnostic = cause or exc
                    error_type = type(diagnostic).__name__
                    status_code = getattr(diagnostic, 'status_code', None)
                    if generation_stage == 'response validation and import':
                        st.error('Groq returned a response that did not pass LearnLoop’s question checks. No questions were imported.')
                    elif error_type == 'AuthenticationError':
                        st.error('Groq rejected the configured credentials. Verify that the key is active and has access to this model.')
                    elif error_type == 'RateLimitError':
                        st.error('Groq rate or quota limit reached. Check the account limits and retry later.')
                    elif error_type == 'APIConnectionError':
                        st.error('LearnLoop could not reach Groq. Check service availability and retry.')
                    elif status_code is not None and int(status_code) >= 500:
                        st.error('Groq returned a service error. Retry later; no questions were imported.')
                    elif status_code is not None and int(status_code) >= 400:
                        st.error('Groq rejected the request. Check the model request configuration; no questions were imported.')
                    else:
                        st.error('Groq generation failed. Check the service and account limits; no questions were imported.')
                    print(f'LearnLoop generation diagnostic: stage={generation_stage}, type={error_type}, status={status_code}')

elif page=='Review':
    st.title('Check before you quiz')
    st.write('Review the answer key, distractors and explanation against the source. Automatic checks verify text matches, not educational correctness.')
    pack=select_pack('review_pack')
    st.caption(f'Model: {pack["model"]} · {sum(q["reviewed"] for q in pack["questions"])}/{len(pack["questions"])} approved')
    if pack['rejected']:
        with st.expander('Rejected model outputs'):st.json(pack['rejected'])
    mapping={q['id']:q for q in pack['questions']}
    qid=st.selectbox('Question to review',list(mapping),format_func=lambda id:id+' · '+mapping[id]['topic'],key='review_q')
    q=mapping[qid];source=next(s for s in pack['sources'] if s['id']==q['source_id'])
    st.caption('Approved' if q['reviewed'] else 'Awaiting review')
    with st.expander('Source passage',expanded=True):
        st.caption(source['document']+(f' · PDF page {source["page"]}' if source['page'] else '')+' · '+source['topic']);st.write(source['text'])
    with st.form(f'review_{pack["id"]}_{qid}'):
        prefix=pack['id']+'_'+qid+'_edit_'
        defaults={k:q[k] for k in ('stem','correct','explanation','quote')}
        defaults.update({f'option{i}':o for i,o in enumerate(q['options'])})
        for key,value in defaults.items():
            if prefix+key not in st.session_state:st.session_state[prefix+key]=value
        stem=st.text_area('Question',key=prefix+'stem')
        options=[st.text_input(f'Option {i+1}',key=prefix+f'option{i}') for i in range(4)]
        correct=st.selectbox('Correct option',[0,1,2,3],format_func=lambda i:f'Option {i+1}',key=prefix+'correct')
        explanation=st.text_area('Explanation',key=prefix+'explanation');quote=st.text_area('Exact evidence quote',key=prefix+'quote')
        checked=st.checkbox('I checked that exactly one option is correct and the explanation follows from the source.',key=prefix+'confirm')
        if st.form_submit_button('Save and approve question',type='primary'):
            try:
                if not checked:raise ValueError('Review the question and tick the confirmation first.')
                store.review(pack['id'],qid,dict(stem=stem,options=options,correct=correct,explanation=explanation,quote=quote))
                st.session_state['notice']='Question approved. Existing attempts keep their original answer-key snapshot.';st.rerun()
            except ValueError as exc:st.error(str(exc))

elif page=='Practice':
    st.title('Practice with purpose')
    pack=select_pack('practice_pack')
    approved=sum(q['reviewed'] for q in pack['questions'])
    st.caption(f'{approved} approved questions available. Unreviewed questions are excluded.')
    mode=st.radio('Practice mode',['Full pack','Weak topics'],horizontal=True)
    if mode=='Weak topics':st.caption('Revision reuses reviewed questions from weak topics in your latest attempt. Repeated scores do not prove mastery of unseen questions.')
    if st.button('Start quiz',type='primary'):
        try:st.session_state['active_attempt']=store.start_attempt(pack['id'],mode)['id'];st.rerun()
        except ValueError as exc:st.error(str(exc))
    active=st.session_state.get('active_attempt')
    if not active:
        unfinished=[a for a in store.list('attempt') if not a['finished'] and a['pack_id']==pack['id']]
        if unfinished and st.button('Resume latest unfinished quiz'):
            st.session_state['active_attempt']=unfinished[0]['id'];st.rerun()
    if active:
        attempt=store.get('attempt',active)
        if attempt['pack_id']!=pack['id']:st.info('Start a quiz for the selected pack.');st.stop()
        if attempt['finished']:show_result(attempt)
        else:
            st.subheader(attempt['title']+' · '+attempt['mode'])
            with st.form('attempt_'+active):
                answers={}
                for i,q in enumerate(attempt['questions'],1):
                    st.markdown(f'**{i}. {q["stem"]}**');st.caption(q['topic']+' · '+q['difficulty'])
                    answers[q['id']]=st.radio('Choose one answer',range(4),index=None,format_func=lambda i,q=q:q['options'][i],key=active+'_'+q['id'])
                if st.form_submit_button('Submit quiz',type='primary'):
                    try:store.finish(active,answers);st.rerun()
                    except ValueError as exc:st.error(str(exc))

elif page=='Progress':
    st.title('See what needs another look')
    pack=select_pack('progress_pack')
    attempts=sorted([a for a in store.list('attempt') if a['finished'] and a['pack_id']==pack['id']],key=lambda a:a['finished_at'])
    if not attempts:st.info('Complete a quiz to see topic performance and a revision plan.');st.stop()
    latest=attempts[-1];r=latest['result'];weak=weak_topics(r)
    x,y,z=st.columns(3);x.metric('Latest score',f'{r["percent"]}%');y.metric('Completed attempts',len(attempts));z.metric('Topics to revise',len(weak))
    rows=[{'Topic':t,'Correct':s['correct'],'Questions':s['total'],'Score (%)':round(100*s['correct']/s['total'],1),'Next step':'Revise source and retry' if t in weak else 'Try new questions'} for t,s in r['topics'].items()]
    st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    st.bar_chart(pd.DataFrame(rows).set_index('Topic')[['Score (%)']])
    st.subheader('Your next study session')
    if weak:
        for topic in weak:st.write(f'• Re-read **{topic}**, explain the missed concepts in your own words, then use Weak topics practice.')
    else:st.success('No topic scored below 70% in this attempt. Test yourself on a fresh question pack next.')
    st.caption('Topic labels reflect performance on this small quiz. A topic with very few questions has limited evidence.')
    table=pd.DataFrame([{'Attempt':i+1,'Mode':a['mode'],'Pack version':a['pack_version'],'Score (%)':a['result']['percent'],'Questions':a['result']['total'],'Completed':a['finished_at']} for i,a in enumerate(attempts)])
    st.subheader('Attempt history');st.dataframe(table,hide_index=True,use_container_width=True)
    st.caption('Compare scores cautiously: revision quizzes may reuse questions, cover fewer topics or use a different reviewed pack version.')
    st.download_button('Export progress JSON',json.dumps(attempts,indent=2),'learnloop_progress.json','application/json')
    if st.checkbox('Review latest answers'):show_result(latest)
