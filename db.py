import json
import models
from models import CafedraArticle, Cafedra
from typing import List

import os

def load_parsed_book(json_file: str) -> List[CafedraArticle]:
    db = json.load(open(json_file))
    assert isinstance(db, list)    
        
    for i in range(len(db)):
        db[i] = models.CafedraArticle.from_dict(db[i])

    return db


class SimpleCafedraDb:
    def __init__(self, json_file):
        self.db = load_parsed_book(json_file)

    def get_cafedra_names(self, query:str=''):
        q = QueryExecutor(query)            
        for (key, caf) in enumerate(self.db, 1):
            if q.match(caf.header):
                yield (key, caf.header)

    def get_article(self, key: int) -> CafedraArticle:
        return self.db[key-1] if key-1 < len(self.db) else None

class QueryExecutor:
    def __init__(self, query):
        self.q = tuple(x.lower() for x in query.split())        

    def match(self, data: str):
        data = data.lower()
        for w in self.q:
            if w not in data:
                return False
        return True

##################### Peewee ORM Db ####################

from peewee import fn, SQL, SqliteDatabase

def get_db(db_name: str):
    db = SqliteDatabase(db_name, {
        'journal_mode': 'wal',
        'cache_size': -1 * 64000,  # 64MB
        'foreign_keys': 1,
        #'ignore_check_constraints': 0,
        #'synchronous': 0
    })

    @db.func('LOWER_PY')
    def lower(s):
        return s.lower()

    return db

DbName = 'hierarh.sqlite3'

def build_db(parsed_book_json = 'articles.json', db_name = DbName, remove_if_exists=False):    
    book = load_parsed_book(parsed_book_json)

    if os.path.exists(db_name):
        if remove_if_exists:
            os.remove(db_name)
        else:
            raise Exception(f"Db {db_name} exists")

    db = get_db(db_name)    

    with db.bind_ctx(models.AllDbModels):
        db.create_tables(models.AllDbModels)
        with db.atomic() as tr:
            for ar in book:
                try:
                    write_cafedra_article_into_db(ar)                    
                except Exception as ex:
                    print(ar.header)
                    raise
    db.close()

def write_cafedra_article_into_db(ar: CafedraArticle):    
    models.Cafedra.create(
        header=ar.header, is_obn=ar.is_obn,
        is_link=ar.is_link, text=ar.text,
        article_json=json.dumps(ar.to_dict(), ensure_ascii=False, indent=4))
    

Db = get_db(DbName)
Db.bind(models.AllDbModels)

class PeeweeCafedraDb:
    def get_cafedra_names(self, query: str=''):
        words = tuple(x.lower() for x in query.split())
        word_cond = lambda w: fn.INSTR(fn.LOWER_PY(Cafedra.header), w)
        
        if words:            
            cond = word_cond(words[0])
            for w in words[1:]:
                cond = cond & word_cond(w)
        else:
            cond = None
    
        q = Cafedra.select(Cafedra.id, Cafedra.header)\
            .where(cond).order_by(Cafedra.header).tuples()

        print(q, Db.execute_sql(f'EXPLAIN QUERY PLAN {q}').fetchall())
        
        for r in q:
            yield r

    def get_article(self, key: int) -> CafedraArticle:
        c = Cafedra.select(Cafedra.article_json).where(Cafedra.id==key).get_or_none()
        if c:
            return CafedraArticle.from_dict(json.loads(c.article_json))
        


        
if __name__ == "__main__":
    build_db(db_name = DbName, remove_if_exists=True)
    print("Created cafedras:", models.Cafedra.select().count())
    
    
