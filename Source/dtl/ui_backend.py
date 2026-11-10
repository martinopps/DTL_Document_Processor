"""Presentation-facing service interface for the local processing engine."""
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from .models import UserError, money
from .excel import workbook_schema, name_options
from .pdf import Stamp, stamped_bytes
from .storage import Store as ProcessingStore, atomic_write, digest

@dataclass(frozen=True)
class Copay:
    required: str
    amount: Decimal
    paid: Decimal | None

    @classmethod
    def parse(cls, required, amount, paid):
        if required not in ('Yes', 'No'):
            raise UserError('Select Yes or No for Copay Required for this document.')
        return cls(required, money(amount), money(paid, True))


def names(clients, query=''):
    return [n for n in name_options(clients) if query.casefold() in n.casefold()]


def sheets(path):
    return workbook_schema(path)[0]


def headers(path, sheet, row=1):
    return workbook_schema(path, sheet, row)[1]


def stamp_object(client, copay, position, font_size):
    return Stamp(client.name, client.number, client.contract, copay.required,
                 f'{copay.amount:.2f}', None if copay.paid is None else f'{copay.paid:.2f}',
                 'Top margin' if position == 'Add top margin' else position, font_size)


def stamp(source, target, client, copay, position='Upper left', font_size=10):
    atomic_write(target, stamped_bytes(source, stamp_object(client, copay, position, font_size)))


class Store:
    """Keep view settings and engine storage settings in one persisted record."""
    KEYS = {'Intake':'intake', 'Processed_Originals':'archive', 'Contract_Output':'output', 'Flagged':'flagged', 'Master_Contracts':'master'}

    def __init__(self, root):
        self.engine = ProcessingStore(root)
        self.root = self.engine.root
        self.db = self.engine.db

    def close(self):
        self.engine.close()

    def load_settings(self):
        s = dict(self.engine.settings)
        s['folders'] = {name:s[key] for name,key in self.KEYS.items()}
        s.setdefault('position', 'Upper left')
        s.setdefault('font', s['font_size'])
        return s

    def settings(self, value):
        previous = dict(self.engine.settings)
        candidate = dict(value)
        for name,key in self.KEYS.items():
            candidate[key] = candidate.get('folders', {}).get(name, previous[key])
        candidate['placement'] = 'Top margin' if candidate.get('position') == 'Add top margin' else candidate.get('position', 'Upper left')
        candidate['font_size'] = candidate.get('font', 10)
        try:
            self.engine.validate_folders(candidate)
            self.engine.settings.update(candidate)
            self.engine.save_settings()
        except Exception:
            self.engine.settings = previous
            raise

    def within(self, path):
        return self.engine.path(self.engine.rel(path))

    def folder(self, name):
        return self.engine.folder(self.KEYS[name])

    def queue(self):
        translation = {'Queued':'queued', 'Processed':'processed', 'Flagged':'flagged', 'Copying / wait':'copying', 'Unavailable':'unavailable'}
        items = [(p, translation[s], None) for p,s in self.engine.queue()]
        seen = {p for p,s,h in items}
        for row in self.db.execute("SELECT archive FROM actions WHERE status='done' ORDER BY created"):
            p = self.engine.path(row['archive'])
            if p.exists() and p not in seen:
                items.append((p, 'processed', None))
        return items

    def flag(self, source):
        self.engine.flag(source)

    def unflag(self, source):
        self.engine.unflag(source)

    def archived_for(self, source):
        row = self.db.execute("SELECT archive FROM actions WHERE source=? AND status='done' ORDER BY created DESC LIMIT 1", (self.engine.rel(source),)).fetchone()
        return self.engine.path(row['archive']) if row else source

    def undo(self):
        return self.engine.undo()

    def process(self, source, client, copay, month, year, position='Upper left', font_size=10, expected_digest=None):
        return self.engine.process(source, client, month, year, stamp_object(client, copay, position, font_size), confirmed=True, expected_digest=expected_digest)

    def masters(self, month, year):
        return [(c,n) for c,n,pages in self.engine.masters(month, year)]
