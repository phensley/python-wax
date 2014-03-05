### python-wax - hierarchical configuration format and context object for Python

### Quick Example

    >>> from wax import Wax, parse_wax
    >>> w = Wax(server=Wax(host='localhost'))
    >>> w.server.port = 1234
    
    >>> print 'hostname is %(server.host)s using port %(server.port)s' % w
    hostname is localhost using port 1234
    
    >>> s = str(w)
    >>> print s
    
    [server]
    host = "localhost"
    port = 1234

    >>> w = parse_wax(s)
    print w
    
    [server]
    host = "localhost"
    port = 1234
    

### Features

 * Context objects can be serialized to / from string
 * Simple hierarchical key structure
 * Key order is maintained
 * Values can be any JSON type
 * Supports comments and annotations


### Overview

Easy to construct in code:

    >>> w = Wax(message='hello world', num=17)

Access values with indexes:

    >>> w['num'] = 18

.. or as properties:

    >>> w.message = 'hello again'

.. or using get, with optional default value:

    >>> w.get('missing.key', 'no problem')
    'no problem'

This object translates directly to a file format.  Reading the format will reconstruct the context
object exactly.  This allows for "round-trip" configuration that can be serialized to utf-8, edited,
and read back in:

    >>> w = Wax(state='New York', zip=10003)
    >>> s = str(w)
    >>> print s
    state = "New York"
    zip = 10003

    >>> q = parse_wax(s)
    >>> print q
    state = "New York"
    zip = 10003

Key order is preserved when keys are added individually.  If you add them in the constructor, 
initial order is governed by kwargs (dict) hashing order:

    >>> w = Wax(a=1, b=2, c=3)
    >>> print w
    a = 1
    c = 3
    b = 2

    >>> w = Wax()
    >>> w.a = 1
    >>> w.b = 2
    >>> w.c = 3
    >>> print w
    a = 1
    b = 2
    c = 3

Create sublevels by attaching a Wax instance to a key:

    >>> w = Wax(level1=Wax(level2=Wax(property='value')))

.. which is equivalent to:

    >>> w = Wax()
    >>> w.level1 = Wax()
    >>> w.level1.level2 = Wax()
    >>> w.level1.level2.property = 'value'

Serializing this:

    >>> print w
    [level1.level2]
    property = "value"


Or you can set dotted keys to create nested values:

    >>> w = Wax()
    >>> w['foo.bar'] = 123
    >>> print w.foo.bar
    123


Dotted access can be used in formatting strings:

    >>> w = Wax(server=Wax(host='localhost', port=1234))
    >>> print 'hostname is %(server.host)s using port %(server.port)s' % w
    hostname is localhost using port 1234


