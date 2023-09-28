from flask import Flask, render_template, redirect, request
import json
from models import CafedraArticle

app = Flask(__name__, static_folder='flask/static', template_folder='flask/templates')

from db import PeeweeCafedraDb

db = PeeweeCafedraDb()

@app.route('/')
def index():
    return redirect('/cafedra')

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
    d = db.get_cafedra_article(key)
    return render_template('cafedra_article.html', article=d, item_type='cafedra')

@app.route('/episkop/<int:key>')
def episkop_article(key):
    d = db.get_data(key)
    return render_template('episkop_article.html', data=d, item_type='episkop')
