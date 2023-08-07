from flask import Flask, render_template, redirect, request
import json
from models import CafedraArticle

app = Flask(__name__, static_folder='flask/static', template_folder='flask/templates')

class SimpleCafedraDb:
    def __init__(self, json_file):
        self.db = json.load(open(json_file))
        assert isinstance(self.db, list)
        
        for i in range(len(self.db)):
            self.db[i] = CafedraArticle.from_dict(self.db[i])            

    def get_cafedra_names(self, query:str=''):
        q = QueryExecutor(query)            
        for (key, caf) in enumerate(self.db, 1):
            if q.match(caf.header):
                yield (key, caf.header)

    def get_article(self, key: int) -> CafedraArticle:
        return self.db[key-1] if key-1 < len(self.db) else None

class QueryExecutor:
    def __init__(self, query):
        self.q = tuple(x.lower() for x in query.split())
        print(self.q)

    def match(self, data: str):
        data = data.lower()
        for w in self.q:
            if w not in data:
                return False
        return True
                

db = SimpleCafedraDb('articles.json')

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
