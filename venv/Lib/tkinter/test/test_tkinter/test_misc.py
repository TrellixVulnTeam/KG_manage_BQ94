import unittest
import tkinter
from sql_mode import support
from tkinter.test.support import AbstractTkTest

support.requires('gui')

class MiscTest(AbstractTkTest, unittest.TestCase):

    def test_repr(self):
        t = tkinter.Toplevel(self.root, name='top')
        f = tkinter.Frame(t, name='child')
        self.assertEqual(repr(f), '<tkinter.Frame object .top.child>')

    def test_generated_names(self):
        t = tkinter.Toplevel(self.root)
        f = tkinter.Frame(t)
        f2 = tkinter.Frame(t)
        b = tkinter.Button(f2)
        for name in str(b).split('.'):
            self.assertFalse(name.isidentifier(), msg=repr(name))

    def test_tk_setPalette(self):
        root = self.root
        root.tk_setPalette('black')
        self.assertEqual(root['background'], 'black')
        root.tk_setPalette('white')
        self.assertEqual(root['background'], 'white')
        self.assertRaisesRegex(tkinter.TclError,
                '^unknown color name "spam"$',
                root.tk_setPalette, 'spam')

        root.tk_setPalette(background='black')
        self.assertEqual(root['background'], 'black')
        root.tk_setPalette(background='blue', highlightColor='yellow')
        self.assertEqual(root['background'], 'blue')
        self.assertEqual(root['highlightcolor'], 'yellow')
        root.tk_setPalette(background='yellow', highlightColor='blue')
        self.assertEqual(root['background'], 'yellow')
        self.assertEqual(root['highlightcolor'], 'blue')
        self.assertRaisesRegex(tkinter.TclError,
                '^unknown color name "spam"$',
                root.tk_setPalette, background='spam')
        self.assertRaisesRegex(tkinter.TclError,
                '^must specify a background color$',
                root.tk_setPalette, spam='white')
        self.assertRaisesRegex(tkinter.TclError,
                '^must specify a background color$',
                root.tk_setPalette, highlightColor='blue')


tests_gui = (MiscTest, )

if __name__ == "__main__":
    support.run_unittest(*tests_gui)
