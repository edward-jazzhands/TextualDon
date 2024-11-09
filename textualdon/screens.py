# Standard Library Imports
from __future__ import annotations
from typing import cast, Any #, TYPE_CHECKING
# if TYPE_CHECKING:
#     pass
import time

# Third party imports
import clipman
import PIL.Image
from textual_imageview.viewer import ImageViewer

# Textual imports
from textual import on
from textual.binding import Binding
from textual.screen import Screen, ModalScreen
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Label, Checkbox, TextArea

# TextualDon imports
from textualdon.simplebutton import SimpleButton
from textualdon.messages import CallbackCancel
from textualdon.sql import SQLite       # this is only for casting purposes

class TextualdonModalScreen(ModalScreen):

    BINDINGS = [
        Binding("escape", "pop_screen", key_display='Esc', description="Close the pop-up screen.", show=True),
        Binding("up,left", "focus_previous", description="Focus the previous button."),
        Binding("down,right", "focus_next", description="Focus the next button."),
    ]

    controls = "Arrow keys (or tab): navigate | Enter: select | Esc: close."

    def action_pop_screen(self):

        self.log.info(f"screen stack: {self.app.screen_stack}")
        self.app.pop_screen()
        # screen_stack = self.app.screen_stack

    def on_mount(self):
        self.mount(
            Container(Label(self.controls, classes='screen_label'), classes='screen_container wide help')
        )        

    def action_focus_previous(self):
        self.focus_previous()
    
    def action_focus_next(self):
        self.focus_next()


class TextualdonScreen(Screen):

    BINDINGS = [
        Binding("escape", "pop_screen", key_display='Esc', description="Close the pop-up screen.", show=True),
        # Binding("up", "focus_previous", description="Focus the previous button."),
        # Binding("down", "focus_next", description="Focus the next button."),
    ]

    # these screens dont have universal controls.

    def action_pop_screen(self):

        self.log.info(f"screen stack: {self.app.screen_stack}")
        self.app.pop_screen()
        # screen_stack = self.app.screen_stack

    # def action_focus_previous(self):
    #     self.focus_previous()
    
    # def action_focus_next(self):
    #     self.focus_next()


class ImageScreen(TextualdonScreen):
    """Called by `ImageViewerWidget.on_click` (widgets.py)"""
    #! TODO the on_click usage needs fixing.

    def __init__(self, image: PIL.Image.Image, **kwargs):
        self.image = image
        super().__init__(**kwargs)

    def compose(self):
        with Container(id='imgview_container', classes='fullscreen'):
            yield ImageViewer(self.image) 
        with Horizontal(classes='screen_buttonbar'):
            yield Button('Close', id='img_close_button')
            yield Label('Zoom in/out with mousewheel', id='imgview_label')

    def on_mount(self):
        self.img_container = self.query_one('#imgview_container')
        self.img_container.can_focus = True         # TODO test if this is necessary

    def on_button_pressed(self, button):
        self.app.pop_screen()


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
    - `TootOptionsOtherUser.report_user` (tootoptions.py) 
    - `TootOptionsOtherUser.filter_toot` (tootoptions.py)"""

    controls = "Arrow keys (or tab): navigate | Enter: select | Esc or click anywhere: close."

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

    def on_click(self):
        self.dismiss()

    @on(Button.Pressed, selector='#close_button')
    def report_close(self):
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

    first_warning = """[red]First time users:[/red] \n
Copy to clipboard functionality may not work universally across all environments. \n
On the other hand, opening a browser window should work for most users but it will not work over SSH. \n
There's several options provided to get links to your browser. If you're having issues, \
try a different option in the settings. At least one of them should work. \n
[red blink]You MUST do this at least once to login to your Mastodon account![/red blink] \n"""

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


class CopyPasteTester(TextualdonScreen):
    """Called by `Settings.open_tester_screen` (settings.py)
    Callback: None."""

    instructions = """This will test if 'Clipman' is working on your system. \n
Use a program like Notepad to write some text, and copy \
that text to your clipboard. Then write the exact same text in the box below, \
(or try to paste it), and press the test button. \n
The app will attempt to access your copy-paste buffer and see if it matches \
what you entered.

If above you see 'Internal test failed', it means TextualDon is not using Clipman. It \
will fall back to its default copy/paste system, and this test is guaranteed \
to fail. You may still be able to copy-paste, but we cannot test it directly.
You will need to simply try it and see if it works for you.\n"""

    def compose(self):

        if self.app.clipman_works:
            status = "Status: [green]Internal test passed[/green]\n"
        else:
            status = "Status: [red]Internal test failed[/red]\n"

        with VerticalScroll(classes='fullscreen'):
            with Container(classes='fullscreen container bordered_primary'):
                yield Label(status, classes='screen_label')
                yield Label(self.instructions, classes='screen_label')
                yield TextArea(id="test_box", classes="link_box")
                yield Label('', id='test_label', classes='screen_label')
                yield SimpleButton("Test", id='test_button', classes='screen_button tall')
                with Horizontal(classes='screen_buttonbar'):
                    yield Button('Close', id='close_button')

    @on(SimpleButton.Pressed, selector='#test_button')
    def run_test(self):

        test_text = self.query_one('#test_box').text
        try:
            paste_text = clipman.paste()
        except Exception as e:
            self.log.error(e)
            # Because this is a test box, we want to silence the error.

        if test_text == paste_text:
            self.query_one('#test_label').update('[green]Test passed.[/green]')
            self.app.notify("Copy/Paste test successful.")
        else:
            self.query_one('#test_label').update('[red]Test failed.[/red]')
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