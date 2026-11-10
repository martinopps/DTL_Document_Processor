import pytest
from openpyxl import Workbook
from dtl.excel import import_clients, name_options, search_names, workbook_schema
from dtl.models import split_name, UserError

MAPPING=dict(full=0,number=1,contract=2,first=None,last=None)

def workbook(path,rows,headers=('Name','Client','Contract')):
    b=Workbook();w=b.active;w.title='Synthetic';w.append(headers)
    for r in rows:w.append(r)
    b.save(path)
    return path

def test_mapping_names_leading_zero_duplicates_contracts(tmp_path):
    p=workbook(tmp_path/'synthetic.xlsx',[
        ['Synthetic Alpha','0007','001'],['Synthetic Alpha','0007','002'],
        ['Synthetic Alpha','0008','001'],['Synthetic Beta','0009','002'],
        ['Synthetic Alpha','0007','001'],[None,None,None]])
    names,headers=workbook_schema(p)
    assert names==['Synthetic'] and headers==['Name','Client','Contract']
    cs,warnings=import_clients(p,'Synthetic',MAPPING)
    assert len(cs)==4 and len(warnings)==1
    assert name_options(cs)==['Synthetic Alpha','Synthetic Beta']
    assert search_names(cs,'alpha')==['Synthetic Alpha']
    assert search_names(cs,'synthetic')==name_options(cs)
    assert cs[0].number=='0007' and cs[0].contract=='001'

def test_separate_names_numeric_warning_and_format(tmp_path):
    p=workbook(tmp_path/'synthetic.xlsx',[['Test','van Example',12,3]],('First','Last','ID','Contract'))
    b=__import__('openpyxl').load_workbook(p);b.active['C2'].number_format='00000';b.save(p)
    cs,warnings=import_clients(p,'Synthetic',dict(first=0,last=1,number=2,contract=3))
    assert cs[0].name=='Test van Example' and cs[0].last=='van Example'
    assert cs[0].number=='00012' and warnings

@pytest.mark.parametrize('row', [['Synthetic Alpha',None,'A'],[None,'007','A'],['Synthetic Alpha','007',None]])
def test_missing_records_rejected(tmp_path,row):
    p=workbook(tmp_path/'synthetic.xlsx',[row])
    with pytest.raises(UserError):import_clients(p,'Synthetic',MAPPING)

def test_conflicting_identity(tmp_path):
    p=workbook(tmp_path/'synthetic.xlsx',[['Synthetic Alpha','007','A'],['Synthetic Beta','007','A']])
    with pytest.raises(UserError):import_clients(p,'Synthetic',MAPPING)

@pytest.mark.parametrize('name,expected', [('Alpha, Synthetic',('Synthetic','Alpha')),('Synthetic Alpha Jr.',('Synthetic','Alpha Jr.'))])
def test_name_extraction(name,expected):
    assert split_name(name)==expected
