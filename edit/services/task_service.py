from collections import namedtuple
from edit.storage import HierarhEditStorage
from edit.task import Task


class TaskService:
    def __init__(self, db: HierarhEditStorage):
        self.db = db

    def get_task_list(self, skip, take=20, status=None) -> "TaskPortion":
        d = self.db.task.portion(skip=skip, take=take + 1, needed_status=status)
        total_count = self.db.task.count(status)

        if len(d) == take + 1:
            has_next = True
            d = d[:-1]
        else:
            has_next = False

        return TaskPortion(d, total_count, has_next, status)
    
    def all_statuses(self):
        return list(self.db.task.get_all_statuses())

    def get_task(self, id) -> 'TaskInfo':
        """
        Получить задачу по id.
        @returns Задача, заголовок связанного с ней документа, id следующей задачи
        """
        t = self.db.task.get_by_id(id)
        if not t:
            raise NoSuchTaskError(id)

        next_task = self.db.task.get_next_task_id(t.id)
        
        doc_header = None
        coll = self.db.get_coll(t.doc_coll)
        if coll and (d := coll.get(t.doc_key)):
            doc_header = d.header()
        

        return TaskInfo(t, doc_header, next_task)
    
    def set_task_answer(self, id, answer_json: dict, who: str) -> str:
        """
        Устанавливает ответ на задачу
        @returns новый статус задачи
        """
        t: Task = self.db.task.get_by_id(id)
        if not t:
            raise NoSuchTaskError(id)
        
        t.set_raw_answer(answer_json)
        problem_count, resolved_count = t.check_problem_resolve_status()

        if resolved_count > 0 or answer_json.get('comment'):
            if problem_count <= resolved_count:
                new_status = "обработано"
            else:
                new_status = "в процессе"
        else:
            new_status = 'новая'
            
        t.status = new_status

        t.save(who)

        return t.status
        
TaskPortion = namedtuple("TaskPortion", ["tasks", "total_count", "has_next", "selected_statuses"])
TaskInfo = namedtuple("TaskInfo", ['task', 'doc_header', 'next_task_id'])

class NoSuchTaskError(Exception):
    def __init__(self, id):
        super().__init__(f"No task with id {id}")