import unittest
import re
import pymongo
from pyremo import q_parse, compose

class TestRegex(unittest.TestCase):

    def test_find(self):
        
        f, a = q_parse('/foo/bar/find', '')
        self.assertEqual(f['cmd'], 'find')
        
    def test_find_sort(self):
        
        f, a = q_parse('/foo/bar/find/', 'sort=hej:ASC')
        self.assertEqual(f['cmd'], 'find')
        self.assertNotEqual(a['sort'], None)
        
    def test_find_sort_multiple(self):
        
        f, a = q_parse('/foo/bar/find/', 'sort=hej:ASC,med:DESC,dig:ASC')
        self.assertEqual(f['cmd'], 'find')
        self.assertNotEqual(a['sort'], None)
        
    def test_find_skip(self):
        
        f, a = q_parse('/foo/bar/find/', 'skip=10')
        self.assertEqual(f['cmd'], 'find')
        self.assertEqual(int(a['skip']), 10)
        
    def test_find_limit(self):
        
        f, a = q_parse('/foo/bar/find/', 'limit=200')
        self.assertEqual(f['cmd'], 'find')
        self.assertEqual(int(a['limit']), 200)
        
    def test_find_doubleskip(self):
        """Last instance of skip should take presedence."""
        
        f, a = q_parse('/foo/bar/find/', 'skip=20&skip=10')
        self.assertEqual(f['cmd'], 'find')
        self.assertEqual(int(a['skip']), 10)
        
    def test_drop(self):
        
        f,a=q_parse('/foo/bar/drop', '')
        self.assertEqual(f['cmd'], 'drop')
    
    def test_drop_subcoll(self):
        
        f,a=q_parse('/foo/bar.jazz/drop', '')
        self.assertEqual(f['cmd'], 'drop')
    
    def test_find_subcoll(self):
        
        f,a=q_parse('/foo/bar.jazz/find', '')
        self.assertEqual(f['cmd'], 'find')
        
    def test_find_one(self):
        
        f,a=q_parse('/foo/bar/find_one','')
        self.assertEqual(f['cmd'], 'find_one')
        
    def test_find_fields(self):
        
        f,a=q_parse('/foo/bar/find/hej,med,dig','')
        self.assertEquals(f['fields'], 'hej,med,dig')
        self.assertEquals(f['cmd'], 'find')
        
class TestCompose(unittest.TestCase):

    def test_compose_sort(self):
        
        f, a = q_parse('/foo/bar/find_one', 'sort=hej:ASC,med:DESC,dig:ASC')
        func, args = compose(f, a)
        
        self.assertEqual(args['skip'], 0)
        self.assertEqual(args['limit'], 0)
        self.assertEqual(args['sort'], [('hej', 'ASC'), ('med', 'DESC'), ('dig', 'ASC')])
        
    def test_compose_fields(self):
        
        f, a = q_parse('/foo/bar/find/hej,med,dig', '')
        func, args = compose(f, a)
        self.assertEqual(args['fields'], ['hej','med','dig'])

class TestConnect(unittest.TestCase):
    
    def test_connect(self):
        f, a = q_parse('/media/pictures/find/name,path', 'limit=2&skip=10')
        func, args = compose(f, a)
        
        conn    = pymongo.Connection()
        db      = conn[func['db']]
        coll    = db[func['coll']]
        
        if func['cmd'] == 'find':
            for p in coll.find(**args):
                print p

if __name__ == '__main__':
    unittest.main()