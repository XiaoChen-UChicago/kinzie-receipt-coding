"""Tenant-scoped receipt review service. Not an accounting-system integration."""
from __future__ import annotations
import os, json, secrets, hashlib, sqlite3, csv, io
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .engine import decide, default_policy, validate_policy

ENV=os.getenv('KINZIE_ENV','development')
DB=os.getenv('KINZIE_DB',str(Path(__file__).parent/'commercial.sqlite3'))
API_KEY=os.getenv('KINZIE_API_KEY','')
if ENV=='production' and (len(API_KEY)<32 or API_KEY=='dev-only-change-me'):
    raise RuntimeError('Production requires a KINZIE_API_KEY of at least 32 characters')
if not API_KEY: API_KEY='dev-only-change-me' if ENV=='development' else ''
APP=FastAPI(title='LedgerLane Receipt Review API',version='0.2.0',docs_url=None if ENV=='production' else '/docs')
BASE=Path(__file__).resolve().parent
APP.mount('/assets',StaticFiles(directory=BASE/'static'),name='assets')

@APP.middleware('http')
async def response_headers(request, call_next):
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Cache-Control']='no-store'
    return response

def now(): return datetime.now(timezone.utc).isoformat()

@contextmanager
def connection():
    con=sqlite3.connect(DB,timeout=10)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    try:
        yield con; con.commit()
    except: con.rollback();raise
    finally: con.close()

def initialize():
    Path(DB).parent.mkdir(parents=True,exist_ok=True)
    with connection() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY, name TEXT NOT NULL, policy TEXT NOT NULL, token_hash TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS receipts(id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id TEXT NOT NULL, receipt_id TEXT NOT NULL, payload TEXT NOT NULL, verdict TEXT NOT NULL, reason TEXT NOT NULL, evidence TEXT NOT NULL, form_rows TEXT NOT NULL, review_state TEXT NOT NULL DEFAULT 'pending', imported_at TEXT NOT NULL, UNIQUE(workspace_id,receipt_id), FOREIGN KEY(workspace_id) REFERENCES workspaces(id));
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id TEXT NOT NULL, receipt_id TEXT, actor TEXT NOT NULL, action TEXT NOT NULL, details TEXT NOT NULL, at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS revisions(id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id TEXT NOT NULL, receipt_id TEXT NOT NULL, actor TEXT NOT NULL, note TEXT NOT NULL, prior_payload TEXT NOT NULL, prior_verdict TEXT NOT NULL, prior_reason TEXT NOT NULL, prior_evidence TEXT NOT NULL, prior_form_rows TEXT NOT NULL, at TEXT NOT NULL);
        """)
initialize()

async def admin_auth(x_api_key: str|None=Header(default=None)):
    if not x_api_key or not secrets.compare_digest(x_api_key,API_KEY):
        raise HTTPException(401,'Invalid administrator API key')
    return 'admin'

async def workspace_auth(wid:str,x_api_key: str|None=Header(default=None)):
    if not x_api_key:raise HTTPException(401,'Missing workspace API key')
    with connection() as con:
        w=workspace(con,wid)
        supplied=hashlib.sha256(x_api_key.encode()).hexdigest()
        if not secrets.compare_digest(supplied,w['token_hash']):
            raise HTTPException(403,'Key is not authorized for this workspace')
    return wid

class Workspace(BaseModel):
    id: str=Field(pattern=r'^[a-z][a-z0-9_-]{2,40}$')
    name: str=Field(min_length=2,max_length=120)
    policy: dict=Field(default_factory=default_policy)
class ImportPayload(BaseModel):
    receipts: list[dict]=Field(min_length=1,max_length=250)
class RevisionPayload(BaseModel):
    corrected_receipt: dict
    actor: str=Field(min_length=2,max_length=100)
    note: str=Field(min_length=10,max_length=2000)
class ReviewPayload(BaseModel):
    state: str
    note: str=Field(min_length=3,max_length=2000)
    actor: str=Field(min_length=2,max_length=100)

def workspace(con,id):
    row=con.execute('SELECT * FROM workspaces WHERE id=?',(id,)).fetchone()
    if row is None: raise HTTPException(404,'Workspace not found')
    return row

def audit(con,wid,rid,actor,action,details):
    con.execute('INSERT INTO audit(workspace_id,receipt_id,actor,action,details,at) VALUES(?,?,?,?,?,?)',(wid,rid,actor,action,details,now()))

@APP.get('/',response_class=HTMLResponse)
def index():return (BASE/'static/index.html').read_text('utf-8')

@APP.get('/health')
def health(): return {'status':'ok','version':'0.2.0'}

@APP.get('/api/workspaces',dependencies=[Depends(admin_auth)])
def list_workspaces():
    with connection() as con:
        return [dict(x) for x in con.execute('SELECT id,name,created_at FROM workspaces ORDER BY created_at DESC')]

@APP.post('/api/workspaces',dependencies=[Depends(admin_auth)],status_code=201)
def create_workspace(payload:Workspace):
    p=validate_policy(payload.policy)
    token=secrets.token_urlsafe(36)
    token_hash=hashlib.sha256(token.encode()).hexdigest()
    with connection() as con:
        try:con.execute('INSERT INTO workspaces VALUES(?,?,?,?,?)',(payload.id,payload.name,json.dumps(p),token_hash,now()))
        except sqlite3.IntegrityError:raise HTTPException(409,'Workspace already exists')
        audit(con,payload.id,None,'api-user','workspace_created',payload.name)
    return {'id':payload.id,'name':payload.name,'workspace_api_key':token,'warning':'Copy this workspace key now; it will not be displayed again'}

@APP.get('/api/workspaces/{wid}',dependencies=[Depends(workspace_auth)])
def get_workspace(wid:str):
    with connection() as con:
        r=workspace(con,wid)
        return {'id':r['id'],'name':r['name'],'policy':json.loads(r['policy'])}

@APP.put('/api/workspaces/{wid}/policy',dependencies=[Depends(workspace_auth)])
def update_policy(wid:str,policy:dict):
    p=validate_policy(policy)
    with connection() as con:
        workspace(con,wid)
        con.execute('UPDATE workspaces SET policy=? WHERE id=?',(json.dumps(p),wid))
        audit(con,wid,None,'api-user','policy_updated','Policy changed; existing decisions remain snapshots and must be re-imported to re-evaluate')
    return {'updated':True,'note':'Previously processed receipts are not silently recalculated'}

def evaluate_batch(con,wid,receipts):
    w=workspace(con,wid);p=json.loads(w['policy']);out=[]
    seen=set()
    for r in con.execute('SELECT payload FROM receipts WHERE workspace_id=?',(wid,)):
        x=json.loads(r['payload'])
        try:
            from .engine import normalize,money
            seen.add((normalize(x.get('technician')),normalize(p['vendor_aliases'].get(normalize(x.get('vendor')),x.get('vendor'))),str(x.get('date')),str(money(x.get('total')))))
        except ValueError:pass
    for item in receipts:
        if not isinstance(item,dict):raise HTTPException(422,'Receipt must be an object')
        rid=str(item.get('receipt_id') or '')
        if not rid or len(rid)>100:raise HTTPException(422,'Receipt ID required, max 100 characters')
        if con.execute('SELECT 1 FROM receipts WHERE workspace_id=? AND receipt_id=?',(wid,rid)).fetchone():
            raise HTTPException(409,f'Receipt {rid} already imported; original decision preserved')
        result=decide(item,p,seen)
        con.execute('INSERT INTO receipts(workspace_id,receipt_id,payload,verdict,reason,evidence,form_rows,imported_at) VALUES(?,?,?,?,?,?,?,?)',
            (wid,rid,json.dumps(item),result['verdict'],result['reason'],json.dumps(result['evidence']),json.dumps(result['form_rows']),now()))
        audit(con,wid,rid,'engine','receipt_reviewed',result['verdict']+': '+result['reason'])
        out.append({'receipt_id':rid,**result})
    return out

@APP.post('/api/workspaces/{wid}/receipts/import',dependencies=[Depends(workspace_auth)])
def import_receipts(wid:str,payload:ImportPayload):
    ids=[str(x.get('receipt_id')) for x in payload.receipts]
    if len(set(ids))!=len(ids):raise HTTPException(422,'Duplicate receipt IDs within import batch')
    with connection() as con:return evaluate_batch(con,wid,payload.receipts)

@APP.post('/api/workspaces/{wid}/receipts/import-csv',dependencies=[Depends(workspace_auth)])
async def import_csv(wid:str,file:UploadFile=File(...)):
    raw=await file.read(2_000_001)
    if len(raw)>2_000_000:raise HTTPException(413,'CSV maximum 2 MB')
    try:content=raw.decode('utf-8-sig');reader=csv.DictReader(io.StringIO(content))
    except UnicodeDecodeError:raise HTTPException(422,'CSV must be UTF-8')
    required={'receipt_id','date','vendor','technician','card_last4','job_number','description','amount','tax','total'}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):raise HTTPException(422,'Missing required CSV columns: '+', '.join(sorted(required-set(reader.fieldnames or []))))
    grouped={}
    for i,row in enumerate(reader):
        if i>=5000:raise HTTPException(413,'Maximum 5,000 line items per upload')
        rid=row['receipt_id'];r=grouped.setdefault(rid,{'receipt_id':rid,**{k:row[k] for k in ('date','vendor','technician','card_last4','job_number','total')},'lines':[]})
        if any(str(r[k])!=str(row[k]) for k in ('date','vendor','technician','card_last4','job_number','total')):raise HTTPException(422,f'Inconsistent receipt header fields for {rid}')
        r['lines'].append({'description':row['description'],'amount':row['amount'],'tax':row['tax']})
    if not grouped or len(grouped)>250:raise HTTPException(422,'Upload 1–250 receipts per batch')
    with connection() as con:return evaluate_batch(con,wid,list(grouped.values()))

@APP.get('/api/workspaces/{wid}/receipts',dependencies=[Depends(workspace_auth)])
def list_receipts(wid:str,verdict:str|None=None):
    if verdict and verdict not in ('coded','needs_review','sent_back'):raise HTTPException(422,'Unknown verdict')
    with connection() as con:
        workspace(con,wid)
        sql='SELECT receipt_id,verdict,reason,review_state,imported_at FROM receipts WHERE workspace_id=?'
        params=[wid]
        if verdict:sql+=' AND verdict=?';params.append(verdict)
        sql+=' ORDER BY id DESC LIMIT 1000'
        return [dict(r) for r in con.execute(sql,params)]

@APP.get('/api/workspaces/{wid}/receipts/{rid}',dependencies=[Depends(workspace_auth)])
def receipt_detail(wid:str,rid:str):
    with connection() as con:
        workspace(con,wid)
        r=con.execute('SELECT * FROM receipts WHERE workspace_id=? AND receipt_id=?',(wid,rid)).fetchone()
        if not r:raise HTTPException(404,'Receipt not found')
        d=dict(r)
        for k in ('payload','evidence','form_rows'):d[k]=json.loads(d[k])
        return d

@APP.post('/api/workspaces/{wid}/receipts/{rid}/review',dependencies=[Depends(workspace_auth)])
def review(wid:str,rid:str,payload:ReviewPayload):
    if payload.state not in ('reviewed','needs_info','rejected'):
        raise HTTPException(422,'Unsupported review state')
    with connection() as con:
        workspace(con,wid)
        r=con.execute('SELECT verdict,review_state FROM receipts WHERE workspace_id=? AND receipt_id=?',(wid,rid)).fetchone()
        if r is None:raise HTTPException(404,'Receipt not found')
        if r['review_state']!='pending':raise HTTPException(409,'Already reviewed; no silent overwrite')
        updated=con.execute("UPDATE receipts SET review_state=? WHERE workspace_id=? AND receipt_id=? AND review_state='pending'",(payload.state,wid,rid))
        if updated.rowcount!=1:raise HTTPException(409,'Another reviewer already handled this receipt')
        audit(con,wid,rid,payload.actor,'review_'+payload.state,payload.note)
    return {'receipt_id':rid,'review_state':payload.state,'verdict_unchanged':True}

@APP.post('/api/workspaces/{wid}/receipts/{rid}/revise',dependencies=[Depends(workspace_auth)])
def revise_receipt(wid:str,rid:str,revision:RevisionPayload):
    item=revision.corrected_receipt
    if item.get('receipt_id')!=rid:
        raise HTTPException(422,'Correction must keep the original receipt ID')
    with connection() as con:
        w=workspace(con,wid)
        original=con.execute('SELECT * FROM receipts WHERE workspace_id=? AND receipt_id=?',(wid,rid)).fetchone()
        if original is None:raise HTTPException(404,'Receipt not found')
        policy=json.loads(w['policy']); seen=set()
        from .engine import normalize,money
        for prior in con.execute('SELECT payload FROM receipts WHERE workspace_id=? AND receipt_id<>?',(wid,rid)):
            x=json.loads(prior['payload'])
            try:
                v=policy['vendor_aliases'].get(normalize(x.get('vendor')),x.get('vendor'))
                seen.add((normalize(x.get('technician')),normalize(v),str(x.get('date')),str(money(x.get('total')))))
            except ValueError:pass
        decision=decide(item,policy,seen)
        con.execute("INSERT INTO revisions(workspace_id,receipt_id,actor,note,prior_payload,prior_verdict,prior_reason,prior_evidence,prior_form_rows,at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (wid,rid,revision.actor,revision.note,original['payload'],original['verdict'],original['reason'],original['evidence'],original['form_rows'],now()))
        con.execute("UPDATE receipts SET payload=?,verdict=?,reason=?,evidence=?,form_rows=?,review_state='pending',imported_at=? WHERE workspace_id=? AND receipt_id=?",
            (json.dumps(item),decision['verdict'],decision['reason'],json.dumps(decision['evidence']),json.dumps(decision['form_rows']),now(),wid,rid))
        audit(con,wid,rid,revision.actor,'receipt_revised',revision.note+'; previous='+original['verdict']+'; new='+decision['verdict'])
    return {'receipt_id':rid,'previous_verdict':original['verdict'],'current':decision,'review_state':'pending'}

@APP.get('/api/workspaces/{wid}/receipts/{rid}/revisions',dependencies=[Depends(workspace_auth)])
def list_revisions(wid:str,rid:str):
    with connection() as con:
        workspace(con,wid)
        if con.execute('SELECT 1 FROM receipts WHERE workspace_id=? AND receipt_id=?',(wid,rid)).fetchone() is None:
            raise HTTPException(404,'Receipt not found')
        return [dict(x) for x in con.execute('SELECT id,actor,note,prior_payload,prior_verdict,prior_reason,prior_evidence,prior_form_rows,at FROM revisions WHERE workspace_id=? AND receipt_id=? ORDER BY id DESC',(wid,rid))]

@APP.get('/api/workspaces/{wid}/export',dependencies=[Depends(workspace_auth)])
def export(wid:str):
    with connection() as con:
        workspace(con,wid)
        rows=con.execute('SELECT receipt_id,verdict,reason,form_rows FROM receipts WHERE workspace_id=? ORDER BY id',(wid,)).fetchall()
    out=io.StringIO();w=csv.writer(out)
    fields=['receipt_id','verdict','reason','date','vendor','job_number','technician','card_last4','amount_before_tax','tax','cost_code','description','billable']
    w.writerow(fields)
    for r in rows:
        def safe(v):
            s=str(v or '')
            return "'"+s if s.lstrip().startswith(('=','+','-','@','\t','\r')) else s
        form=json.loads(r['form_rows'])
        for f in form if r['verdict']=='coded' else [{}]:
            w.writerow([safe(r['receipt_id']),r['verdict'],safe(r['reason'])]+[safe(f.get(k,'')) for k in fields[3:]])
    return StreamingResponse(iter([out.getvalue()]),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="{wid}-review.csv"','Cache-Control':'no-store'})

@APP.get('/api/workspaces/{wid}/audit',dependencies=[Depends(workspace_auth)])
def get_audit(wid:str):
    with connection() as con:
        workspace(con,wid)
        return [dict(r) for r in con.execute('SELECT receipt_id,actor,action,details,at FROM audit WHERE workspace_id=? ORDER BY id DESC LIMIT 500',(wid,))]
