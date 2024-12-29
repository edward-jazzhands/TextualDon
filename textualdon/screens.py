# Standard Library Imports
from __future__ import annotations
from typing import cast, Any #, TYPE_CHECKING
# if TYPE_CHECKING:
#     pass
import time

# Third party imports
import clipman
import pyperclip
import PIL.Image

# Textual imports
from textual import on
from textual.binding import Binding
from textual.screen import Screen, ModalScreen
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Label, Checkbox, TextArea, Markdown

# TextualDon imports
from textualdon.simplebutton import SimpleButton
from textualdon.messages import CallbackCancel, OpenRoadmap
from textualdon.sql import SQLite       # this is only for casting purposes
from textualdon.imageviewer import ImageViewer

class TextualdonModalScreen(ModalScreen):

    BINDINGS = [
        Binding("escape", "pop_screen", key_display='Esc', description="Close the pop-up screen.", show=True),
        Binding("up,left", "focus_previous", description="Focus the previous button."),
        Binding("down,right", "focus_next", description="Focus the next button."),
    ]

    controls = "Arrow keys (or tab): navigate | Enter: select | Esc: close"

    def action_pop_screen(self):

        self.log.info(f"screen stack: {self.app.screen_stack}")
        self.app.pop_screen()
        # screen_stack = self.app.screen_stack

    def on_mount(self):
        self.mount(
            Container(
                Label(self.controls, classes='screen_label'),
                classes='screen_container wide help',
                id="help_container"
            )
        )        

    def action_focus_previous(self):
        self.focus_previous()
    
    def action_focus_next(self):
        self.focus_next()


class ImageScreen(Screen):
    """Called by `ImageViewerWidget.fullscreen` (widgets.py)
    Callback: None."""

    BINDINGS = [
        Binding("escape", "dismiss", key_display='Esc', description="Close the image screen."),
        Binding("i", "zoom_in", description="Zoom the image in."),
        Binding("o", "zoom_out", description="Zoom the image out."),
        Binding("up", "pan_up", description="Pan the image up."),
        Binding("down", "pan_down", description="Pan the image down."),
        Binding("left", "pan_left", description="Pan the image left."),
        Binding("right", "pan_right", description="Pan the image right."),
    ]

    def __init__(self, image: PIL.Image.Image, **kwargs):
        self.image = image
        super().__init__(**kwargs)

    def compose(self):
        with Container(id='imgview_container', classes='fullscreen'):
            yield ImageViewer(self.image) 
        with Horizontal(classes='screen_buttonbar'):
            yield Button('Close', id='img_close_button')
            yield Label('i/o and arrows (or mousewheel/drag): Zoom in/out and pan | Esc to close', id='imgview_label')

    def on_mount(self):
        self.img_container = self.query_one('#imgview_container')
        self.img_viewer = self.query_one(ImageViewer)
        self.img_container.can_focus = True         # TODO test if this is necessary

    def on_button_pressed(self, button):
        self.dismiss()

    def action_zoom_in(self):
        self.log.info('Zooming in')
        self.img_viewer.image.zoom(-1)
        self.img_viewer.refresh()

    def action_zoom_out(self):
        self.img_viewer.image.zoom(1)
        self.img_viewer.refresh()

    def action_pan_up(self):
        self.img_viewer.image.move(0, 2)    # NOTE: the integer values here are actually
        self.img_viewer.refresh()           # reveresed from how its done in the ImageViewer class.

    def action_pan_down(self):                  # That's because with mouse drag, you always drag up
        self.img_viewer.image.move(0, -2)       # to pull the image down, and vice versa.
        self.img_viewer.refresh()               # But with keyboard, its not normally reversed.

    def action_pan_left(self):                  # So we want up key to move the image up, and
        self.img_viewer.image.move(2, 0)        # Down key to move the image down.
        self.img_viewer.refresh()

    def action_pan_right(self):                 # Also using 2 instead of 1 to make it more sensitive.
        self.img_viewer.image.move(-2, 0)
        self.img_viewer.refresh()


class ConfirmationScreen(TextualdonModalScreen):
    """ Generic screen used in two places. \n
    Called by:
    - `TootWidget.delete_toot` | Callback: `TootWidget._delete_toot` (toot.py) 
    - `SavedUsersManager.user_deleted_confirm` | Callback: `SavedUsersManager.user_deleted` (savedusers.py) """

    def __init__(
        self, 
        forward: Any = None, 
        **kwargs
    ):
        self.forward = forward
        super().__init__(**kwargs)

    def compose(self):
        with Container(classes='screen_container'):
            yield Label('Are you sure? \n', classes='screen_label')
            with Horizontal(classes='screen_buttonbar'):
                yield Button('Yes', id='confirm_yes_button')
                yield Button('Cancel', id='confirm_no_button')

    @on(Button.Pressed, selector='#confirm_yes_button')
    async def confirm_yes(self):

        self.log.info(f'Forward value: {self.forward}')
        if self.forward:
            self.dismiss(self.forward)
        else:
            self.dismiss()         

    @on(Button.Pressed, selector='#confirm_no_button')
    def confirm_no(self):
        self.action_pop_screen()


class NotImplementedScreen(TextualdonModalScreen):
    """ Generic screen used in three places. | Callbacks: None \n
    Called by:
    - `TootBox.search_mode` (tootbox.py)
    - `TootOptionsOtherUser.report_user` (tootscreens.py) 
    - `TootOptionsOtherUser.filter_toot` (tootscreens.py)"""

    controls = "Arrow keys (or tab): navigate | Enter: select | Esc or click anywhere: close"

    def __init__(self, roadmap_name: str, **kwargs):
        super().__init__(**kwargs)
        self.roadmap_name = roadmap_name

    def compose(self):
        with Container(classes='screen_container'):
            yield Label((
                'This feature is not yet implemented. \n\n'
                f'Roadmap entry: {self.roadmap_name} \n'
                ), classes='screen_label'
            )
            with Horizontal(classes='screen_buttonbar'):
                yield Button('Close', id='close_button')
                yield Button('View Roadmap', id='roadmap_button')               

    def on_click(self):
        self.dismiss()

    @on(Button.Pressed, selector='#close_button')
    def report_close(self):
        self.dismiss()  

    @on(Button.Pressed, selector='#roadmap_button')
    def roadmap_button(self):
        self.app.post_message(OpenRoadmap())
        self.dismiss()


class WSLWarning(TextualdonModalScreen):
    """Intro / First time user screen.
    Called by `app.on_mount` | Callback: `app.intro_screens_callback` """

    BINDINGS = [Binding("escape", "pass", show=False)]   # remove the escape key feature here
    def action_pass(self):
        pass
    controls = "Arrow keys (or tab): navigate | Enter: select"

    wsl_warning = """TextualDon has detected that it's running inside of WSL. \n
You might notice little flashes of an error whenever you open a link in your browser. \n
Unfortunately there's nothing I can do about that. You can just ignore it. \n
If you know a solution, feel free to let me know on the github page. \n"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = cast(SQLite, self.app.sqlite)

    def compose(self):

        with Container(classes='screen_container wide'):
            yield Label(self.wsl_warning, classes='screen_label')
            with Horizontal(classes='screen_buttonbar'):
                yield Checkbox("Don't show again", id='warning_checkbox')
                yield Button('Close', id='close_button')               

    def on_mount(self):
        self.checkbox = self.query_one('#warning_checkbox')
        self.focus_next()   

    @on(Button.Pressed, selector='#close_button')
    def report_close(self):
        self.dismiss()    # callback: intro_screens_callback on App

    @on(Checkbox.Changed, selector='#warning_checkbox')
    def toggle_checkbox(self, event: Checkbox.Changed):

        self.db.update_column('settings', 'value', str(event.value), 'name', 'warning_checkbox_wsl')


class FirstWarning(TextualdonModalScreen):
    """Intro / First time user screen.
    Called by `app.on_mount` | Callback: `app.intro_screens_callback` """

    BINDINGS = [Binding("escape", "pass", show=False)]   # remove the escape key feature here
    def action_pass(self):
        pass
    controls = "Arrow keys (or tab): navigate | Enter: select"

    first_warning = """First time users: \n
The Mastodon authentication process will require you to open a browser window \
at least once to login. \n
Unfortunately this does not work over SSH yet. It is on the roadmap. \n
There's 3 options provided to get links into your browser. If one of them \
isn't working, try a different option. \n"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = cast(SQLite, self.app.sqlite)

    def compose(self):

        with Container(classes='screen_container wide'):
            yield Label(self.first_warning, classes='screen_label')
            with Horizontal(classes='screen_buttonbar'):
                yield Checkbox("Don't show again", id='warning_checkbox')
                yield Button('Close', id='close_button')    

    def on_mount(self):
        self.focus_next()

    @on(Button.Pressed, selector='#close_button')
    def report_close(self):
        self.dismiss()   # callback: intro_screens_callback on App

    @on(Checkbox.Changed, selector='#warning_checkbox')
    def toggle_checkbox(self, event: Checkbox.Changed):

        self.db.update_column('settings', 'value', str(event.value), 'name', 'warning_checkbox_first')


class CallbackScreen(TextualdonModalScreen):
    """ Called by `OauthWidget.login_stage3` for the Oauth callback.
    Callback function: None. """
    
    # override the escape key feature here
    BINDINGS = [Binding("escape", "action_cancel_callback", description="Cancel Login", show=False)]   

    controls = "Arrow keys (or tab): navigate | Enter: select | Esc: cancel"

    def __init__(self, link: str, **kwargs):
        super().__init__(**kwargs)
        self.link = link
        self.link_button: SimpleButton | None = None
        self.callback_wait_time = self.app.config.getint('MAIN', 'callback_wait_time')

        if self.app.link_behavior == 0:     
            self.mode_msg = 'Current mode: Open browser window'
            self.label_msg = (
                '[green]Opening browser window.[/green]\n\n'
                'If needed, use an alternative option below.'
            )
        elif self.app.link_behavior == 1:  
            self.mode_msg = 'Current mode: Copy to clipboard'
            self.label_msg = (
                '[green]Link copied to clipboard.[/green]\n'
                'Paste the link in your browser to continue.\n\n'
                'If needed, use an alternative option below.'
            )
        elif self.app.link_behavior == 2:
            self.mode_msg = 'Current mode: Manual copy'
            self.label_msg = (
                'If needed, use an alternative option below.\n'
            )

    def compose(self):
        with Container(classes='screen_container wide'):
            yield Label(self.mode_msg, classes='screen_label')
            yield Label(self.label_msg, classes='screen_label')
            yield TextArea(id="link_box", read_only=True, classes="link_box")
            yield SimpleButton("Open in browser", id='browser_button', classes='screen_button')
            yield SimpleButton("Copy to clipboard", id='clipboard_button', classes='screen_button')
            yield Label(id='callback_label', classes='screen_label')                
            with Horizontal(classes='screen_buttonbar'):
                yield Button('Cancel', id='cancel_button')                

    def on_mount(self):

        self.callback_label   = self.query_one('#callback_label')
        self.browser_button   = self.query_one('#browser_button')
        self.clipboard_button = self.query_one('#clipboard_button')

        def insert_text():
            self.query_one('#link_box').text = self.link
        self.set_timer(self.app.text_insert_time, insert_text)

        if self.app.link_behavior != 2:
            self.app.handle_link(self.link)

        self.start_time = time.time()
        self.set_interval(1, self.update_countdown, repeat=self.callback_wait_time)

    @on(Button.Pressed, selector='#cancel_button')
    def action_cancel_callback(self):
        self.post_message(CallbackCancel())
        self.dismiss()

    @on(SimpleButton.Pressed, selector='#browser_button')
    def link_browser(self):

        def revert_button():
            self.browser_button.update("Open in browser")

        self.app.open_browser(self.link)
        self.browser_button.update('Link opened in browser.')
        self.set_timer(2, revert_button)

    @on(SimpleButton.Pressed, selector='#clipboard_button')
    def link_clipboard(self):

        def revert_button():
            self.clipboard_button.update("Copy to clipboard")

        self.app.copy_to_clipboard(self.link)
        self.clipboard_button.update('Link copied to clipboard.')
        self.set_timer(2, revert_button)

    def update_countdown(self):
        seconds = int(self.callback_wait_time - (time.time() - self.start_time))
        self.callback_label.update(f"Timeout in {seconds} seconds.")


class LinkScreen(TextualdonModalScreen):
    """Called by `App.handle_link` when a link is clicked in Manual Copy mode.
    Callback: None."""

    def __init__(self, link: str, **kwargs):
        super().__init__(**kwargs)
        self.link = link

    def compose(self):
        with Container(classes='screen_container'):
            yield Label('You can copy the link below with ctrl-C (or your normal command)', classes='screen_label')
            yield TextArea(id="link_box", classes="link_box", read_only=True)
            with Horizontal(classes='screen_buttonbar'):
                yield Button('Close', id='close_button')

    def on_mount(self):

        def insert_text():
            self.query_one('#link_box').text = self.link
        self.set_timer(self.app.text_insert_time, insert_text)

    @on(Button.Pressed, selector='#close_button')
    def report_close(self):
        self.dismiss()


class CopyPasteTester(TextualdonModalScreen):
    """Called by `Settings.open_tester_screen` (settings.py)
    Callback: None."""

    instructions = """This will help determine which copy/paste engine works best
on your system. \n
Use a program like Notepad to write some text, and copy \
that text to your clipboard. Then write the exact same text in the box below, \
(or try to paste it), and press the test button. \n
The app will attempt to access your copy-paste buffer and see if it matches \
what you entered.

If above you see 'Internal test failed' on either one, There's a good chance it won't \
work, and you should use one of the other options. \n
Note the app will attempt to use whatever engine you set, regardless of the test results.\n"""

    def compose(self):

        if self.app.clipman_works:
            clipman_status = "Clipman: [green]Internal test passed[/green]\n"
        else:
            clipman_status = "Clipman: [red]Internal test failed[/red]\n"
        if self.app.pyperclip_works:
            pyperclip_status = "Pyperclip: [green]Internal test passed[/green]\n"
        else:
            pyperclip_status = "Pyperclip: [red]Internal test failed[/red]\n"

        if self.app.copypaste_engine == 0:
            engine_status = "Current engine: Textual default\n"
        elif self.app.copypaste_engine == 1:
            engine_status = "Current engine: Pyperclip\n"
        elif self.app.copypaste_engine == 2:
            engine_status = "Current engine: Clipman\n"

        with VerticalScroll(classes='fullscreen'):
            with Container(classes='fullscreen container bordered_primary'):
                yield Label(clipman_status, classes='screen_label h1')
                yield Label(pyperclip_status, classes='screen_label h1')
                yield Label(self.instructions, classes='screen_label')
                yield Label(engine_status, classes='screen_label')
                yield TextArea(id="test_box", classes="link_box")
                yield Label('', id='test_label', classes='screen_label h2')
                yield Label(
                    "Note: Textual default can't be tested directly. \n Just try it out and see if it works.", 
                    classes='screen_label'
                )
                with Horizontal(classes='screen_buttonbar'):
                    yield Button("Test Clipman", id='clipman_test_button', classes='screen_button')
                    yield Button("Test Pyperclip", id='pyperclip_test_button', classes='screen_button')
                    yield Button('Close', id='close_button', classes='screen_button')

    @on(Button.Pressed, selector='#clipman_test_button')
    def run_clipman_test(self):

        test_text = self.query_one('#test_box').text
        paste_text = None
        try:
            paste_text = clipman.paste()
        except Exception as e:
            self.log.error(e)
            # Because this is a test box, we want to silence the error.

        if test_text == paste_text:
            self.query_one('#test_label').update('[green]Clipman test passed.[/green]')
            self.app.notify("Copy/Paste test successful.")
        else:
            self.query_one('#test_label').update('[red]Clipman test failed.[/red]')
            self.app.notify("Copy/Paste test failed.")

    @on(Button.Pressed, selector='#pyperclip_test_button')
    def run_pyperclip_test(self):

        test_text = self.query_one('#test_box').text
        paste_text = None
        try:
            paste_text = pyperclip.paste()
        except Exception as e:
            self.log.error(e)
            # Because this is a test box, we want to silence the error.

        if test_text == paste_text:
            self.query_one('#test_label').update('[green]Pyperclip test passed.[/green]')
            self.app.notify("Copy/Paste test successful.")
        else:
            self.query_one('#test_label').update('[red]Pyperclip test failed.[/red]')
            self.app.notify("Copy/Paste test failed.")

    @on(Button.Pressed, selector='#close_button')
    def window_close(self):
        self.dismiss()
    

class MessageScreen(TextualdonModalScreen):
    """ Generic screen used in two places. | Callbacks: None \n
    Called by:
    - `PortInput.action_info` (settings.py)
    - `WelcomeWidget.show_alpha_message` (widgets.py)"""

    BINDINGS = [
        Binding("enter", "dismiss", description="Close the pop-up screen.", show=True),
    ]
    controls = "Press enter, esc, or click anywhere to close."

    def __init__(self, message: str, **kwargs):
        super().__init__(**kwargs)
        self.message = message

    def compose(self):
        with Container(classes='screen_container wide'):
            yield Label(self.message, classes='screen_label')

    def on_click(self):
        self.dismiss()

class RoadmapScreen(TextualdonModalScreen):

    BINDINGS = [
        Binding("enter", "dismiss", description="Close the pop-up screen.", show=True),
    ]
    controls = "Press enter, esc, or click anywhere to close."

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with open('Roadmap.md', 'r') as f:
            self.roadmap = f.read()

    def compose(self):
        with VerticalScroll(classes='fullscreen'):
            yield Markdown(self.roadmap, classes='fullscreen container bordered_primary')

    def on_mount(self):
        self.query_one(VerticalScroll).focus()

    def on_click(self):
        self.dismiss()