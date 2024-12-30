# Standard library imports
from __future__ import annotations
from typing import TYPE_CHECKING, cast
import webbrowser
import platform
import configparser
import os
from collections import deque
from contextlib import contextmanager
from pathlib import Path
import random
import sys
from sqlite3 import DatabaseError       # for testing

if TYPE_CHECKING:
    from textual.app import ComposeResult 
    from mastodon import Mastodon

# third party imports
from mastodon import MastodonError      # for testing
import pyperclip
import clipman
from clipman.exceptions import ClipmanBaseException
from platformdirs import user_data_dir
from textual_pyfiglet.pyfiglet import figlet_format

# Textual imports
from textual import work
from textual.message import Message
# from textual.reactive import reactive
from textual.errors import TextualError     # for testing
from textual.worker import Worker, WorkerState #, WorkerFailed
from textual.events import Resize
from textual.binding import Binding
from textual.app import App, on
from textual.containers import VerticalScroll
from textual.widgets import (
    Footer,
    ContentSwitcher,
    Label,
)

# TextualDon imports
import textualdon.pages as pages
from textualdon.error_handler import ErrorHandler
from textualdon.proxy import MastodonProxy
from textualdon.bars import TopBar, MessageBarWidget, BottomBar, SafeModeBar
from textualdon.tootbox import TootBox
from textualdon.settings import Settings
from textualdon.sql import SQLite
from textualdon.messages import (
    UpdateBannerMessage,
    SuperNotify,
    LoginComplete,
    LoginStatus,
    ExamineToot,
    RefreshCurrentPage,
    SwitchMainContent,
    UserPopupMessage,
    CallbackSuccess,
    CallbackCancel,
    ScrollToWidget,
    EnableSafeMode,
    TriggerRandomError,
    ExceptionMessage,
    DeleteLogs,
    OpenRoadmap
)
from textualdon.screens import (
    WSLWarning,
    FirstWarning,
    LinkScreen,
    RoadmapScreen
)

# Rich imports and setup
# from rich.emoji import Emoji
from rich.text import Text
from rich import traceback
traceback.install()                 # setup functions must go after imports or ruff complains
        

class TextualDon(App):

    class CheckResult(Message):
        pass

    CSS_PATH = [
        "css/main.tcss",
        "css/pages.tcss",
        "css/widgets.tcss",
        "css/bars.tcss",
        "css/toot.tcss",
        "css/settings.tcss",
        "css/screens.tcss",
    ]

    BINDINGS = [
        Binding(key="f1", action="home",      description="Home",             key_display="F1", show=False),
        Binding(key="f2", action="notif",     description="Notifications",    key_display="F2", show=False),
        Binding(key="f3", action="explore",   description="Explore",          key_display="F3", show=False),
        Binding(key="f4", action="live",      description="Live Feeds",       key_display="F4", show=False),
        Binding(key="f5", action="mentions",  description="Private Mentions", key_display="F5", show=False),
        Binding(key="f6", action="bookmarks", description="Bookmarks",        key_display="F6", show=False),
        Binding(key="f7", action="favorites", description="Favorites",        key_display="F7", show=False),
        Binding(key="f8", action="lists",     description="Lists",            key_display="F8", show=False),
        Binding(key="f9", action="settings",  description="Settings",         key_display="F10", show=False),
        Binding(key="f12", action="previous_page", description="Back to Previous Page", key_display="F12", show=False),
        Binding(key="ctrl+r", action="refresh_page", description="Refresh Page", show=False),
        Binding(key="ctrl+d", action="disable_safe_mode", description="Disable Safe Mode", show=False, priority=True),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.error_handler: ErrorHandler | None = None  # Error handler instance
        self.mastodon:     Mastodon | None = None       # API Wrapper instance
        self.sqlite:         SQLite | None = None       # SQLite database instance
        self.instance_url:      str | None = None       # current connected instance
        self.stored_page:       str | None = None       # stored page when the window is too small
        self.logged_in_user_id: int | None = None       # ID of the logged in user
        self.previous_pages = deque(maxlen=5)           # previous pages before the current one
        self.WSL  = False                               # Windows Subsystem for Linux flag
        self.safe_mode = False                          # Safe mode flag
        self.error = False                              # Flag for error state
        self.init_complete = False

        self.current_os = platform.system()
        self.release = platform.uname().release.lower() # nwrite comment: 

        if 'linux' in self.current_os.lower() and 'microsoft' in self.release.lower():
            self.WSL = True

        self.app_name = "textualdon"
        self.data_dir: Path = Path(user_data_dir(appname=self.app_name, ensure_exists=True))    # using platformdirs library

        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_dir, "config.ini")
        self.config = configparser.ConfigParser()      #~ Access the configs globally with self.app.config

        cfg_read = self.config.read(config_path)
        if not cfg_read:
            raise FileNotFoundError("config.ini file not found.")
        
        ##~ Development settings ~##
        self.delete_db_on_start = self.config.getboolean("MAIN", "delete_db_on_start")
        self.force_no_clipman   = self.config.getboolean("MAIN", "force_no_clipman")
        self.force_no_pyperclip = self.config.getboolean("MAIN", "force_no_pyperclip")
        self.text_insert_time = self.config.getfloat("MAIN", "text_insert_time") #* used in many places

        # These are premade figlets for prettying up the dev console.
        # Because I'm just super fancy like that.
        self.breaker_figlet = figlet_format("-----------", font="smblock").strip() + "\n"  
        self.logo_figlet = figlet_format("  TextualDon  ", font="smblock")

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""

        self.log(Text(f"{self.breaker_figlet}\n{self.logo_figlet}", style="cyan"))

        #~ 3 classes in the app are Hidden classes that inherit from DOMNode:
        # ErrorHandler   (app.error_handler)  |  error_handler.py
        # SQLite         (app.sqlite)         |  sql.py
        # MastodonProxy  (app.mastodon)       |  proxy.py

        try:
            self.error_handler = ErrorHandler(self.data_dir)
        except Exception as e:
            raise e         # if this doesnt work, crash the app.

        with self.capture_exceptions():     # access the SQLite database globally with self.app.sqlite
            self.sqlite = SQLite(
                app_name=self.app_name,
                data_dir=self.data_dir,
                sql_script="create_tables.sql",
                del_on_start=self.delete_db_on_start
            )
        if self.error:
            return
        else:
            self.initial_page = self.sqlite.fetchone(
                "SELECT value FROM settings WHERE name= ?", ("show_on_startup",)
            )[0]
            self.previous_page = self.initial_page

            hatching = self.sqlite.fetchone(
                "SELECT value FROM settings WHERE name= ?", ("hatching",)
            )[0]
            hatching = None if hatching == 'none' else hatching

            self.theme = self.sqlite.fetchone(
                "SELECT value FROM settings WHERE name= ?", ("current_theme",)
            )[0]

        if self.force_no_clipman:
            self.clipman_works = False
        else:
            try:
                self.clipman_works = self.test_clipman()
            except:  # noqa
                self.clipman_works = False
        if self.force_no_pyperclip:
            self.pyperclip_works = False
        else:
            try:
                self.pyperclip_works = self.test_pyperclip()
            except: # noqa
                self.pyperclip_works = False

        self.log(
            f"Current OS: {self.current_os}\n"
            f"Release: {self.release}\n"
            f"Python version: {platform.python_version()}\n"
            f"WSL: {self.WSL}\n"
            f"Clipman available: {self.clipman_works}\n"
            f"Pyperclip available: {self.pyperclip_works}\n"
            f"Database location: \n{self.sqlite.user_db_path}\n"
        )

        if self.delete_db_on_start:
            self.log.warning(Text("You are in Development Mode. Database is deleted on start.", style="red"))

        with self.capture_exceptions():
            yield TopBar(id="topbar", classes="topbar")
            yield SafeModeBar(id="safe_mode_bar", classes="topbar safemode")
            yield MessageBarWidget(id="message_widget", classes="topbar message")
            yield TootBox(id="main_tootbox")
            with VerticalScroll(id="main_scroll", classes=f"main_scroll {hatching}"):
                with ContentSwitcher(initial=self.initial_page, id="main_switcher"):   
                    yield pages.LoginPage(    id="login_page",  classes=f"page_area {hatching}")                  
                    yield pages.HomePage(     id="home",        classes=f"page_area {hatching}")                        
                    yield pages.NotificationsPage(id="notifications", classes=f"page_area {hatching}")     
                    yield pages.ExplorePage(  id="explore",     classes=f"page_area {hatching}")                    
                    yield pages.LiveFeeds(    id="live_feeds",  classes=f"page_area {hatching}")                 
                    yield pages.PrivateMentionsPage(id="private_mentions", classes=f"page_area {hatching}") 
                    yield pages.BookmarksPage(id="bookmarks",   classes=f"page_area {hatching}")  
                    yield pages.FavoritesPage(id="favorites",   classes=f"page_area {hatching}")  
                    yield pages.ListsPage(    id="lists",       classes=f"page_area {hatching}")            
                    yield pages.TootPage(     id="toot_page",   classes=f"page_area {hatching}")
                    yield pages.UserProfilePage(id="user_page", classes=f"page_area {hatching}")
                    yield pages.TooSmallPage( id="too_small",   classes=f"page_area {hatching}")
                    yield pages.AboutPage(    id="about",       classes=f"page_area {hatching}")
                    yield pages.DevelopmentPage(id="dev_settings", classes=f"page_area {hatching}")
            yield BottomBar(id="bottombar")
            yield Footer(Label("TextualDon"))

    async def on_mount(self):

        if self.error:
            return

        # set convenience properties
        self.main_switcher = cast(ContentSwitcher, self.query_one("#main_switcher"))
        self.main_scroll   = cast(VerticalScroll, self.query_one("#main_scroll"))
        self.main_tootbox  = self.query_one("#main_tootbox")
        self.topbar        = self.query_one("#topbar")
        self.bottom_bar    = self.query_one("#bottombar")
        self.safemode_bar  = self.query_one("#safe_mode_bar")
        self.messagebar    = self.query_one("#message_widget")
        self.login_status  = self.query_one("#login_status")
        self.oauth_widget  = self.query_one("#oauth_widget")

        self.safemode_bar.display = False

        login_page = self.main_switcher.query_one("#login_page")
        self.settings_widget = login_page.query_one("#settings_widget")

        self.main_scroll.can_focus = False 

        self.init_complete = True
        self.log(Text(f"Initialization complete. \n {self.breaker_figlet}", style="green"))

        row1 = self.sqlite.fetchone("SELECT value FROM settings WHERE name= ?", ("show_images",))
        row2 = self.sqlite.fetchone("SELECT value FROM settings WHERE name= ?", ("auto_load",))
        row3 = self.sqlite.fetchone("SELECT value FROM settings WHERE name= ?", ("link_behavior",))
        row4 = self.sqlite.fetchone("SELECT value FROM settings WHERE name= ?", ("copypaste_engine",))
        self.show_images    = (row1[0] == "True")
        self.autoload_value = (row2[0] == "True")
        self.link_behavior    = int(row3[0])       # 0 = open in browser, 1 = copy to clipboard, 2 = helper popup
        self.copypaste_engine = int(row4[0])       # 0 = clipman, 1 = pyperclip, 2 = built-in

        warning_checkbox_wsl  = self.sqlite.fetchone("SELECT value FROM settings WHERE name= ?", ("warning_checkbox_wsl",))
        warning_checkbox_wsl  = (warning_checkbox_wsl[0] == "True")
        warning_checkbox_first = self.sqlite.fetchone("SELECT value FROM settings WHERE name= ?", ("warning_checkbox_first",))
        warning_checkbox_first = (warning_checkbox_first[0] == "True")

        if self.initial_page == "login_page":
            self.focus_login()

        if self.WSL and not warning_checkbox_wsl:
            await self.push_screen(WSLWarning(classes="modal_screen", id="introscreen_wsl"), self.intro_screens_callback)
        if not warning_checkbox_first:                  # pushed after = on top / seen first.
            await self.push_screen(FirstWarning(classes="modal_screen", id="introscreen_first"), self.intro_screens_callback) 

        # Finally:   
        self.oauth_widget.saved_users_manager.check_auto_login() 

    def attach_mastodon(self, mastodon: Mastodon):
        """The proxy class runs all calls to the Mastodon API in a worker thread. \n"""

        self.log("Attaching Mastodon object.")
        self.mastodon = MastodonProxy(mastodon)

    @on(CheckResult)
    def check_result(self):
        """Sends message if API call is hanging"""

        def internal_check():
            if self.api_startflag and not self.api_finishflag:
                workers = list(self.workers._workers)
                self.log.debug(f"HIT 2 SECONDS. ACTIVE WORKERS: {workers}")
                self.post_message(SuperNotify("This is taking a long time..."))
            
        self.set_timer(2, internal_check)   #~ 2 seconds for notification.

    @work(thread=True, exit_on_error=False, group="api_call", exclusive=False)    
    def run_api_call(self, attr, *args, **kwargs):
        """This is used by the Mastodon proxy class in proxy.py
        Would have preferred to put it in that class but it did not work for strange reasons."""

        print(f"Running API call: {attr} with args: {args}, kwargs: {kwargs}")

        self.post_message(self.CheckResult())   # used above ^
        self.api_startflag = True
        self.api_finishflag = False
        
        try:
            api_result = attr(*args, **kwargs)
        except Exception as e:
            raise e
        else:
            return api_result
        finally:
            self.api_finishflag = True

    @contextmanager
    def capture_exceptions(self):
        """Context manager that captures and forwards exceptions to the async error handler. \n\n
        This is here to allow the custom ErrorHandler class to be async. Regular sync functions
        or exceptions can use this context manager to capture exceptions (replacing the `try/except` block).
        ```
        with self.capture_exceptions():
            # dangerous code here
        ``` """
        self.error = False
        try:
            yield
        except Exception as e:
            self.error = True
            tb = sys.exc_info()[2]     
            if tb is not None:
                e.__traceback__ = tb
            self.post_message(ExceptionMessage(e))

    @on(ExceptionMessage)
    async def handle_exception(self, event: ExceptionMessage):
        """Exceptions caught with capture_exceptions (above) are sent here for transfer to
        async error handler class."""
        try:
            await self.error_handler.handle_exception(event.exception)
        except Exception as e:
            self.log.error(f"Error handler failed to handle exception: {e}")
            self._handle_exception(e)

    def intro_screens_callback(self, _=None):
        """ Function to manage the two intro screens. If both are active, the first callback will \
        focus the second screen instead of the login widget. \n
        The first argument is required to be here because self.dismiss in the screen class \
        always sends an argument. If nothing is provided it sends `None`. """

        self.log(f"intro_screens_callback: Current active screen: {self.screen.id}")

        if self.screen.id in ["introscreen_wsl", "introscreen_first"]:
            self.screen.query_one("#warning_checkbox").focus()
        else:
            self.focus_login()

    def focus_login(self):
        """Triggered by intro_screens_callback above, or on_mount if there's no intro popup."""

        self.set_focus(self.oauth_widget.login_input)
        self.post_message(ScrollToWidget(self.oauth_widget.login_input))

    def on_resize(self, event: Resize):

        if self.init_complete:
            width, height = event.size
            if self.main_switcher.current != "too_small" and width < 65:
                self.stored_page = self.main_switcher.current
                self.post_message(SwitchMainContent("too_small"))
                self.main_tootbox.visible = False
                self.log.debug(f"stored_page: {self.stored_page}")

            if self.main_switcher.current == "too_small" and width > 65:
                self.post_message(SwitchMainContent(self.stored_page))
                self.main_tootbox.visible = True

    def handle_link(self, link: str):

        if self.link_behavior == 0:
            self.open_browser(link)
        elif self.link_behavior == 1:
            self.copy_to_clipboard(link)
        elif self.link_behavior == 2:
            self.push_screen(LinkScreen(link, classes="modal_screen"))

    def test_clipman(self) -> bool:

        clipman.init()
        # save original clipboard contents. Don't want to piss off the user ;)
        current_clipboard = clipman.paste()

        clipman.copy("cuExOGZorS")
        foo = clipman.paste()

        if foo == "cuExOGZorS":
            self.log.debug("Clipman test successful.")
            testpass = True
        else:
            self.log.error("Clipman test failed.")
            testpass = False

        clipman.copy(current_clipboard)
        return testpass
    
    def test_pyperclip(self):

        # save original clipboard contents. Don't want to piss off the user ;)
        current_clipboard = pyperclip.paste()

        pyperclip.copy("4ECqwBMwTS")
        foo = pyperclip.paste()

        if foo == "4ECqwBMwTS":
            self.log.debug("Pyperclip test successful.")
            testpass = True
        else:
            self.log.error("Pyperclip test failed.")
            testpass = False

        pyperclip.copy(current_clipboard)
        return testpass

    def copy_to_clipboard(self, text: str | Path) -> None:

        with self.capture_exceptions():
            if self.copypaste_engine == 0:
                super().copy_to_clipboard(text)
                self.log.debug("Copied to clipboard with built-in method.")
            elif self.copypaste_engine == 1:
                pyperclip.copy(text)
                self.log.debug("Copied to clipboard with Pyperclip.")
            elif self.copypaste_engine == 2:
                clipman.copy(text)
                self.log.debug("Copied to clipboard with Clipman.")

        if not self.error:
            self.notify("Copied to clipboard.")

    def get_history_data(self, history: list[dict]) -> tuple[list[int], int, int]:

        counts_list = [int(day_record["accounts"]) for day_record in history]
        counts_list.reverse()
        past_2_days = sum(counts_list[-2:]) # sum of the last 2 days
        past_week = sum(counts_list)
        return counts_list, past_2_days, past_week

    @work(exclusive=True, thread=True, group='browser')
    async def open_browser(self, url):

        if url is None:
            self.log.error("No URL provided to open_browser.")
            return
        
        if isinstance(url, Path):
            # check that Path exists first
            if not url.exists():
                self.log.error(f"File does not exist: {url}")
                return
            else:
                self.log.debug(f"Confirmed file exists: {url}")
            url = url.as_uri()

        self.log.debug(f"Opening browser to: {url}")

        if self.error:  # need to check if there's already an error (we're on the reporting screen)
            try:
                result = webbrowser.open(url, new=2, autoraise=False)    # 2 = new tab
            except:  # noqa         # we're already on the error screen, so swallow any new errors
                pass
            if not result:
                self.log.error("Failed to open browser.")
                self.notify("Failed to open browser.", timeout=3)
            else:
                self.notify("Browser opened.", timeout=3)
        else:
            with self.capture_exceptions():
                result = webbrowser.open(url, new=2, autoraise=False)    # 2 = new tab
            if self.error:
                return
            self.log.debug(f"Browser open result: {result}")
            if result:
                self.notify("Browser opened.", timeout=3)
            else:
                self.notify("Failed to open browser.", timeout=3)

    ###~ EVENT HANDLERS ~###

    @on(LoginComplete)
    async def login_complete(self):
        """Event sent by OauthWidget.login_stage5 when it completes.
        Refreshes page if auto-load is enabled. """

        self.log.debug(Text("Auto-loading is enabled.", style="yellow"))

        current = self.main_switcher.current
        page_obj = self.main_switcher.query_one(f"#{current}")
        if self.autoload_value and page_obj.refresh_allowed:
            await page_obj.start_refresh_page()

    @on(ScrollToWidget)
    def scroll_to_widget(self, event: ScrollToWidget) -> None:
        """Allows scrolling the main scroll area to a specific widget on the page.
        Used by:
        - app.focus_login 
        - toot.TextAreaEdit.focus (overridden method)
        - tootbox.TextAreaReply.focus (overridden method)"""

        self.log.debug(f"Scrolling to widget: {event.widget}")
        self.main_scroll.scroll_to_center(event.widget)

    @on(UserPopupMessage)
    async def handle_msg_user_popup(self, event: UserPopupMessage):
        """ This is here because the user can either follow the user, or view their profile, \n
        and page changing has to be handled in the main app. """
        message = event.message
        account = event.account         # account dict
        relation = event.relation       # relation dict

        #! TODO Following your own account is not allowed.
        # Button should be disabled if the user is viewing their own profile.        

        if message == "follow":

            with self.capture_exceptions():
                if relation['following']:
                    await self.mastodon.account_unfollow(account["id"])
                    self.log.debug(f"Unfollowed {account['display_name']}")
                    self.post_message(SuperNotify(f"Unfollowed {account['display_name']}"))  
                else:
                    await self.mastodon.account_follow(account["id"])
                    self.log.debug(f"Followed {account['display_name']}")
                    self.post_message(SuperNotify(f"Followed {account['display_name']}"))

        elif message == "profile":

            user_page = self.main_switcher.query_one("#user_page")
            user_page.update_user(account, relation)
            self.post_message(SwitchMainContent("user_page"))
            self.post_message(UpdateBannerMessage(f"Viewing profile for {account['display_name']}"))
            await user_page.start_refresh_page()    # all pages have this method

    @on(CallbackSuccess)
    def handle_callback_success(self):

        self.log.debug(
            "Received callback success event. \n"
            f"Current active screen: {self.screen}"
        )
        self.app.pop_screen()

    @on(CallbackCancel)
    def handle_callback_cancel(self):
        self.oauth_widget.cancel_callback()

    @on(UpdateBannerMessage)
    async def update_message(self, event: UpdateBannerMessage) -> None:

        self.log.debug(f"Updating banner message: {event.message}")
        await self.messagebar.update(event.message)

    @on(SuperNotify)
    async def super_notify(self, event: SuperNotify) -> None:

        await self.messagebar.update(event.message)
        self.notify(event.message)

    @on(LoginStatus)
    def update_login_status(self, event: LoginStatus) -> None:
        """Login status in the Oauth widget."""
        self.login_status.update(event.loginpage_message)
        self.topbar.update(event.statusbar, event.instance_url)

    @on(SwitchMainContent)
    async def switch_page(self, event: SwitchMainContent) -> None:

        self.log.debug(f"Switching to page: {event.content}")
        self.log.debug(f"Previous pages: {self.previous_pages}")

        if event.content == "back":
            if len(self.previous_pages) > 0:
                self.main_switcher.current = self.previous_pages.pop()
            else:
                self.log.debug("No previous pages to go back to.")
        else:

            if event.content == self.main_switcher.current:
                self.log.debug(f"Page {event.content} is already active.")
                return
            self.previous_pages.append(self.main_switcher.current)
            self.main_switcher.current = event.content

            page_obj = self.main_switcher.query_one(f"#{event.content}")

            if self.autoload_value and page_obj.refresh_allowed:
                await page_obj.start_refresh_page()
            
        self.screen.focus_next()

    @on(ExamineToot)
    async def examine_toot(self, event: ExamineToot) -> None:

        toot_page = self.main_switcher.query_one("#toot_page")
        toot_page.main_toot_id = event.toot_id   
        self.post_message(SwitchMainContent("toot_page"))
        self.post_message(UpdateBannerMessage("Expanding single toot"))
        await toot_page.start_refresh_page()

    @on(Settings.ChangeHatching)
    def change_hatching(self, event: Settings.ChangeHatching) -> None:
        value = event.changed.value
        self.log(f"Changing hatching to {value}")

        query = self.main_switcher.query_children()
        for child in query.results():
            child.set_classes(f"page_area {value}")
        self.main_scroll.set_classes(f"main_scroll {value}")

        self.main_switcher.query_one("#login_page").refresh()
        self.main_scroll.refresh()

        # The above refreshing is to make it instantly show the new hatching.
        # It does not instantly update without the manual refreshing.

    @on(EnableSafeMode)
    def enter_safe_mode(self):

        self.log.error(Text("Entering Safe Mode.", style="white on blue"))
        self.workers.cancel_all()
        self.sqlite.readonly_mode = True
        self.safemode_bar.display = True
        self.settings_widget.disabled = True
        self.safe_mode = True

    def disable_safe_mode(self, _=None):

        self.log.error(Text("Disabling Safe Mode.", style="white on blue"))
        self.sqlite.readonly_mode = False
        self.notify("Safe Mode disabled.")
        self.safemode_bar.display = False
        self.settings_widget.disabled = False
        self.error_handler.reset_stored_errors()
        self.safe_mode = False

    @on(TriggerRandomError)
    def trigger_random_error(self):

        python_errors = [
            ValueError, DatabaseError, TextualError, MastodonError, ClipmanBaseException
        ]

        error = random.choice(python_errors)

        with self.capture_exceptions():
            raise error("Random error triggered.")

    @on(DeleteLogs)
    async def delete_logs(self):

        await self.error_handler.delete_logs()

    @on(OpenRoadmap)
    async def open_roadmap(self):

        await self.push_screen(RoadmapScreen(classes="fullscreen"))

    ###~ ACTIONS ~###

    @on(RefreshCurrentPage)     
    def action_refresh_page(self) -> None:
        """ Message is sent by:
        - `tootscreens.TootOptionsMainUser.delete_toot` """

        if self.mastodon is None:
            self.notify("You are not logged in.")
            return

        page_str = self.main_switcher.current
        page = self.main_switcher.query_one(f"#{page_str}")
        self.log(f"Refreshing current page: {page}")
        if page.refresh_allowed:
            self.set_timer(0.50, page.start_refresh_page)     # half second delay to give server time to refresh.
        else:
            self.notify("This page cannot be refreshed.")

    def action_disable_safe_mode(self):
        self.log.debug("Action: Disabling Safe Mode.")
        self.disable_safe_mode()

    def action_home(self):
        self.post_message(SwitchMainContent("home"))

    def action_notif(self):
        self.post_message(SwitchMainContent("notifications"))

    def action_explore(self):
        self.post_message(SwitchMainContent("explore"))

    def action_live(self):
        self.post_message(SwitchMainContent("live_feeds"))

    def action_mentions(self):
        self.post_message(SwitchMainContent("private_mentions"))

    def action_bookmarks(self):
        self.post_message(SwitchMainContent("bookmarks"))

    def action_favorites(self):
        self.post_message(SwitchMainContent("favorites"))

    def action_lists(self):
        self.post_message(SwitchMainContent("lists"))

    def action_settings(self):
        self.post_message(SwitchMainContent("login_page"))

    def action_previous_page(self):
        self.post_message(SwitchMainContent("back"))

    ###~ REACTIVES ~###

    def watch_theme(self, value: str) -> None:

        self.log.debug(f"Theme changed to: {value}")
        self.sqlite.update_column("settings", "value", value, "name", "current_theme")


    ###~ Worker Debug stuff ~###

    @on(Worker.StateChanged)
    def worker_state_changed(self, event: Worker.StateChanged) -> None:

        if event.state == WorkerState.SUCCESS:
            self.log(Text(f"Worker {event.worker.name} completed successfully", style="green"))
        elif event.state == WorkerState.ERROR:
            self.log.error(Text(f"Worker {event.worker.name} encountered an error", style="red"))
        elif event.state == WorkerState.CANCELLED:
            self.log(Text(f"Worker {event.worker.name} was cancelled", style="yellow"))

def run():
    """Entry point for the `textualdon` command."""
    TextualDon().run()

# for running with python -m textualdon
if __name__ == "__main__":
    TextualDon().run()