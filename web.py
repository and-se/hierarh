from flask import Flask, render_template, redirect, request, \
                  make_response, send_from_directory, Blueprint, \
                  url_for, flash, abort

import flask_login
from flask_login import login_required

from db import PeeweeHistHierarhStorage, PeeweeUserCommentsStorage, \
               StorageException

from edit.services.snippet import SnippetService
from edit.services.task_service import NoSuchTaskError, TaskService
from edit.storage import HierarhEditStorage, TextCollectionDb
from edit.services.diff import DiffService

from models import UserComment

import logging

import time
from time import time as unix_now

from urllib.parse import urlsplit

from pathlib import Path

app = Flask(__name__, static_folder='flask/static',
            template_folder='flask/templates')

app.json.ensure_ascii = False # type: ignore

from jinja2 import StrictUndefined
# шаблоны должны падать при обращении к неизвестной переменной
app.jinja_env.undefined = StrictUndefined

@app.context_processor
def inject_error_raise_into_template():
    def raise_error(msg):        
        raise Exception(msg)
    
    return {'raise_error': raise_error}
    

#import secrets
#app.secret_key = secrets.token_bytes(20)
#from werkzeug.security import generate_password_hash
#app.secret_key = generate_password_hash('hierarh-dev-secret')

try:
    from settings import FLASK_APP_SECRET_KEY
except ImportError as er:
    print('Наверно надо создать settings.py на основе settings-template.py')
    raise

app.secret_key = FLASK_APP_SECRET_KEY

login_manager = flask_login.LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = None


db = PeeweeHistHierarhStorage()
comments_db = PeeweeUserCommentsStorage()

from datetime import datetime, UTC
@app.context_processor
def inject_now():
    return {'time_now': datetime.now(UTC)}

@app.route('/')
def index():
    #return redirect('/cafedra')
    return render_template('main.html')

@app.route('/cafedra')
def cafedra_list():
    query = request.args.get('query', '')
    return render_template('item_list.html', item_type='cafedra', items=db.get_cafedra_names(query), query=query)

@app.route('/episkop')
def episkop_list():
    query = request.args.get('query', '')
    return render_template('item_list.html', item_type='episkop', items=db.get_episkop_names(query), query=query)

@app.route('/cafedra/<int:key>')
def cafedra_article(key):
    d = db.get_cafedra_data(key)
    if not d:
        abort(404, 'Статья не найдена')
    return render_template('cafedra_article.html', article=d, item_type='cafedra')

@app.route('/episkop/<int:key>')
def episkop_article(key):
    d = db.get_episkop_data(key)
    return render_template('episkop_article.html', data=d, item_type='episkop')

# TODO Оставлено для картинок в меню и приложения 11 (картинка-схема)
@app.route('/files/<path:name>')
def get_file(name):
    return send_from_directory('data/hierarh-files', name)


@app.route('/material/<string:name>')
def get_material(name):
    try:
        name = name.replace('/', '').replace('\\', '')
        html = Path(app.root_path) \
                    .joinpath('data/hierarh-files') \
                    .joinpath(name) \
                    .read_text(encoding="utf8")
        return render_template('material.html', html=html, header=name)
    except Exception as ex:
        print(ex)
        return abort(404, "Такого материала нет")
        
        

@app.route('/aboutproject')
def about_project():
    return get_material('О проекте.html')
    #return render_template('about.html')

@app.post('/comments')
def add_comment():
    # TODO if request is html-form-data (not json),
    # then client browser has disabled js - then send html response!
    json = request.json;
    try:
        uc = UserComment(**json)
        r = comments_db.create(uc)
        return {
            "success" : True,
            "id": r.id,
        }
    except Exception as ex:
        logging.exception(ex)
        return {
            "success": False,
            "message": str(ex),
            "info": repr(ex)
        }


@app.get('/comments')
def get_comments():
    c = comments_db.get_all()
    return render_template('comments.html', items=c)
    # return [x.model_dump() for x in c]


@app.get('/robots.txt')
def for_search_engines():
    #fixme Пока просим поисковики не индексировать наш сайт
    #todo Когда сайт будет готов к публикации, это место надо поправить.
    txt = "User-agent: *\n" + \
             "Disallow: /\n"
    r = make_response(txt, 200)
    r.mimetype = "text/plain"
    return r


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', msg=e), 404


###### AUTH #################
class SiteUser(flask_login.UserMixin):
    def __init__(self, user_id, active=True):
        self.id = user_id

    @property
    def title(self):
        return self.id



from settings import Users as KnownUsers

@login_manager.user_loader
def load_user(user_id):
    if user_id in KnownUsers:
        return SiteUser(user_id)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if flask_login.current_user.is_authenticated:
        return redirect(url_for('hierarh_edit.edit_root'))
    if request.method == 'POST':
        user_name = request.form.get('user')
        if user_name in KnownUsers and request.form.get('password') == KnownUsers.get(user_name):
            flask_login.login_user(SiteUser(user_name))
            next_page = request.args.get('next')
            if not next_page or urlsplit(next_page).netloc != '':
                next_page = url_for('hierarh_edit.edit_root')
            return redirect(next_page)
        else:
            flash("Неверное имя пользователя или пароль")
            return redirect(url_for('.login'))
    else:
        return render_template('login.html')

@app.route('/logout')
def logout():
    flask_login.logout_user()
    return redirect('/')



####### EDIT ################

ed = Blueprint('hierarh_edit', __name__)

db_edit = HierarhEditStorage()
diff_service = DiffService(db_edit)

snippet_service = SnippetService(db_edit)
task_service = TaskService(db_edit)

@ed.get('/')
@login_required
def edit_root():
    return redirect('./cafedra')

@ed.get('/cafedra')
@login_required
def list_cafedra_edit(skip=0, take=10**7):
    return _list_any(db_edit.cafedra, 'cafedra', skip, take)

@ed.get('/episkop')
@login_required
def list_episkop_edit(skip=0, take=10**7):
    return _list_any(db_edit.episkop, 'episkop', skip, take)

def _list_any(db_coll, item_type, skip, take):
    query = request.args.get('query', '')
    d = db_coll.portion(query=query, skip=skip, take=take)
    return render_template('edit/list.html', items=d, item_type=item_type, query=query)


@ed.get('/cafedra/new')
@login_required
def new_cafedra_ui():
    caf = db_edit.cafedra.new()
    return render_template('edit/cafedra.html', doc=caf, item_type='cafedra', post_url=url_for('.create_cafedra'))

@ed.get('/episkop/new')
@login_required
def new_episkop_ui():
    ep = db_edit.episkop.new()
    return render_template('edit/episkop.html', doc=ep, item_type='episkop', post_url=url_for('.create_episkop'))


@ed.post('/cafedra')
@login_required
def create_cafedra():
    d = request.json
    # print("NEW", d)    
    return _do_upsert(db_edit.cafedra, d['html'], d['key'], d['comment'])
    
@ed.post('/episkop')
@login_required
def create_episkop():
    d = request.json
    # print("NEW", d)
    return _do_upsert(db_edit.episkop, d['html'], d['key'], d['comment'])

def _do_upsert(db_coll: TextCollectionDb, html, key, comment):
    try:
        reg_data = {
            'who': flask_login.current_user.title,
            'when': unix_now()
        }

        if comment:
            reg_data['comment'] = comment

        c = db_coll.new()
        c.key = key
        c.html = html
        doc = db_coll.upsert(c, reg_data=reg_data)
        return {
            "success" : True,
            "key": doc.key,
        }
    except Exception as ex:
        logging.exception(ex)
        return {
            "success": False,
            "message": str(ex),
            "info": repr(ex)
        }

@ed.route('/cafedra/<int:key>', methods=['GET', 'POST'])
@login_required
def update_cafedra(key):
    return _do_doc_request(db_edit.cafedra, key)
    
@ed.route('/episkop/<int:key>', methods=['GET', 'POST'])
@login_required
def update_episkop(key):
    return _do_doc_request(db_edit.episkop, key)

def _do_doc_request(db_coll, key):
    if request.method == 'POST':
        d = request.json
        # print("UPDATE", d)
        return _do_upsert(db_coll, d['html'], d['key'], d['comment'])
    elif request.method == 'GET':
        doc = db_coll.get(key)
        if not doc: abort(404, 'Статья не найдена')
        last_edit = None
        if doc.reg_data:
            last_edit = build_editor_info(doc.reg_data)
            
        if db_coll.name == 'cafedra':
            tmpl = 'edit/cafedra.html'
            item_type = 'cafedra'
            post_url=url_for('.update_cafedra', key=key)
        elif db_coll.name == 'episkop':
            tmpl = 'edit/episkop.html'
            item_type = 'episkop'
            post_url=url_for('.update_episkop', key=key)
        else:
            raise ValueError("Unexpected collection " + db_coll.name)

        return render_template(tmpl, doc=doc, item_type=item_type, key=key,
                                post_url=post_url, last_edit=last_edit, comment=doc.reg_data.get('comment'))

def build_editor_info(reg_data, if_none="<нет данных>"):
    if not reg_data: return if_none
    last_edit = reg_data.get('who') or ''
    when = reg_data.get('when')
    if when:
        last_edit += time.strftime(' %d-%m-%y %H:%M', time.localtime(when))
    return last_edit


@ed.get('/cafedra/<int:key>/versions')
@login_required
def cafedra_history(key):
    return _do_versions_request(db_edit.cafedra, key)

@ed.get('/episkop/<int:key>/versions')
@login_required
def episkop_history(key):
    return _do_versions_request(db_edit.episkop, key)

def _do_versions_request(db_coll, key):
    doc = db_coll.get(key)
    if not doc: abort(404, 'Такой статьи нет, нет и её истории')

    if db_coll.name == 'cafedra':        
        item_type = 'cafedra'        
    elif db_coll.name == 'episkop':        
        item_type = 'episkop'

    hist = db_coll.versions(key, take=10**7, reverse=True)
    return render_template('edit/doc_history.html', cur_doc=doc, items=hist, item_type=item_type, time_convert=build_editor_info)


@ed.get('/cafedra/<int:key>/diff/<string:new>/<string:old>')
@login_required
def cafedra_diff(key, new, old):  
    header, new_reg_data, old_reg_data, diff = diff_service.make_html_diff('cafedra', key, new, old)
    
    return render_template('edit/doc_diff.html', diff=diff, header=header, new_reg_data=new_reg_data, old_reg_data=old_reg_data,
                            time_convert=build_editor_info, item_type='cafedra')


@ed.get('/episkop/<int:key>/diff/<string:new>/<string:old>')
@login_required
def episkop_diff(key, new, old):  
    header, new_reg_data, old_reg_data, diff = diff_service.make_html_diff('episkop', key, new, old)
    
    return render_template('edit/doc_diff.html', diff=diff, header=header, new_reg_data=new_reg_data, old_reg_data=old_reg_data,
                            time_convert=build_editor_info, item_type='episkop')




################# TASKS ########################

@ed.get('/task')
@login_required
def list_tasks():
    try:        
        skip = int(request.args.get('skip', 0))
    except ValueError:
        skip = 0
    
    take = 20
    
    status = request.args.getlist('status')
    portion = task_service.get_task_list(skip, take, status)
    tasks, cnt = portion.tasks, portion.total_count
    all_st = task_service.all_statuses()
    return render_template('edit/task-list.html', items=tasks, task_count=cnt,
                             all_statuses=all_st, selected_statuses=status or all_st, 
                            next_page_url=url_for('.list_tasks', skip=skip+take, status=status))
    

@ed.get('/task/<int:id>')
@login_required
def get_task(id):
    try:
        tinfo = task_service.get_task(id)
        t, doc_header, next_task = tinfo.task, tinfo.doc_header, tinfo.next_task_id
        return render_template('edit/task.html', task=t, next_task=next_task, doc_header=doc_header)
    except NoSuchTaskError:
        abort(404, "Задача не найдена")

    

@ed.post('/task/<int:id>/answer')
def set_task_answer(id):
    try:
        new_status = task_service.set_task_answer(id, request.json)
        return {
            "success": True,
            "status": new_status
        }
    except NoSuchTaskError:
        return {
            "success": False,
            "message": f"no such task {id}"
        }, 404
    
@ed.get('/suggest/cafedra')
@login_required
def suggest_cafedra():
    q = request.args.get("query", '')
    return db_edit.cafedra.suggest(q)

@ed.get('/cafedra/<int:key>/snippet')
@login_required
def snippet_cafedra(key):
    snippet = snippet_service.get_cafedra_snippet(key, max_length=350)
    if not snippet:
        return {
            "success": False,
            "message": f"no such cafedra {key}"
        }, 404
    
    return {
        "success": True,
        "key": key,
        "snippet": snippet 
    }


app.register_blueprint(ed, url_prefix='/edit')


if __name__ == '__main__':
    app.run(debug=True, port=5000)
