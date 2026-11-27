# List one subject's exam topics (3+ questions) with one candidate sample question and its KEYED answer.
# Run from ciel_study_bot/:  ..\study_bot_site\pyt_notes\_candidates.py is read-only on study.db.
#   venv/Scripts/python.exe ../study_bot_site/pyt_notes/_candidates.py "Dermatology"
import sqlite3,sys
subj=sys.argv[1]; c=sqlite3.connect('study.db')
ts=c.execute("select id,topic,(select count(*) from mcq_pyt m where m.topic_id=t.id) from pyt_topics t where subject=? and rank between 1 and 3 order by ord",(subj,)).fetchall()
for tid,tp,n in ts:
  if n<3: continue
  r=c.execute('''select q.id,q.question,q.option_a,q.option_b,q.option_c,q.option_d,q.correct from mcq_pyt m join questions q on q.id=m.mcq_id
   where m.topic_id=? and q.has_image=0 and q.source like 'FMGE Recall%' and length(q.question) between 40 and 190
   and length(q.option_a||q.option_b||q.option_c||q.option_d)<160 order by q.id limit 1''',(tid,)).fetchone()
  s=''
  if r:
    k='abcd'.index(r[6].strip().lower()); s=f' || {r[0]} {r[1][:150]} => {r[2+k][:60]}'
  print(f'{tid}|{tp}|n{n}{s}'.replace('\n',' '))
