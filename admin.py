from functools import wraps
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
import tempfile
import threading
import time
import os
import json
from flask import Blueprint, Response, abort, render_template, request, send_file, url_for
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

# очередь сообщений для передачи клиенту через /sse_stream
SSE_Queue = Queue()

def send_sse_message(x):
    #print("sse", x)
    SSE_Queue.put(f"data: {x.replace('\n', '\\n')}\n\n")


@adm.route('/rebuild_episkop_index')
@admin_required
def rebuild_episkop_index():
    global The_long_task
    if The_long_task and The_long_task.is_alive():
        return {
            'success': False,
            'message': 'Другая долгая задача уже работает - дождитесь её завершения'
        }, 409
    
    def worker():
        global The_long_task
        # Чтобы в консоль тестового сервера не сыпались лишние логи
        oldl = logging.getLogger().level
        logging.getLogger().setLevel(logging.ERROR)
        
        db_edit.episkop_index.rebuild(send_sse_message)
        
        logging.getLogger().setLevel(oldl)

    The_long_task = threading.Thread(target=worker)
    The_long_task.start()

    return {
        'success': True,
        'message': 'Перестроение индекса запущено',
        'see-progress': url_for('.sse')
    }, 200
    

@adm.route('/sse_stream')
@admin_required
def sse():
    """
    server side events
    Поток сообщений для показа на клиенте
    """
    def event_gen():
        #while The_long_task and (The_long_task.is_alive() or not SSE_Queue.empty()):
        while True:
            try:
                msg = SSE_Queue.get(timeout=1)
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

@adm.post('import_tasks')
@admin_required
def upload_tasks():
    global The_long_task
    if The_long_task and The_long_task.is_alive():
        return {
            'success': False,
            'message': 'Другая долгая задача уже работает - дождитесь её завершения'
        }, 409
    
    _, tmpfile = tempfile.mkstemp(prefix='hierarh-task-import')

    def worker(path):
        try:
            db_edit.task.import_from(path, send_sse_message)
        except Exception as ex:
            send_sse_message('Ошибка импорта задач: ' + str(ex))
            raise
        finally:
            os.unlink(path)
        
    try:
        file = request.files['task_file']
        file.save(tmpfile)

        The_long_task = threading.Thread(target=worker, args=(tmpfile,))
        The_long_task.start()
        return {
            'success': True,
            'message': 'Импорт задач запущен',
            'see-progress': url_for('.sse')
        }
    except Exception as ex:
        os.unlink(tmpfile)
        
        return {
            'success': False,
            'message': 'Ошибка запуска импорта задач: ' + str(ex)
        }, 500


@adm.route('remove_all_tasks')
@admin_required
def remove_all_tasks():
    try:
        db_edit.task.remove_all()
        return {
                'success': True,
                'message': 'Задачи удалены'
        }
    except Exception as ex:
        return {
                'success': False,
                'message': 'Ошибка при удалении задач: ' + str(ex)
        }


@adm.route('dbstat')
@admin_required
def get_stat():
    return {
        'success': True,
        'cafedra': db_edit.cafedra.count(),
        'episkop': db_edit.episkop.count(),
        'task': db_edit.task.count()
    }
    


