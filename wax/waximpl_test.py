
# wax module unit tests.
# 
# Author: Patrick Hensley <spaceboy@indirect.com>


# std
import unittest
import UserDict

# local
from waximpl import parse_wax, wax_to_dict, Wax, WaxError, BAD_KEY_NAMES


# Pychecker suppressions:
# no-objattrs   - the Wax class is designed to dynamically create attributes.
# maxrefs=20    - need to test references to deeply-nested Wax attributes.
# no-constattr  - Wax can set dotted attributes, so we need to pass a constant
# string to setattr.
__pychecker__ = 'no-objattrs maxrefs=20 no-constattr'


class TestWax(unittest.TestCase):

    """
    Wax construction and set/get behaviors.
    """ 

    def test_basic(self):
        w = Wax()
        w.foo = 1
        w.bar = 2
        w.group1 = Wax()
        w.group1.foo = 1
        self.assertEquals(w.foo, 1)
        self.assertEquals(w.bar, 2)
        self.assertEquals(w.group1.foo, 1)
        self.assertEquals(w['group1.foo'], 1)

    def test_from_dict(self):
        # passing dict to constructor
        kv = {'aa': 1, 'bb': {'cc': 2, 'dd': {'ee': 3}}}
        wx = Wax(kv)
        self.assertEquals(wx.aa, 1)
        self.assertEquals(wx.bb.cc, 2)
        self.assertEquals(wx.bb.dd.ee, 3)

        # merge dict into instance with existing keys
        kv1 = {'aa': 1, 'bb': {'cc': 2}}
        kv2 = {'aa': 5, 'bb': {'cc': 6, 'dd': 7}}
        wx = Wax(kv1, kv2)
        self.assertEquals(wx.aa, 5)
        self.assertEquals(wx.bb.cc, 6)
        self.assertEquals(wx.bb.dd, 7)

        # test dotted keys in dict
        kv = {'aa.bb.cc': 1, 'aa.cc.dd': 2}
        wx = Wax(kv)
        self.assertEquals(wx.aa.bb.cc, 1)
        self.assertEquals(wx.aa.cc.dd, 2)

        # try a DictMixin
        class Foo(UserDict.DictMixin):
            def __init__(self, keyvals):
                self.kv = keyvals

            def items(self):
                return self.kv.items()

        foo = Foo({'aa': 1, 'bb.cc': 2, 'bb': Foo({'dd': 3})})
        wx = Wax(foo)
        self.assertEquals(wx.aa, 1)
        self.assertEquals(wx.bb.cc, 2)
        self.assertEquals(wx.bb.dd, 3)

    def test_annotations(self):
        inp = '; one\n; two\n[foo]\n; three\nval1 = 123'
        w = parse_wax(inp)
        self.assertEquals(w._get_annotation('foo'), ' one\n two')
        self.assertEquals(w._annotations['foo'], ' one\n two')
        del w.foo.val1
        self.assertTrue('val1' not in w.foo._annotations)

        w = parse_wax(WELLFORMED)
        self.assertEquals(w.one._get_annotation('bar'), ' C 1\n C 2')
        self.assertEquals(w.one._annotations['bar'], ' C 1\n C 2')

        # make sure annotations are formatted in output
        out = str(w)
        self.assertTrue('; C 1\n; C 2\n' in out)

        # test for missing annotations
        self.assertEquals(w._get_annotation('xxxxxxx'), None)
        self.assertEquals(w._get_annotation('zzzzzzz', 'foo'), 'foo')

        # test for bad annotation type
        self.assertRaises(WaxError, w._set_annotation, 'foo', 123)

        # check removal
        w = Wax()
        w.a = 123
        w._set_annotation('a', 'hi there')
        self.assertEquals(w._get_annotation('a'), 'hi there')
        w._remove_annotation('a')
        self.assertEquals(w._annotations, {})

    def test_unicode_annotations(self):
        inp = u'; \u2018hi\u2019\nfoo = 123\n'.encode('utf-8')
        w = parse_wax(inp)
        exp = u' \u2018hi\u2019'
        self.assertEquals(w._get_annotation('foo'), exp)

        # check properly formatted utf-8 in output
        out = str(w)
        self.assertTrue(';' + exp.encode('utf-8') in out)

    def test_comments(self):
        inp = '# one\n# two\n[foo]\n# three\nbar = 123\n'
        w = parse_wax(inp)
        self.assertEquals(w._comments[0], ' one\n two')
        self.assertEquals(w.foo._comments[0], ' three')
        del w.bar
        self.assertEquals(w.foo._comments[0], ' three')
        w.foo._clear_comments()
        self.assertEquals(w.foo._comments, {})
        self.assertEquals(w._comments[0], ' one\n two')
        w._clear_comments()
        self.assertEquals(w._comments, {})

        # bad comments
        self.assertRaises(WaxError, w._add_comment, 123)

    def test_unicode_comments(self):
        inp = u'# \u2018hi there\u2019\nfoo = 123\n'.encode('utf-8')
        w = parse_wax(inp)
        res = str(w)
        self.assertTrue(u'# \u2018hi there\u2019'.encode('utf-8') in res)

    def test_string_substitute(self):
        w = Wax()
        w.foo = 1
        w.bar = Wax()
        w.bar.baz = 1
        self.assertEquals('1 = 1', '%(foo)s = %(bar.baz)s'.__mod__(w))

    def test_rewrites(self):
        for v1, v2 in T_REWRITES:
            w = Wax()
            w.key = v1
            w.key = v2

        # ensure that values that are instances of builtin types can be
        # replaced with classes which inherit from a compatible type, and vice
        # versa.
        class Foo(str): 
            pass

        fstr = Foo("hi")
        w = Wax()
        w.foo = "hello"
        w.foo = fstr
        w.foo = "goodbye"

    def test_add(self):
        w1 = Wax(foo=1)
        w2 = Wax(bar=2)
        w3 = w1 + w2
        exp = Wax(foo=1, bar=2)
        self.assertEquals(exp, w3)

        w1 = Wax(foo=1)
        w2 = Wax(foo=2)
        w3 = w1 + w2
        self.assertEquals(str(w3).strip(), "foo = 2")

    def test_add_with_comments(self):
        w1 = Wax(a=1)
        w1._add_comment('foo\nbar')
        w1.b = 'a string'
        w1._add_comment('abc\ndef\nghi')
        self.assertEquals(w1.keys(), ['a', 'b'])
        w2 = Wax()
        w2 += w1
        self.assertEquals(w2._comments[0], 'foo\nbar')
        out = str(w2)
        self.assertTrue('# foo\n# bar\n' in out)

    def test_add_with_annotations(self):
        w1 = Wax(a=1)
        w1._set_annotation('a', 'foo\nbar')
        w1.b = 'a string'
        w1._set_annotation('b', 'abc\ndef\nghi')
        self.assertEquals(w1.keys(), ['a', 'b'])
        w2 = Wax()
        w2 += w1
        self.assertEquals(w2._annotations['a'], 'foo\nbar')
        self.assertEquals(w2._annotations['b'], 'abc\ndef\nghi')
        out = str(w2)
        self.assertTrue('; foo\n; bar\n' in out)

    def test_nested_add(self):
        w1 = Wax(foo=Wax(a=1, c=3))
        w2 = Wax(foo=Wax(b=2, d=4))
        w3 = w1 + w2
        exp = Wax(foo=Wax(a=1, b=2, c=3, d=4))
        self.assertEquals(exp, w3)

    def test_subtract(self):
        w1 = Wax(foo=1)
        w2 = Wax(foo=1)
        w3 = Wax(bar=2)
        w4 = Wax(foo=1, bar=2)
        self.assertEquals(Wax(), w1 - w2)
        self.assertEquals(w1, w1 - w3)
        self.assertEquals(w3, w4 - w1)

        w1 = Wax(foo=1, sub=Wax(x=1, y=2))
        w2 = Wax(foo=2, sub=Wax(x=1, z=3))
        res = Wax(sub=Wax(y=2))
        self.assertEquals(res, w1 - w2)

    def test_len(self):
        wx = Wax(aa=1, bb=Wax(cc=2))
        self.assertEquals(len(wx), 2)
        self.assertEquals(len(wx.bb), 1)

    def test_equals(self):
        w1 = Wax(foo=1, bar=Wax(x=1, y=2), baz=[1, 2, 3])
        w2 = Wax(foo=1, bar=Wax(x=1, y=2), baz=[1, 2, 3])
        w3 = Wax(baz=2)
        self.assertEquals(w1, w2)
        self.assertTrue(w1 == w2)
        self.assertFalse(w1 == w3)
        self.assertRaises(TypeError, w1.__eq__, {'foo': 1})

    def test_notequals(self):
        w1 = Wax(foo=1, bar=Wax(x=1, y=2), baz=[1, 2, 3])
        w2 = Wax(foo=1, bar=Wax(x=1, y=2), baz=[1, 2, 3])
        w3 = Wax(foo=1, bar=Wax(x=2, z=2), baz=[1, 2, 3])
        self.assertNotEquals(w1, w3)
        self.assertTrue(w1 != w3)
        self.assertFalse(w1 != w2)
        self.assertRaises(TypeError, w1.__ne__, {'foo': 1})

    def test_contains(self):
        w = Wax(foo=1, sub=Wax(bar=2))
        self.assertTrue('foo' in w)
        self.assertTrue('sub.bar' in w)
        self.assertFalse('bar' in w)
        self.assertFalse('foo.bar' in w)

    def test_iterate(self):
        w = Wax()
        w.foo=1
        w.bar=2
        w.abc=3
        w.xyz=4
        keys = []
        for key in w:
            keys.append(key)
        self.assertEquals(['foo','bar','abc','xyz'], keys)

    def test_delete(self):
        w1 = Wax(foo=1, bar=2)
        w2 = Wax(foo=1)
        del w1['bar']
        self.assertEquals(w1, w2)

        w1 = Wax(foo=1, bar=2)
        w2 = Wax(foo=1)
        delattr(w1, 'bar')
        self.assertEquals(w1, w2)

    def test_dotted_delitem(self):
        w = Wax(foo=Wax(bar=Wax()))
        del w['foo.bar']
        self.assertEquals(w, Wax(foo=Wax()))

    def test_dotted_setitem(self):
        w = Wax()
        w['foo.bar'] = Wax(baz=123)
        self.assertEquals(w.foo.bar.baz, 123)

    def test_dotted_setattr(self):
        w = Wax()
        setattr(w, "foo.bar.baz", 123)
        self.assertEquals(w.foo.bar.baz, 123)

    def test_getitem(self):
        w = Wax(a=1, b="foo")
        self.assertEquals(w['a'], 1)
        self.assertEquals(w['b'], 'foo')

    def test_keys(self):
        w = Wax()
        w.a = 1
        w.z = 2
        w.c = 3
        w.b = 4
        self.assertEquals(w.keys(), ['a','z','c','b'])

    def test_key_order(self):
        w = Wax()
        w.zz = Wax()
        w.aa = Wax()
        w.aa.xx = Wax()
        w.aa.bb = Wax()
        w.zz.cc = Wax()
        w.zz.yy = Wax()
        expected = ['[zz.cc]','[zz.yy]','[aa.xx]','[aa.bb]']
        res = str(w).split()
        self.assertEquals(res, expected)

    def test_get_method(self):
        w = Wax(a=1, b=Wax(c=Wax(d=1)))
        self.assertEquals(w.get('a'), 1)
        self.assertEquals(w.get('a', 2), 1)
        self.assertEquals(w.get('a'), w['a'])
        self.assertEquals(w.get('a'), w.a)
        self.assertEquals(w.get('x', 1), 1)
        self.assertEquals(w.get('x', 2), 2)
        # dotted keys, possibly missing intermediate levels
        self.assertEquals(w.get('b.c.d'), 1)
        self.assertEquals(w.get('b.c.d.e'), None)
        self.assertEquals(w.get('b.c.d.e', 1), 1)


    def test_wax_to_dict(self):
        w = Wax(a=Wax(b=Wax(c=Wax(d=1))))
        wd = wax_to_dict(w)
        self.assertEquals(wd, {'a': {'b': {'c': {'d': 1}}}})

    def test_copy(self):
        w1 = Wax(foo=1, bar={"a":1,"b":[1,2]}, baz=[1,2,3])
        w1.sub = Wax(foo=1, bar=Wax(baz=3.1415))
        w2 = Wax(w1)
        self.assertEquals(w1, w2)
        # append some data to ensure a pure copy with no shared refs
        w2.bar['c'] = 3
        w2.baz.append(4)
        self.assertNotEquals(w1, w2)

    def test_link(self):
        w1 = Wax(bar=2, sub=Wax(baz=3))
        w2 = Wax(foo=1, **w1)
        w3 = Wax(foo=1, bar=2, sub=Wax(baz=3))
        self.assertEquals(w2, w3)

    def test_double_dotted_add(self):
        w = Wax(key='abc')
        w['foo.bar'] = 1
        w['foo.bar'] = 1
        lines = [l for l in str(w).split('\n') if l]
        self.assertEquals(lines[0], 'key = "abc"')
        self.assertEquals(lines[1], '[foo]')
        self.assertEquals(lines[2], 'bar = 1')
        self.assertEquals(len(lines), 3)

    def test_merge(self):
        w1 = Wax(foo=1)
        s = "bar=2\n[sub]\nbaz=3\n"
        parse_wax(s, w1)
        self.assertEquals(w1.bar, 2)
        self.assertEquals(w1.sub.baz, 3)

    def test_as_kwargs(self):
        def _impl(**kw):
            return kw
        w = Wax(foo=1, bar=Wax(x=1), baz=[1, 2])
        res = _impl(**w)
        self.assertEquals(res, {'foo': 1, 'bar': Wax(x=1), 'baz': [1, 2]})

    def test_bad_add(self):
        w = Wax(foo=1)
        self.assertRaises(WaxError, w.__add__, {"abc": 123})
        self.assertRaises(WaxError, w.__iadd__, [1,2,3])

    def test_bad_delete(self):
        w = Wax(foo=1)
        self.assertRaises(WaxError, w.__delitem__, 'foo.bar')

    def test_bad_keynames(self):
        w = Wax()
        for key in BAD_KEY_NAMES:
            tmp = key.encode('utf-8')
            self.assertRaises(WaxError, setattr, w, tmp, 1)
            self.assertRaises(WaxError, w.__setitem__, tmp, 1)

    def test_bad_key(self):
        w = Wax()
        for key in T_BAD_KEYS:
            tmp = key.encode('utf-8')
            self.assertRaises(WaxError, setattr, w, tmp, 1)
            self.assertRaises(WaxError, w.__setitem__, tmp, 1)

    def test_bad_select(self):
        w = Wax()
        w.foo = 1
        self.assertRaises(WaxError, w.__getitem__, 'foo.bar')


# example of a well-formed cw config file.  don't follow the naming scheme
# below where keys are single-char or are named after JSON types. these are 
# here for some clarity in the test cases and to help ensure that the INI 
# and JSON worlds do not mix at the parse level.
WELLFORMED = """
; this is an annotation
str = "foo"
num = 123
float = 3.14159
numexp = 3e2
true = true
false = false
null = null
unicode = "\u2018this is quoted\u2019"
dict = {"abc": 123, "list": [1,2,3]}
list = ["this", "is", "json", "data"]

# other comment style
[one]
str = "foo"

[one.two]
str = "foo"

[a.b.c.d.e.f.g]
num = 1

[a]
b.c.num = 1

[one]
num = 123

; C 1
; C 2
bar = 123

; C 3
baz = 456

; C 4
; C 5
[level1.level2]
level3 = 123

"""

T_VALID = [
    # keyvals
    ("foo = 1", Wax(foo=1)),
    ("foo = true", Wax(foo=True)),
    ("foo = false", Wax(foo=False)),
    ("foo = null", Wax(foo=None)),

    # groups
    ("[one]\n", Wax(one=Wax())),
    ("[one.two]\n", Wax(one=Wax(two=Wax()))),
    ]

T_BAD_KEYS = [
    "1key",
    u"unic\u2018odekey",
    "?:",
    "%",
    ]

T_REWRITES = [
    (1, 3),
    (1.5, -3),
    (1, True),
    ("str", u"\u2018"),
    (True, False),
    (None, "str"),
    ("str", None),
    (None, Wax()),
    ({"abc": 123}, {"def": 456}),
    ([1, 2, 3], [4, 5, 6]),
    ]


class TestWaxParsing(unittest.TestCase):

    """
    Focus on Wax parsing from strings.  
    """

    def test_wellformed(self):
        w = parse_wax(WELLFORMED)
        self.assertEquals(w.str, "foo")
        self.assertEquals(w.num, 123)
        self.assertEquals(w.float, 3.14159)
        self.assertEquals(w.numexp, 300)
        self.assertEquals(w.true, True)
        self.assertEquals(w.false, False)
        self.assertEquals(w.null, None)
        self.assertEquals(w.dict, {"abc": 123, "list": [1, 2, 3]})
        self.assertEquals(w.list, ["this", "is", "json", "data"])
        self.assertEquals(w.unicode, u"\u2018this is quoted\u2019")

        # groups
        self.assertEquals(w.one.str, "foo")
        self.assertEquals(w.one.num, 123)
        self.assertEquals(w.one.two.str, "foo")

        self.assertEquals(w.a.b.c.d.e.f.g.num, 1)
        self.assertEquals(w.a.b.c.num, 1)

    def test_parse_append(self):
        w = Wax()
        w.foo = 1
        w += parse_wax('bar = 2\n[one.two]\nkey = "val"')
        self.assertEquals(w.bar, 2)
        self.assertEquals(w.one.two.key, "val")

    def test_parse_valid(self):
        for raw, expected in T_VALID:
            val = parse_wax(raw)
            self.assertEquals(val, expected)

    def test_roundtrip(self):
        # construct
        w = Wax(foo=1, bar=[1,2,3])
        sub1 = Wax(state="AZ", city="Phoenix")
        sub2 = Wax(title=u"\u2018this is single quoted\u2019")
        sub3 = Wax(dict={"abc": {"key": "val", "float": 3.14159}})
        w.sub = sub1
        sub1.sub = sub2
        sub2.sub = sub3

        # serialize
        js = str(w)

        # parse and compare
        res = parse_wax(js)
        self.assertEquals(res, w)

    def test_dotted_keys(self):
        js = "foo.bar = 123\n"
        w = parse_wax(js)
        self.assertEquals(Wax(foo=Wax(bar=123)), w)

    def test_bad_input_data(self):
        # input must be a str
        self.assertRaises(WaxError, parse_wax, u"foo = 1")

    def test_bad_keyvals(self):
        for test in T_PARSE_BAD_KEYVALS:
            self.assertRaises(WaxError, parse_wax, test)

    def test_bad_keys(self):
        w = Wax()
        for key in (1, ('a',), ['a'], True, None):
            self.assertRaises(WaxError, w.__setattr__, key, "a")
            self.assertRaises(WaxError, w.__delattr__, key)
            self.assertRaises(WaxError, w.__setitem__, key, "a")
            self.assertRaises(WaxError, w.__getitem__, key)
            self.assertRaises(WaxError, w.__delitem__, key)

    def test_bad_groups(self):
        for test in T_PARSE_BAD_GROUPS:
            self.assertRaises(WaxError, parse_wax, test)

    def test_bad_groupnames(self):
        for key in BAD_KEY_NAMES:
            data = "\n[foo.%s.bar]\nfoo = 1\n" % key
            self.assertRaises(WaxError, parse_wax, data)

    def test_bad_keynames(self):
        for key in BAD_KEY_NAMES:
            data = "\n%s = 1\n" % key
            self.assertRaises(WaxError, parse_wax, data)

    def test_bad_overwrites(self):
        for test in T_PARSE_BAD_OVERWRITES:
            self.assertRaises(WaxError, parse_wax, test)


T_PARSE_BAD_OVERWRITES = [
    "foo = 1\n[foo]\nbar=1"
    ]

T_PARSE_BAD_KEYVALS = [
    "foo",
    "foo =",
    "foo === bar",
    ":?/ = 1",
    u"unicodekey = 1",
    "foo\n[blah] = 1",
    ]

T_PARSE_BAD_GROUPS = [
    "[group name]", 
    "[group\nfoo = 1", 
    "[group\n#\n",
    ]

def main():
    unittest.main()


if __name__ == "__main__":
    main()


