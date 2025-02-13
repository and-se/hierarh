import re
import json
from db import get_db, orm_all_words_search_condition
import settings
from peewee import Model, AutoField, TextField, BooleanField, IntegerField

DbName = settings.EditDbName
EditDb = None  # БД редактирования, инициализируется ниже

class HierarhEditStorage:
    def __init__(self):
        self.cafedra = TextCollectionDb('cafedra', CafedraEditOrm)

    def atomic(self):
        return EditDb.atomic()



class TextCollectionDb:
    def __init__(self, name, orm_model):
        self.name = name
        self.orm = orm_model

    def new(self):
        doc = TextCafedra()
        return doc

    def upsert(self, doc: 'TextCafedra', reg_data:dict=None, fix_reg_data=True) -> 'TextCafedra':
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
                old = self.orm.get(doc.key)
                if old:
                    num = self.version_count(doc.key) or 0
                    hist = old.toVersionOrm(coll_name = self.name, num=num + 1)
                    hist.save()

                key2 = self.orm.replace(id=doc.key, header=doc.header(), html=doc.html, reg_data=rgd).execute()
                assert doc.key==key2
        else:
            doc.key = self.orm.create(header=doc.header(), html=doc.html, reg_data=rgd).id

        doc.reg_data = reg_data

        return doc

    def get(self, key):
        # get from db
        r = self.orm.get_or_none(key)
        if r:
            return r.toTextCafedra()

    def _portion_query(self, query):
        return self.orm.select() \
                    .where(orm_all_words_search_condition(query, self.orm.header)) \

    def portion(self, skip=0, take=20, query=None):
        q = self._portion_query(query) \
                    .order_by(self.orm.header) \
                    .limit(take).offset(skip)
        return [x.toTextCafedra() for x in q]

    def count(self, query=None):
        return self._portion_query(query).count()

    def _version_query(self, key):
        return VersionOrm.select().where((VersionOrm.doc_key == key) & \
                                      (VersionOrm.collection == self.name))

    def versions(self, key, skip=0, take=20):
        q = self._version_query(key) \
                      .order_by(VersionOrm.num, VersionOrm.id) \
                      .limit(take).offset(skip)
        return [x.toTextVersion() for x in q]

    def version_count(self, key):
        return self._version_query(key).count()



class TextCafedra:
    def __init__(self):
        self.key = None
        self.html = """
        <article class="cafedra_article" data-is-obn="false">
            <div class="header">Заголовок...</div>
            <div class="text">Текст статьи...</div>
            <table class="episkops"></table>
        </article>
        """
        self.reg_data = {}

    @staticmethod
    def from_html(key, html):
        doc = TextCafedra()
        if key:
            key = int(key)
        doc.key = key
        doc.html = html
        return doc

    def header(self):
        m = re.search(r'<div class="header">([^<]+)', self.html)
        return m.group(1) if m else self.html.strip().split('\n')[0]

    def is_obn(self):
        return False  # ...

    def __repr__(self):
        return f"TextCafedra({self.key}, {self.header()})"

    def __str__(self):
        return repr(self)

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

class CafedraEditOrm(Model):
    class Meta:
        table_name = 'CafedraEdit'

    id = AutoField()
    header = TextField(index=True)
    html = TextField()
    reg_data = TextField()

    def toTextCafedra(self):
        r = TextCafedra.from_html(self.id, self.html)
        r.reg_data = json.loads(self.reg_data)
        assert isinstance(r.reg_data, dict)
        return r

    def toVersionOrm(self, coll_name, num: int):
        return VersionOrm(collection = coll_name, doc_key = self.id, \
                          doc_data = self.html, \
                          doc_reg_data = self.reg_data,
                          num = num)

class VersionOrm(Model):
    class Meta:
        table_name = 'TextHistory'

    id = AutoField()
    collection = TextField()
    doc_key = IntegerField()
    doc_data = TextField()
    doc_reg_data = TextField()

    num = IntegerField()

    def toTextVersion(self):
        return TextVersion(self.collection, self.doc_key, \
                           self.doc_data, json.loads(self.doc_reg_data))


VersionOrm.add_index(VersionOrm.collection, VersionOrm.doc_key)


def init_edit_db():
    global EditDb
    EditDb = get_db(settings.EditDbName)
    EditDb.bind([CafedraEditOrm, VersionOrm])
    EditDb.create_tables([CafedraEditOrm, VersionOrm])
    return EditDb

init_edit_db()


if __name__ == '__main__':
    test()
