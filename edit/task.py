import json
from peewee import AutoField, IntegerField, Model, TextField, DoubleField, TimestampField
from time import time as unix_now

import logging
tlog = logging.Logger('tasks')

DEBUG_TASKS = True
if DEBUG_TASKS:
    tlog.warning("DEBUG_TASKS=TRUE!!!! ЗАДАЧИ ЛОГИРУЮТСЯ в файл tasks.txt!")
    import os  # noqa: E402
    if os.path.exists('tasks.txt'):
        os.unlink('tasks.txt')
    tlog.addHandler(logging.FileHandler('tasks.txt'))



class TaskCollection:
    def __init__(self):
        pass

    def get(self, coll_name, doc_key, doc_reg_data_when):
        orm = TaskOrm.get_or_none(TaskOrm.collection==coll_name, TaskOrm.doc_key==doc_key, TaskOrm.doc_reg_data_when==doc_reg_data_when)
        if not orm:
            orm = TaskOrm(collection=coll_name, doc_key=doc_key, doc_reg_data_when=doc_reg_data_when)
        return Task(orm)
    
    def get_by_id(self, id):
        orm = TaskOrm.get_or_none(id)
        if orm:
            return Task(orm)
    
    def portion(self, skip, take, needed_status=None):
        dbdata = TaskOrm.select().limit(take).offset(skip)
        dbdata = self._apply_status_filter(needed_status, dbdata)

        return [Task(x) for x in dbdata]

    def _apply_status_filter(self, needed_status, db_query):
        if needed_status:
            if isinstance(needed_status, str):
                needed_status = [needed_status]
            if not isinstance(needed_status, list):
                raise ValueError('needed_status must be list[str] or str')
            db_query = db_query.where(TaskOrm.status.in_(needed_status))
        return db_query
    
    def count(self, needed_status=None) -> int:
        db_data = self._apply_status_filter(needed_status, TaskOrm.select())
        return db_data.count()
    
    def get_next_task_id(self, cur_id, needed_status=None):
        r = TaskOrm.select(TaskOrm.id).where(TaskOrm.id > cur_id)
        r = self._apply_status_filter(needed_status, r).get_or_none()
        if r:
            return r.id
    
    def get_all_statuses(self) -> list[str]:
        return [x[0] for x in TaskOrm.select(TaskOrm.status).distinct().tuples()]
    
    def remove_all(self):
        TaskOrm.delete().execute()
    
    def reset(self):
        TaskOrm.drop_table()
        TaskOrm.create_table()

    def remove_by_type(self, type):
        TaskOrm.delete().where(TaskOrm.type == type).execute()


class Task:
    def __init__(self, orm):        
        self.orm:TaskOrm = orm
        self._problems = []        
        self.title = None
        if self.orm.question:
            dd = json.loads(self.orm.question)
            self.title = dd['title']
            self._problems = dd['problems']

        self.changed = False

    @property
    def id(self):
        return self.orm.id
    
    @property
    def target(self):
        return [self.orm.collection, self.orm.doc_key, self.orm.doc_reg_data_when]
    
    @property
    def doc_key(self):
        return self.orm.doc_key
    
    @property
    def doc_coll(self):
        return self.orm.collection

    @property
    def type_(self):
        return self.orm.type
    
    @type_.setter
    def type_(self, value):
        self.changed = True
        self.orm.type = value

    @property
    def status(self):
        return self.orm.status
    
    @status.setter
    def status(self, value):
        self.changed = True
        self.orm.status = value

    def add_problem(self, where, item, *msg):        
        self._problems.append({
            'where': where,
            'item': str(item),
            'msg': ' '.join([str(x) for x in msg])
        })
        self.changed = True

    def raw_question(self):
        dd = {
            'title' : self.title or f"{self.orm.collection}/{self.orm.doc_key}",
            'problems': self._problems
        }            
            
        return self.something_to_json(dd) # type: ignore
    
    def raw_answer(self):
        return self.orm.answer

    def set_raw_answer(self, value):
        if not isinstance(value, dict) or value.get('answers') is None:
            raise ValueError('answer must be json seriazible dict with \'answers\' field')
        self.orm.answer = self.something_to_json(value)
        self.changed = True

    def check_problem_resolve_status(self)-> tuple[int, int]:
        """
        returns total problem count and resolved by answer count
        """
        if not self.orm.answer:
            return False

        answer = json.loads(self.orm.answer)

        def gather_where(source: list):
            r = set()
            for i in source:
                wh = i.get('where')
                # has 'where' and 'value' key and something else
                if wh and len(i.keys()) > 2: r.add(str(wh))
            return r

        q_wheres = set([x['where'] for x in self._problems])
        a_wheres = gather_where(answer.get('answers') or [])
        return (len(q_wheres), len(a_wheres))

    def save(self, who: str):
        if self.changed:            
            self.orm.question = self.raw_question()
            self.orm.who = who or '<noname>'
            self.orm.when = unix_now()
            #self.orm.answer = see set_raw_answer         
            self.orm.save()
            tlog.info(str(self))

    def something_to_json(self, dd):
        if dd is None: return None
        return json.dumps(dd, ensure_ascii=False, indent=4)

    def __str__(self):
        from pprint import pformat
        return f"Task({self.target}: {pformat(self._problems, sort_dicts=False)})"
    
    def __repr__(self):
        return str(self)


class TaskOrm(Model):
    class Meta:
        table_name = 'Tasks'

    id = AutoField()
    collection = TextField()
    doc_key = IntegerField()
    doc_reg_data_when = DoubleField()

    type = TextField()
    status = TextField(default='новая')
    question = TextField()  # json
    answer = TextField(null=True)

    who = TextField()
    when = DoubleField() # TimestampField(3)
    # - просто храним double из python time.time() как есть
    
