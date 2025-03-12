from flask import Flask, render_template, redirect, request, \
                  make_response, send_from_directory, Blueprint, \
                  url_for, flash, abort

import flask_login
from flask_login import login_required

from db import PeeweeHistHierarhStorage, PeeweeUserCommentsStorage, \
               StorageException

from edit.storage import HierarhEditStorage
from edit.services.diff import DiffService

from models import UserComment

import logging

import time
from time import time as unix_now

from urllib.parse import urlsplit

app = Flask(__name__, static_folder='flask/static',
            template_folder='flask/templates')

app.json.ensure_ascii = False

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

from datetime import datetime
@app.context_processor
def inject_now():
    return {'time_now': datetime.utcnow()}

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

@app.route('/files/<path:name>')
def get_file(name):
    return send_from_directory('data/hierarh-files', name)

@app.route('/aboutproject')
def about_project():
    return render_template('about.html')

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

@ed.get('/')
@login_required
def edit_root():
    return redirect('./cafedra')

@ed.get('/cafedra')
@login_required
def list_cafedra_edit():
    query = request.args.get('query', '')
    d = db_edit.cafedra.portion(query=query, take=10**7)
    return render_template('edit/list.html', items=d, item_type='cafedra', query=query)


@ed.get('/cafedra/new')
@login_required
def new_cafedra_ui():
    caf = db_edit.cafedra.new()
    return render_template('edit/cafedra.html', doc=caf, item_type='cafedra', post_url=url_for('.create_cafedra'))


@ed.post('/cafedra')
@login_required
def create_cafedra():
    d = request.json
    # print("NEW", d)
    return do_cafedra_upsert(d['html'], None, d['comment']);

def do_cafedra_upsert(html, key, comment):
    try:
        reg_data = {
            'who': flask_login.current_user.title,
            'when': unix_now()
        }

        if comment:
            reg_data['comment'] = comment

        c = db_edit.cafedra.new()
        c.key = key
        c.html = html
        doc = db_edit.cafedra.upsert(c, reg_data=reg_data)
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
    if request.method == 'POST':
        d = request.json
        # print("UPDATE", d)
        return do_cafedra_upsert(d['html'], d['key'], d['comment'])
    elif request.method == 'GET':
        caf = db_edit.cafedra.get(key)
        if not caf: abort(404, 'Статья не найдена')
        last_edit = None
        if caf.reg_data:
            last_edit = build_editor_info(caf.reg_data)

        return render_template('edit/cafedra.html', doc=caf, item_type='cafedra', key=key,
                                post_url=url_for('.update_cafedra', key=key), last_edit=last_edit, comment=caf.reg_data.get('comment'))

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
    caf = db_edit.cafedra.get(key)
    if not caf: abort(404, 'Такой статьи нет, нет и её истории')

    hist = db_edit.cafedra.versions(key, take=10**7, reverse=True)
    return render_template('edit/cafedra_history.html', cur_doc=caf, items=hist, item_type='cafedra', time_convert=build_editor_info)
    
@ed.get('/cafedra/<int:key>/diff/<string:new>/<string:old>')
@login_required
def cafedra_diff(key, new, old):  
    header, new_reg_data, old_reg_data, diff = diff_service.make_html_diff('cafedra', key, new, old)
    
    return render_template('edit/cafedra_diff.html', diff=diff, header=header, new_reg_data=new_reg_data, old_reg_data=old_reg_data,
                            time_convert=build_editor_info, item_type='cafedra')


app.register_blueprint(ed, url_prefix='/edit')



if __name__ == '__main__':
    app.run(debug=True, port=5000)
