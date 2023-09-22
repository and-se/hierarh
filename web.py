from flask import Flask, render_template, redirect, request
import json
from models import CafedraArticle

app = Flask(__name__, static_folder='flask/static', template_folder='flask/templates')

from db import SimpleCafedraDb, PeeweeCafedraDb

#db = SimpleCafedraDb('articles.json')
db = PeeweeCafedraDb()

@app.route('/')
def index():
    return redirect('/cafedra')

@app.route('/cafedra')
def cafedra_list():
    query = request.args.get('query', '')
    return render_template('cafedra_list.html', cafedras=db.get_cafedra_names(query), query=query)

@app.route('/cafedra/<int:key>')
def cafedra_article(key):
    d = db.get_article(key)
    return render_template('cafedra_article.html', article=d)
