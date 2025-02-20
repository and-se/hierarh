from edit.storage import HierarhEditStorage, TextCafedra, TextCollectionDb

#from htmltreediff.html import diff



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
            
        
        return header, new_reg_data, old_reg_data, '<div style="color:red">some diffs</div>'
        #return new_reg_data, old_reg_data, diff(old, new, pretty=True)
    
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
        
