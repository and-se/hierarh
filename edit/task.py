from peewee import AutoField, IntegerField, Model, TextField, BooleanField

import logging
tlog = logging.Logger('tasks')
tlog.addHandler(logging.FileHandler('tasks.txt'))

class TaskCollection:
    def __init__(self):
        self.db = []

    def get_opened(self, coll_name, doc_key, reg_data_when):        
        return Task(coll_name, doc_key, reg_data_when)
    
class Task:
    def __init__(self, coll, key, when):        
        self.target = [coll, key, when]
        self.l = []
        self.changed = False
    
    def add(self, num, item, *msg):
        self.l.append([num, item, *msg])
        self.changed = True

    def save(self):
        ...
        tlog.info(self)

    def __str__(self):
        from pprint import pformat
        return f"Task({self.target}: {pformat(self.l)})"
    
    def __repr__(self):
        return str(self)


class TaskOrm(Model):
    class Meta:
        table_name = 'Tasks'

    id = AutoField()
    collection = TextField()
    doc_key = IntegerField()

    solved = BooleanField(default=False)

    text = TextField()
