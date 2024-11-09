# Standard Library imports
from __future__ import annotations
from typing import TYPE_CHECKING, cast, List, Tuple
import urllib.request

if TYPE_CHECKING:
    from textual.app import ComposeResult 

# Third party imports
from mastodon import Mastodon
from rich.text import Text
import PIL.Image
from textual_imageview.viewer import ImageViewer    # takes PIL.Image.Image as only argument

# Textual imports
from textual import on, work
from textual.dom import NoScreen
from textual.worker import Worker #, WorkerCancelled, WorkerFailed
from textual.binding import Binding
from textual.message import Message
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import (
    Sparkline,
    Pretty,
    Static,
    TextArea,
    Input,
)

# TextualDon imports
from textualdon.screens import ImageScreen, MessageScreen
from textualdon.simplebutton import SimpleButton
from textualdon.messages import ScrollToWidget


class InputCustom(Input):

    BINDINGS = [
        Binding("enter", "submit", "Submit", key_display='Enter', show=True),
    ]


class WelcomeWidget(Container):

    welcome_text = """TextualDon is designed for both keyboard and mouse users. \
The bar at the bottom of the screen will show you the available commands for whatever you have focused. \n
You can see your status in the top right corner of the screen. \
Hover your mouse over it to see which instance you are connected to (or check this page). \n
You can also use the command palette (bottom right, or press 'ctrl + p') to read Textual's command list \
and to change themes. (I tried to make sure TextualDon looks good in most themes.)\n
If you are using TextualDon over SSH and you want to keep a low profile, you might want to disable \
images in the settings. \n"""
    welcome_text2 = """Note that default link behavior is to open in your browser. \
You can change this in the settings below. This will be useful for people who cannot \
open a browser window automatically."""
    alpha_text = """Hey there! This program is still in alpha stages. If you're reading this, \
you're probably one of the first people to try it. Many features are still missing, and \
there's a chance you'll run into bugs. If you do, please let me know! The reporting \
screen should save you some time in doing so, assuming it works properly. \n"""

    def compose(self):

        with Container(id="text", classes="page_box content"):
            yield SimpleButton("Testers/Discord group press here", id="testers_button", classes="page_button short")
            yield Static(self.welcome_text, classes="page_box content")
        with Horizontal(classes="page_box bar"):
            yield Static(self.welcome_text2, id="welcome2", classes="page_box content")
            yield SimpleButton("Hide", id="hide_button", classes="page_button bordered")

    def on_mount(self):

        self.query_one("#hide_button").can_focus = True

        row = self.app.sqlite.fetchone(
            "SELECT value FROM settings WHERE name = ?", ("show_welcome_message",)
        )
        show_welcome = (row[0] == "True")
        if not show_welcome:
            self.hide_widget(update_db=False)

    @on(SimpleButton.Pressed, selector="#hide_button")
    def show_hide_trigger(self) -> None:

        if self.query_one("#text").display is True:
            self.hide_widget()
        else:
            self.show_widget()

    @on(SimpleButton.Pressed, selector="#testers_button")
    def show_alpha_message(self) -> None:

        self.app.push_screen(MessageScreen(self.alpha_text, classes="modal_screen"))

    def hide_widget(self, update_db: bool = True) -> None:

        self.query_one("#text").display = False
        self.query_one("#hide_button").update("Show")
        self.query_one("#welcome2").update("\nPress 'Show' to see the introduction again.")
        self.set_classes("page_box message hidden")

        if update_db:
            self.app.sqlite.update_column("settings", "value", "False", "name", "show_welcome_message")

    def show_widget(self, update_db: bool = True) -> None:

        self.query_one("#text").display = True
        self.query_one("#hide_button").update("Hide")
        self.query_one("#welcome2").update(self.welcome_text2)
        self.set_classes("page_box message")

        if update_db:
            self.app.sqlite.update_column("settings", "value", "True", "name", "show_welcome_message")


class TimelineSelector(Horizontal):

    class ChangeTimeline(Message):
        """This message is sent when a timeline is selected in the TimelineSelector widget."""
        def __init__(self, timeline: str) -> None:
            super().__init__()
            self.timeline = timeline

    def __init__(self, options: List[Tuple[str, str]], current: int, **kwargs):
        super().__init__(**kwargs)
        self.options = options
        self.current = current

    def compose(self) -> ComposeResult:

        #~ NOTE: Timeline CSS is in pages.tcss

        with Horizontal(classes="page_box timeline"):
            for index, option in enumerate(self.options):   
                yield SimpleButton(option[0], id=option[1], index=index, classes="timeline_button")

    def on_mount(self):
        selected = self.query_one(f"#{self.options[self.current][1]}")
        selected.set_classes("timeline_button selected")

    @on(SimpleButton.Pressed)
    def switch_timeline(self, event: SimpleButton.Pressed) -> None:
        if event.button.index == self.current:
            self.log.debug("Already on this timeline.")
            return
        self.log.debug(f"Switching to {event.button.id}")
        for option in self.options:
            button = self.query_one(f"#{option[1]}")
            button.set_classes("timeline_button")
        selected = self.query_one(f"#{event.button.id}")
        selected.set_classes("timeline_button selected")
        self.current = event.button.index
        self.post_message(self.ChangeTimeline(event.button.id))


class HashtagWidget(Container):


    def __init__(self, json: dict, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.json = json

    def compose(self):
        yield Static("hashtag", id="hashtag_name", classes="titlebar")
        # yield Static("following", id="hashtag_following")
        with Horizontal(classes="trend_footer"):
            yield Static("history", id="hashtag_history", classes="trend_footer_nums")
            with Vertical(classes="sparkline_container"):
                yield Sparkline([0], id="hashtag_sparkline")
                yield Static("Weekly Trend", classes="trend_label")

    def on_mount(self):

        history = self.json["history"]
        counts_list, past_2_days, past_week = self.app.get_history_data(history)

        self.query_one("#hashtag_name").update(f"#{self.json['name']}")
        self.query_one("#hashtag_name").tooltip = self.json["url"]
        # self.query_one("#hashtag_following").update(f"Following: {self.json["following"]}")
        self.query_one("#hashtag_history").update(
                    f"{past_2_days} people in the past 2 days. \n"
                    f"{past_week} people in the past week.")
        self.query_one("#hashtag_sparkline").data = counts_list

        self.loading = False


class NewsWidget(Container):


    def __init__(self, json: dict, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.json = json
        self.html_on = False     # flag
        self.json_on = False     # flag
        self.loading = True

    # TODO These should be using the card widget for the news.

    def compose(self):
        yield Static("title", id="news_title", classes="titlebar")
        yield Static("url", id="news_url")
        yield Static("description", id="news_description")
        yield Static("author", id="news_author")
        yield Static("date", id="news_date")
        yield Static("provider", id="news_provider")

        with Horizontal(classes="trend_footer"):
            yield Static("history", id="news_history", classes="trend_footer_nums")
            with Vertical(classes="sparkline_container"):
                yield Sparkline([0], id="news_sparkline")
                yield Static("Weekly Trend", classes="trend_label")

    def on_mount(self):

        counts_list, past_2_days, past_week = self.app.get_history_data(self.json["history"])
        date_object: type = self.json["published_at"]  # Mastodon.py returns datetime objects
        self.log.debug(date_object)
        self.log.debug(date_object.__class__)
        self.log.debug(date_object.__class__.mro())
        
        self.query_one("#news_title").update(self.json["title"])
        self.query_one("#news_url").update(self.json["url"])
        self.query_one("#news_description").update(self.json["description"])
        self.query_one("#news_author").update(self.json["author_name"])
        # self.query_one("#news_date").update(date)
        self.query_one("#news_provider").update(self.json["provider_name"])
        self.query_one("#news_history").update(
                    f"{past_2_days} people in the past 2 days. \n"
                    f"{past_week} people in the past week.")
        self.query_one("#news_sparkline").data = counts_list

        self.loading = False


# TODO Make PeopleWidget


class ImageViewerWidget(Container):
    """This is a simple widget that displays an image in a container.
    It's used across the program to display images. It's controlled by the ImageViewer class."""

    def __init__(self, image_url: str, in_card: bool = False, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.url = image_url
        self.in_card = in_card  # If True, the image is displayed in a card.
        self.can_focus = False

    async def on_mount(self):
        # Yes, it appears strange how this setup is in on_mount istead of __init__ and compose.
        # But its because it loads the image in the background with a worker.
        # The worker protocol is async and can't be used in __init__ or compose.
        
        with self.app.capture_exceptions():
            img_worker = self.load_image_from_url()
        if self.app.error:
            return

        self.img = await img_worker.wait()
        self.imgview = ImageViewer(self.img, nested=True, id="imgview")
        self.mount(self.imgview)
        if not self.in_card:
            self.tooltip = 'Click to view full size'

    @work(thread=True, exit_on_error=False, group="image")
    async def load_image_from_url(self) -> PIL.Image.Image:

        headers = {"User-Agent": "Mozilla/5.0"}

        try:
            req = urllib.request.Request(self.url, headers=headers)
        except Exception as e:
            raise e
        
        with urllib.request.urlopen(req) as response:
            return PIL.Image.open(response)
        
    async def on_click(self):
        if not self.in_card:
            await self.app.push_screen(ImageScreen(self.img, classes="fullscreen"))

    @on(Worker.StateChanged)
    def worker_state_changed(self, event: Worker.StateChanged) -> None:
        
        if event.worker.state.name == 'SUCCESS':
            self.log(Text(f"Worker {event.worker.name} completed successfully", style="green"))
        elif event.worker.state.name == 'ERROR':
            self.log.error(Text(f"Worker {event.worker.name} encountered an error", style="red"))
        elif event.worker.state.name == 'CANCELLED':
            self.log(Text(f"Worker {event.worker.name} was cancelled", style="yellow"))


class ProfileWidget(Container):
    """Displays a user's profile. Used by the UserProfilePage class."""

    def __init__(self, account_dict, relation_dict, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.account_dict = account_dict
        self.relation_dict = relation_dict

    def compose(self):
        yield Pretty(self.account_dict, classes="page_box")
        yield Pretty(self.relation_dict, classes="page_box")

    def on_mount(self):
        self.mastodon = cast(Mastodon, self.app.mastodon)


class NestedTextArea(TextArea):

    class Submit(Message):
        pass

    BINDINGS = [
        Binding("ctrl+e", "submit", "Submit edit", show=True),
        Binding("escape", "cancel", "Cancel edit", key_display='Esc', show=True),
    ]

    def on_mount(self):
        self.focus()

    def focus(self, scroll_visible: bool = True):
        """Copied from Widget.focus() but with scroll_visible set to False."""

        try:
            self.screen.set_focus(self, scroll_visible=False)
        except NoScreen:
            pass

        self.post_message(ScrollToWidget(self))
        self.parent.parent.toot_widget.on_focus()

        return self

    def on_focus(self):
        self.parent.parent.toot_widget.on_focus()

    def on_blur(self):
        self.parent.parent.toot_widget.on_blur()

    def action_submit(self):
        self.post_message(self.Submit())

    async def action_cancel(self):
        await self.parent.parent.toot_widget.reply_to_toot()

