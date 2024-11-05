class HierarhEditStorage:
    def __init__(self):
        self.cafedra = TextCollection('cafedra')


class TextCafedra:
    def __init__(self):
        self.key = None
        self.html = ""

    @staticmethod
    def from_html(key, html):
        doc = TextCafedra()
        doc.key = key
        doc.html = html
        return doc

    def header(self):
        return self.html.split('\n')[0]

    def is_obn(self):
        return False  # ...

    def __repr__(self):
        return f"TextCafedra({self.key}, {self.html})"

    def __str__(self):
        return repr(self)



TCAF = {
    1: TextCafedra.from_html(1, "cafedra 1\n<b>some text</b>"),
    2: TextCafedra.from_html(2, "cafedra 2\n<b>some text 2</b>"),
    3: TextCafedra.from_html(3, "cafedra 3\n<b>some text 3</b>")
}

class TextCollection:
    def __init__(self, name):
        self.name = name

    def portion(self, skip=0, take=20, query=None):
        return [x for x in TCAF.values()]

    def new(self):
        doc = TextCafedra()
        doc.html = "empty NEW"
        return doc

    def upsert(self, key, html=None):
        # create new or update current item

        if isinstance(key, TextCafedra):
            key, html = key.key, key.html

        global TCAF
        if key in TCAF:
            doc = TCAF[key]
            doc.html = html
        else:
            if not key:
                key = max(TCAF.keys())+1
            doc = TextCafedra.from_html(key, html)
            TCAF[key] = doc

        return doc

    def get(self, key):
        # get from db
        return TCAF.get(key)


def test():
    caf = HierarhEditStorage().cafedra
    print("PORTION", caf.portion())

    print("UPDATE key=2")
    doc = caf.get(2)
    print(doc)
    print("HEADER key=2", doc.header())
    doc.html = "UPDATED"
    doc = caf.upsert(doc)
    print("after: ", doc)
    print(caf.portion(), '\n')

    print("KEY=123", caf.get(123), '\n')

    print("NEW")
    doc = caf.new()
    doc.html = "THE NEW"
    print(doc)
    doc = caf.upsert(doc)
    print("after:", doc)
    print(caf.portion())
    print()

if __name__ == '__main__':
    test()
