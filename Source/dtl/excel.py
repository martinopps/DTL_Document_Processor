from collections import defaultdict
from openpyxl import load_workbook
from .models import Client, UserError, split_name


def workbook_schema(path, sheet=None, header_row=1):
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        names = book.sheetnames
        ws = book[sheet or names[0]]
        headers = [str(c.value or '').strip() for c in next(ws.iter_rows(min_row=header_row,max_row=header_row))]
        return names,headers
    finally:
        book.close()


def import_clients(path, sheet, mapping, header_row=1):
    book = load_workbook(path, read_only=True, data_only=True)
    clients,seen,warnings = [],set(),set()
    try:
        for row in book[sheet].iter_rows(min_row=header_row+1):
            if not any(c.value is not None for c in row):
                continue
            def value(key, identifier=False):
                idx = mapping.get(key)
                if idx is None or idx>=len(row) or row[idx].value is None:
                    return ''
                cell = row[idx]
                v = cell.value
                if identifier and isinstance(v,(float,int)):
                    warnings.add('Numeric identifiers were found. Verify leading zeroes against an approved source; Excel may have lost them.')
                    if isinstance(v,float) and not v.is_integer():
                        raise UserError('A numeric identifier has a fractional value. Correct it to text in an approved workbook copy.')
                    if cell.number_format and set(cell.number_format)=={'0'}:
                        return str(int(v)).zfill(len(cell.number_format))
                    return str(int(v))
                return str(v).strip()
            first,last = value('first'),value('last')
            name = value('full') if mapping.get('full') is not None else ' '.join(filter(None,[first,last]))
            if not name:
                raise UserError('A populated row has no mapped name. Correct the mapping or workbook copy.')
            if not last:
                first,last = split_name(name)
            number,contract = value('number',True),value('contract',True)
            if not number or not contract or not last:
                raise UserError('A row is missing a required name, client number, or contract. Correct the mapping or workbook copy.')
            key = (name,number,contract)
            if key in seen:
                warnings.add('Exact duplicate assignments were ignored.')
                continue
            seen.add(key)
            clients.append(Client(name,first,last,number,contract))
        identities = defaultdict(set)
        for c in clients:
            identities[c.number].add((c.name,c.first,c.last))
        if any(len(v)>1 for v in identities.values()):
            raise UserError('One client number has conflicting names. Resolve those records before importing.')
        if not clients:
            raise UserError('No complete client assignments were found.')
        return sorted(clients,key=lambda c:(c.last.casefold(),c.first.casefold(),c.number,c.contract)),sorted(warnings)
    finally:
        book.close()


def name_options(clients):
    return sorted({c.name for c in clients},key=str.casefold)


def search_names(clients, query):
    return [n for n in name_options(clients) if all(p in n.casefold() for p in query.casefold().split())]
