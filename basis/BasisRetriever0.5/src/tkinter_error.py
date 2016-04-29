'''
A small function to put an error message on the screen with Tkinter.

Used by Windows programs started from a desktop icon.
'''

import string
from Tkinter import *


def tkinter_error(msg, title=None, note=None, master=None):
    """Show an error message in a Tkinter dialog.

    msg  text message to display (may contain newlines, etc)
    title  the window title (defaults to 'ERROR')

    The whole point of this is to get *some* output from a python GUI
    program when run from an icon double-click.  We use Tkinter since it's
    part of standard python and we may be trying to say:

        +-----------------------------+
        |  you must install wxPython  |
        +-----------------------------+

    NOTE: For some reason, Ubuntu python doesn't have tkinter installed as
    part of the base install.  Do "sudo apt-get install python-tk".
    """

    ######
    # Define the Application class
    ######

    class Application(Frame):
        def createWidgets(self):
            self.LABEL = Label(self, text=self.text, font=("Courier", 10))
            self.LABEL["fg"] = "black"
            self.LABEL["bg"] = "yellow"
            self.LABEL["justify"] = "left"
            self.LABEL.pack()
            if self.note:
              Label(self, text=self.note).pack()
            self.button = Button(self, text='Copy to Clipboard')
            self.button.pack()
            self.button.bind('<Button-1>', self.Copy)

        def __init__(self, text, master=None, note=None):
            self.text = text
            self.note = note
            self.master = master
            Frame.__init__(self, master)
            self.pack()
            self.createWidgets()

        def Copy(self, event):
            #print 'hast',hasattr(self.master, 'clipboard_append')#self.master.clipboard_clear()
            self.master.clipboard_clear()
            self.master.clipboard_append(self.text)

    # set the title string
    if title is None:
        title = 'ERROR'

    # get the message text
    msg = '\n' + msg.strip() + '\n'

    msg = string.replace(msg, '\r', '')
    msg = string.replace(msg, '\n', '   \n   ')
    app = Application(msg, note=note, master=master)
    app.master.title(title)
    app.master.attributes('-topmost', True)
    app.mainloop()


if __name__ == '__main__':
    tkinter_error('A short message:\n\tHello, world!\n\n'
                  'Some extended chars: \v\a\b',
                  title='Test Error Message')
