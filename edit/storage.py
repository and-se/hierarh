import re

class HierarhEditStorage:
    def __init__(self, mode="db"):
        if mode=='test':
            self.cafedra = TestTextCollection('cafedra')
        else:
            self.cafedra = TextCollectionDb('cafedra', CafedraEditOrm)



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


############# ORM ################

from peewee import Model, AutoField, TextField, BooleanField

class TextCollectionDb:
    def __init__(self, name, orm_model):
        self.name = name
        self.orm = orm_model

    def portion(self, skip=0, take=20, query=None):
        q = self.orm.select(self.orm.id, self.orm.html).order_by(self.orm.header).limit(take).offset(skip)
        return [TextCafedra.from_html(x.id, x.html) for x in q]

    def new(self):
        doc = TextCafedra()
        return doc

    def upsert(self, key, html=None):
        # create new or update current item
        if isinstance(key, TextCafedra):
            key, html = key.key, key.html

        doc = TextCafedra.from_html(key, html)

        if key:
            key = int(key)
            key2 = self.orm.replace(id=key, header=doc.header(), html=html).execute()
            assert key==key2
            doc.key = key
        else:
            doc.key = self.orm.create(header=doc.header(), html=html).id

        return doc

    def get(self, key):
        # get from db
        r = self.orm.get_or_none(key)
        if r:
            return TextCafedra.from_html(r.id, r.html)


class CafedraEditOrm(Model):
    class Meta:
        table_name = 'CafedraEdit'

    id = AutoField()
    header = TextField(index=True)
    html = TextField(null=False)

if __name__ == '__main__':
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))

#import sys
#print(sys.path)
from db import get_db

DbName = 'data/hierarh-edit.sqlite3'

Edit_db = get_db(DbName)
Edit_db.bind([CafedraEditOrm])

Edit_db.create_tables([CafedraEditOrm])



#############  TEST ##############


def load_test_file(key, path):
    with open(path) as f:
        html = f.read()
        return TextCafedra.from_html(key, html)

TCAF = {
    1: TextCafedra.from_html(1, "cafedra 1\n<b>some text</b>"),
    2: TextCafedra.from_html(2, "cafedra 2\n<b>some text 2</b>"),
    3: TextCafedra.from_html(3, "cafedra 3\n<b>some text 3</b>"),
    4: load_test_file(4, 'edit/testdata/1.html'),
    5: load_test_file(5, 'edit/testdata/2.html'),
}


class TestTextCollection:
    def __init__(self, name):
        self.name = name

    def portion(self, skip=0, take=20, query=None):
        return [x for x in TCAF.values()]

    def new(self):
        doc = TextCafedra()
        return doc

    def upsert(self, key, html=None):
        # create new or update current item

        if isinstance(key, TextCafedra):
            key, html = key.key, key.html

        if key:
            key = int(key)

        global TCAF
        if key in TCAF:
            doc = TCAF[key]
            doc.html = html
        else:
            if not key:
                key = max(TCAF.keys())+1
            doc = TextCafedra.from_html(key, html)
            TCAF[key] = doc

        return doc

    def get(self, key):
        # get from db
        return TCAF.get(key)


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
