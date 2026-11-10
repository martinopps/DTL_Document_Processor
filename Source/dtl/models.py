from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import re
import unicodedata

class UserError(Exception):
    """Non-identifying message suitable for display."""

@dataclass(frozen=True)
class Client:
    name: str
    first: str
    last: str
    number: str
    contract: str

    @property
    def identity(self):
        return hashlib.sha256(self.number.encode()).hexdigest()


def money(value, optional=False):
    value = value.strip().removeprefix('$').strip()
    if not value and optional:
        return None
    if not re.fullmatch(r'\d+(?:\.\d{1,2})?', value):
        raise UserError('Enter a nonnegative amount with at most two decimal places, such as 25.00.')
    try:
        amount = Decimal(value).quantize(Decimal('.01'))
        if amount > Decimal('999999999.99'):
            raise InvalidOperation
        return amount
    except InvalidOperation:
        raise UserError('The currency amount is too large.') from None


def safe_component(value):
    value = unicodedata.normalize('NFKC', str(value)).strip()
    if not value or value in {'.', '..'} or '/' in value or '\\' in value or any(ord(c)<32 for c in value):
        raise UserError('A filename or identifier contains unsafe characters. Correct the source or selection.')
    result = re.sub(r'[^\w .-]', '_', value).strip(' .')[:100].rstrip(' .')
    if not result:
        raise UserError('An identifier or filename is empty after cleanup.')
    # Device names remain reserved even with an extension on Windows.
    stem = result.split('.')[0].rstrip(' ').upper()
    if stem in {'CON','PRN','AUX','NUL','CONIN$','CONOUT$'} or re.fullmatch(r'(COM|LPT)[1-9¹²³]', stem):
        result = '_' + result
    return result


def split_name(full):
    full = ' '.join(full.split())
    if ',' in full:
        last,first = full.split(',',1)
        return first.strip(),last.strip()
    parts = full.split()
    end = -2 if len(parts)>1 and parts[-1].lower() in {'jr','jr.','sr','sr.','ii','iii','iv'} else -1
    return ' '.join(parts[:end]),' '.join(parts[end:])
