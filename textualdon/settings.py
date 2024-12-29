# Standard Library imports
from typing import cast
import random
from dataclasses import dataclass

# Third Party imports
from mastodon import Mastodon
# from textual_spinbox import SpinBox

# Textual imports
from textual import on
from textual.messages import Message
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Static, Switch, Select, Label, Input
from textual.widget import Widget
from textual.validation import Number, ValidationResult

# TextualDon imports
from textualdon.messages import (
    SuperNotify,
    LoginStatus,
    EnableSafeMode,
    TriggerRandomError,
    SwitchMainContent,
    DeleteLogs
)
from textualdon.sql import SQLite
from textualdon.simplebutton import SimpleButton
from textualdon.screens import CopyPasteTester, MessageScreen
# from textualdon.widgets import InputCustom


class PortInput(Input):

    BINDINGS = [Binding("ctrl+k", "info", "Toggle info")]

    port_info = """
TextualDon will choose a random port between 49152 and 65535 for the callback port \
when it first launches. If this creates a conflict for you, you can change the port \
here. The port must be a number between 1024 and 65535.
"""

    @dataclass
    class Blur(Message):
        """Posted when the input is blurred.

        Can be handled using `on_input_blur` in a subclass of `Input` or in a
        parent widget in the DOM.
        """

        input: Input
        """The `Input` widget that is being submitted."""
        value: str
        """The value of the `Input` being submitted."""
        validation_result: ValidationResult | None = None
        """The result of validating the value on submission, formed by combining the results for each validator.
        This value will be None if no validation was performed, which will be the case if no validators are supplied
        to the corresponding `Input` widget."""

        @property
        def control(self) -> Input:
            """Alias for self.input."""
            return self.input

    def _on_blur(self):

        self._pause_blink()

        validation_result = (
            self.validate(self.value) if "blur" in self.validate_on else None
        )
        self.post_message(self.Blur(self, self.value, validation_result))    

    def action_info(self) -> None:
        self.app.push_screen(MessageScreen(self.port_info, classes="modal_screen"))


class Settings(Widget):
    """This is a simple widget that displays the login settings for the user.
    It's used in the LoginPage class to display the login settings."""

    class ChangeHatching(Message):
        """Message to change the hatching of the main content."""
        def __init__(self, event: Select.Changed) -> None:
            super().__init__()
            self.changed = event

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.mastodon = cast(Mastodon, self.app.mastodon)
        self.db = cast(SQLite, self.app.sqlite)

        sql_query = "SELECT value FROM settings WHERE name = ?"

        row1 = self.db.fetchone(sql_query, ("first_launch",))
        row2 = self.db.fetchone(sql_query, ("auto_login",))
        row3 = self.db.fetchone(sql_query, ("auto_load",))
        row4 = self.db.fetchone(sql_query, ("show_images",))
        row5 = self.db.fetchone(sql_query, ("link_behavior",))
        row6 = self.db.fetchone(sql_query, ("copypaste_engine",))
        row7 = self.db.fetchone(sql_query, ("show_on_startup",))
        row8 = self.db.fetchone(sql_query, ("hatching",))
        row9 = self.db.fetchone(sql_query, ("callback_port",))

        first_launch: bool = ('True' == row1[0])
        self.auto_login:   bool = ('True' == row2[0])
        self.auto_load:    bool = ('True' == row3[0])
        self.show_images:  bool = ('True' == row4[0])
        self.link_behavior:    int = int(row5[0])  # 0 = browser, 1 = clipboard, 2 = manual
        self.copypaste_engine: int = int(row6[0])  # 0 = textual default, 1 = pyperclip, 2 = clipman 
        self.show_on_startup: str = row7[0]
        self.hatching:        str = row8[0]
        self.callback_port:   str = row9[0]   # this is a number, but Input expects a string

        if first_launch:
            self.db.update_column("settings", "value", "False", "name", "first_launch")
            self.callback_port = str(random.randint(49152, 65535))
            self.db.update_column("settings", "value", self.callback_port, "name", "callback_port")
        
        self.log.debug(
            f"first_launch: {first_launch} \n"
            f"auto_login: {self.auto_login} \n"
            f"auto_load: {self.auto_load} \n"
            f"show_images: {self.show_images} \n"
            f"link_behavior: {self.link_behavior} \n"
            f"show_on_startup: {self.show_on_startup} \n"
            f"hatching: {self.hatching} \n"
            f"callback_port: {self.callback_port} \n"
        )

        #~ Options lists ~#
        def format(x):
            return x.replace("_", " ").title()

        select_page_options = [
            "login_page", "home", "notifications", "explore", "live_feeds",
            "private_mentions", "bookmarks", "favorites", "lists"
        ]
        self.select_page_options = [(format(option), option) for option in select_page_options]

        hatching_options = ["none", "left", "right", "cross"]
        self.hatching_options = [(format(option), option) for option in hatching_options]

        self.link_options = [
            ("Open in browser", 0),
            ("Copy to clipboard", 1),
            ("Manual", 2)]
        
        self.copypaste_options = [
            ("Textual default", 0),
            ("Pyperclip", 1),
            ("Clipman", 2)]

        self.border_title = "Settings"

    def compose(self):

        yield Static("[middle]Settings with * have a help pop-up toggled with ctrl-k", classes="short_label")
        with Container(classes="settings_container"):
            yield Static("Sign out of current account", classes="settings_text")
            yield SimpleButton(" Logout ", id="logout", classes="settings_button bordered")

            yield Static("\nSign in automatically. \n (Uses most recent sign-in)", classes="settings_text")
            yield Switch(self.auto_login, id="auto_login", classes="settings_button")

            yield Static("Auto-load page content", classes="settings_text")
            yield Switch(self.auto_load, id="auto_load", classes="settings_button")

            yield Static("Show page on startup", classes="settings_text")
            yield Select(
                self.select_page_options,
                value=self.show_on_startup,
                id="show_on_startup",
                classes="settings_list",
                allow_blank=False
            ) 

            yield Static("Download/Show images", classes="settings_text")
            yield Switch(self.show_images, id="show_images", classes="settings_button")

            yield Static("Link behavior", id="clicklink_desc", classes="settings_text")
            yield Select(
                self.link_options,
                value=self.link_behavior,
                id="link_behavior",
                classes="settings_list",
                allow_blank=False
            )

            yield Static("Copy/Paste engine", classes="settings_text")
            yield Select(
                self.copypaste_options,
                value=self.copypaste_engine,
                id="copypaste_engine",
                classes="settings_list",
                allow_blank=False
            )

            yield Static("Copy/Paste Tester", id="copytest_label", classes="settings_text")
            yield SimpleButton(" Open ", id="copy_paste_tester", classes="settings_button bordered")

            yield Static("Background hatching", classes="settings_text")
            yield Select(
                self.hatching_options,
                value=self.hatching,
                id="hatching",
                classes="settings_list",
                allow_blank=False
            )

            yield Static("Callback Port* \nMust be number between 1024 - 65535", classes="settings_text")
            yield PortInput(
                value=self.callback_port,
                type="integer",
                max_length=5,
                validators=Number(minimum=1024, maximum=65535),
                validate_on=["blur"]
            )

            yield Static("Reset all startup warnings", classes="settings_text")    
            yield SimpleButton(" Reset ", id="reset_warnings", classes="settings_button bordered")

            yield Static("View Development settings", classes="settings_text")    
            yield SimpleButton(" View ", id="view_dev", classes="settings_button bordered")

            # Remember to make the grid bigger with each additional setting
            # settings.tcss / #settings_container - increment grid rows by one for each new setting
            # also must adjust height of Settings class manually  (auto mode not working)

    def on_mount(self):

        issues = 0
        if not self.app.clipman_works:
            issues += 1
        if not self.app.pyperclip_works:
            issues += 1

        if issues == 0:
            self.query_one("#copytest_label").update(
                "Copy/Paste Tester \n Test Status: [green](All Passed)[/green]"
            )
        elif issues == 1:
            self.query_one("#copytest_label").update(
                "Copy/Paste Tester \n Test Status: [yellow](1 Issue)[/yellow]"
            )
        elif issues == 2:
            self.query_one("#copytest_label").update(
                "Copy/Paste Tester \n Test Status: [red](2 Issues)[/red]"
            )

    @on(SimpleButton.Pressed, "#logout")
    def logout(self) -> None:

        self.post_message(SuperNotify("Logged out."))
        self.app.mastodon = None
        self.app.logged_in_user_id = None
        self.post_message(LoginStatus(
            statusbar="Status: Offline",
            loginpage_message="Logged out.",
        ))

    @on(Switch.Changed, "#auto_login")
    def auto_login(self, event: Switch.Changed) -> None:

        self.db.update_column("settings", "value", str(event.value), "name", "auto_login")
        self.notify(f"Auto-login set to {event.value}")

    @on(Switch.Changed, "#auto_load")
    def auto_load(self, event: Switch.Changed) -> None:

        self.db.update_column("settings", "value", str(event.value), "name", "auto_load")
        self.app.autoload_value = event.value
        self.notify(f"Auto-load set to {event.value}")

    @on(Select.Changed, "#show_on_startup")
    def show_on_startup(self, event: Select.Changed) -> None:

        self.db.update_column("settings", "value", str(event.value), "name", "show_on_startup")

    @on(Switch.Changed, "#show_images")
    def show_images(self, event: Switch.Changed) -> None:
        
        self.db.update_column("settings", "value", str(event.value), "name", "show_images")
        self.app.show_images = event.value
        self.notify(f"Show images set to {event.value}")

    @on(Select.Changed, "#link_behavior")
    def change_link_behavior(self, event: Select.Changed) -> None:
        
        self.db.update_column("settings", "value", str(event.value), "name", "link_behavior")
        self.app.link_behavior = event.value
        self.log.debug(f"self.app.link_behavior: {self.app.link_behavior}")
        desc_static = cast(Label, self.query_one("#clicklink_desc"))
        if event.value == 0:
            desc_static.update("Link behavior: \nOpen URL in a new browser tab.")
        elif event.value == 1:
            desc_static.update("Link behavior: \nCopy link to clipboard.")
        elif event.value == 2:
            desc_static.update("Link behavior: \nProvides pop-up to copy link manually.")
        desc_static.refresh()

    @on(Select.Changed, "#copypaste_engine")
    def copy_paste_engine(self, event: Select.Changed) -> None:
        
        self.db.update_column("settings", "value", str(event.value), "name", "copypaste_engine")
        self.app.copypaste_engine = event.value
        self.log.debug(f"self.app.copypaste_engine: {self.app.copypaste_engine}")


    @on(SimpleButton.Pressed, "#copy_paste_tester")
    def open_tester_screen(self) -> None:
        self.app.push_screen(CopyPasteTester(classes="fullscreen"))

    @on(Select.Changed, "#hatching")
    def change_hatching(self, event: Select.Changed) -> None:

        self.db.update_column("settings", "value", str(event.value), "name", "hatching")
        self.post_message(self.ChangeHatching(event))

    @on(PortInput.Blur)
    def update_port(self, event: PortInput.Blur) -> None:

        if event.value != self.callback_port:

            if event.validation_result.is_valid:
                self.log.debug(f"event.value type: {type(event.value)}")        #! TODO remove me.
                self.db.update_column("settings", "value", str(event.value), "name", "callback_port")
                self.notify(f"Callback port set to {event.value}")
                self.callback_port = event.value
            else:
                self.notify(str(event.validation_result.failure_descriptions[0]))
                event.input.value = self.callback_port
        
    @on(SimpleButton.Pressed, "#reset_warnings")
    def show_warnings(self) -> None:

        self.db.update_column("settings", "value", "False", "name", "warning_checkbox_wsl")
        self.db.update_column("settings", "value", "False", "name", "warning_checkbox_first")
        self.notify("Startup Warnings re-enabled.")

    @on(SimpleButton.Pressed, "#view_dev")
    def view_dev_settings(self) -> None:
        self.post_message(SwitchMainContent("dev_settings"))

class DevSettings(Widget):
    """This is a simple widget that displays the developer settings for the user.
    It's used in the LoginPage class to display the developer settings."""

    def compose(self):

        self.db = cast(SQLite, self.app.sqlite)

        sql_query = "SELECT value FROM settings WHERE name = ?"
        row1 = self.db.fetchone(sql_query, ("view_json_active",))
        view_json_active: bool = ('True' == row1[0])
            
        self.border_title = "Developer Settings"

        with Container(classes="settings_container dev"):
            yield Static("Trigger a random exception", classes="settings_text")
            yield SimpleButton(" Bring it ", id="test_error", classes="settings_button bordered")

            yield Static("Enable safe mode", classes="settings_text")
            yield SimpleButton(" Enable ", id="test_safemode", classes="settings_button bordered")

            yield Static("Show button to view JSON \nin toot options menu", classes="settings_text")
            yield Switch(view_json_active, id="view_json_active", classes="settings_button")

            yield Static("Delete all log files in logs folder", classes="settings_text")
            yield SimpleButton( " Delete ", id="delete_logs", classes="settings_button bordered")

            # Remember to make the grid bigger with each additional setting
            # settings.tcss / #settings_container - increment grid rows by one for each new setting
            # also must adjust height of Settings class manually  (auto mode not working)

    @on(SimpleButton.Pressed, "#test_error")
    def trigger_mock_error(self):
        self.post_message(TriggerRandomError())

    @on(SimpleButton.Pressed, "#test_safemode")
    def trigger_safe_mode(self):
        self.post_message(EnableSafeMode())

    @on(Switch.Changed, "#view_json_active")
    def auto_login(self, event: Switch.Changed) -> None:

        self.db.update_column("settings", "value", str(event.value), "name", "view_json_active")
        if event.value:
            self.notify("View JSON button enabled.")

    @on(SimpleButton.Pressed, "#delete_logs")
    async def delete_logs(self) -> None:

        self.post_message(DeleteLogs())