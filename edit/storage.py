import re
import json
from typing import Iterator
from db import get_db, orm_all_words_search_condition
from edit.index import EpiskopIndex, EpiskopIndexOrm
from edit.task import TaskCollection, TaskOrm
import settings
from peewee import Model, AutoField, TextField, BooleanField, IntegerField, fn, Cast

DbName = settings.EditDbName
EditDb = None  # БД редактирования, инициализируется ниже

class HierarhEditStorage:
    def __init__(self, enable_ram_cache=True):
        self._enable_ram_cache = enable_ram_cache
        self.cafedra = TextCollectionDb('cafedra', CafedraEditOrm)
        self.episkop = TextCollectionDb('episkop', EpiskopEditOrm)
        self.task = TaskCollection()

        self._episkop_index = None

    @property
    def episkop_index(self):
        if not self._episkop_index:
            self._episkop_index = EpiskopIndex(self, copy_to_ram=self._enable_ram_cache)
        return self._episkop_index

    def get_coll(self, name) -> 'TextCollectionDb':
        r = {
            'cafedra': self.cafedra,
            'episkop': self.episkop
        }

        return r.get(name)

    def atomic(self):
        return EditDb.atomic()
    
    def backup_into(self, filename):
        EditDb.execute_sql("vacuum into ?", (filename,))



class TextCollectionDb:
    def __init__(self, name, orm_model: '_BaseEditOrm'):
        self.name = name
        self.orm = orm_model        
        self.text_model = self.orm._meta.target_text_model

    def new(self):
        return self.text_model()
        
    def _convert_orm_to_text(self, orm_item):
        return self.orm.to_text_model(orm_item)
    
    def upsert(self, doc: 'TextBase', reg_data:dict=None, fix_reg_data=True) -> 'TextBase':
        if not isinstance(doc, self.text_model):
            raise ValueError(f'Expected doc of type {self.text_model} got {type(doc)}')
            
        # create new or update current item
        if reg_data is not None:
            if not isinstance(reg_data, dict):
                raise ValueError("reg_data must be dict or None")
        else:
            reg_data = doc.reg_data or {}

        if fix_reg_data:
            from time import time as unix_now
            reg_data['when'] = unix_now()

        rgd = json.dumps(reg_data, ensure_ascii=False, indent=2)
        if doc.key:
            with EditDb.atomic(lock_type = 'IMMEDIATE'):
                doc.key = int(doc.key)
                old = self.orm.get_or_none(doc.key)
                if old:
                    num = self.version_count(doc.key) or 0
                    hist = old.to_version_orm(coll_name = self.name, num=num + 1)
                    hist.save()

                key2 = self.orm.replace(id=doc.key, header=doc.header(), html=doc.html, reg_data=rgd).execute()
                assert doc.key==key2
        else:
            doc.key = self.orm.create(header=doc.header(), html=doc.html, reg_data=rgd).id

        doc.reg_data = reg_data

        return doc
        
    def get(self, key) -> 'TextBase':        
        r = self.orm.get_or_none(key)
        if r:
            return self._convert_orm_to_text(r)
    
    def _portion_query(self, query):
        return self.orm.select() \
                    .where(orm_all_words_search_condition(query, self.orm.header)) \

    def portion(self, skip=0, take=20, query=None) -> list['TextBase']:
        q = self._portion_query(query) \
                    .order_by(self.orm.header) \
                    .limit(take).offset(skip)
        return [self._convert_orm_to_text(x) for x in q]
    
    def iterate(self, query=None) -> Iterator['TextBase']:
        i = 0
        step = 20        
        while(p:=self.portion(i, step, query)):
            for caf in p:
                yield caf
            i += 20

    def count(self, query=None):
        return self._portion_query(query).count()

    def _version_query(self, key):
        return VersionOrm.select().where((VersionOrm.doc_key == key) & \
                                      (VersionOrm.collection == self.name))

    def versions(self, key, skip=0, take=20, reverse=False):
        so = lambda x: x.desc() if reverse else x
        q = self._version_query(key) \
                      .order_by(so(VersionOrm.num), so(VersionOrm.id)) \
                      .limit(take).offset(skip)
        return [x.to_text_version() for x in q]
    
    def version(self, key, when):
        """
        получить версию документа по дате (reg_data.when)
        Если на эту отметку времени несколько версий - берётся самая последняя
        """
        r = self._version_query(key) \
            .where(fn.json_extract(VersionOrm.doc_reg_data, '$.when') == float(when)) \
            .order_by(VersionOrm.id.desc()) \
            .get_or_none()
   
        
        if r: return r.to_text_version()

    def version_count(self, key):
        return self._version_query(key).count()
    
    def find_by_name(self, name: str, limit=10):
        d = self.orm.select(self.orm.id, self.orm.header) \
            .where(fn.LOWER_PY(self.orm.header) == name.lower()).limit(limit).namedtuples()
        return list(d)
    
    def suggest(self, query, limit=10, full_search=False):
        """
        Реализует подсказку при вводе в текстовое поле поиска.
        full_search - искать по полному всему тексту (иначе только по заголовку)
        """
        if full_search:
            filter_field= self.orm.html
        else:
            filter_field = self.orm.header

        r = self.orm.select(self.orm.id, self.orm.header) \
            .where(orm_all_words_search_condition(query, filter_field)).order_by(self.orm.header).limit(limit)
        
        return [{'value': x.header, 'key': x.id} for x in r]
        



class TextBase:
    def __init__(self):
        self.key = None
        self.html = ""  # данные документа
        self.reg_data = {}

    def header(self):
        # предполагается, что все данные лежат в self.html,
        # а этот метод достаёт оттуда нужный кусок
        raise NotImplementedError('implement header method')
    
    def as_dict(self):
        return {
            'key': self.key,
            'header': self.header(),
            'html': self.html,
            'reg_data': self.reg_data
        }
    
    def __repr__(self):
        return f"Text~model({self.key}, {self.header()})"

    def __str__(self):
        return repr(self)

def text_model_from_html(model_class, key, html):
    doc = model_class()
    if key:
        key = int(key)
    doc.key = key
    doc.html = html
    return doc


class BaseCafEp(TextBase):
    def header(self):
        m = re.search(r'<div class="header">([^<]+)', self.html)
        return m.group(1) if m else self.html.strip().split('\n')[0]

    def is_obn(self):
        # <article class="cafedra_article" data-start-line="8" data-is-link="False" data-is-obn="False">
        m = re.search(r'<article [^>]*data-is-obn="([A-Za-z]+)"', self.html)
        if m:
            v = m.group(1)
            if v.strip().lower() in ['true', '1', 'yes', 'да']:
                return True
        return False

    @classmethod
    def from_html(cls, key, html):
        return text_model_from_html(cls, key, html)
    

class TextCafedra(BaseCafEp):
    def __init__(self):
        super().__init__()        
        self.html = """
        <article class="cafedra_article" data-is-obn="false">
            <div class="header">Заголовок...</div>
            <div class="text">Текст статьи...</div>
            <table class="episkops"></table>
        </article>
        """
   
        
class TextEpiskop(BaseCafEp):    
    def __init__(self):
        super().__init__()        
        self.html = f'''
        <article class="episkop_article" data-is-obn="false">
            <div class="header">Имя...</div>
            <div class="text">Текст...</div>            
            <table class="cafedras"></table>
        </article>
        '''
    
class TextVersion:
    def __init__(self, coll, key, html, reg_data: dict):
        self.collection = coll
        self.key = key
        self.html = html

        if not reg_data:
            reg_data = {}
        if not isinstance(reg_data, dict):
            raise ValueError('reg_data must be dict')
        self.reg_data = reg_data

    def __repr__(self):
        return f"TextVersion({self.collection} {self.key} {self.reg_data.get('when')})"

    def __str__(self):
        return repr(self)



### ORM ###

class _BaseEditOrm(Model):
    id = AutoField()
    header = TextField(index=True)
    html = TextField()
    reg_data = TextField()
    
    
    def to_version_orm(self, coll_name, num: int):
        return VersionOrm(collection = coll_name, doc_key = self.id, \
                          doc_data = self.html, \
                          doc_reg_data = self.reg_data,
                          num = num)
    

class CafedraEditOrm(_BaseEditOrm):
    class Meta:
        table_name = 'CafedraEdit'
        target_text_model = TextCafedra
    
    def to_text_model(self):
        r = TextCafedra.from_html(self.id, self.html)
        r.reg_data = json.loads(self.reg_data)
        assert isinstance(r.reg_data, dict)
        return r
        

class EpiskopEditOrm(_BaseEditOrm):
    class Meta:
        table_name = 'EpiskopEdit'
        target_text_model = TextEpiskop
    
    def to_text_model(self):
        r = TextEpiskop.from_html(self.id, self.html)
        r.reg_data = json.loads(self.reg_data)
        assert isinstance(r.reg_data, dict)
        return r
        

class VersionOrm(Model):
    class Meta:
        table_name = 'TextHistory'

    id = AutoField()
    collection = TextField()
    doc_key = IntegerField()
    doc_data = TextField()
    doc_reg_data = TextField()

    num = IntegerField()

    def to_text_version(self):
        return TextVersion(self.collection, self.doc_key, \
                           self.doc_data, json.loads(self.doc_reg_data))


VersionOrm.add_index(VersionOrm.collection, VersionOrm.doc_key)

def init_edit_db():
    global EditDb

    all_models = [CafedraEditOrm, EpiskopEditOrm, VersionOrm, TaskOrm, EpiskopIndexOrm] 

    EditDb = get_db(settings.EditDbName)
    EditDb.bind(all_models)
    EditDb.create_tables(all_models)
    return EditDb

init_edit_db()
