from chain import Chain, ChainLink

from book_parser import CafedraArticlesFromJson
from article_parser import CafedraArticleParser, WholeRussiaCafedraFixer,\
                           CafedraJsonPatcher, UnparsedCafedraEpiskopLogger

import models
from models import CafedraOrm, EpiskopOrm, EpiskopCafedraOrm, NoteOrm
from models import Cafedra, ArticleNote, EpiskopInfo
from models import CafedraDto, EpiskopDto, \
                   EpiskopOfCafedraDto, CafedraOfEpiskopDto
from models import UserCommentOrm, UserComment

import human


import json
import os
from collections import Counter
from typing import Tuple, Iterable
from datetime import datetime


class HistHierarhStorageBase:
    def get_cafedra_names(self, query: str = '') \
                -> Iterable[Tuple[int, str, bool]]:
        """
        returns tuples (cafedra id, cafedra header, is obn)
        """
        raise NotImplementedError()

    def get_episkop_names(self, query: str = '') \
            -> Iterable[Tuple[int, str, bool]]:
        """
        returns tuples (episkop id, episkop name, is obn)
        """
        raise NotImplementedError()

    def get_cafedra_data(self, key: int) -> CafedraDto:
        raise NotImplementedError()

    def get_episkop_data(self, key: int) -> EpiskopDto:
        raise NotImplementedError()

    def count_cafedra(self, query: str = '') -> int:
        raise NotImplementedError()

    def count_episkop(self, query: str = '') -> int:
        raise NotImplementedError()

    def begin_transaction(self):
        raise NotImplementedError()

    def commit(self):
        raise NotImplementedError()

    def rollback(self):
        raise NotImplementedError()


# ----------------- Peewee ORM Db ----------------

from peewee import fn, SqliteDatabase, PeeweeException  # noqa: E402


def get_db(db_name: str):
    db = SqliteDatabase(db_name, {
        'journal_mode': 'wal',
        'cache_size': -1 * 10000,  # 10MB
        'foreign_keys': 1,
        # 'ignore_check_constraints': 0,
        # 'synchronous': 0
    })

    @db.func('LOWER_PY', deterministic=True)
    def lower(s):
        return s.lower() if s else None

    return db

# Global db settings


DbName = 'data/hierarh.sqlite3'
_Db = get_db(DbName)
_Db.bind(models.HierarhOrmModels)

DbCommentsName = 'data/hierarh.comments.sqlite3'
_DbComments = get_db(DbCommentsName)
_DbComments.bind(models.CommentOrmModels)

def _create_sqlite_db(db_name, schema_creator, when_exists='fail'):
    if os.path.exists(db_name):
        match when_exists:
            case 'remove':
                os.remove(db_name)
            case 'fail':
                raise Exception(f"Db {db_name} exists")
            case 'skip':
                return
            case _:
                raise Exception(f'Wrong action when_exists={when_exists}. '
                                f"Expected 'fail', 'remove' or 'skip'")

    db = get_db(db_name)
    schema_creator(db)
    db.close()

class PeeweeHistHierarhStorage(HistHierarhStorageBase):
    @staticmethod
    def create_new_sqlite_db(remove_if_exists):
        def schema_creator(db):
            with db.bind_ctx(models.HierarhOrmModels):
                db.create_tables(models.HierarhOrmModels)

        _create_sqlite_db(DbName, schema_creator,
                          'remove' if remove_if_exists else 'fail')

    # Now we use global _Db object bound to HierarhOrmModels, so all
    # PeeweeHistHierarhStorage objects are automatically connected
    # to one sqlite Db named DbName.
    # If you want manage db connection manually (and possible use
    # different dbs), uncomment this code and use 'with self.ctx():'
    # for all db operations in this class
    # def __init__(self, db: peewee.Database):
    #     self.db = db
    # def ctx(self):
    #     return self.db.bind_ctx(models.HierarhOrmModels)

    def begin_transaction(self):
        _Db.begin()

    def commit(self):
        _Db.commit()

    def rollback(self):
        _Db.rollback()

    @staticmethod
    def _build_search_condition(query, column):
        words = tuple(x.lower() for x in query.split())

        def word_cond(w):
            return fn.INSTR(fn.LOWER_PY(column), w)

        if words:
            cond = word_cond(words[0])
            for w in words[1:]:
                cond = cond & word_cond(w)
        else:
            cond = None

        return cond

    def _cafedra_q(self, query):
        cond = self._build_search_condition(query, CafedraOrm.header)
        # with self.ctx():
        q = CafedraOrm.select(CafedraOrm.id,
                              CafedraOrm.header,
                              CafedraOrm.is_obn) \
            .where(cond).order_by(CafedraOrm.header)
        # print(q, _Db.execute_sql(f'EXPLAIN QUERY PLAN {q}').fetchall())
        return q

    def get_cafedra_names(self, query: str = ''):
        q = self._cafedra_q(query).tuples()
        for r in q:
            yield r

    def count_cafedra(self, query: str = ''):
        q = self._cafedra_q(query).count()
        return q

    def _episkop_q(self, query):
        cond = self._build_search_condition(query, EpiskopOrm.header)
        q = EpiskopOrm.select(EpiskopOrm.id,
                              EpiskopOrm.header,
                              EpiskopOrm.is_obn) \
                      .where(cond) \
                      .order_by(EpiskopOrm.name, EpiskopOrm.surname)
        return q

    def get_episkop_names(self, query: str = ''):
        q = self._episkop_q(query)
        for r in q.tuples():
            yield r

    def count_episkop(self, query: str = ''):
        q = self._episkop_q(query)
        return q.count()

    def get_cafedra_data(self, key: int) -> CafedraDto:
        c = CafedraOrm.select(CafedraOrm.id, CafedraOrm.article_json) \
                      .where(CafedraOrm.id == key).get_or_none()
        if c:
            r = CafedraDto.from_dict(json.loads(c.article_json))
            return r

    def get_episkop_data(self, key: int) -> EpiskopDto:
        ep = EpiskopOrm.get(key)

        epv = EpiskopDto(header=ep.header, is_obn=ep.is_obn, id=key)

        cnt = Counter()
        for caf in ep.cafedras.order_by(
                            EpiskopCafedraOrm.estimated_begin_date):
            cnt.update([caf.cafedra.id])
            ecv: CafedraOfEpiskopDto = caf.to_cafedra_of_episkop_dto(
                                            cnt[caf.cafedra.id]
                                       )
            epv.cafedras.append(ecv)

        return epv

    def upsert_cafedra(self, caf: Cafedra):
        caf_orm = CafedraOrm.create(
            header=caf.header, is_obn=caf.is_obn,
            is_link=caf.is_link,  # text=caf.text,
            article_json="TODO")

        # TODO use Cafedra object, don't use Dto
        cafjson = models.CafedraDto(
            header=caf.header,
            is_obn=caf.is_obn, is_link=caf.is_link,
            text=caf.text,
            id = caf_orm.id
        )

        cnt = Counter()
        for i, ep in enumerate(caf.episkops, 1):
            if isinstance(ep, str):
                cafjson.episkops.append(ep)
                continue  # TODO now table subheaders are skipped in db...

            ep.episkop: EpiskopInfo
            is_obn = caf.is_obn

            # fixme: now we possibly merge people with same name+surname
            ep_orm = self.find_episkop(ep.episkop.name, ep.episkop.surname)
            if not ep_orm:
                ep_orm = EpiskopOrm.create(header=ep.episkop
                                           .get_header(is_obn),
                                           name=ep.episkop.name,
                                           surname=ep.episkop.surname,
                                           saint_title=ep.episkop.saint_title,
                                           # todo check is it always correct?
                                           is_obn=is_obn
                                           )

            ep.episkop.id = ep_orm.id
            # Отдельно считаем количество раз для в/у и "настоящего"
            cnt[(ep.episkop.id, bool(ep.temp_status))] += 1

            beg = ep.begin_dating
            end = ep.end_dating

            EpiskopCafedraOrm.create(
                episkop=ep_orm, cafedra=caf_orm,
                begin_dating=beg.dating if beg else None,
                estimated_begin_date=beg.estimated_date if beg
                else None,
                end_dating=end.dating if end else None,
                temp_status=ep.temp_status,
                episkop_num=i,
                inexact=ep.inexact
            )

            epjson: EpiskopOfCafedraDto = \
                ep.to_episkop_of_cafedra_dto(cnt[(ep.episkop.id,
                                             bool(ep.temp_status))], is_obn)

            if ep.notes:
                epjson.episkop += ' '.join([
                        f'<span class="note" data-note="{i}">{i}</span>'
                        for i in ep.notes
                ])

            epjson.notes = [ArticleNote(num=note.num, text=note.text)
                            for note in caf.notes
                            if note.num in ep.notes]
            caf.notes = [note for note in caf.notes if note.num not in ep.notes]

            cafjson.episkops.append(epjson)

        cafjson.notes = [ArticleNote(num=x.num, text=x.text)
                         for x in caf.notes]  # TODO now no notes in db

        caf_orm.article_json = json.dumps(cafjson.to_dict(),
                                          ensure_ascii=False, indent=4)
        caf_orm.save()

        for note in caf.notes:
            note_orm = NoteOrm.create(
                text=note.text,
                cafedra_id=caf_orm.id,
                #TODO episkop_cafedra_id=
            )
            note_orm.save()


    def find_episkop(self, name, surname=None) -> EpiskopOrm | None:
        if not name:
            raise ValueError('name must be not empty!')
        if name == 'NN' and not surname:
            return None  # NN is unknown man, so two NNs are different
        cond = fn.LOWER_PY(EpiskopOrm.name) == name.lower()
        if surname:
            cond = cond & (fn.LOWER_PY(EpiskopOrm.surname) == surname.lower())
        else:
            cond = cond & EpiskopOrm.surname.is_null()

        ep_qq = EpiskopOrm.select().where(cond)

        # print(ep_qq,
        #       _Db.execute_sql(f'EXPLAIN QUERY PLAN {ep_qq}').fetchall())

        return ep_qq.get_or_none()


class PeeweeUserCommentsStorage:
    @staticmethod
    def create_new_sqlite_db(remove_if_exists):
        def schema_creator(db):
            with db.bind_ctx(models.CommentOrmModels):
                db.create_tables(models.CommentOrmModels)

        _create_sqlite_db(DbCommentsName, schema_creator,
                          'remove' if remove_if_exists else 'skip')

    def create(self, data: UserComment) -> UserComment:
        data.id = None
        data.timestamp = datetime.now()

        try:
            orm = UserCommentOrm.create(**data.dict())
        except PeeweeException as ex:
            raise StorageException(ex)
        else:
            return UserComment.model_validate(orm, from_attributes=True)

    def get_all(self):
        return [
            UserComment.model_validate(orm) \
            for orm in UserCommentOrm.select() \
                       .order_by(UserCommentOrm.timestamp.desc()).dicts()
        ]

class StorageException(Exception):
    pass

# -------------- End Peewee -------------


class CafedraDbImporter(ChainLink):
    def __init__(self, db: HistHierarhStorageBase):
        self.db = db
        self.db.begin_transaction()

    @human.show_exception
    def process(self, s: Cafedra):
        self.db.upsert_cafedra(s)

    def finish(self):
        self.db.commit()


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("""add these parameters:
        build main - delete old and rebuild main db.
                     comments db will be created if not exists

        build all - delete old and rebuild main db.
                    comments db will be recreated (old comments will be lost!)
                    
        build main-old - delete old and rebuild main db using 'cafedra_articles.json' file 
                    generated from xml. Text data contains many abbreviations.
                    In 'main' mode they are resolved.

        create comments - only create comments db if not exists
        reset comments - delete old and recreate comments db
                         (old comments will be lost!)
        """)
        sys.exit(1)

    cmd, arg = sys.argv[1:]

    if cmd == 'build' and arg in ('main', 'all', 'main-old'):
        PeeweeHistHierarhStorage.create_new_sqlite_db(remove_if_exists=True)
        db = PeeweeHistHierarhStorage()

        f = (arg=='all')
        PeeweeUserCommentsStorage.create_new_sqlite_db(remove_if_exists=f)

        patch_file = 'data/patch/cafedra-episkop-patch.txt'
        if arg == 'main-old':
            patch_file = 'data/patch/cafedra-episkop-patch-old.txt'

        ch = Chain(CafedraArticlesFromJson()) \
            .add(CafedraJsonPatcher(patch_file)) \
            .add(CafedraArticleParser()) \

        # comment this when using sample_cafedry.xml
        ch = ch.add(WholeRussiaCafedraFixer())

        ch = ch.add(UnparsedCafedraEpiskopLogger('data/cafedra-episkop-fail.txt')) \
               .add(CafedraDbImporter(db))

        if arg == 'main-old':
            ch.process('data/cafedra_articles.json')  # old file built from xml
        else:
            # new file base on old cafedra_articles.json with expanded abbreviations.
            ch.process('data/cafedra_articles_expand_abbrs.json')

        print("Created cafedras:", db.count_cafedra())
        print("Created episkops:", db.count_episkop())
    elif arg == 'comments':
        if cmd == 'create':
            f = False
        elif cmd == 'reset':
            f = True
        else:
            print("Wrong args")
            sys.exit(2)
        PeeweeUserCommentsStorage.create_new_sqlite_db(remove_if_exists=f)
    else:
        print("Wrong args")
        sys.exit(3)
