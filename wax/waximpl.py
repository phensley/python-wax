
# wax - a context object and file format.
#
# Author: Patrick Hensley <spaceboy@indirect.com>


# std
import re
import string
import sys
import traceback
import UserDict

# local
import microjson


__all__ = ["Wax", "WaxError", "parse_wax", "wax_to_dict"]


# Pychecker suppressions:
# no-noeffect       - Wax instances do 'self[key]' to test existence.
__pychecker__ = 'no-noeffect'


# Character classes
CHARS = string.lowercase + string.uppercase
KEYSTART = set(CHARS)
KEYVALID = set('_0123456789').union(KEYSTART)
GRPVALID = set('.').union(KEYVALID)
RE_KEYVALID = re.compile('^[%s][%s0-9\_]*$' % (CHARS, CHARS), re.M)

# Illegal key names, you cannot use these as attributes on Wax instances
BAD_KEY_NAMES = set(['and','as','assert','break','class','continue','def',
    'del','elif','else','except','exec','finally','for','from','get','global',
    'if','import','in','is','keys','lambda','not','or','pass','print',
    'raise','return','try','while','with','yield'])

E_BADKEY = "key '%s' contains illegal characters."
E_DIFFTYPE = "attempt to overwrite key/val (%s=%s) with incompatible type %s"
E_DOTSET = "attempt to %s key %s. cannot set/delete keys containing dots."
E_GROUP = "invalid group declaration '%s'"
E_NOCOPY = "Wax only knows how to copy Wax instances, not %s"
E_DOTKEY = "found key '%s' with a dot. only groups can contain dots."
E_JSON = "bad JSON data"
E_KEYNAME = "key name '%s' is illegal"
E_KEYTYPE = "key '%s' is illegal type '%s'. must be a str()"
E_MALF = "malformed"
E_NONTEXT = "cannot add %s value %s: must be text."
E_NOTSTR = "input must be of type 'str'"
E_REWRITE = "attempt to rewrite value for key %s"
E_SELECT = "group '%s' path goes through a non-Wax / non-dict type"
E_TRUNC = "truncated input"


class Wax(object):

    '''
    A flexible context object to make it easy to write code which relies on
    frequent access to a large number of nested runtime attributes.  Values are
    rich types, defined using JSON syntax. 

    See docs/wax.txt for details.
    '''

    def __init__(self, *n, **kv):
        self._key_order = []
        self._annotations = {}
        self._comments = {}
        self._comment_index = 0
        if n:
            for obj in n:
                if isinstance(obj, (dict, UserDict.DictMixin)):
                    self._from_dict(obj, self)
                else:
                    self._deep_copy(obj, self)
        for k, v in kv.items():
            self[k] = v

    @classmethod
    def _from_dict(cls, kvs, dest):
        '''
        Import all keys and values from dict 'kvs'.
        '''
        for key, val in kvs.items():
            if isinstance(val, (dict, UserDict.DictMixin)):
                if key in dest:
                    tmp = dest[key]
                    cls._from_dict(val, tmp)
                else:
                    tmp = Wax(val)
                dest[key] = tmp
            else:
                dest[key] = val

    def _get_annotation(self, key, default=None):
        '''
        Return the annotation for 'key' or 'default' if it does not exist.
        '''
        return self._annotations.get(key, default)

    def _set_annotation(self, key, text):
        '''
        An annotation is a ';' comment associated with a particular key.
        It must occur immediately before the key to become associated with
        it.
        '''
        if not isinstance(text, (unicode, str)):
            raise WaxError(E_NONTEXT % ('annotation', repr(text)))
        self._annotations[key] = text.rstrip()

    def _remove_annotation(self, key):
        '''
        If an annotation exists for 'key', remove it.
        '''
        if key in self._annotations:
            del self._annotations[key]

    def _add_comment(self, text):
        if not isinstance(text, (unicode, str)):
            raise WaxError(E_NONTEXT % ('comment', repr(text)))
        idx = self._comment_index
        self._comment_index += 1
        self._comments[idx] = text.rstrip()
        self._key_order.append(idx)
        return idx

    def _clear_comments(self):
        '''
        Since comments cannot be individually accessed (yet) we allow them
        to be cleared.
        '''
        self._comment_index = 0
        self._comments = {}
        self._key_order = [k for k in self._key_order if isinstance(k, str)]

    def __iadd__(self, obj):
        "Merge 'obj' into this instance."
        self._deep_copy(obj, self)
        return self

    def __add__(self, obj):
        "Add 'obj' to this instance and return the result."
        w = self._deep_copy(self, Wax())
        return self._deep_copy(obj, w)

    def __sub__(self, obj):
        "Subtract 'obj' from this instance and return the result."
        w = Wax()
        for key in self.keys():
            if key in obj:
                lt = self[key]
                rt = obj[key]
                if isinstance(lt, Wax) and isinstance(rt, Wax):
                    tmp = lt - rt
                    if tmp.keys():
                        w[key] = tmp
            else:
                w[key] = self[key]
        return w

    def __len__(self):
        "Return the number of keys stored in this instance."
        return len(self.keys())

    def _deep_copy(self, src, dst):
        "Recursively copy key/vals from 'src' to 'dst'."
        if not isinstance(src, Wax):
            raise WaxError(E_NOCOPY % type(src))

        dst._clear_comments()
        for key in src._key_order:

            # TODO: figure out how to best merge comments. - phensley
            # for now we clear out all comments in the dst and use
            # comments from src.
            if isinstance(key, int):
                text = src._comments.get(key, '')
                dst._add_comment(text)
                continue

            # handle annotations
            src_note = src._annotations.get(key, '')
            dst_note = dst._annotations.get(key, '')
            if src_note and src_note != dst_note:
                # src key's annotation wins
                dst._set_annotation(key, src_note)

            val = src[key]
            if isinstance(val, Wax):
                if key in dst and isinstance(dst[key], Wax):
                    self._deep_copy(val, dst[key])
                else:
                    dst[key] = Wax(val)
            elif isinstance(val, dict):
                dst[key] = val.copy()
            elif isinstance(val, list):
                dst[key] = list(val)
            else:
                dst[key] = val
        return dst

    def _remove_key(self, key):
        if not isinstance(key, str):
            raise WaxError(E_KEYTYPE % (key, type(key)))
        if key in self.__dict__:
            del self.__dict__[key]
            self._key_order.remove(key)
            if key in self._annotations:
                del self._annotations[key]

    def __contains__(self, key):
        try:
            self[key]
        except (WaxError, KeyError):
            return False
        return True

    def __iter__(self):
        return iter(self.keys())

    def __getitem__(self, key):
        '''
        Support getting values via "wax[key]" syntax.  In this case the
        key can contain dots and __getitem__ will recurse to obtain
        the right scope.  This is done to support string substitution
        via dotted patterns, e.g. "the host is %(database.host)s".
        '''
        # recursive key lookups inline, to support dotted string subs.
        # this will drill into dicts as well.
        if not isinstance(key, str):
            raise WaxError(E_KEYTYPE % (key, type(key)))
        curr = self
        if '.' in key:
            parts = key.split('.')
            for part in parts[:-1]:
                validate_key(part)
                curr = curr[part]
                if not isinstance(curr, (Wax, dict, UserDict.DictMixin)):
                    raise WaxError(E_SELECT % key)
            key = parts[-1]
        return curr.__dict__[key]

    def __delitem__(self, key):
        if not isinstance(key, str):
            raise WaxError(E_KEYTYPE % (key, type(key)))
        curr = self
        if '.' in key:
            parts = key.split('.')
            for part in parts[:-1]:
                validate_key(part)
                curr = curr[part]
                if not isinstance(curr, Wax):
                    raise WaxError(E_SELECT % key)
            key = parts[-1]
            validate_key(key)
        self = curr
        Wax._remove_key(self, key)

    def __setitem__(self, key, val):
        '''
        Support setting values via "wax[key] = val" syntax.  Key cannot
        contain dots, so 'wax["foo.bar"] = val' will not work. This is
        to avoid ambiguity between Wax instances and the properties of
        other objects attached to them.
        '''
        self.__setattr__(key, val)

    def __setattr__(self, key, val):
        '''
        Support setting values via 'wax.key = val' syntax.  The
        key cannot contain dots, so 'setattr(wax, "foo.bar", val)' will not
        work.  This is to avoid ambiguity between Wax instances and the
        other objects attached to them.
        '''
        if not isinstance(key, str):
            raise WaxError(E_KEYTYPE % (key, type(key)))
        if key and key[0] == '_':
            self.__dict__[key] = val
            return
        curr = self
        if '.' in key:
            parts = key.split('.')
            for part in parts[:-1]:
                validate_key(part)
                if not hasattr(curr, part):
                    setattr(curr, part, Wax())
                curr = curr[part]
            key = parts[-1]
        validate_key(key)
        curr.__dict__[key] = val
        if key not in curr._key_order:
            curr._key_order.append(key)

    def __delattr__(self, key):
        self._remove_key(key)

    def get(self, key, default=None):
        '''
        Given 'key' return a value. If 'key' doesn't exist, return 'default'.
        Also 'key' may be dotted.
        '''
        try:
            return self[key]
        except (WaxError, KeyError):
            return default

    def keys(self):
        '''
        Return a list of keys stored in this instance.
        '''
        return [k for k in self._key_order if not isinstance(k, int)]

    def __eq__(self, obj):
        '''
        Compute recursive equivalence between two Wax instances.  Comments
        and annotations are ignored in comparison.
        '''
        if not isinstance(obj, Wax):
            raise TypeError("argument is not of type Wax")
        if not sorted(self.keys()) == sorted(obj.keys()):
            return False
        for key in self.keys():
            if not self[key] == obj[key]:
                return False
        return True

    def __ne__(self, obj):
        '''
        Compute recursive inequality between two Wax instances.  Comments
        and annotations are ignored in comparison.
        '''
        if not isinstance(obj, Wax):
            raise TypeError("argument is not of type Wax")
        if sorted(self.keys()) != sorted(obj.keys()):
            return True
        for key in self.keys():
            if self[key] != obj[key]:
                return True
        return False


    def __str__(self):
        '''
        Dump out the contents of this instance.
        '''
        return self._render('', self) + '\n'

    def _render(self, parent, obj):
        '''
        Implementation of __str__.
        '''
        def _dotted(k):
            if parent:
                return '%s.%s' % (parent, k)
            return k

        # output this instance's keys
        buf = ''
        subs = []
        vals = 0
        for key in obj._key_order:
            if isinstance(key, int):
                comment = obj._comments.get(key, '')
                buf += _format_comment('#', comment)
                continue

            val = obj[key]
            if isinstance(val, Wax):
                subs.append( (key, val) )
                continue

            vals += 1
            note = obj._annotations.get(key, '')
            buf += _format_comment(';', note)
            buf += key + ' = ' + microjson.to_json(val) + '\n'

        # output sub-instances
        for key, inst in subs:
            note = obj._annotations.get(key, '')
            buf += _format_comment(';', note)
            buf += self._render(_dotted(key), inst)

        # only output this group header if:
        # - we have at least 1 non sub-instance key
        # - we have no contents at all
        # we output a header when we are empty in order to completely 
        # recreate the original hierarchy.
        if parent and (vals or not subs):
            return ('\n[%s]\n' % parent) + buf
        return buf


def parse_wax(data, dest=None):
    '''
    Parse a config file into a Wax instance, or merge the contents of the
    file to the 'dest' Wax instance.
    '''
    if not isinstance(data, str):
        raise WaxError(E_NOTSTR)
    stm = WaxStream(data)
    if dest is None:
        dest = Wax()
    return parse_wax_raw(stm, dest)


def wax_to_dict(obj):
    '''
    Convert a Wax instance recursively into a Python dict representation.
    '''
    if not isinstance(obj, Wax):
        return obj
    d = dict()
    for key in obj.keys():
        d[key] = wax_to_dict(obj[key])
    return d


class WaxError(Exception):

    def __init__(self, msg, stm=None, pos=0, jsonexc=None):
        if stm:
            tmp = repr(stm.substr(pos, 32))
            msg += ' on line %d, "%s"' % (stm.lineno, tmp)
        if jsonexc:
            trace = '  '.join(traceback.format_exception(*sys.exc_info()))
            msg += ' \n  Original json exception: ' + trace
        Exception.__init__(self, msg)
 

# Implementation details are below.  You shouldn't need these for 
# typical uses of Wax.


class WaxStream(microjson.JSONStream):

    def __init__(self, data):
        self.lineno = 1
        microjson.JSONStream.__init__(self, data)

    def next(self, num=1):
        s = super(WaxStream, self).next(num)
        self.lineno += len([c for c in s if c == '\n'])
        return s
    
    def skipto(self, ch):
        "post-cond: read pointer will be over first occurrance of 'ch'"
        self._skip(lambda c: c == ch)


def validate_key(key):
    '''
    Checks if a key is valid.  Caller must handle splitting dotted keys
    and calling this with each part.
    '''
    if not RE_KEYVALID.match(key):
        raise WaxError(E_BADKEY % key)
    if key in BAD_KEY_NAMES:
        raise WaxError(E_KEYNAME % key)


def parse_dotted(stm):
    # skip '['
    stm.next()
    pos = stm.pos
    group = None
    while True:
        c = stm.next()
        if c in GRPVALID:
            continue

        # end of group
        elif c == ']':
            group = stm.substr(pos, stm.pos - pos - 1)
            break

        elif c == '':
            raise WaxError(E_TRUNC, stm, stm.pos)

        partial = stm.substr(pos, stm.pos - pos)
        raise WaxError(E_GROUP % partial, stm, stm.pos)
    stm.skipto('\n')
    return pos, group


def parse_group(stm, top, annotation=None):
    pos, group = parse_dotted(stm)
    # create a path to the group from the top instance.
    prev = curr = top
    parts = group.split('.')
    for part in parts:
        if part in BAD_KEY_NAMES:
            raise WaxError(E_KEYNAME % part, stm, pos)
        if not hasattr(curr, part):
            curr[part] = Wax()
        prev = curr
        curr = curr[part]
        if not isinstance(curr, Wax):
            raise WaxError(E_SELECT % group, stm, pos)
    stm.next()
    prev._set_annotation(parts[-1], annotation.decode('utf-8'))
    return curr


def parse_keyval(stm, dest, annotation=None):
    "Parse an INI key/value pair, where the value is a JSON type."
    pos = stm.pos
    key = None
    while True:
        c = stm.next()
        if c == '':
            raise WaxError(E_TRUNC, stm, stm.pos - 1)

        elif c in microjson.WS:
            continue

        # parse "key = <json>"
        elif c == '=':
            key = stm.substr(pos, stm.pos - pos - 1)
            key = key.strip()
            stm.skipspaces()
            c = stm.peek()
            val = None
            try:
                val = microjson._from_json_raw(stm)
            except microjson.JSONError, jexc:
                raise WaxError(E_JSON, stm, stm.pos, jexc)
            try:
                setattr(dest, key, val)
            except WaxError, exc:
                raise WaxError(str(exc), stm, stm.pos)
            dest._set_annotation(key, annotation.decode('utf-8'))
            break

        elif c not in KEYVALID and c != '.':
            key = stm.substr(pos, stm.pos - pos - 1)
            raise WaxError(E_BADKEY % key, stm, stm.pos - 1)
    return key


def parse_wax_raw(stm, top):
    comment = ''
    annotation = ''
    curr = top
    while True:
        stm.skipspaces()
        c = stm.peek()
        if c != '#' and comment:
            curr._add_comment(comment.decode('utf-8'))
            comment = ''

        # end of stream
        if c == '':
            return top

        # [dotted.group]
        elif c == '[':
            curr = parse_group(stm, top, annotation)
            annotation = ''

        # '# comment text'
        elif c == '#':
            stm.next()
            pos = stm.pos
            stm.skipto('\n')
            comment += stm.substr(pos, stm.pos - pos) + '\n'
            stm.next()

        # '; annotation text'
        elif c == ';':
            stm.next()
            pos = stm.pos
            stm.skipto('\n')
            annotation += stm.substr(pos, stm.pos - pos) + '\n'
            stm.next()

        # 'key = "val"'
        elif c in KEYSTART:
            # parse key, val pair where val is a json type
            parse_keyval(stm, curr, annotation)
            annotation = ''

        # illegal char
        else:
            raise WaxError(E_MALF, stm, stm.pos)


def _format_comment(delim, text):
    '''
    Format a comment / annotation, ensuring there is at least one space
    before each line.
    '''
    if not text:
        return ''
    tmp = []
    for line in text.split('\n'):
        if line and line[0] not in (' ', '\t'):
            tmp.append(delim + ' ' + line)
        else:
            tmp.append(delim + line)
    res = '\n' + '\n'.join(tmp) + '\n'
    if isinstance(text, unicode):
        return res.encode('utf-8')
    return res

