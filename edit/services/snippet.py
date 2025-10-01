from edit.storage import HierarhEditStorage

from lxml import html

class SnippetService:
    def __init__(self, db: HierarhEditStorage):
        self.db = db

    def get_cafedra_snippet(self, key, max_length=100):
        d = self.db.cafedra.get(key)
        if not d: return None

        tree = html.fragment_fromstring(d.html)
        for tx in tree.xpath("//div[contains(@class, 'text')]"):
            tx = tx.text_content()
            i=tx.find('.')
            prev_i = None
            while i>=0 and i < max_length:
                prev_i = i
                i = tx.find('.', i+1)            
            if prev_i:
                res = tx[:prev_i+1]
            else:
                res = tx[:max_length-3] + '...'
            
            return res
            


