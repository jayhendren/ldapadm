import unittest
import src.foo

class TestFooClass(unittest.TestCase):

    def setUp(self):
        self.f = src.foo.Foo()
    
    def test_foo(self):
        self.assertEqual(self.f.foo(), "foo")
    
    def test_bar(self):
        self.assertEqual(self.f.bar(), "bar")
