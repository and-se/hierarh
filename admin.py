from functools import wraps
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
import tempfile
import threading
import time
from flask import Blueprint, Response, abort, render_template, send_file
from flask_login import current_user, login_required

from edit.storage import HierarhEditStorage
import logging

adm_log = logging.getLogger('admin')
adm = Blueprint('hierarh_admin', __name__)

def admin_required(func):
    """
    Декоратор для допуска к route только администратора
    """
    @wraps(func)
    @login_required
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated or current_user.name != 'admin':
            abort(403)
        return func(*args, **kwargs)

    return decorated_view




# TODO админка с возможность перестроить индекс епископов, 
# экспортировать/импортировать задачи (и удалить сделанные), 
# посмотреть кто что правил

@adm.route('/')
@admin_required
def index():
    return render_template('admin.html') 

db_edit = HierarhEditStorage()

The_long_task = None

@adm.route('/rebuild_episkop_index')
@admin_required
def rebuild_episkop_index():
    global The_long_task
    if The_long_task and The_long_task.is_alive():
        abort(409, 'Перестроение индекса уже запущено')
    
    def sse_progress_sender(x):
        #print("sse", x)
        The_long_task._my_queue.put(f"data: {x.replace('\n', '\\n')}\n\n")

    def worker():
        global The_long_task
        # Чтобы в консоль тестового сервера не сыпались лишние логи
        oldl = logging.getLogger().level
        logging.getLogger().setLevel(logging.ERROR)
        
        db_edit.episkop_index.rebuild(sse_progress_sender)
        
        logging.getLogger().setLevel(oldl)
        sse_progress_sender("$CLOSE")

    The_long_task = threading.Thread(target=worker)
    The_long_task._my_queue = Queue()
    The_long_task.start()
    
    def event_gen():
        while The_long_task and (The_long_task.is_alive() or not The_long_task._my_queue.empty()):
            try:
                msg = The_long_task._my_queue.get(timeout=1)
                #print('yield', msg)
                yield msg
            except Empty:
                time.sleep(0.5)
            
    return Response(
        event_gen(),
        mimetype="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        },
    )

def download_backup(backup_callback, download_name):
    temp = tempfile.NamedTemporaryFile()  

    # Бэкап данных в заданный файл (путь)
    backup_callback(temp.name)
    
    temp.seek(0)  # на всякий случай
    
    # Добавим к результрующему имени дату и время
    nm = Path(download_name)
    timestr = datetime.now().strftime('%Y-%m-%d_%H-%M')    
    return send_file(temp, as_attachment=True, download_name= nm.stem + '_' + timestr + nm.suffix)

@adm.route('backup_db_edit')
@admin_required
def backup_db_edit():
    def callback(path):
        adm_log.debug(f'backup edit db into {path}')
        db_edit.backup_into(path)
    
    return download_backup(callback, 'hierarh_edit_backup.sqlite3')


@adm.route('backup_tasks')
@admin_required
def download_tasks():
    def callback(path):
        db_edit.task.backup_into(path)

    return download_backup(callback, 'hierarh_tasks.json')


