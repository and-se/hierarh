import json
import models
from models import CafedraArticle, Cafedra, Episkop, EpiskopCafedra, EpiskopView, CafedraOfEpiskopView
from typing import List

import os
import re

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

    def get_cafedra_article(self, key: int) -> CafedraArticle:
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
        'cache_size': -1 * 10000,  # 10MB
        'foreign_keys': 1,
        #'ignore_check_constraints': 0,
        #'synchronous': 0
    })

    @db.func('LOWER_PY') #, deterministic=True)
    def lower(s):
        return s.lower() if s else None

    return db

DbName = 'hierarh.sqlite3'
Db = get_db(DbName)
Db.bind(models.AllDbModels)

# FIXME peewee now doesn't support DETERMINISTIC flag for sqlite functions, so we can't use thim in index on expression.
# But it already fixed on trunk - see https://github.com/coleifer/peewee/issues/2782
# Db.execute_sql('create index if not exists EpiskopsLowerPy on episkop(lower_py(name))')


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
            i=0
            for ar in book:
                try:
                    write_cafedra_article_into_db(ar)                    
                except Exception as ex:
                    print(ar.header)
                    raise
                else:
                    i+=1
                    if i%100==0:
                        print(f"{i} of {len(book)}")
    db.close()

def write_cafedra_article_into_db(ar: CafedraArticle):    
    caf = models.Cafedra.create(
        header=ar.header, is_obn=ar.is_obn,
        is_link=ar.is_link, # text=ar.text,
        article_json="TODO")

    for aep in ar.episkops:
        if isinstance(aep, str):
            continue  # TODO not table subheaders are skipped in db...
        if not aep.who:
            assert aep.unparsed_data is not None
            print(f'SKIP EPISKOP {caf.id} {caf.header}:\t{aep.unparsed_data}')  # TODO
            continue
            
        vy, who, paki = parse_episkop_str(aep.who)        
        if not who:
            print(f'EMPTY EPISKOP {caf.id} {caf.header}:\t{aep.who}')  # TODO

        ep = Episkop.select(Episkop.id).where(fn.LOWER_PY(Episkop.name) == who.lower()).get_or_none()
        if not ep:
            ep = Episkop.create(name=who)

        EpiskopCafedra.create(episkop=ep, cafedra=caf,
                              begin_dating=null_if_empty(aep.begin_dating),
                              begin_year = try_extract_year(aep.begin_dating),
                              end_dating=null_if_empty(aep.end_dating),
                              temp_status = vy,
                              again_status = paki
                             )
        
        aep.episkop_id = ep.id

    caf.article_json = json.dumps(ar.to_dict(), ensure_ascii=False, indent=4)
    caf.save()

        
        

def null_if_empty(s):
    return s if s else None

def parse_episkop_str(s):
    ss = s
    # remove note
    s = re.sub(r'<span\s+class="note"[^>]*>\s*\d+\s*</span>', '', s)
    s = re.match(r'''^\s*(?P<vy> \(?\s* в\s*/\s*у \s* \(?\s*\??\s*\)? \s*\)? )?
                    (?P<who>.*?)
                    (,\s*  (?P<paki>(паки)|(в\s+\d-й\s+раз))   )?
                    \s*$
                  ''', s, re.I | re.X)

    vy = s.group('vy')
    if vy:
        if '?' in vy:
            vy = 'в/y?'
        else:
            vy = 'в/y'
    
    return (vy, s.group('who').strip(), s.group('paki'))
    
    return s

def try_extract_year(s):
    m = re.match(r'.*\b(\d{3,4})$', s)
    if m:
        return int(m.group(1))



class PeeweeCafedraDb:
    @staticmethod
    def _build_search_condition(query, column):
        words = tuple(x.lower() for x in query.split())
        word_cond = lambda w: fn.INSTR(fn.LOWER_PY(column), w)
        
        if words:            
            cond = word_cond(words[0])
            for w in words[1:]:
                cond = cond & word_cond(w)
        else:
            cond = None

        return cond
    
    
    def get_cafedra_names(self, query: str=''):
        cond = self._build_search_condition(query, Cafedra.header)
        
        q = Cafedra.select(Cafedra.id, Cafedra.header)\
            .where(cond).order_by(Cafedra.header).tuples()

        # print(q, Db.execute_sql(f'EXPLAIN QUERY PLAN {q}').fetchall())
        
        for r in q:
            yield r

    def get_episkop_names(self, query: str=''):
        cond = self._build_search_condition(query, Episkop.name)

        for r in Episkop.select(Episkop.id, Episkop.name).where(cond).order_by(Episkop.name).tuples():
            yield r

    def get_cafedra_article(self, key: int) -> CafedraArticle:
        c = Cafedra.select(Cafedra.article_json).where(Cafedra.id==key).get_or_none()
        if c:
            return CafedraArticle.from_dict(json.loads(c.article_json))

    def get_episkop_view(self, key: int) -> EpiskopView:
        ep = Episkop.get(key)

        epv = EpiskopView(name=ep.name)
        for caf in ep.cafedras.order_by(EpiskopCafedra.begin_year):
            ecv = CafedraOfEpiskopView(
                cafedra=caf.build_cafedra_of_episkop_title(),
                cafedra_id = caf.cafedra.id,
                begin_dating = caf.begin_dating,
                end_dating = caf.end_dating
            )
            epv.cafedras.append(ecv)

        return epv

        
if __name__ == "__main__":
    build_db(db_name = DbName, remove_if_exists=True)
    print("Created cafedras:", models.Cafedra.select().count())
    print("Created episkops:", models.Episkop.select().count())
    
    
