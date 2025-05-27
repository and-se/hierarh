import unittest
from pathlib import Path
import os

TestDbName = 'data/test-hierarh-edit.sqlite3'

if __name__ == '__main__':
    import sys
    sys.path.append(str(Path(__file__).parent.parent))


# Подменяем БД для редактирования
import settings
settings.EditDbName = TestDbName

# Теперь подключаем модуль storage - при этом он настроится на тестовую БД
import storage
from storage import TextCafedra, TextEpiskop, TextVersion


def load_file(text_model, test_file, key):
    path = Path(__file__).parent.joinpath('testdata').joinpath(test_file)
    with open(path) as f:
        html = f.read()
        return text_model.from_html(key, html)


def load_caf_file(test_file, key=None):
    return load_file(TextCafedra, test_file, key)
    
def load_ep_file(test_file, key=None):
    return load_file(TextEpiskop, test_file, key)


class TestStorage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("start storage test")
        if os.path.exists(TestDbName):
            print("Remove old db", TestDbName)
            os.remove(TestDbName)

        print("create new db")
        storage.init_edit_db()

        TestStorage.db = storage.HierarhEditStorage()
        assert storage.EditDb.database == TestDbName

        TestStorage.cafedra = TestStorage.db.cafedra
        TestStorage.episkop = TestStorage.db.episkop

    @classmethod
    def tearDownClass(cls):
        print("end storage test")

    def test_cafedra_crud(self):
        # create
        #n = self.db.new()
        n = load_caf_file('caf-1.html')
        self.assertEqual(n.key, None)

        n2 = self.cafedra.upsert(n)
        self.assertIsInstance(n2, TextCafedra)
        self.assertTrue(n2.key is not None)
        self.assertTrue(id(n2) == id(n))

        n3 = self.cafedra.get(n2.key)
        self.checkTextEqual(n2, n3)
        self.assertTrue('when' in n3.reg_data)

        mn = self.cafedra.portion(take=1)
        self.assertEqual(len(mn), 1)
        n4 = mn[0]
        self.checkTextEqual(n2, n4)

        # Update
        n4.html = load_caf_file('caf-1-div.html').html
        old_when = n4.reg_data['when']
        n5 = self.cafedra.upsert(n4)
        self.assertTrue(id(n5) == id(n4))
        self.assertGreater(n5.reg_data['when'], old_when)

        ## Новый объект без reg_data
        n6 = load_caf_file('caf-1.html')
        n6.key = n5.key
        self.cafedra.upsert(n6)
        self.assertGreater(n6.reg_data['when'], n5.reg_data['when'])

        n7 = self.cafedra.get(n6.key)
        self.checkTextEqual(n7, n6)
        n8 = self.cafedra.portion(take=1)[0]
        self.checkTextEqual(n8, n6)

        # Откатываем документ к начальному состоянию
        # Используем режим, когда reg_data записываются какие есть,
        # а не исправляются системой, в частности
        # reg_data[when] должен откатиться назад
        self.cafedra.upsert(n2, fix_reg_data=False)
        self.checkTextEqual(n2, n3)
        self.assertEqual(n2.reg_data['when'], n3.reg_data['when'])
        self.assertGreater(n8.reg_data['when'], n2.reg_data['when'])

        # test no unknown doc
        no = self.cafedra.get(12345)
        self.assertIsNone(no)
        
        # test check proper doc model
        ep = TextEpiskop.from_html(n2.key, "unexpected episkop")        
        with self.assertRaisesRegex(ValueError, 'Expected doc of type'):
            self.cafedra.upsert(ep)

    def test_cafedra_versions(self):
        def checkCafVerEqual(caf, ver):
            self.checkTextVerEqual('cafedra', caf, ver)
            self.assertIsInstance(caf, TextCafedra)
            
        n1 = load_caf_file('caf-1.html')
        self.cafedra.upsert(n1)
        
        n1_copy = self.cafedra.get(n1.key)
        self.assertTrue(isinstance(n1_copy, TextCafedra))

        v = self.cafedra.versions(n1.key)
        self.assertEqual(len(v), 0)

        n2 = load_caf_file('caf-1-div.html')
        n2.reg_data['who'] = 'editor'
        n2.key = n1.key
        self.cafedra.upsert(n2)

        v = self.cafedra.versions(n1.key)

        self.assertEqual(len(v), 1)
        checkCafVerEqual(n1, v[0])
        
        self.assertEqual([], self.cafedra.versions(n1.key, skip=1))

        n3 = self.cafedra.get(n2.key)
        n3.html += 'UPDATED3'
        n3.reg_data['who'] = 'admin'
        n3.reg_data['comment'] = 'restore db'
        self.cafedra.upsert(n3, fix_reg_data=False)

        v = self.cafedra.versions(n1.key)
        self.assertEqual(len(v), 2)
        checkCafVerEqual(n2, v[-1])

        old_when = n1.reg_data['when']
        self.cafedra.upsert(n1)
        v = self.cafedra.versions(n3.key)
        self.assertEqual(len(v), 3)
        checkCafVerEqual(n3, v[-1])

        self.assertGreater(n1.reg_data['when'], old_when)
        
        v = self.cafedra.versions(n3.key, skip=1, take=2)
        self.assertEqual(len(v), 2)
        checkCafVerEqual(n3, v[-1])        
        
        # test reverse
        v = self.cafedra.versions(n1.key, reverse=True)
        self.assertEqual(len(v), 3)
        checkCafVerEqual(n3, v[0])
        
        v = self.cafedra.versions(n1.key, skip=2, take=1, reverse=True)
        self.assertEqual(len(v), 1)
        checkCafVerEqual(n1_copy, v[0])


    def checkTextEqual(self, c1, c2):
        self.assertEqual(c1.key, c2.key)
        self.assertEqual(c1.html, c2.html)
        self.assertEqual(type(c1), type(c2))
        
    def checkTextVerEqual(self, coll_name, text, ver):        
        self.assertEqual(ver.collection, coll_name)
        self.assertEqual(ver.key, text.key)
        self.assertEqual(ver.reg_data, text.reg_data)
        self.assertEqual(ver.html, text.html)
        self.assertIsInstance(ver, TextVersion)        
        
    def test_episkop_mini(self):
        # create        
        n = TextEpiskop.from_html(None, "Episkop 1")

        n2 = self.episkop.upsert(n)
        self.assertIsInstance(n2, TextEpiskop)
        self.assertTrue(n2.key is not None)
        self.assertTrue(id(n2) == id(n))

        n3 = self.episkop.get(n2.key)
        self.checkTextEqual(n2, n3)
        self.assertTrue('when' in n3.reg_data)
        old_when = n2.reg_data['when']

        # Update
        n4 = TextEpiskop.from_html(n2.key, "Episkop 1 v2")        
        n5 = self.episkop.upsert(n4)
        self.assertTrue(id(n5) == id(n4))
        self.assertGreater(n5.reg_data['when'], old_when)
        
        # Portion
        n222 = TextEpiskop.from_html(123, "Episkop 2")
        self.episkop.upsert(n222)        
        self.assertTrue(n222.key is not None, 'Не проставился ключ')
        self.assertEqual(n222.key, 123)
        
        p = self.episkop.portion(take=100)
        self.assertEqual(len(p), 2)
        self.checkTextEqual(n5, p[0])
        self.checkTextEqual(n222, p[1])
        
        # Version
        vs = self.episkop.versions(n2.key)
        self.assertEqual(len(vs), 1)
        
        self.checkTextVerEqual('episkop', n3, vs[0])
        self.assertIsInstance(n3, TextEpiskop)
        
        vs2 = self.episkop.versions(n222.key)
        self.assertEqual(len(vs2), 0)
        
        # test check proper doc model
        caf = TextCafedra.from_html(n2.key, "unexpected cafedra")        
        with self.assertRaisesRegex(ValueError, 'Expected doc of type'):
            self.episkop.upsert(caf)
        
        

if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
