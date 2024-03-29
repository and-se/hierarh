from flask import Flask, render_template, redirect, request, \
                  make_response, send_from_directory

from db import PeeweeHistHierarhStorage, PeeweeUserCommentsStorage, \
               StorageException

from models import UserComment

import logging

app = Flask(__name__, static_folder='flask/static',
            template_folder='flask/templates')

app.json.ensure_ascii = False



db = PeeweeHistHierarhStorage()
comments_db = PeeweeUserCommentsStorage()

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
    return render_template('cafedra_article.html', article=d, item_type='cafedra')

@app.route('/episkop/<int:key>')
def episkop_article(key):
    d = db.get_episkop_data(key)
    return render_template('episkop_article.html', data=d, item_type='episkop')

@app.route('/files/<path:name>')
def get_file(name):
    return send_from_directory('data/hierarh-files', name)

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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
