# Copyright (C) 2001,2002 Python Software Foundation
# csv package unit tests

import copy
import sys
import unittest
from io import StringIO
from tempfile import TemporaryFile
import csv
import gc
import pickle
from sql_mode import support
from itertools import permutations
from textwrap import dedent
from collections import OrderedDict

class Test_Csv(unittest.TestCase):
    """
    Test the underlying C csv parser in ways that are not appropriate
    from the high level interface. Further tests of this nature are done
    in TestDialectRegistry.
    """
    def _test_arg_valid(self, ctor, arg):
        self.assertRaises(TypeError, ctor)
        self.assertRaises(TypeError, ctor, None)
        self.assertRaises(TypeError, ctor, arg, bad_attr = 0)
        self.assertRaises(TypeError, ctor, arg, delimiter = 0)
        self.assertRaises(TypeError, ctor, arg, delimiter = 'XX')
        self.assertRaises(csv.Error, ctor, arg, 'foo')
        self.assertRaises(TypeError, ctor, arg, delimiter=None)
        self.assertRaises(TypeError, ctor, arg, delimiter=1)
        self.assertRaises(TypeError, ctor, arg, quotechar=1)
        self.assertRaises(TypeError, ctor, arg, lineterminator=None)
        self.assertRaises(TypeError, ctor, arg, lineterminator=1)
        self.assertRaises(TypeError, ctor, arg, quoting=None)
        self.assertRaises(TypeError, ctor, arg,
                          quoting=csv.QUOTE_ALL, quotechar='')
        self.assertRaises(TypeError, ctor, arg,
                          quoting=csv.QUOTE_ALL, quotechar=None)

    def test_reader_arg_valid(self):
        self._test_arg_valid(csv.reader, [])

    def test_writer_arg_valid(self):
        self._test_arg_valid(csv.writer, StringIO())

    def _test_default_attrs(self, ctor, *args):
        obj = ctor(*args)
        # Check defaults
        self.assertEqual(obj.dialect.delimiter, ',')
        self.assertEqual(obj.dialect.doublequote, True)
        self.assertEqual(obj.dialect.escapechar, None)
        self.assertEqual(obj.dialect.lineterminator, "\r\n")
        self.assertEqual(obj.dialect.quotechar, '"')
        self.assertEqual(obj.dialect.quoting, csv.QUOTE_MINIMAL)
        self.assertEqual(obj.dialect.skipinitialspace, False)
        self.assertEqual(obj.dialect.strict, False)
        # Try deleting or changing attributes (they are read-only)
        self.assertRaises(AttributeError, delattr, obj.dialect, 'delimiter')
        self.assertRaises(AttributeError, setattr, obj.dialect, 'delimiter', ':')
        self.assertRaises(AttributeError, delattr, obj.dialect, 'quoting')
        self.assertRaises(AttributeError, setattr, obj.dialect,
                          'quoting', None)

    def test_reader_attrs(self):
        self._test_default_attrs(csv.reader, [])

    def test_writer_attrs(self):
        self._test_default_attrs(csv.writer, StringIO())

    def _test_kw_attrs(self, ctor, *args):
        # Now try with alternate options
        kwargs = dict(delimiter=':', doublequote=False, escapechar='\\',
                      lineterminator='\r', quotechar='*',
                      quoting=csv.QUOTE_NONE, skipinitialspace=True,
                      strict=True)
        obj = ctor(*args, **kwargs)
        self.assertEqual(obj.dialect.delimiter, ':')
        self.assertEqual(obj.dialect.doublequote, False)
        self.assertEqual(obj.dialect.escapechar, '\\')
        self.assertEqual(obj.dialect.lineterminator, "\r")
        self.assertEqual(obj.dialect.quotechar, '*')
        self.assertEqual(obj.dialect.quoting, csv.QUOTE_NONE)
        self.assertEqual(obj.dialect.skipinitialspace, True)
        self.assertEqual(obj.dialect.strict, True)

    def test_reader_kw_attrs(self):
        self._test_kw_attrs(csv.reader, [])

    def test_writer_kw_attrs(self):
        self._test_kw_attrs(csv.writer, StringIO())

    def _test_dialect_attrs(self, ctor, *args):
        # Now try with dialect-derived options
        class dialect:
            delimiter='-'
            doublequote=False
            escapechar='^'
            lineterminator='$'
            quotechar='#'
            quoting=csv.QUOTE_ALL
            skipinitialspace=True
            strict=False
        args = args + (dialect,)
        obj = ctor(*args)
        self.assertEqual(obj.dialect.delimiter, '-')
        self.assertEqual(obj.dialect.doublequote, False)
        self.assertEqual(obj.dialect.escapechar, '^')
        self.assertEqual(obj.dialect.lineterminator, "$")
        self.assertEqual(obj.dialect.quotechar, '#')
        self.assertEqual(obj.dialect.quoting, csv.QUOTE_ALL)
        self.assertEqual(obj.dialect.skipinitialspace, True)
        self.assertEqual(obj.dialect.strict, False)

    def test_reader_dialect_attrs(self):
        self._test_dialect_attrs(csv.reader, [])

    def test_writer_dialect_attrs(self):
        self._test_dialect_attrs(csv.writer, StringIO())


    def _write_test(self, fields, expect, **kwargs):
        with TemporaryFile("w+", newline='') as fileobj:
            writer = csv.writer(fileobj, **kwargs)
            writer.writerow(fields)
            fileobj.seek(0)
            self.assertEqual(fileobj.read(),
                             expect + writer.dialect.lineterminator)

    def _write_error_test(self, exc, fields, **kwargs):
        with TemporaryFile("w+", newline='') as fileobj:
            writer = csv.writer(fileobj, **kwargs)
            with self.assertRaises(exc):
                writer.writerow(fields)
            fileobj.seek(0)
            self.assertEqual(fileobj.read(), '')

    def test_write_arg_valid(self):
        self._write_error_test(csv.Error, None)
        self._write_test((), '')
        self._write_test([None], '""')
        self._write_error_test(csv.Error, [None], quoting = csv.QUOTE_NONE)
        # Check that exceptions are passed up the chain
        class BadList:
            def __len__(self):
                return 10;
            def __getitem__(self, i):
                if i > 2:
                    raise OSError
        self._write_error_test(OSError, BadList())
        class BadItem:
            def __str__(self):
                raise OSError
        self._write_error_test(OSError, [BadItem()])

    def test_write_bigfield(self):
        # This exercises the buffer realloc functionality
        bigstring = 'X' * 50000
        self._write_test([bigstring,bigstring], '%s,%s' % \
                         (bigstring, bigstring))

    def test_write_quoting(self):
        self._write_test(['a',1,'p,q'], 'a,1,"p,q"')
        self._write_error_test(csv.Error, ['a',1,'p,q'],
                               quoting = csv.QUOTE_NONE)
        self._write_test(['a',1,'p,q'], 'a,1,"p,q"',
                         quoting = csv.QUOTE_MINIMAL)
        self._write_test(['a',1,'p,q'], '"a",1,"p,q"',
                         quoting = csv.QUOTE_NONNUMERIC)
        self._write_test(['a',1,'p,q'], '"a","1","p,q"',
                         quoting = csv.QUOTE_ALL)
        self._write_test(['a\nb',1], '"a\nb","1"',
                         quoting = csv.QUOTE_ALL)

    def test_write_escape(self):
        self._write_test(['a',1,'p,q'], 'a,1,"p,q"',
                         escapechar='\\')
        self._write_error_test(csv.Error, ['a',1,'p,"q"'],
                               escapechar=None, doublequote=False)
        self._write_test(['a',1,'p,"q"'], 'a,1,"p,\\"q\\""',
                         escapechar='\\', doublequote = False)
        self._write_test(['"'], '""""',
                         escapechar='\\', quoting = csv.QUOTE_MINIMAL)
        self._write_test(['"'], '\\"',
                         escapechar='\\', quoting = csv.QUOTE_MINIMAL,
                         doublequote = False)
        self._write_test(['"'], '\\"',
                         escapechar='\\', quoting = csv.QUOTE_NONE)
        self._write_test(['a',1,'p,q'], 'a,1,p\\,q',
                         escapechar='\\', quoting = csv.QUOTE_NONE)

    def test_write_iterable(self):
        self._write_test(iter(['a', 1, 'p,q']), 'a,1,"p,q"')
        self._write_test(iter(['a', 1, None]), 'a,1,')
        self._write_test(iter([]), '')
        self._write_test(iter([None]), '""')
        self._write_error_test(csv.Error, iter([None]), quoting=csv.QUOTE_NONE)
        self._write_test(iter([None, None]), ',')

    def test_writerows(self):
        class BrokenFile:
            def write(self, buf):
                raise OSError
        writer = csv.writer(BrokenFile())
        self.assertRaises(OSError, writer.writerows, [['a']])

        with TemporaryFile("w+", newline='') as fileobj:
            writer = csv.writer(fileobj)
            self.assertRaises(TypeError, writer.writerows, None)
            writer.writerows([['a','b'],['c','d']])
            fileobj.seek(0)
            self.assertEqual(fileobj.read(), "a,b\r\nc,d\r\n")

    @support.cpython_only
    def test_writerows_legacy_strings(self):
        import _testcapi

        c = _testcapi.unicode_legacy_string('a')
        with TemporaryFile("w+", newline='') as fileobj:
            writer = csv.writer(fileobj)
            writer.writerows([[c]])
            fileobj.seek(0)
            self.assertEqual(fileobj.read(), "a\r\n")

    def _read_test(self, input, expect, **kwargs):
        reader = csv.reader(input, **kwargs)
        result = list(reader)
        self.assertEqual(result, expect)

    def test_read_oddinputs(self):
        self._read_test([], [])
        self._read_test([''], [[]])
        self.assertRaises(csv.Error, self._read_test,
                          ['"ab"c'], None, strict = 1)
        # cannot handle null bytes for the moment
        self.assertRaises(csv.Error, self._read_test,
                          ['ab\0c'], None, strict = 1)
        self._read_test(['"ab"c'], [['abc']], doublequote = 0)

        self.assertRaises(csv.Error, self._read_test,
                          [b'ab\0c'], None)


    def test_read_eol(self):
        self._read_test(['a,b'], [['a','b']])
        self._read_test(['a,b\n'], [['a','b']])
        self._read_test(['a,b\r\n'], [['a','b']])
        self._read_test(['a,b\r'], [['a','b']])
        self.assertRaises(csv.Error, self._read_test, ['a,b\rc,d'], [])
        self.assertRaises(csv.Error, self._read_test, ['a,b\nc,d'], [])
        self.assertRaises(csv.Error, self._read_test, ['a,b\r\nc,d'], [])

    def test_read_eof(self):
        self._read_test(['a,"'], [['a', '']])
        self._read_test(['"a'], [['a']])
        self._read_test(['^'], [['\n']], escapechar='^')
        self.assertRaises(csv.Error, self._read_test, ['a,"'], [], strict=True)
        self.assertRaises(csv.Error, self._read_test, ['"a'], [], strict=True)
        self.assertRaises(csv.Error, self._read_test,
                          ['^'], [], escapechar='^', strict=True)

    def test_read_escape(self):
        self._read_test(['a,\\b,c'], [['a', 'b', 'c']], escapechar='\\')
        self._read_test(['a,b\\,c'], [['a', 'b,c']], escapechar='\\')
        self._read_test(['a,"b\\,c"'], [['a', 'b,c']], escapechar='\\')
        self._read_test(['a,"b,\\c"'], [['a', 'b,c']], escapechar='\\')
        self._read_test(['a,"b,c\\""'], [['a', 'b,c"']], escapechar='\\')
        self._read_test(['a,"b,c"\\'], [['a', 'b,c\\']], escapechar='\\')

    def test_read_quoting(self):
        self._read_test(['1,",3,",5'], [['1', ',3,', '5']])
        self._read_test(['1,",3,",5'], [['1', '"', '3', '"', '5']],
                        quotechar=None, escapechar='\\')
        self._read_test(['1,",3,",5'], [['1', '"', '3', '"', '5']],
                        quoting=csv.QUOTE_NONE, escapechar='\\')
        # will this fail where locale uses comma for decimals?
        self._read_test([',3,"5",7.3, 9'], [['', 3, '5', 7.3, 9]],
                        quoting=csv.QUOTE_NONNUMERIC)
        self._read_test(['"a\nb", 7'], [['a\nb', ' 7']])
        self.assertRaises(ValueError, self._read_test,
                          ['abc,3'], [[]],
                          quoting=csv.QUOTE_NONNUMERIC)

    def test_read_bigfield(self):
        # This exercises the buffer realloc functionality and field size
        # limits.
        limit = csv.field_size_limit()
        try:
            size = 50000
            bigstring = 'X' * size
            bigline = '%s,%s' % (bigstring, bigstring)
            self._read_test([bigline], [[bigstring, bigstring]])
            csv.field_size_limit(size)
            self._read_test([bigline], [[bigstring, bigstring]])
            self.assertEqual(csv.field_size_limit(), size)
            csv.field_size_limit(size-1)
            self.assertRaises(csv.Error, self._read_test, [bigline], [])
            self.assertRaises(TypeError, csv.field_size_limit, None)
            self.assertRaises(TypeError, csv.field_size_limit, 1, None)
        finally:
            csv.field_size_limit(limit)

    def test_read_linenum(self):
        r = csv.reader(['line,1', 'line,2', 'line,3'])
        self.assertEqual(r.line_num, 0)
        next(r)
        self.assertEqual(r.line_num, 1)
        next(r)
        self.assertEqual(r.line_num, 2)
        next(r)
        self.assertEqual(r.line_num, 3)
        self.assertRaises(StopIteration, next, r)
        self.assertEqual(r.line_num, 3)

    def test_roundtrip_quoteed_newlines(self):
        with TemporaryFile("w+", newline='') as fileobj:
            writer = csv.writer(fileobj)
            self.assertRaises(TypeError, writer.writerows, None)
            rows = [['a\nb','b'],['c','x\r\nd']]
            writer.writerows(rows)
            fileobj.seek(0)
            for i, row in enumerate(csv.reader(fileobj)):
                self.assertEqual(row, rows[i])

    def test_roundtrip_escaped_unquoted_newlines(self):
        with TemporaryFile("w+", newline='') as fileobj:
            writer = csv.writer(fileobj,quoting=csv.QUOTE_NONE,escapechar="\\")
            rows = [['a\nb','b'],['c','x\r\nd']]
            writer.writerows(rows)
            fileobj.seek(0)
            for i, row in enumerate(csv.reader(fileobj,quoting=csv.QUOTE_NONE,escapechar="\\")):
                self.assertEqual(row,rows[i])

class TestDialectRegistry(unittest.TestCase):
    def test_registry_badargs(self):
        self.assertRaises(TypeError, csv.list_dialects, None)
        self.assertRaises(TypeError, csv.get_dialect)
        self.assertRaises(csv.Error, csv.get_dialect, None)
        self.assertRaises(csv.Error, csv.get_dialect, "nonesuch")
        self.assertRaises(TypeError, csv.unregister_dialect)
        self.assertRaises(csv.Error, csv.unregister_dialect, None)
        self.assertRaises(csv.Error, csv.unregister_dialect, "nonesuch")
        self.assertRaises(TypeError, csv.register_dialect, None)
        self.assertRaises(TypeError, csv.register_dialect, None, None)
        self.assertRaises(TypeError, csv.register_dialect, "nonesuch", 0, 0)
        self.assertRaises(TypeError, csv.register_dialect, "nonesuch",
                          badargument=None)
        self.assertRaises(TypeError, csv.register_dialect, "nonesuch",
                          quoting=None)
        self.assertRaises(TypeError, csv.register_dialect, [])

    def test_registry(self):
        class myexceltsv(csv.excel):
            delimiter = "\t"
        name = "myexceltsv"
        expected_dialects = csv.list_dialects() + [name]
        expected_dialects.sort()
        csv.register_dialect(name, myexceltsv)
        self.addCleanup(csv.unregister_dialect, name)
        self.assertEqual(csv.get_dialect(name).delimiter, '\t')
        got_dialects = sorted(csv.list_dialects())
        self.assertEqual(expected_dialects, got_dialects)

    def test_register_kwargs(self):
        name = 'fedcba'
        csv.register_dialect(name, delimiter=';')
        self.addCleanup(csv.unregister_dialect, name)
        self.assertEqual(csv.get_dialect(name).delimiter, ';')
        self.assertEqual([['X', 'Y', 'Z']], list(csv.reader(['X;Y;Z'], name)))

    def test_incomplete_dialect(self):
        class myexceltsv(csv.Dialect):
            delimiter = "\t"
        self.assertRaises(csv.Error, myexceltsv)

    def test_space_dialect(self):
        class space(csv.excel):
            delimiter = " "
            quoting = csv.QUOTE_NONE
            escapechar = "\\"

        with TemporaryFile("w+") as fileobj:
            fileobj.write("abc def\nc1ccccc1 benzene\n")
            fileobj.seek(0)
            reader = csv.reader(fileobj, dialect=space())
            self.assertEqual(next(reader), ["abc", "def"])
            self.assertEqual(next(reader), ["c1ccccc1", "benzene"])

    def compare_dialect_123(self, expected, *writeargs, **kwwriteargs):

        with TemporaryFile("w+", newline='', encoding="utf-8") as fileobj:

            writer = csv.writer(fileobj, *writeargs, **kwwriteargs)
            writer.writerow([1,2,3])
            fileobj.seek(0)
            self.assertEqual(fileobj.read(), expected)

    def test_dialect_apply(self):
        class testA(csv.excel):
            delimiter = "\t"
        class testB(csv.excel):
            delimiter = ":"
        class testC(csv.excel):
            delimiter = "|"
        class testUni(csv.excel):
            delimiter = "\u039B"

        csv.register_dialect('testC', testC)
        try:
            self.compare_dialect_123("1,2,3\r\n")
            self.compare_dialect_123("1\t2\t3\r\n", testA)
            self.compare_dialect_123("1:2:3\r\n", dialect=testB())
            self.compare_dialect_123("1|2|3\r\n", dialect='testC')
            self.compare_dialect_123("1;2;3\r\n", dialect=testA,
                                     delimiter=';')
            self.compare_dialect_123("1\u039B2\u039B3\r\n",
                                     dialect=testUni)

        finally:
            csv.unregister_dialect('testC')

    def test_bad_dialect(self):
        # Unknown parameter
        self.assertRaises(TypeError, csv.reader, [], bad_attr = 0)
        # Bad values
        self.assertRaises(TypeError, csv.reader, [], delimiter = None)
        self.assertRaises(TypeError, csv.reader, [], quoting = -1)
        self.assertRaises(TypeError, csv.reader, [], quoting = 100)

    def test_copy(self):
        for name in csv.list_dialects():
            dialect = csv.get_dialect(name)
            self.assertRaises(TypeError, copy.copy, dialect)

    def test_pickle(self):
        for name in csv.list_dialects():
            dialect = csv.get_dialect(name)
            for proto in range(pickle.HIGHEST_PROTOCOL + 1):
                self.assertRaises(TypeError, pickle.dumps, dialect, proto)

class TestCsvBase(unittest.TestCase):
    def readerAssertEqual(self, input, expected_result):
        with TemporaryFile("w+", newline='') as fileobj:
            fileobj.write(input)
            fileobj.seek(0)
            reader = csv.reader(fileobj, dialect = self.dialect)
            fields = list(reader)
            self.assertEqual(fields, expected_result)

    def writerAssertEqual(self, input, expected_result):
        with TemporaryFile("w+", newline='') as fileobj:
            writer = csv.writer(fileobj, dialect = self.dialect)
            writer.writerows(input)
            fileobj.seek(0)
            self.assertEqual(fileobj.read(), expected_result)

class TestDialectExcel(TestCsvBase):
    dialect = 'excel'

    def test_single(self):
        self.readerAssertEqual('abc', [['abc']])

    def test_simple(self):
        self.readerAssertEqual('1,2,3,4,5', [['1','2','3','4','5']])

    def test_blankline(self):
        self.readerAssertEqual('', [])

    def test_empty_fields(self):
        self.readerAssertEqual(',', [['', '']])

    def test_singlequoted(self):
        self.readerAssertEqual('""', [['']])

    def test_singlequoted_left_empty(self):
        self.readerAssertEqual('"",', [['','']])

    def test_singlequoted_right_empty(self):
        self.readerAssertEqual(',""', [['','']])

    def test_single_quoted_quote(self):
        self.readerAssertEqual('""""', [['"']])

    def test_quoted_quotes(self):
        self.readerAssertEqual('""""""', [['""']])

    def test_inline_quote(self):
        self.readerAssertEqual('a""b', [['a""b']])

    def test_inline_quotes(self):
        self.readerAssertEqual('a"b"c', [['a"b"c']])

    def test_quotes_and_more(self):
        # Excel would never write a field containing '"a"b', but when
        # reading one, it will return 'ab'.
        self.readerAssertEqual('"a"b', [['ab']])

    def test_lone_quote(self):
        self.readerAssertEqual('a"b', [['a"b']])

    def test_quote_and_quote(self):
        # Excel would never write a field containing '"a" "b"', but when
        # reading one, it will return 'a "b"'.
        self.readerAssertEqual('"a" "b"', [['a "b"']])

    def test_space_and_quote(self):
        self.readerAssertEqual(' "a"', [[' "a"']])

    def test_quoted(self):
        self.readerAssertEqual('1,2,3,"I think, therefore I am",5,6',
                               [['1', '2', '3',
                                 'I think, therefore I am',
                                 '5', '6']])

    def test_quoted_quote(self):
        self.readerAssertEqual('1,2,3,"""I see,"" said the blind man","as he picked up his hammer and saw"',
                               [['1', '2', '3',
                                 '"I see," said the blind man',
                                 'as he picked up his hammer and saw']])

    def test_quoted_nl(self):
        input = '''\
1,2,3,"""I see,""
said the blind man","as he picked up his
hammer and saw"
9,8,7,6'''
        self.readerAssertEqual(input,
                               [['1', '2', '3',
                                   '"I see,"\nsaid the blind man',
                                   'as he picked up his\nhammer and saw'],
                                ['9','8','7','6']])

    def test_dubious_quote(self):
        self.readerAssertEqual('12,12,1",', [['12', '12', '1"', '']])

    def test_null(self):
        self.writerAssertEqual([], '')

    def test_single_writer(self):
        self.writerAssertEqual([['abc']], 'abc\r\n')

    def test_simple_writer(self):
        self.writerAssertEqual([[1, 2, 'abc', 3, 4]], '1,2,abc,3,4\r\n')

    def test_quotes(self):
        self.writerAssertEqual([[1, 2, 'a"bc"', 3, 4]], '1,2,"a""bc""",3,4\r\n')

    def test_quote_fieldsep(self):
        self.writerAssertEqual([['abc,def']], '"abc,def"\r\n')

    def test_newlines(self):
        self.writerAssertEqual([[1, 2, 'a\nbc', 3, 4]], '1,2,"a\nbc",3,4\r\n')

class EscapedExcel(csv.excel):
    quoting = csv.QUOTE_NONE
    escapechar = '\\'

class TestEscapedExcel(TestCsvBase):
    dialect = EscapedExcel()

    def test_escape_fieldsep(self):
        self.writerAssertEqual([['abc,def']], 'abc\\,def\r\n')

    def test_read_escape_fieldsep(self):
        self.readerAssertEqual('abc\\,def\r\n', [['abc,def']])

class TestDialectUnix(TestCsvBase):
    dialect = 'unix'

    def test_simple_writer(self):
        self.writerAssertEqual([[1, 'abc def', 'abc']], '"1","abc def","abc"\n')

    def test_simple_reader(self):
        self.readerAssertEqual('"1","abc def","abc"\n', [['1', 'abc def', 'abc']])

class QuotedEscapedExcel(csv.excel):
    quoting = csv.QUOTE_NONNUMERIC
    escapechar = '\\'

class TestQuotedEscapedExcel(TestCsvBase):
    dialect = QuotedEscapedExcel()

    def test_write_escape_fieldsep(self):
        self.writerAssertEqual([['abc,def']], '"abc,def"\r\n')

    def test_read_escape_fieldsep(self):
        self.readerAssertEqual('"abc\\,def"\r\n', [['abc,def']])

class TestDictFields(unittest.TestCase):
    ### "long" means the row is longer than the number of fieldnames
    ### "short" means there are fewer elements in the row than fieldnames
    def test_write_simple_dict(self):
        with TemporaryFile("w+", newline='') as fileobj:
            writer = csv.DictWriter(fileobj, fieldnames = ["f1", "f2", "f3"])
            writer.writeheader()
            fileobj.seek(0)
            self.assertEqual(fileobj.readline(), "f1,f2,f3\r\n")
            writer.writerow({"f1": 10, "f3": "abc"})
            fileobj.seek(0)
            fileobj.readline() # header
            self.assertEqual(fileobj.read(), "10,,abc\r\n")

    def test_write_multiple_dict_rows(self):
        fileobj = StringIO()
        writer = csv.DictWriter(fileobj, fieldnames=["f1", "f2", "f3"])
        writer.writeheader()
        self.assertEqual(fileobj.getvalue(), "f1,f2,f3\r\n")
        writer.writerows([{"f1": 1, "f2": "abc", "f3": "f"},
                          {"f1": 2, "f2": 5, "f3": "xyz"}])
        self.assertEqual(fileobj.getvalue(),
                         "f1,f2,f3\r\n1,abc,f\r\n2,5,xyz\r\n")

    def test_write_no_fields(self):
        fileobj = StringIO()
        self.assertRaises(TypeError, csv.DictWriter, fileobj)

    def test_write_fields_not_in_fieldnames(self):
        with TemporaryFile("w+", newline='') as fileobj:
            writer = csv.DictWriter(fileobj, fieldnames = ["f1", "f2", "f3"])
            # Of special note is the non-string key (issue 19449)
            with self.assertRaises(ValueError) as cx:
                writer.writerow({"f4": 10, "f2": "spam", 1: "abc"})
            exception = str(cx.exception)
            self.assertIn("fieldnames", exception)
            self.assertIn("'f4'", exception)
            self.assertNotIn("'f2'", exception)
            self.assertIn("1", exception)

    def test_typo_in_extrasaction_raises_error(self):
        fileobj = StringIO()
        self.assertRaises(ValueError, csv.DictWriter, fileobj, ['f1', 'f2'],
                          extrasaction="raised")

    def test_write_field_not_in_field_names_raise(self):
        fileobj = StringIO()
        writer = csv.DictWriter(fileobj, ['f1', 'f2'], extrasaction="raise")
        dictrow = {'f0': 0, 'f1': 1, 'f2': 2, 'f3': 3}
        self.assertRaises(ValueError, csv.DictWriter.writerow, writer, dictrow)

    def test_write_field_not_in_field_names_ignore(self):
        fileobj = StringIO()
        writer = csv.DictWriter(fileobj, ['f1', 'f2'], extrasaction="ignore")
        dictrow = {'f0': 0, 'f1': 1, 'f2': 2, 'f3': 3}
        csv.DictWriter.writerow(writer, dictrow)
        self.assertEqual(fileobj.getvalue(), "1,2\r\n")

    def test_read_dict_fields(self):
        with TemporaryFile("w+") as fileobj:
            fileobj.write("1,2,abc\r\n")
            fileobj.seek(0)
            reader = csv.DictReader(fileobj,
                                    fieldnames=["f1", "f2", "f3"])
            self.assertEqual(next(reader), {"f1": '1', "f2": '2', "f3": 'abc'})

    def test_read_dict_no_fieldnames(self):
        with TemporaryFile("w+") as fileobj:
            fileobj.write("f1,f2,f3\r\n1,2,abc\r\n")
            fileobj.seek(0)
            reader = csv.DictReader(fileobj)
            self.assertEqual(next(reader), {"f1": '1', "f2": '2', "f3": 'abc'})
            self.assertEqual(reader.fieldnames, ["f1", "f2", "f3"])

    # Two test cases to make sure existing ways of implicitly setting
    # fieldnames continue to work.  Both arise from discussion in issue3436.
    def test_read_dict_fieldnames_from_file(self):
        with TemporaryFile("w+") as fileobj:
            fileobj.write("f1,f2,f3\r\n1,2,abc\r\n")
            fileobj.seek(0)
            reader = csv.DictReader(fileobj,
                                    fieldnames=next(csv.reader(fileobj)))
            self.assertEqual(reader.fieldnames, ["f1", "f2", "f3"])
            self.assertEqual(next(reader), {"f1": '1', "f2": '2', "f3": 'abc'})

    def test_read_dict_fieldnames_chain(self):
        import itertools
        with TemporaryFile("w+") as fileobj:
            fileobj.write("f1,f2,f3\r\n1,2,abc\r\n")
            fileobj.seek(0)
            reader = csv.DictReader(fileobj)
            first = next(reader)
            for row in itertools.chain([first], reader):
                self.assertEqual(reader.fieldnames, ["f1", "f2", "f3"])
                self.assertEqual(row, {"f1": '1', "f2": '2', "f3": 'abc'})

    def test_read_long(self):
        with TemporaryFile("w+") as fileobj:
            fileobj.write("1,2,abc,4,5,6\r\n")
            fileobj.seek(0)
            reader = csv.DictReader(fileobj,
                                    fieldnames=["f1", "f2"])
            self.assertEqual(next(reader), {"f1": '1', "f2": '2',
                                             None: ["abc", "4", "5", "6"]})

    def test_read_long_with_rest(self):
        with TemporaryFile("w+") as fileobj:
            fileobj.write("1,2,abc,4,5,6\r\n")
            fileobj.seek(0)
            reader = csv.DictReader(fileobj,
                                    fieldnames=["f1", "f2"], restkey="_rest")
            self.assertEqual(next(reader), {"f1": '1', "f2": '2',
                                             "_rest": ["abc", "4", "5", "6"]})

    def test_read_long_with_rest_no_fieldnames(self):
        with TemporaryFile("w+") as fileobj:
            fileobj.write("f1,f2\r\n1,2,abc,4,5,6\r\n")
            fileobj.seek(0)
            reader = csv.DictReader(fileobj, restkey="_rest")
            self.assertEqual(reader.fieldnames, ["f1", "f2"])
            self.assertEqual(next(reader), {"f1": '1', "f2": '2',
                                             "_rest": ["abc", "4", "5", "6"]})

    def test_read_short(self):
        with TemporaryFile("w+") as fileobj:
            fileobj.write("1,2,abc,4,5,6\r\n1,2,abc\r\n")
            fileobj.seek(0)
            reader = csv.DictReader(fileobj,
                                    fieldnames="1 2 3 4 5 6".split(),
                                    restval="DEFAULT")
            self.assertEqual(next(reader), {"1": '1', "2": '2', "3": 'abc',
                                             "4": '4', "5": '5', "6": '6'})
            self.assertEqual(next(reader), {"1": '1', "2": '2', "3": 'abc',
                                             "4": 'DEFAULT', "5": 'DEFAULT',
                                             "6": 'DEFAULT'})

    def test_read_multi(self):
        sample = [
            '2147483648,43.0e12,17,abc,def\r\n',
            '147483648,43.0e2,17,abc,def\r\n',
            '47483648,43.0,170,abc,def\r\n'
            ]

        reader = csv.DictReader(sample,
                                fieldnames="i1 float i2 s1 s2".split())
        self.assertEqual(next(reader), {"i1": '2147483648',
                                         "float": '43.0e12',
                                         "i2": '17',
                                         "s1": 'abc',
                                         "s2": 'def'})

    def test_read_with_blanks(self):
        reader = csv.DictReader(["1,2,abc,4,5,6\r\n","\r\n",
                                 "1,2,abc,4,5,6\r\n"],
                                fieldnames="1 2 3 4 5 6".split())
        self.assertEqual(next(reader), {"1": '1', "2": '2', "3": 'abc',
                                         "4": '4', "5": '5', "6": '6'})
        self.assertEqual(next(reader), {"1": '1', "2": '2', "3": 'abc',
                                         "4": '4', "5": '5', "6": '6'})

    def test_read_semi_sep(self):
        reader = csv.DictReader(["1;2;abc;4;5;6\r\n"],
                                fieldnames="1 2 3 4 5 6".split(),
                                delimiter=';')
        self.assertEqual(next(reader), {"1": '1', "2": '2', "3": 'abc',
                                         "4": '4', "5": '5', "6": '6'})

class TestArrayWrites(unittest.TestCase):
    def test_int_write(self):
        import array
        contents = [(20-i) for i in range(20)]
        a = array.array('i', contents)

        with TemporaryFile("w+", newline='') as fileobj:
            writer = csv.writer(fileobj, dialect="excel")
            writer.writerow(a)
            expected = ",".join([str(i) for i in a])+"\r\n"
            fileobj.seek(0)
            self.assertEqual(fileobj.read(), expected)

    def test_double_write(self):
        import array
        contents = [(20-i)*0.1 for i in range(20)]
        a = array.array('d', contents)
        with TemporaryFile("w+", newline='') as fileobj:
            writer = csv.writer(fileobj, dialect="excel")
            writer.writerow(a)
            expected = ",".join([str(i) for i in a])+"\r\n"
            fileobj.seek(0)
            self.assertEqual(fileobj.read(), expected)

    def test_float_write(self):
        import array
        contents = [(20-i)*0.1 for i in range(20)]
        a = array.array('f', contents)
        with TemporaryFile("w+", newline='') as fileobj:
            writer = csv.writer(fileobj, dialect="excel")
            writer.writerow(a)
            expected = ",".join([str(i) for i in a])+"\r\n"
            fileobj.seek(0)
            self.assertEqual(fileobj.read(), expected)

    def test_char_write(self):
        import array, string
        a = array.array('u', string.ascii_letters)

        with TemporaryFile("w+", newline='') as fileobj:
            writer = csv.writer(fileobj, dialect="excel")
            writer.writerow(a)
            expected = ",".join(a)+"\r\n"
            fileobj.seek(0)
            self.assertEqual(fileobj.read(), expected)

class TestDialectValidity(unittest.TestCase):
    def test_quoting(self):
        class mydialect(csv.Dialect):
            delimiter = ";"
            escapechar = '\\'
            doublequote = False
            skipinitialspace = True
            lineterminator = '\r\n'
            quoting = csv.QUOTE_NONE
        d = mydialect()
        self.assertEqual(d.quoting, csv.QUOTE_NONE)

        mydialect.quoting = None
        self.assertRaises(csv.Error, mydialect)

        mydialect.doublequote = True
        mydialect.quoting = csv.QUOTE_ALL
        mydialect.quotechar = '"'
        d = mydialect()
        self.assertEqual(d.quoting, csv.QUOTE_ALL)
        self.assertEqual(d.quotechar, '"')
        self.assertTrue(d.doublequote)

        mydialect.quotechar = "''"
        with self.assertRaises(csv.Error) as cm:
            mydialect()
        self.assertEqual(str(cm.exception),
                         '"quotechar" must be a 1-character string')

        mydialect.quotechar = 4
        with self.assertRaises(csv.Error) as cm:
            mydialect()
        self.assertEqual(str(cm.exception),
                         '"quotechar" must be string, not int')

    def test_delimiter(self):
        class mydialect(csv.Dialect):
            delimiter = ";"
            escapechar = '\\'
            doublequote = False
            skipinitialspace = True
            lineterminator = '\r\n'
            quoting = csv.QUOTE_NONE
        d = mydialect()
        self.assertEqual(d.delimiter, ";")

        mydialect.delimiter = ":::"
        with self.assertRaises(csv.Error) as cm:
            mydialect()
        self.assertEqual(str(cm.exception),
                         '"delimiter" must be a 1-character string')

        mydialect.delimiter = ""
        with self.assertRaises(csv.Error) as cm:
            mydialect()
        self.assertEqual(str(cm.exception),
                         '"delimiter" must be a 1-character string')

        mydialect.delimiter = b","
        with self.assertRaises(csv.Error) as cm:
            mydialect()
        self.assertEqual(str(cm.exception),
                         '"delimiter" must be string, not bytes')

        mydialect.delimiter = 4
        with self.assertRaises(csv.Error) as cm:
            mydialect()
        self.assertEqual(str(cm.exception),
                         '"delimiter" must be string, not int')

    def test_lineterminator(self):
        class mydialect(csv.Dialect):
            delimiter = ";"
            escapechar = '\\'
            doublequote = False
            skipinitialspace = True
            lineterminator = '\r\n'
            quoting = csv.QUOTE_NONE
        d = mydialect()
        self.assertEqual(d.lineterminator, '\r\n')

        mydialect.lineterminator = ":::"
        d = mydialect()
        self.assertEqual(d.lineterminator, ":::")

        mydialect.lineterminator = 4
        with self.assertRaises(csv.Error) as cm:
            mydialect()
        self.assertEqual(str(cm.exception),
                         '"lineterminator" must be a string')

    def test_invalid_chars(self):
        def create_invalid(field_name, value):
            class mydialect(csv.Dialect):
                pass
            setattr(mydialect, field_name, value)
            d = mydialect()

        for field_name in ("delimiter", "escapechar", "quotechar"):
            with self.subTest(field_name=field_name):
                self.assertRaises(csv.Error, create_invalid, field_name, "")
                self.assertRaises(csv.Error, create_invalid, field_name, "abc")
                self.assertRaises(csv.Error, create_invalid, field_name, b'x')
                self.assertRaises(csv.Error, create_invalid, field_name, 5)


class TestSniffer(unittest.TestCase):
    sample1 = """\
Harry's, Arlington Heights, IL, 2/1/03, Kimi Hayes
Shark City, Glendale Heights, IL, 12/28/02, Prezence
Tommy's Place, Blue Island, IL, 12/28/02, Blue Sunday/White Crow
Stonecutters Seafood and Chop House, Lemont, IL, 12/19/02, Week Back
"""
    sample2 = """\
'Harry''s':'Arlington Heights':'IL':'2/1/03':'Kimi Hayes'
'Shark City':'Glendale Heights':'IL':'12/28/02':'Prezence'
'Tommy''s Place':'Blue Island':'IL':'12/28/02':'Blue Sunday/White Crow'
'Stonecutters ''Seafood'' and Chop House':'Lemont':'IL':'12/19/02':'Week Back'
"""
    header1 = '''\
"venue","city","state","date","performers"
'''
    sample3 = '''\
05/05/03?05/05/03?05/05/03?05/05/03?05/05/03?05/05/03
05/05/03?05/05/03?05/05/03?05/05/03?05/05/03?05/05/03
05/05/03?05/05/03?05/05/03?05/05/03?05/05/03?05/05/03
'''

    sample4 = '''\
2147483648;43.0e12;17;abc;def
147483648;43.0e2;17;abc;def
47483648;43.0;170;abc;def
'''

    sample5 = "aaa\tbbb\r\nAAA\t\r\nBBB\t\r\n"
    sample6 = "a|b|c\r\nd|e|f\r\n"
    sample7 = "'a'|'b'|'c'\r\n'd'|e|f\r\n"

# Issue 18155: Use a delimiter that is a special char to regex:

    header2 = '''\
"venue"+"city"+"state"+"date"+"performers"
'''
    sample8 = """\
Harry's+ Arlington Heights+ IL+ 2/1/03+ Kimi Hayes
Shark City+ Glendale Heights+ IL+ 12/28/02+ Prezence
Tommy's Place+ Blue Island+ IL+ 12/28/02+ Blue Sunday/White Crow
Stonecutters Seafood and Chop House+ Lemont+ IL+ 12/19/02+ Week Back
"""
    sample9 = """\
'Harry''s'+ Arlington Heights'+ 'IL'+ '2/1/03'+ 'Kimi Hayes'
'Shark City'+ Glendale Heights'+' IL'+ '12/28/02'+ 'Prezence'
'Tommy''s Place'+ Blue Island'+ 'IL'+ '12/28/02'+ 'Blue Sunday/White Crow'
'Stonecutters ''Seafood'' and Chop House'+ 'Lemont'+ 'IL'+ '12/19/02'+ 'Week Back'
"""

    def test_has_header(self):
        sniffer = csv.Sniffer()
        self.assertEqual(sniffer.has_header(self.sample1), False)
        self.assertEqual(sniffer.has_header(self.header1 + self.sample1),
                         True)

    def test_has_header_regex_special_delimiter(self):
        sniffer = csv.Sniffer()
        self.assertEqual(sniffer.has_header(self.sample8), False)
        self.assertEqual(sniffer.has_header(self.header2 + self.sample8),
                         True)

    def test_sniff(self):
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(self.sample1)
        self.assertEqual(dialect.delimiter, ",")
        self.assertEqual(dialect.quotechar, '"')
        self.assertEqual(dialect.skipinitialspace, True)

        dialect = sniffer.sniff(self.sample2)
        self.assertEqual(dialect.delimiter, ":")
        self.assertEqual(dialect.quotechar, "'")
        self.assertEqual(dialect.skipinitialspace, False)

    def test_delimiters(self):
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(self.sample3)
        # given that all three lines in sample3 are equal,
        # I think that any character could have been 'guessed' as the
        # delimiter, depending on dictionary order
        self.assertIn(dialect.delimiter, self.sample3)
        dialect = sniffer.sniff(self.sample3, delimiters="?,")
        self.assertEqual(dialect.delimiter, "?")
        dialect = sniffer.sniff(self.sample3, delimiters="/,")
        self.assertEqual(dialect.delimiter, "/")
        dialect = sniffer.sniff(self.sample4)
        self.assertEqual(dialect.delimiter, ";")
        dialect = sniffer.sniff(self.sample5)
        self.assertEqual(dialect.delimiter, "\t")
        dialect = sniffer.sniff(self.sample6)
        self.assertEqual(dialect.delimiter, "|")
        dialect = sniffer.sniff(self.sample7)
        self.assertEqual(dialect.delimiter, "|")
        self.assertEqual(dialect.quotechar, "'")
        dialect = sniffer.sniff(self.sample8)
        self.assertEqual(dialect.delimiter, '+')
        dialect = sniffer.sniff(self.sample9)
        self.assertEqual(dialect.delimiter, '+')
        self.assertEqual(dialect.quotechar, "'")

    def test_doublequote(self):
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(self.header1)
        self.assertFalse(dialect.doublequote)
        dialect = sniffer.sniff(self.header2)
        self.assertFalse(dialect.doublequote)
        dialect = sniffer.sniff(self.sample2)
        self.assertTrue(dialect.doublequote)
        dialect = sniffer.sniff(self.sample8)
        self.assertFalse(dialect.doublequote)
        dialect = sniffer.sniff(self.sample9)
        self.assertTrue(dialect.doublequote)

class NUL:
    def write(s, *args):
        pass
    writelines = write

@unittest.skipUnless(hasattr(sys, "gettotalrefcount"),
                     'requires sys.gettotalrefcount()')
class TestLeaks(unittest.TestCase):
    def test_create_read(self):
        delta = 0
        lastrc = sys.gettotalrefcount()
        for i in range(20):
            gc.collect()
            self.assertEqual(gc.garbage, [])
            rc = sys.gettotalrefcount()
            csv.reader(["a,b,c\r\n"])
            csv.reader(["a,b,c\r\n"])
            csv.reader(["a,b,c\r\n"])
            delta = rc-lastrc
            lastrc = rc
        # if csv.reader() leaks, last delta should be 3 or more
        self.assertEqual(delta < 3, True)

    def test_create_write(self):
        delta = 0
        lastrc = sys.gettotalrefcount()
        s = NUL()
        for i in range(20):
            gc.collect()
            self.assertEqual(gc.garbage, [])
            rc = sys.gettotalrefcount()
            csv.writer(s)
            csv.writer(s)
            csv.writer(s)
            delta = rc-lastrc
            lastrc = rc
        # if csv.writer() leaks, last delta should be 3 or more
        self.assertEqual(delta < 3, True)

    def test_read(self):
        delta = 0
        rows = ["a,b,c\r\n"]*5
        lastrc = sys.gettotalrefcount()
        for i in range(20):
            gc.collect()
            self.assertEqual(gc.garbage, [])
            rc = sys.gettotalrefcount()
            rdr = csv.reader(rows)
            for row in rdr:
                pass
            delta = rc-lastrc
            lastrc = rc
        # if reader leaks during read, delta should be 5 or more
        self.assertEqual(delta < 5, True)

    def test_write(self):
        delta = 0
        rows = [[1,2,3]]*5
        s = NUL()
        lastrc = sys.gettotalrefcount()
        for i in range(20):
            gc.collect()
            self.assertEqual(gc.garbage, [])
            rc = sys.gettotalrefcount()
            writer = csv.writer(s)
            for row in rows:
                writer.writerow(row)
            delta = rc-lastrc
            lastrc = rc
        # if writer leaks during write, last delta should be 5 or more
        self.assertEqual(delta < 5, True)

class TestUnicode(unittest.TestCase):

    names = ["Martin von Löwis",
             "Marc André Lemburg",
             "Guido van Rossum",
             "François Pinard"]

    def test_unicode_read(self):
        with TemporaryFile("w+", newline='', encoding="utf-8") as fileobj:
            fileobj.write(",".join(self.names) + "\r\n")
            fileobj.seek(0)
            reader = csv.reader(fileobj)
            self.assertEqual(list(reader), [self.names])


    def test_unicode_write(self):
        with TemporaryFile("w+", newline='', encoding="utf-8") as fileobj:
            writer = csv.writer(fileobj)
            writer.writerow(self.names)
            expected = ",".join(self.names)+"\r\n"
            fileobj.seek(0)
            self.assertEqual(fileobj.read(), expected)

class KeyOrderingTest(unittest.TestCase):

    def test_ordering_for_the_dict_reader_and_writer(self):
        resultset = set()
        for keys in permutations("abcde"):
            with TemporaryFile('w+', newline='', encoding="utf-8") as fileobject:
                dw = csv.DictWriter(fileobject, keys)
                dw.writeheader()
                fileobject.seek(0)
                dr = csv.DictReader(fileobject)
                kt = tuple(dr.fieldnames)
                self.assertEqual(keys, kt)
                resultset.add(kt)
        # Final sanity check: were all permutations unique?
        self.assertEqual(len(resultset), 120, "Key ordering: some key permutations not collected (expected 120)")

    def test_ordered_dict_reader(self):
        data = dedent('''\
            FirstName,LastName
            Eric,Idle
            Graham,Chapman,Over1,Over2

            Under1
            John,Cleese
        ''').splitlines()

        self.assertEqual(list(csv.DictReader(data)),
            [OrderedDict([('FirstName', 'Eric'), ('LastName', 'Idle')]),
             OrderedDict([('FirstName', 'Graham'), ('LastName', 'Chapman'),
                          (None, ['Over1', 'Over2'])]),
             OrderedDict([('FirstName', 'Under1'), ('LastName', None)]),
             OrderedDict([('FirstName', 'John'), ('LastName', 'Cleese')]),
            ])

        self.assertEqual(list(csv.DictReader(data, restkey='OtherInfo')),
            [OrderedDict([('FirstName', 'Eric'), ('LastName', 'Idle')]),
             OrderedDict([('FirstName', 'Graham'), ('LastName', 'Chapman'),
                          ('OtherInfo', ['Over1', 'Over2'])]),
             OrderedDict([('FirstName', 'Under1'), ('LastName', None)]),
             OrderedDict([('FirstName', 'John'), ('LastName', 'Cleese')]),
            ])

        del data[0]            # Remove the header row
        self.assertEqual(list(csv.DictReader(data, fieldnames=['fname', 'lname'])),
            [OrderedDict([('fname', 'Eric'), ('lname', 'Idle')]),
             OrderedDict([('fname', 'Graham'), ('lname', 'Chapman'),
                          (None, ['Over1', 'Over2'])]),
             OrderedDict([('fname', 'Under1'), ('lname', None)]),
             OrderedDict([('fname', 'John'), ('lname', 'Cleese')]),
            ])


class MiscTestCase(unittest.TestCase):
    def test__all__(self):
        extra = {'__doc__', '__version__'}
        support.check__all__(self, csv, ('csv', '_csv'), extra=extra)


if __name__ == '__main__':
    unittest.main()
