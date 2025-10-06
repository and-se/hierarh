from collections import namedtuple
from edit.storage import HierarhEditStorage
from edit.task import Task


class TaskService:
    def __init__(self, db: HierarhEditStorage):
        self.db = db

    def get_task_list(self, skip, take=20, status=None) -> "TaskPortion":
        if status:
            raise NotImplementedError

        d = self.db.task.portion(skip=skip, take=take + 1)
        total_count = self.db.task.count()

        if len(d) == take + 1:
            has_next = True
            d = d[:-1]
        else:
            has_next = False

        return TaskPortion(d, total_count, has_next)

    def get_task(self, id) -> 'TaskInfo':
        """
        Получить задачу по id.
        @returns Задачу и id следующей
        """
        t = self.db.task.get_by_id(id)
        if not t:
            raise NoSuchTaskError(id)

        next_task = self.db.task.get_next_task_id(t.id)

        return TaskInfo(t, next_task)
    
    def set_task_answer(self, id, answer_json: dict) -> str:
        """
        Устанавливает ответ на задачу
        @returns новый статус задачи
        """
        t = self.db.task.get_by_id(id)
        if not t:
            raise NoSuchTaskError(id)
        
        t.set_raw_answer(answer_json)
        if t.check_all_problems_resolved():
            new_status = "обработано"
        else:
            new_status = "в процессе"

        t.status = new_status
        t.save()

        return new_status
        
TaskPortion = namedtuple("TaskPortion", ["tasks", "total_count", "has_next"])
TaskInfo = namedtuple("TaskInfo", ['task', 'next_task_id'])

class NoSuchTaskError(Exception):
    def __init__(self, id):
        super().__init__(f"No task with id {id}")