import json
from peewee import AutoField, IntegerField, Model, TextField, DoubleField

import logging
tlog = logging.Logger('tasks')
import os
os.unlink('tasks.txt')
tlog.addHandler(logging.FileHandler('tasks.txt'))

class TaskCollection:
    def __init__(self):
        self.db = []

    def get(self, coll_name, doc_key, reg_data_when):
        orm = TaskOrm.get_or_none(TaskOrm.collection==coll_name, TaskOrm.doc_key==doc_key, TaskOrm.reg_data_when==reg_data_when)
        if not orm:
            orm = TaskOrm(collection=coll_name, doc_key=doc_key, reg_data_when=reg_data_when)
        return Task(orm)
    
    def remove_all(self):
        TaskOrm.delete().execute()
    
    def reset(self):
        TaskOrm.drop_table()
        TaskOrm.create_table()
    
class Task:
    def __init__(self, orm):        
        self.orm:TaskOrm = orm
        self.l = []
        if self.orm.data:
            self.l = json.loads(self.orm.data)
            
        self.changed = False

    @property
    def type_(self):
        return self.orm.type
    
    @type_.setter
    def type_(self, value):
        self.orm.type = value

    @property
    def status(self):
        return self.orm.status
    
    @status.setter
    def status(self, value):
        self.orm.status = value

    @property
    def target(self):
        return [self.orm.collection, self.orm.doc_key, self.orm.reg_data_when]
    
    def add(self, num, item, *msg):        
        self.l.append({
            'num': num,
            'item': item,
            'msg': ' '.join([str(x) for x in msg])
        })
        self.changed = True

    def save(self):
        if self.changed:
            self.orm.data = json.dumps(self.l, ensure_ascii=False, indent=4)            
            self.orm.save()
            tlog.info(str(self))

    def __str__(self):
        from pprint import pformat
        return f"Task({self.target}: {pformat(self.l, sort_dicts=False)})"
    
    def __repr__(self):
        return str(self)


class TaskOrm(Model):
    class Meta:
        table_name = 'Tasks'

    id = AutoField()
    collection = TextField()
    doc_key = IntegerField()
    reg_data_when = DoubleField()

    type = TextField()
    status = TextField(default='new')
    data = TextField()  # json
    
