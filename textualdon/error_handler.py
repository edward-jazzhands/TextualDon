# Standard Library Imports
from typing import List, Dict, Tuple, cast
from sqlite3 import DatabaseError
from pathlib import Path
from datetime import datetime

# Third party imports
from rich.console import Console
from rich.traceback import Traceback
from mastodon import (
    MastodonError, 
    MastodonNetworkError, 
    MastodonUnauthorizedError,
    MastodonNotFoundError
)
from clipman.exceptions import ClipmanBaseException
from pyperclip import PyperclipException

# Textual Imports
from textual import on
from textual.screen import ModalScreen, Screen
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Label, TextArea
from textual.dom import DOMNode
from textual.binding import Binding
from textual.worker import WorkerError, WorkerFailed, WorkerCancelled
from textual.errors import TextualError
from textual.css.query import NoMatches

# Textualdon Imports
from textualdon.messages import UpdateBannerMessage, SuperNotify
from textualdon.simplebutton import SimpleButton


class SafeModeError(Exception):
    """Raised when the app is in safe mode and a restricted action is attempted."""
    pass


class ErrorHandler(DOMNode):

    def __init__(self, data_dir: Path, **kwargs):
        """Initialize the Error Handler.

        Args:
            data_dir: The directory where the app's data is stored.
            name: The name of the widget.
            id: The ID of the widget in the DOM.
            classes: The CSS classes for the widget. """

        super().__init__(**kwargs)
        self.data_dir = data_dir
        self.logs_dir = self.data_dir / "logs"
        self.logfile = None     # Will be set in the handle_exception method.
        self.loghtml = None     # Will be set in the handle_exception method.

        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.super_error_dict = {}
        self.error_number = 0

    def reset_stored_errors(self):
        """Triggered by app.disable_safe_mode()."""
        self.super_error_dict = {}
        self.error_number = 0

    async def recursive_cause(self, e, error_list) -> List:

        error_list.append(e)

        if hasattr(e, '__notes__') and e.__notes__:
            error_list.append(e.__notes__)

        if hasattr(e, '__cause__') and e.__cause__:    # Check for explicit chaining
            await self.recursive_cause(e.__cause__, error_list)
        elif hasattr(e, '__context') and e.__context__:  # Check for implicit chaining
            await self.recursive_cause(e.__context__, error_list)

        return error_list

    async def handle_exception(self, e: Exception):

        self.log.debug(f"Exception traceback in ErrorHandler: {e.__traceback__}")
        logfile = self.logs_dir / f"error_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')}.txt"
        loghtml = self.logs_dir / f"error_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')}.html"
        self.logfiles = [logfile, loghtml]

        if isinstance(e, SafeModeError):
            self.app.notify("Please disable safe mode to perform this action.", timeout=7)
            return

        try:
            cause = e.__cause__                         # I'm honestly not sure if any of this
            cause_type = type(cause).__name__           # section here is really necessary.
        except: # noqa: E722
            cause = None
            cause_type = None
        try:
            context = e.__context__
            context_type = type(context).__name__
        except: # noqa: E722
            context = None
            context_type = None

        self.log.error(
            f"Exception type: {type(e)}\n"
            f"Cause: {cause_type}: {cause}\n"
            f"Context: {context_type}: {context}\n"
            f"args: {e.args}"
        )

        error_list = []
        try:
            error_msg_list = await self.recursive_cause(e, error_list)
        except: # noqa: E722
            self.log.error("Recursive error cause failed.")
            error_msg_list = [e]
        self.log.debug(error_msg_list)

        if isinstance(e, WorkerFailed):
            #* If a worker failed, its either going to be the Mastodon Proxy class's "APIRunner",
            #* or it'll be some essential part of the app.
            if isinstance(e.error, MastodonError):
                await self.handle_mastodon_error(e.error, error_msg_list)
                return
            
        elif isinstance(e, WorkerCancelled):
            self.log(f"Worker was cancelled: {e}")
            return

        elif isinstance(e, ClipmanBaseException):
            self.app.post_message(UpdateBannerMessage(f"Clipman +failed: {error_msg_list[-1]}"))
            self.app.notify(f"Clipman failed: {error_msg_list[-1]}")
            return
        
        elif isinstance(e, PyperclipException) or "clip.exe" in str(e).lower():
            self.app.post_message(UpdateBannerMessage(f"Pyperclip +failed: {error_msg_list[-1]}"))
            self.app.notify(f"Pyperclip failed: {error_msg_list[-1]}")
            return
        
        #* Then if we cant handle it in some above manner, save it to the super error dict,
        #* and increase the error_number by 1. We only make an addition and increment the counter
        #* if we can't handle the error in some other way.
        #* Errors are stored until the user disables safe mode.

        self.error_number += 1
        self.super_error_dict[self.error_number] = (error_msg_list, self.logfiles)

        #* Any exceptions that we can't handle above get written to a log file, then the user
        #* is shown the more serious App Error Screen, which will suggest they restart the program
        #* and consider posting the error to the issue tracker on Github.

        self.log(f"Current screen stack: {self.app.screen_stack}")
        for screen in self.app.screen_stack:        
            if screen.name == "error_screen":       # prevents having more than 1 error screen.
                screen.update_errors(self.super_error_dict)
                return
                #* we only care about logging the traceback once, for the first error.
                #* all other errors are caused by the first error so we don't need to log them.

        try:
            self.app.enter_safe_mode()
        except Exception as safe_error:
            self.log.error(f"Failed to enter safe mode: {safe_error}")

        try:      #~ Here writes error to log file
            await self.record_log_files(e, logfile, loghtml)
        except Exception as log_error:
            self.log.error(
                "Error writing error report to file. \n"
                f"Error: {log_error}"
            )
        else:
            self.log("Error report written to file.")

        if isinstance(e, MastodonError):
            component = 'mastodon.py'
        elif isinstance(e, DatabaseError):
            component = 'database'
        elif isinstance(e, TextualError) or isinstance(e, NoMatches):
            component = 'textual'
        elif isinstance(e, WorkerError):
            component = 'worker'
        else:
            component = 'python'

        try:
            await self.app.push_screen(ErrorScreen(
                    exception=e,
                    error_msg_list=error_msg_list,
                    component=component,
                    classes="modal_screen",
                    name="error_screen"
                ),
                callback=self.push_report_screen
            )
        except: # noqa: E722
            self.log.error("ERROR pushing error screen.")
            raise e         # if this fails, we want to see the error in the terminal.
        else:
            self.log("Error screen pushed.")

    async def handle_mastodon_error(self, e: Exception, error_msg_list: List):

        #* These will mostly be network or permission related errors. We can just notify the user
        #* and continue the program.

        self.log.debug(f"Mastodon Error type: {type(e)}")
        e_str = str(e)
        e_str_list:list = e_str.replace("'", "").split(", ")
        # deepest_e_str = e_str_list[-1]
        deepest_msg = error_msg_list[-1]

        if isinstance(e, MastodonNetworkError):
            self.app.notify("Network Error: URL doesn't exist, or your internet is down.", timeout=7)
            self.app.post_message(UpdateBannerMessage(f"Mastodon server says: {deepest_msg}"))
            return
        
        if isinstance(e, MastodonUnauthorizedError):
            self.app.notify(f"Mastodon server says: {deepest_msg}", timeout=7)
            self.app.post_message(UpdateBannerMessage(f"Mastodon server says: {deepest_msg}"))
            return

        if isinstance(e, MastodonNotFoundError):
            self.app.post_message(SuperNotify("404: Requested record not found."))
            return

        self.app.post_message(SuperNotify(f"Mastodon Error: {deepest_msg}"))
        self.log.debug(f"Mastodon Error: {e_str_list}")
        

    async def push_report_screen(self, result):
        """Callback function from the ErrorScreen."""

        try:
            await self.app.push_screen(ReportScreen(
                exception=result[0],
                super_error_dict=self.super_error_dict,
                component=result[1],
                classes="fullscreen"
            ))
        except: # noqa: E722
            self.log.error("Error pushing report screen.")
            raise self.e    # safety in case this process fails.
        else:
            self.log("Report screen pushed successfully.")

    async def record_log_files(self, e: Exception, logfile: Path, loghtml: Path):
        """Record the log files to the app's logfiles list."""

        # TODO Check amount of log files and delete oldest over a certain amount (10?)

        with open(logfile, "w") as report_file:
            console = Console(file=report_file, record=True, width=100)
            console.print(f"TextualDon Error Report: {datetime.now()}\n")
            # console.print_exception(show_locals=False)
            traceback = Traceback.from_exception(
                type(e),
                e,
                e.__traceback__,
                show_locals=False
            )
            console.print(traceback)            
            console.save_html(loghtml)

    async def delete_logs(self):
        """Delete all log files."""
        try:
            logs = list(self.logs_dir.iterdir())
            if not logs:
                self.app.post_message(SuperNotify("No log files to delete."))
                return
            for log in logs:
                log.unlink()
        except Exception as e:
            self.log.error(f"Error deleting logs: {e}")
            self.app.post_message(SuperNotify("Error deleting log files"))
        else:
            self.log("Logs deleted.")
            self.app.post_message(SuperNotify("Log files deleted."))

# NOTE: I really would have preferred to combine a bunch of commonality of the two screens
# here into one parent class. However, one is a regular Screen and the other is a ModalScreen.
# I'm sure there's a way to make that work but I didn't feel like digging into it right now.

class ErrorScreen(ModalScreen):

    BINDINGS = [
        Binding('q', 'quit', 'Quit'),
        Binding('i', 'ignore', 'Ignore'),
        Binding("up,left", "focus_previous", description="Focus the previous button."),
        Binding("down,right", "focus_next", description="Focus the next button."),
    ]

    controls = "Arrow keys, Tab/Shift+Tab: navigate | Enter: select | q: quit | i: ignore"   
        
    generic_warning = """TextualDon has encountered an unexpected error. 
Its recommended to quit the app immediately. If you have something you were working \
on, you can attempt to hit ignore and save your work. But be warned, there is a chance \
the app will freeze or crash as soon as you press the ignore button.

For full error information and to file a report, please press 'Read and Report' \n"""

    db_warning = """The database has encountered an error.
Ignoring this warning is disabled. The app will not work without the database.

For full error information and to file a report, please press 'Read and Report'  \n"""

    mastodon_warning = """The Mastodon connection returned an unexpected error. \n """


    def __init__(
        self, 
        exception: Exception, 
        error_msg_list: List, 
        component: str,
        **kwargs
    ):
        """Args:
            exception: The exception that was raised.
            error_msg_list: A list of error messages.
            logfiles: A list of log files to display to the user.
            component: The component that raised the error.
            name: The name of the screen.
            id: The ID of the screen in the DOM.
            classes: The CSS classes for the screen. """

        super().__init__(**kwargs)

        self.log(
            "Error screen initialized with exception: "
            f"{exception} and error messages: \n {error_msg_list}\n"
            f"component: {component}"
        )

        self.exception = exception
        self.error_msg_list = error_msg_list
        self.component = component
        self.super_error_count = 1

        if component == 'mastodon':
            self.warning = self.mastodon_warning
            self.banner = "[yellow]Mastodon API Error[/yellow]"
        elif component == 'database':
            self.warning = self.db_warning
            self.banner = "[red]! DATABASE ERROR ![/red]"
        else:
            self.warning = self.generic_warning
            self.banner = "[red blink]! ERROR ![/red blink]"

    def compose(self):

        with Container(classes='screen_container ultrawide'):
            yield Label(self.banner, classes='screen_label')
            yield Label(self.warning, classes='screen_label')
            yield SimpleButton("Show Error", id='show_error', classes='screen_button')
            with VerticalScroll(id="error_scroll"):
                yield Label("Size of error stack: 1", id="error_counter", classes='screen_label left')
                yield Label(f"Component: {self.component}", classes='screen_label left')
                yield Label(f'{type(self.exception).__name__}: {self.error_msg_list[-1]}', classes='screen_label left')
            yield SimpleButton("Read & Report", id='read_report', classes='screen_button')
            with Horizontal(classes='screen_buttonbar'):
                yield Button('Ignore', id='ignore', classes='screen_button large')
                yield Button('Quit', id='quit', classes='screen_button large')
        with Container(classes='screen_container wide help'):
            yield Label(self.controls, classes='screen_label')

    def on_mount(self):

        if self.component == 'database':
            self.query_one('#ignore').disabled = True

        self.query_one("#error_scroll").display = False

    @on(Button.Pressed, selector='#ignore')
    def ignore(self):
        if self.component == 'database':
            self.app.notify("You can't ignore this")
        else:
            self.app.pop_screen()
    
    @on(Button.Pressed, selector='#quit')
    def quitme(self):
        self.app.exit()

    @on(SimpleButton.Pressed, selector='#read_report')
    def read_report(self):
        result = (self.exception, self.component)
        self.dismiss(result)

    @on(SimpleButton.Pressed, selector='#show_error')
    def show_error(self):
        self.query_one("#error_scroll").display = not self.query_one("#error_scroll").display

    def update_errors(self, super_error_dict: Dict):
        self.query_one("#error_counter").update(f"Size of error stack: {len(super_error_dict)}")

    ###~ Keybindings ~###

    def action_focus_previous(self):
        self.focus_previous()
    
    def action_focus_next(self):
        self.focus_next()

    def action_quit(self):
        self.quitme()

    def action_ignore(self):
        self.ignore()
    

class ReportScreen(Screen):

    BINDINGS = [
        Binding('q', 'quit', 'Quit'),
        Binding('i', 'ignore', 'Ignore'),
        Binding("up,left", "focus_previous", description="Focus the previous button."),
        Binding("down,right", "focus_next", description="Focus the next button."),
    ]

    controls = "Arrow keys, Tab/Shift+Tab: navigate | Enter: select | q: quit | i: ignore"   
    gitrepo_path = "https://github.com/edward-jazzhands/textualdon/issues"

    def __init__(
        self, 
        exception: Exception, 
        super_error_dict: Dict,
        component: str,
        **kwargs
    ):
        """
        Args:
            exception: The exception that was raised.
            error_msg_list: A list of error messages.
            logfiles: A list of log files to display to the user.
            component: The component that raised the error.
            name: The name of the screen.
            id: The ID of the screen in the DOM.
            classes: The CSS classes for the screen. """

        super().__init__(**kwargs)
        self.exception:   Exception = exception
        self.super_error_dict: Dict = super_error_dict
        self.component:         str = component

    def compose(self):

        with VerticalScroll(classes='fullscreen'):
            with Container(classes='fullscreen container bordered_red'):
                yield Label("Exceptions are stored here until safe mode is disabled.", classes='screen_label')
                yield TextArea(id="error_box", read_only=True)
                yield SimpleButton("Copy above text to clipboard", id='copy_errors', classes='screen_button')
                yield SimpleButton("Copy log file path to clipboard", id='copy_path', classes='screen_button')
                yield SimpleButton(
                    "Open Rich traceback in your browser (works offline)", id='open_browser', classes='screen_button'
                )
                yield SimpleButton("Open Github issues page", id='open_github', classes='screen_button')
                yield Label(
                    "The logs folder contains both a plain txt version and an html version. \n"
                    "Log file location:", classes='screen_label'
                )
                yield TextArea(id="link_box", read_only=True, classes="link_box")
                yield TextArea(id="github_link", read_only=True, classes="link_box")
                with Horizontal(classes='screen_buttonbar'):
                    yield Button('Ignore & return', id='ignore', classes='screen_button large')
                    yield Button('Quit', id='quit', classes='screen_button large')
            with Container(classes='screen_container wide help'):
                yield Label(self.controls, classes='screen_label')

    def on_mount(self):

        self.error_box = cast(TextArea, self.query_one('#error_box'))
        self.error_box = self.query_one('#error_box')

        if self.component == 'database':
            self.query_one('#ignore').disabled = True

        self.set_timer(self.app.text_insert_time, self.set_text)

    def set_text(self):

        self.error_box.insert(
            f"Component that failed: {self.component}\n\n",
            maintain_selection_offset=False
        )

        # key is 1-based index. Each value in dict is tuple: (error_msg_list: List, self.logfiles: List)

        for key, value in self.super_error_dict.items():
            if key == 1:
                self.error_box.insert("Causing error set:\n\n", maintain_selection_offset=False)
            else:
                self.error_box.insert(f"Error set {key}:\n\n", maintain_selection_offset=False)

            for error in value[0]:
                error_type: str = type(error).__name__
                if error_type == 'list':
                    error_type = 'Notes'
                    self.error_box.insert("Notes:\n", maintain_selection_offset=False)
                    for note in error:
                        self.error_box.insert(
                            f"{note}\n",
                            maintain_selection_offset=False
                        )
                else:
                    self.error_box.insert(
                        f"{error_type}: {error}\n\n",
                        maintain_selection_offset=False
                    )

        # key 1 = first error, 2 = second error, etc
        # Each value is a tuple of the error message list and the log files list.
        # [1][0][0] = first error, error message list, first error message
        # [1][1][0] = first error, log files list, first log file path

        self.query_one('#link_box').insert(str(self.super_error_dict[1][1][0]))
        self.query_one('#github_link').insert(self.gitrepo_path)

    @on(Button.Pressed, selector='#ignore')
    def ignore(self):
        if self.component == 'database':
            self.app.notify("You can't ignore this")
        else:
            self.app.pop_screen()

    @on(Button.Pressed, selector='#quit')
    def quitme(self):
        self.app.exit()

    @on(SimpleButton.Pressed, selector='#copy_errors')
    def copy_errors(self):
        self.app.copy_to_clipboard(str(self.error_box.text))

    @on(SimpleButton.Pressed, selector='#copy_path')
    def copy_path(self):
        self.app.copy_to_clipboard(self.super_error_dict[1][1][0])  #  [1][1][0] = log file text

    @on(SimpleButton.Pressed, selector='#open_browser')
    def read_report(self):
        self.app.open_browser(self.super_error_dict[1][1][1])   # [1][1][1] = log file html

    @on(SimpleButton.Pressed, selector='#open_github')
    def open_github(self):
        self.app.handle_link(self.gitrepo_path)

    ###~ Keybindings ~###

    def action_focus_previous(self):
        self.focus_previous()
    
    def action_focus_next(self):
        self.focus_next()

    def action_quit(self):
        self.quitme()

    def action_ignore(self):
        self.ignore()


