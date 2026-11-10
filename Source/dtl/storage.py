import calendar
from datetime import datetime
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import uuid
from .models import UserError, safe_component, money
from .pdf import read_pdf, stamped_bytes, merge_bytes, verify
from .platform_support import lock_workspace, lock_is_busy, sync_directory

DEFAULT_WORKBOOK = ''
FOLDERS = ['Intake','Processed_Originals','Contract_Output','Flagged','Master_Contracts','Config','Logs']
GROUP_COLUMNS = ['key','identity','contract','month','year','name','first','last','path','hash','pages']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_write(path,data):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,temp=tempfile.mkstemp(prefix='.dtl-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            if os.name != 'nt':
                os.fchmod(f.fileno(),0o600)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp,path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class Store:
    def __init__(self,root):
        self.root=Path(root).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        for folder in FOLDERS:
            p=self.path(folder)
            p.mkdir(mode=0o700,exist_ok=True)
            p.chmod(0o700)
        self.lock=open(self.path('Config/session.lock'),'a+b')
        os.chmod(self.lock.name,0o600)
        try:
            lock_workspace(self.lock)
        except OSError as exc:
            self.lock.close()
            if lock_is_busy(exc):
                raise UserError('DTL is already running for this workspace. Close that window first.') from None
            raise
        self.db=sqlite3.connect(self.path('Config/audit.sqlite'))
        self.db.row_factory=sqlite3.Row
        os.chmod(self.path('Config/audit.sqlite'),0o600)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS groups (
              key TEXT PRIMARY KEY, identity TEXT, contract TEXT, month INTEGER, year INTEGER,
              name TEXT, first TEXT, last TEXT, path TEXT UNIQUE, hash TEXT, pages INTEGER);
            CREATE TABLE IF NOT EXISTS actions (
              id TEXT PRIMARY KEY, hash TEXT, source TEXT, archive TEXT, group_key TEXT,
              status TEXT, payload TEXT, created TEXT);
            CREATE TABLE IF NOT EXISTS flags (hash TEXT PRIMARY KEY, source TEXT, created TEXT);
            CREATE TABLE IF NOT EXISTS masters (period TEXT PRIMARY KEY, stale INTEGER);
        ''')
        self.db.commit()
        now=datetime.now()
        self.settings=dict(workbook=DEFAULT_WORKBOOK,sheet='',mapping={},header_row=1,
             month=now.month,year=now.year,placement='Top margin',font_size=10,auto_next=True,
             intake='Intake',output='Contract_Output',archive='Processed_Originals',flagged='Flagged',
             master='Master_Contracts',viewer_sizes=[230,650,380],zoom='Fit Width',prompts=True)
        p=self.path('Config/settings.json')
        if p.exists():
            self.settings.update(json.loads(p.read_text()))
        self.validate_folders(self.settings)
        self.recover()

    def close(self):
        self.db.close()
        self.lock.close()

    def path(self,relative):
        p=(self.root/relative).resolve()
        if p==self.root or not p.is_relative_to(self.root):
            raise UserError('Storage must stay inside the DTL workspace and cannot be its root.')
        return p

    def rel(self,path):
        p=Path(path).resolve()
        if not p.is_relative_to(self.root):
            raise UserError('This document is outside the approved workspace.')
        return str(p.relative_to(self.root))

    def validate_folders(self,settings):
        dirs=[self.path(settings[k]) for k in ('intake','output','archive','flagged','master')]
        protected=[self.path(k) for k in ('Source','Tests','Build','Config','Logs','.venv','.git')]
        for i,p in enumerate(dirs):
            if any(p==q or p.is_relative_to(q) or q.is_relative_to(p) for q in dirs[i+1:]+protected):
                raise UserError('Choose separate storage folders outside Source, Tests, Build, Config, Logs, and the virtual environment.')

    def save_settings(self):
        self.validate_folders(self.settings)
        atomic_write(self.path('Config/settings.json'),json.dumps(self.settings,indent=2).encode())

    def folder(self,key):
        p=self.path(self.settings[key])
        p.mkdir(parents=True,exist_ok=True,mode=0o700)
        p.chmod(0o700)
        return p

    def stable_source(self,source):
        path=self.path(self.rel(source))
        if path.parent!=self.folder('intake') or path.suffix.lower()!='.pdf':
            raise UserError('Select a PDF directly inside the configured Intake folder.')
        s=path.stat()
        if time.time()-s.st_mtime<2:
            raise UserError('This PDF may still be copying. Wait a few seconds, then refresh.')
        data=path.read_bytes()
        after=path.stat()
        if (s.st_size,s.st_mtime_ns,s.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
            raise UserError('The PDF changed while being read. Wait, then refresh.')
        read_pdf(BytesIO(data))
        return data

    def status(self,h):
        if self.db.execute("SELECT 1 FROM actions WHERE hash=? AND status='done'",(h,)).fetchone():
            return 'Processed'
        if self.db.execute('SELECT 1 FROM flags WHERE hash=?',(h,)).fetchone():
            return 'Flagged'
        return 'Queued'

    def queue(self):
        items=[]
        for p in sorted(self.folder('intake').glob('*'),key=lambda p:p.name.casefold()):
            if p.suffix.lower()!='.pdf' or not p.is_file():
                continue
            try:
                self.path(self.rel(p))
                status='Copying / wait' if time.time()-p.stat().st_mtime<2 else self.status(digest(p.read_bytes()))
                items.append((p,status))
            except (OSError,UserError):
                items.append((p,'Unavailable'))
        return items

    def flag(self,source):
        # A corrupt PDF can still be flagged: do not require it to parse.
        p=self.path(self.rel(source))
        if p.parent!=self.folder('intake') or time.time()-p.stat().st_mtime<2:
            raise UserError('Wait for copying to finish before flagging this file.')
        data=p.read_bytes()
        h=digest(data)
        if self.status(h)=='Processed':
            raise UserError('This exact original has already been processed.')
        dest=self.folder('flagged')/(h+'.pdf')
        if dest.exists() and digest(dest.read_bytes())!=h:
            raise UserError('A review copy has changed. Ask your administrator to recover it.')
        atomic_write(dest,data)
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO flags VALUES(?,?,?)',(h,self.rel(source),datetime.now().isoformat()))

    def unflag(self,source):
        h=digest(self.path(self.rel(source)).read_bytes())
        with self.db:
            self.db.execute('DELETE FROM flags WHERE hash=?',(h,))

    def mark_stale(self,month,year):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO masters VALUES(?,1)',(f'{year}-{month:02}',))
        for p in self.folder('master').glob(f'*/*_DTL_{calendar.month_name[month]}_{year}_MASTER.pdf'):
            atomic_write(p.with_suffix('.STALE.txt'),b'STALE: Regenerate masters in DTL before using this PDF.\n')

    def is_stale(self,month,year):
        row=self.db.execute('SELECT stale FROM masters WHERE period=?',(f'{year}-{month:02}',)).fetchone()
        return bool(row and row[0])

    def ensure_recovered(self):
        if self.db.execute("SELECT 1 FROM actions WHERE status IN ('pending','undo_pending')").fetchone():
            raise UserError('A file operation needs recovery. Restart DTL before continuing; keep all workspace files intact.')

    def process(self,source,client,month,year,stamp,confirmed=False,expected_digest=None):
        self.ensure_recovered()
        source=Path(source)
        if not confirmed:
            raise UserError('Preview the stamp and confirm one client, placement, and processing period before saving.')
        if not 1<=month<=12 or not 1900<=year<=2200:
            raise UserError('Select a valid processing period.')
        if not all(v.strip() for v in [client.name,client.number,client.contract,client.last]):
            raise UserError('Verify the client, contract, and filing last name.')
        if (stamp.name,stamp.number,stamp.contract)!=(client.name,client.number,client.contract):
            raise UserError('The preview no longer matches the client. Preview again.')
        if stamp.required not in ('Yes','No'):
            raise UserError('Select Copay Required explicitly.')
        money(stamp.amount)
        if stamp.paid is not None:
            money(stamp.paid)
        safe_component(client.contract)
        safe_component(client.last)
        data=self.stable_source(source)
        h=digest(data)
        if expected_digest is not None and h != expected_digest:
            raise UserError('The intake PDF changed after preview. Refresh and preview the new document before saving.')
        if self.status(h)=='Processed':
            raise UserError('This exact original was already processed. Use Undo to reclassify it.')
        key=digest(json.dumps([client.identity,client.contract,month,year]).encode())
        old=self.db.execute('SELECT * FROM groups WHERE key=?',(key,)).fetchone()
        previous=dict(old) if old else None
        if previous and (previous['last']!=client.last or previous['first']!=client.first or previous['name']!=client.name):
            raise UserError('This client already has a different filing name for this period. Use the same verified name or undo the earlier assignment first.')
        contract_folder=self.folder('output')/safe_component(client.contract)
        other=self.db.execute('SELECT DISTINCT contract,path FROM groups WHERE contract != ?',(client.contract,)).fetchall()
        if any(self.path(r['path']).parent==contract_folder for r in other):
            contract_folder=contract_folder.with_name(contract_folder.name+'_'+digest(client.contract.encode())[:10])
        contract_folder=self.path(self.rel(contract_folder))
        contract_folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        contract_folder.chmod(0o700)
        prior_data=None
        if previous:
            dest=self.path(previous['path'])
            prior_data=dest.read_bytes() if dest.exists() else None
            if prior_data is None or digest(prior_data)!=previous['hash']:
                raise UserError('The existing client PDF is missing or changed outside DTL. Restore it before appending.')
        else:
            base=f'{safe_component(client.last)}_DTL_{calendar.month_name[month]}_{year}'
            dest=contract_folder/(base+'.pdf')
            if dest.exists():
                dest=contract_folder/(base+'_'+client.identity[:12]+'.pdf')
            if dest.exists():
                raise UserError('An unrelated file occupies this output name. Resolve it without overwriting, then retry.')
        new_pages=len(read_pdf(BytesIO(data)).pages)
        stamped=stamped_bytes(BytesIO(data),stamp)
        output=merge_bytes([prior_data,stamped]) if previous else stamped
        pages=new_pages+(previous['pages'] if previous else 0)
        verify(output,pages)
        if source.read_bytes()!=data:
            raise UserError('The original changed during preparation. Wait and refresh.')
        if previous and (not dest.exists() or digest(dest.read_bytes())!=previous['hash']):
            raise UserError('The existing output changed during preparation. Keep all files and retry after recovery.')
        if not previous and dest.exists():
            raise UserError('Another file appeared at the output name. It was not overwritten. Retry to choose a collision-safe name.')
        action=uuid.uuid4().hex
        archive=self.folder('archive')/(action+'.pdf')
        backup=self.path(f'Config/recovery/{action}.pdf') if previous else None
        if backup:
            atomic_write(backup,prior_data)
        payload=dict(previous=previous,dest=self.rel(dest),backup=self.rel(backup) if backup else None,
                     new_hash=digest(output),month=month,year=year)
        with self.db:
            self.db.execute('INSERT INTO actions VALUES(?,?,?,?,?,?,?,?)',(action,h,self.rel(source),self.rel(archive),key,'pending',json.dumps(payload),datetime.now().isoformat()))
        try:
            atomic_write(archive,data)
            if digest(archive.read_bytes())!=h:
                raise UserError('The original archive could not be verified.')
            atomic_write(dest,output)
            verify(dest.read_bytes(),pages)
            if digest(dest.read_bytes())!=payload['new_hash']:
                raise UserError('The output could not be verified.')
            self.mark_stale(month,year)
            with self.db:
                self.db.execute('INSERT OR REPLACE INTO groups VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (key,client.identity,client.contract,month,year,client.name,client.first,client.last,self.rel(dest),payload['new_hash'],pages))
                self.db.execute("UPDATE actions SET status='done' WHERE id=?",(action,))
                self.db.execute('DELETE FROM flags WHERE hash=?',(h,))
        except BaseException:
            self.rollback_pending(self.db.execute('SELECT * FROM actions WHERE id=?',(action,)).fetchone())
            raise
        # A failure deleting Intake after commit leaves an idempotent Processed queue item.
        try:
            self.finalize_source(self.db.execute('SELECT * FROM actions WHERE id=?',(action,)).fetchone())
        except OSError:
            pass
        return dest

    def finalize_source(self,row):
        source,archive=self.path(row['source']),self.path(row['archive'])
        if archive.exists() and digest(archive.read_bytes())==row['hash']:
            if source.exists() and digest(source.read_bytes())==row['hash']:
                source.unlink()

    def rollback_pending(self,row):
        p=json.loads(row['payload'])
        dest=self.path(p['dest'])
        if dest.exists() and digest(dest.read_bytes()) not in {p['new_hash'],(p['previous'] or {}).get('hash')}:
            raise UserError('Recovery found an externally changed output. Keep all files and contact your administrator.')
        if p['backup']:
            backup=self.path(p['backup']).read_bytes()
            if digest(backup)!=p['previous']['hash']:
                raise UserError('A recovery backup failed verification. Contact your administrator.')
            atomic_write(dest,backup)
        elif dest.exists():
            dest.unlink()
        with self.db:
            self.db.execute("UPDATE actions SET status='rolled_back' WHERE id=?",(row['id'],))
        # Retain any archived original after rollback for recovery.

    def recover(self):
        for row in self.db.execute("SELECT * FROM actions WHERE status IN ('pending','undo_pending') ORDER BY created").fetchall():
            if row['status']=='pending':
                self.rollback_pending(row)
            else:
                self.finish_undo(row)
        for row in self.db.execute("SELECT * FROM actions WHERE status='done'").fetchall():
            try:
                self.finalize_source(row)
            except OSError:
                pass

    def undo(self):
        self.ensure_recovered()
        row=self.db.execute("SELECT * FROM actions WHERE status='done' ORDER BY created DESC LIMIT 1").fetchone()
        if not row:
            raise UserError('There is no processing action to undo.')
        p=json.loads(row['payload'])
        dest=self.path(p['dest'])
        if not dest.exists() or digest(dest.read_bytes())!=p['new_hash']:
            raise UserError('The output changed outside DTL. Restore it before undoing.')
        source=self.path(row['source'])
        if source.exists() and digest(source.read_bytes())!=row['hash']:
            raise UserError('A different intake file uses the original filename. Rename it, then retry undo.')
        with self.db:
            self.db.execute("UPDATE actions SET status='undo_pending' WHERE id=?",(row['id'],))
        self.finish_undo(row)
        return source

    def finish_undo(self,row):
        p=json.loads(row['payload'])
        archive=self.path(row['archive'])
        if not archive.exists() or digest(archive.read_bytes())!=row['hash']:
            raise UserError('The archived original is missing or changed. Restore it before undoing.')
        source,dest=self.path(row['source']),self.path(p['dest'])
        if source.exists() and digest(source.read_bytes())!=row['hash']:
            raise UserError('Recovery cannot restore the original because another file occupies its filename.')
        if dest.exists() and digest(dest.read_bytes()) not in {p['new_hash'],(p['previous'] or {}).get('hash')}:
            raise UserError('Recovery found an externally changed output. Contact your administrator.')
        atomic_write(source,archive.read_bytes())
        os.utime(source,(time.time()-5,time.time()-5))
        if p['backup']:
            backup=self.path(p['backup']).read_bytes()
            if digest(backup)!=p['previous']['hash']:
                raise UserError('A recovery backup failed verification.')
            atomic_write(dest,backup)
        elif dest.exists():
            dest.unlink()
        self.mark_stale(p['month'],p['year'])
        with self.db:
            self.db.execute('DELETE FROM groups WHERE key=?',(row['group_key'],))
            if p['previous']:
                self.db.execute('INSERT INTO groups VALUES(?,?,?,?,?,?,?,?,?,?,?)',tuple(p['previous'][k] for k in GROUP_COLUMNS))
            self.db.execute("UPDATE actions SET status='undone' WHERE id=?",(row['id'],))

    def masters(self,month,year):
        self.ensure_recovered()
        rows=self.db.execute('SELECT * FROM groups WHERE month=? AND year=?',(month,year)).fetchall()
        contracts={}
        for r in rows:
            contracts.setdefault(r['contract'],[]).append(r)
        if not contracts:
            # A stale master after undoing the last client must never masquerade as current.
            raise UserError('There are no completed client PDFs for this period. Any old masters remain STALE and must not be used.')
        self.mark_stale(month,year)
        summary=[]
        active_paths=set()
        for contract,clients in sorted(contracts.items()):
            clients.sort(key=lambda r:(r['last'].casefold(),r['first'].casefold(),r['identity']))
            sources=[]
            for r in clients:
                p=self.path(r['path'])
                snapshot=p.read_bytes() if p.exists() else None
                if snapshot is None or digest(snapshot)!=r['hash']:
                    raise UserError('A client PDF is missing or changed. Restore it before generating masters.')
                sources.append(snapshot)
            content=merge_bytes(sources)
            pages=sum(r['pages'] for r in clients)
            verify(content,pages)
            # Contract slug stays stable even if there are sanitization collisions.
            slug=safe_component(contract)
            folder=self.folder('master')/slug
            dest=self.path(self.rel(folder/f'{safe_component(contract)}_DTL_{calendar.month_name[month]}_{year}_MASTER.pdf'))
            ownership=dest.with_suffix('.owner')
            token=digest(json.dumps([contract,month,year]).encode())
            if ownership.exists() and ownership.read_text()!=token:
                folder=folder.with_name(slug+'_'+digest(contract.encode())[:10])
                dest=self.path(self.rel(folder/dest.name))
                ownership=dest.with_suffix('.owner')
            if dest.exists() and (not ownership.exists() or ownership.read_text()!=token):
                raise UserError('An unmanaged PDF occupies a master output name. Move it safely before regeneration.')
            atomic_write(ownership,token.encode())
            atomic_write(dest.with_suffix('.STALE.txt'),b'STALE: Master regeneration in progress.\n')
            atomic_write(dest,content)
            verify(dest.read_bytes(),pages)
            active_paths.add(dest)
            summary.append((contract,len(clients),pages))
        # Only managed obsolete masters are removed. Originals and client PDFs are untouched.
        for p in self.folder('master').glob(f'*/*_DTL_{calendar.month_name[month]}_{year}_MASTER.pdf'):
            if p not in active_paths and p.with_suffix('.owner').exists():
                p.unlink()
                p.with_suffix('.owner').unlink(missing_ok=True)
                p.with_suffix('.STALE.txt').unlink(missing_ok=True)
        for p in active_paths:
            p.with_suffix('.STALE.txt').unlink(missing_ok=True)
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO masters VALUES(?,0)',(f'{year}-{month:02}',))
        return summary
