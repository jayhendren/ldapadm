import unittest
from src import foo

class TestFooClass(unittest.TestCase):

    def setUp(self):
        self.f = foo.Foo()
    
    def test_foo(self):
        self.assertEqual(self.f.foo(), "foo")
    
    def test_bar(self):
        self.assertEqual(self.f.bar(), "bar")
