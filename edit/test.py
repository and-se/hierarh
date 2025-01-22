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
from storage import TextCafedra


def load_file(test_file, key=None):
    path = Path(__file__).parent.joinpath('testdata').joinpath(test_file)
    with open(path) as f:
        html = f.read()
        return TextCafedra.from_html(key, html)


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

    @classmethod
    def tearDownClass(cls):
        print("end storage test")

    def test_crud(self):
        # create
        #n = self.db.new()
        n = load_file('1.html')
        self.assertEqual(n.key, None)

        n2 = self.cafedra.upsert(n)
        self.assertTrue(n2.key is not None)
        self.assertTrue(id(n2) == id(n))

        n3 = self.cafedra.get(n2.key)
        self.checkCafEqual(n2, n3)
        self.assertTrue('when' in n3.reg_data)

        mn = self.cafedra.portion(take=1)
        self.assertEqual(len(mn), 1)
        n4 = mn[0]
        self.checkCafEqual(n2, n4)

        # Update
        n4.html = load_file('1-div.html').html
        old_when = n4.reg_data['when']
        n5 = self.cafedra.upsert(n4)
        self.assertTrue(id(n5) == id(n4))
        self.assertGreater(n5.reg_data['when'], old_when)

        ## Новый объект без reg_data
        n6 = load_file('1.html')
        n6.key = n5.key
        self.cafedra.upsert(n6)
        self.assertGreater(n6.reg_data['when'], n5.reg_data['when'])

        n7 = self.cafedra.get(n6.key)
        self.checkCafEqual(n7, n6)
        n8 = self.cafedra.portion(take=1)[0]
        self.checkCafEqual(n8, n6)

        # Откатываем документ к начальному состоянию
        # Используем режим, когда reg_data записываются какие есть,
        # а не исправляются системой, в частности
        # reg_data[when] должен откатиться назад
        self.cafedra.upsert(n2, fix_reg_data=False)
        self.checkCafEqual(n2, n3)
        self.assertEqual(n2.reg_data['when'], n3.reg_data['when'])
        self.assertGreater(n8.reg_data['when'], n2.reg_data['when'])

        # test no unknown doc
        no = self.cafedra.get(12345)
        self.assertIsNone(no)

    def test_versions(self):

        def checkCafVerEqual(caf, ver):
            self.assertEqual(ver.collection, 'cafedra')
            self.assertEqual(ver.key, caf.key)
            self.assertEqual(ver.reg_data, caf.reg_data)
            self.assertEqual(ver.html, caf.html)

        n1 = load_file('1.html')
        self.cafedra.upsert(n1)

        v = self.cafedra.versions(n1.key)
        self.assertEqual(len(v), 0)

        n2 = load_file('1-div.html')
        n2.reg_data['who'] = 'editor'
        n2.key = n1.key
        self.cafedra.upsert(n2)

        v = self.cafedra.versions(n1.key)

        self.assertEqual(len(v), 1)
        checkCafVerEqual(n1, v[0])

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


    def checkCafEqual(self, c1, c2):
        self.assertEqual(c1.key, c2.key)
        self.assertEqual(c1.html, c2.html)



if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
