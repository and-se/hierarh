from edit.storage import HierarhEditStorage, TextCafedra, TextCollectionDb

import xmldiff.main
import xmldiff.formatting
import lxml.html

from pathlib import Path

with open(Path(__file__).parent.joinpath('xmldiff-html-formatter.xslt'),
          encoding="utf8") as xs:
    XSLT = lxml.etree.fromstring(xs.read())

class HTMLFormatter(xmldiff.formatting.XMLFormatter):
    def render(self, result):
        transform = lxml.etree.XSLT(XSLT)
        result = transform(result)
        return super(HTMLFormatter, self).render(result)


def diff_html(html_old, html_new):
    if not html_old:
        html_old = "Нет старых данных"
    if not html_new:
        html_new = "Нет новых данных"
        
    tree1 = lxml.html.fromstring(html_old)
    tree2 = lxml.html.fromstring(html_new)
    
    f = HTMLFormatter()
    #f = xmldiff.formatting.XMLFormatter()
    res = xmldiff.main.diff_trees(tree1, tree2, formatter=f)
    return res


class DiffService:
    def __init__(self, edit_db: HierarhEditStorage):
        self.db = edit_db
    
    def make_html_diff(self, coll_name: str, doc_key, new_target: str, old_target: str):
        coll = getattr(self.db, coll_name)
        
        new: TextCafedra = self.get_doc_data(coll, doc_key, new_target) or ""
        old: TextCafedra = self.get_doc_data(coll, doc_key, old_target) or ""
        
        new_reg_data = None
        old_reg_data = None
        header = "???"
        
        if new:
            new_reg_data = new.reg_data
            header = new.header()
            new = new.html
        if old:
            old_reg_data = old.reg_data
            if not header:
                header = old.header()
            old = old.html
        
        #return header, new_reg_data, old_reg_data, '<div style="color:red">some diffs</div>'
        
        # Медленно на больших кафедрах - на Киевской за минуту не отрабатывает
        #from ext.htmltreediff.html import diff
        #html_diff_result = diff(old, new, pretty=True)
        
        html_diff_result = diff_html(old, new) # На Киевской - 10 секунд
        return header, new_reg_data, old_reg_data, html_diff_result
    
    def get_doc_data(self, coll: TextCollectionDb, doc_key, target_version) -> TextCafedra:
        if target_version=='cur':
            return coll.get(doc_key)
        elif target_version.startswith('v'):
            version_num = int(target_version[1:])
            v = coll.versions(doc_key, skip=version_num-1, take=1, reverse=True)
            if v:
                vv = v[0]
                res = TextCafedra.from_html(doc_key, vv.html)
                res.reg_data = vv.reg_data
                return res
                
        else:
            raise ValueError(f"Can't get doc_data for doc_key={doc_key} target={target_version}")
