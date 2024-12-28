# Standard library imports
from __future__ import annotations
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from textual.app import ComposeResult 
    from textual.timer import Timer
    # from textual.events import Click

# Third party imports
from rich.emoji import Emoji

# Textual imports
from textual import on
from textual.containers import Horizontal
from textual.widgets import Label, Static

# Textualdon imports
from textualdon.simplebutton import SimpleButton
from textualdon.messages import SwitchMainContent

class TopBarType(Horizontal):

    def on_mount(self):
        for child in self.children:
            child.can_focus = False

class TopBarMenu(TopBarType):

    def compose(self) -> ComposeResult:
        yield SimpleButton(f"{Emoji('house')}",    id="home",             name="Home",          classes="topbar_button")   
        yield SimpleButton(f"{Emoji('bell')}",     id="notifications",    name="Notifications", classes="topbar_button")  
        yield SimpleButton("#",                    id="explore",          name="Explore",       classes="topbar_button")     
        yield SimpleButton(f"{Emoji('earth_americas')}", id="live_feeds", name="Live Feeds",    classes="topbar_button") 
        yield SimpleButton("@",                 id="private_mentions", name="Private Mentions", classes="topbar_button")     
        yield SimpleButton(f"{Emoji('bookmark')}", id="bookmarks",        name="Bookmarks",     classes="topbar_button")      
        yield SimpleButton(f"{Emoji('star2')}",    id="favorites",        name="Favorites",     classes="topbar_button")      
        yield SimpleButton(f"{Emoji('scroll')}",   id="lists",            name="Lists",         classes="topbar_button")

class StatusWidget(TopBarType):

    def compose(self) -> ComposeResult:
        yield Static("Status: Offline", id="online_status")
        yield SimpleButton("≡", id="login_page", name="Settings", classes="topbar_button status")

class TopBar(TopBarType):

    def compose(self) -> ComposeResult:
        yield SimpleButton(f"{Emoji('arrow_backward')}", id="back", name="Back", classes="topbar_button back")
        yield TopBarMenu()
        yield Label(id="topbar_label")
        yield StatusWidget()

    def on_mount(self):
        self.online_status = self.query_one("#online_status")
        self.topbar_label = self.query_one("#topbar_label")

    def update(self, status: str, instance_url: str = None) -> None:
        self.online_status.update(status)
        self.online_status.tooltip = instance_url

    @on(SimpleButton.Pressed)
    def change_page(self, event: SimpleButton.Pressed) -> None:
        self.post_message(SwitchMainContent(event.button.id))

    @on(SimpleButton.HoverEnter)
    def show_label(self, event: SimpleButton.HoverEnter) -> None:
        self.topbar_label.update(event.button.name)

    @on(SimpleButton.HoverLeave)
    def hide_label(self, event: SimpleButton.HoverLeave) -> None:
        self.topbar_label.update("")

    

class BottomBar(Horizontal):

    class BindingLabel(Horizontal):
        def __init__(self, binding, label, **kwargs):
            super().__init__(**kwargs)
            self.binding = binding
            self.label = label

        def compose(self) -> ComposeResult:
            yield Static(self.binding, classes="bottombar_label one")
            yield Static(self.label, classes="bottombar_label two")

    def compose(self) -> ComposeResult:
        yield self.BindingLabel("Tab | Shift+Tab", "Focus")
        yield self.BindingLabel("F1-F8", "Page")
        yield self.BindingLabel("F9", "Settings")
        yield self.BindingLabel("^r", "Refresh Page")
        yield self.BindingLabel("F12", "Back", id="hide_bottombar")        

class MessageBarWidget(Horizontal):
    """This is a simple widget that displays a message at the top bar.
    It's used across the program to relay simple messages.
    It's controlled by the UpdateBannerMessage message which is in the messages.py file."""

    # notification: Reactive[str] = Reactive("")  # Store the current notification
    timer: Timer = None  # Timer instance
    clear_time = 5       # seconds to clear the message

    def compose(self) -> ComposeResult:
        yield Label(id="message_widget_text")
        Label.update

    def on_mount(self):
        self.message_widget = cast(Label, self.query_one("#message_widget_text"))


    async def update(self, message: str) -> None:
        """This overrides the normal update to add the timer.
        Activated by update_message in __init__.py"""

        self.message_widget.update(message)
        if self.timer:
            self.timer.stop()
        self.timer = self.set_timer(self.clear_time, self.clear_message)

    def clear_message(self) -> None:
        self.message_widget.update("")
        self.timer = None  


class SafeModeBar(Horizontal):

    def compose(self) -> ComposeResult:
        yield SimpleButton(
            "Safe Mode - Click here or press ctrl-d to disable",
            id="safe_mode", name="Safe Mode", classes="topbar_button safe_mode"
        )

    @on(SimpleButton.Pressed)
    def safemode_bar_disable(self) -> None:
        self.app.disable_safe_mode()

#######################################################

        

# class LeftBar(Vertical):

#     def compose(self) -> ComposeResult:
#         yield Static("", id='leftbar_content')

#     def on_mount(self):
#         # user_db = self.app.tinydb.all()
#         leftbar_content = self.query_one("#leftbar_content")
#         for item in self.app.tinydb:
#             username = item['username']
#             instance_url = item['instance_url']
#             leftbar_content.update(f"{username}\n{instance_url}")

#     def hide_if_too_small(self, width):
#         if width < 120:  # For example, hide if the width is less than 80
#             self.display = False  # This hides the widget
#         else:
#             self.display = True   # This shows the widget

# class RightBar(Vertical):

#     def compose(self) -> ComposeResult:
#         yield Static("")

#     def hide_if_too_small(self, width):
#         if width < 120:  # For example, hide if the width is less than 80
#             self.display = False  # This hides the widget
#         else:
#             self.display = True   # This shows the widget
