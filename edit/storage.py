import re
import json
from db import get_db, orm_all_words_search_condition
import settings
from peewee import Model, AutoField, TextField, BooleanField

DbName = settings.EditDbName

class HierarhEditStorage:
    def __init__(self):
        self.cafedra = TextCollectionDb('cafedra', CafedraEditOrm)

    def atomic(self):
        return EditDb.atomic()



class TextCollectionDb:
    def __init__(self, name, orm_model):
        self.name = name
        self.orm = orm_model

    def portion(self, skip=0, take=20, query=None):
        q = self.orm.select(self.orm.id, self.orm.html, self.orm.reg_data) \
                    .where(orm_all_words_search_condition(query, self.orm.header)) \
                    .order_by(self.orm.header) \
                    .limit(take).offset(skip)
        return [x.toTextCafedra() for x in q]

    def new(self):
        doc = TextCafedra()
        return doc

    def upsert(self, doc: 'TextCafedra', reg_data:dict=None) -> 'TextCafedra':
        # create new or update current item
        if reg_data is not None:
            if not isinstance(reg_data, dict):
                raise ValueError("reg_data must be dict or None")
        else:
            reg_data = doc.reg_data

        if 'when' not in reg_data:
            from time import time as unix_now
            reg_data['when'] = unix_now()

        rgd = json.dumps(reg_data)
        if doc.key:
            doc.key = int(doc.key)
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


### ORM ###

class CafedraEditOrm(Model):
    class Meta:
        table_name = 'CafedraEdit'

    id = AutoField()
    header = TextField(index=True)
    html = TextField(null=False)
    reg_data = TextField(null=True)

    def toTextCafedra(self):
        r = TextCafedra.from_html(self.id, self.html)
        r.reg_data = json.loads(self.reg_data)
        return r


EditDb = None

def init_edit_db():
    global EditDb
    EditDb = get_db(settings.EditDbName)
    EditDb.bind([CafedraEditOrm])
    EditDb.create_tables([CafedraEditOrm])
    return EditDb

init_edit_db()

#############  TEST ##############

if __name__ == '__main__':
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))



def test():
    caf = HierarhEditStorage().cafedra
    print("PORTION", caf.portion())

    print("UPDATE key=2")
    doc = caf.get(2)
    if not doc:
        print("FAIL => CREATE key=2")
        doc = caf.upsert(2, "new 2 ar")
    print(doc)
    print("HEADER key=2", doc.header())
    from datetime import datetime
    doc.html = "UPDATED " + str(datetime.now())
    doc = caf.upsert(doc)
    print("after: ", doc)
    print(caf.portion(), '\n')

    print("KEY=123", caf.get(123), '\n')

    print("NEW")
    doc = caf.new()
    doc.html = "THE NEW"
    print(doc)
    doc = caf.upsert(doc)
    print("after:", doc)
    print(caf.portion())
    print()

if __name__ == '__main__':
    test()
