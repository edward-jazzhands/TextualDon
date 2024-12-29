# Standard Library imports
from __future__ import annotations
from typing import TYPE_CHECKING, cast, List, Tuple
import urllib.request
from datetime import datetime


if TYPE_CHECKING:
    from textual.app import ComposeResult 

# Third party imports
from mastodon import Mastodon
from rich.text import Text
import PIL.Image

# Textual imports
from textual import on, work
# from textual.reactive import reactive
# from textual.dom import NoScreen
from textual.worker import Worker, WorkerState
from textual.binding import Binding
from textual.message import Message
from textual.containers import Horizontal, Vertical, Container
from textual.widget import Widget
from textual.widgets import (
    Sparkline,
    Pretty,
    Static,
    # TextArea,
    Input,
)

# TextualDon imports
from textualdon.screens import ImageScreen, MessageScreen, NotImplementedScreen
from textualdon.simplebutton import SimpleButton
# from textualdon.messages import ScrollToWidget
from textualdon.imageviewer import ImageViewer    # takes PIL.Image.Image as only argument


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
and to change themes. (I tried to make sure TextualDon looks good in most themes, and \
it will remember your theme setting as well.) \n"""
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


class TimelineSelector(Widget):

    BINDINGS = [
        Binding("left", "focus_previous", "Focus left", show=True),
        Binding("right", "focus_next", "Focus right", show=True),
    ]
    # focused_index = reactive(0)     # start on leftmost timeline

    class ChangeTimeline(Message):
        """This message is sent when a timeline is selected in the TimelineSelector widget.
        This is handled in the page the TimelineSelector is mounted in."""
        def __init__(self, timeline: str) -> None:
            super().__init__()
            self.timeline = timeline

    def __init__(self, options: List[Tuple[str, str]], **kwargs):
        super().__init__(**kwargs)
        self.options = options
        self.current = 0        # index of the selected timeline

        # NOTE: Every entry in options is a tuple of the display name and id of the timeline.
        self.buttons_list = [
            SimpleButton(option[0], id=option[1], index=index, classes="timeline_button") 
            for index, option in enumerate(self.options)
        ]
        self.amt_of_buttons = len(self.buttons_list)

    def compose(self) -> ComposeResult:

        #~ NOTE: Timeline CSS is in pages.tcss

        with Horizontal(id="timeline_container", classes="page_box timeline"):
            for button in self.buttons_list:
                yield button

    def on_mount(self):
        timeline_container = self.query_one("#timeline_container")
        self.buttons = list(timeline_container.query_children().results())

        selected = self.query_one(f"#{self.options[self.current][1]}")
        selected.set_classes("timeline_button selected")

    @on(SimpleButton.Pressed)
    def switch_timeline(self, event: SimpleButton.Pressed) -> None:

        if event.button.index == self.current:
            self.log.debug("Already on this timeline.")
            return
        
        self.log.debug(f"Switching to {event.button.id}")
        for option in self.options:                         # First reset all buttons
            button = self.query_one(f"#{option[1]}")
            button.set_classes("timeline_button")

        selected = self.query_one(f"#{event.button.id}")
        selected.set_classes("timeline_button selected")
        self.current = event.button.index
        self.post_message(self.ChangeTimeline(event.button.id))  # Send message to parent page

    def action_focus_previous(self) -> None:
        if self.buttons[0].has_focus:
            self.buttons[-1].focus()
        self.screen.focus_previous()

    def action_focus_next(self) -> None:
        if self.buttons[-1].has_focus:
            self.buttons[0].focus()
        self.screen.focus_next()


class MiscMastoWidget(Widget):


    def on_focus(self):
        self.log.debug(f"{self.name} focused. ")
        self.styles.border = ('dashed', self.app.theme_variables["primary"])

    def on_blur(self):
        self.styles.border = ('blank', 'transparent')


    def get_days_of_week(self):
        # Get the current day of the week
        current_day = datetime.now().strftime("%a")
        day_list = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_codes = ["M", "T", "W", "T", "F", "S", "S"]
        index = day_list.index(current_day)
        if index == 6:
            return " ".join(day_codes)
        else:
            my_days = day_codes[index+1:] + day_codes[:index+1]
            return " ".join(my_days)


class HashtagWidget(MiscMastoWidget):

    BINDINGS = [
        Binding("enter", "switch_to_hashtagpage", "Expand hashtag", show=True),
    ]

    def __init__(self, json: dict, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.json = json

    def compose(self):
        with Container(classes="content_container"):
            yield SimpleButton("hashtag", id="hashtag_name", classes="titlebar")
            with Horizontal(classes="trend_footer"):
                yield Static("history", id="hashtag_history", classes="trend_footer nums")
                with Vertical(classes="trend_footer sparkline"):
                    yield Sparkline([0], id="hashtag_sparkline", classes="sparkline")
                    yield Static(self.get_days_of_week(), classes="trend_label")

    def on_mount(self):

        self.can_focus = True
        self.query_one("#hashtag_name").can_focus = False
        history = self.json["history"]
        counts_list, past_2_days, past_week = self.app.get_history_data(history)

        self.query_one("#hashtag_name").update(f"#{self.json['name']}")
        self.query_one("#hashtag_name").tooltip = self.json["url"]
        self.query_one("#hashtag_history").update(
                    f"{past_2_days} people in the past 2 days. \n"
                    f"{past_week} people in the past week.")
        self.query_one("#hashtag_sparkline").data = counts_list

        self.loading = False

    def action_switch_to_hashtagpage(self):
        self.app.push_screen(NotImplementedScreen("More pages"))


class NewsWidget(MiscMastoWidget):

    BINDINGS = [
        Binding("enter", "switch_to_newspage", "Expand news story", show=True),
    ]

    def __init__(self, json: dict, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.json = json
        self.html_on = False     # flag
        self.json_on = False     # flag
        self.loading = True

    # TODO These should be using the card widget for the news.

    def compose(self):
        with Container(classes="content_container"):
            yield Static("title", id="news_title", classes="titlebar")
            yield Static("url", id="news_url")
            yield Static("description", id="news_description")
            yield Static("author", id="news_author")
            yield Static("date", id="news_date")
            yield Static("provider", id="news_provider")

            with Horizontal(classes="trend_footer news"):
                yield Static("history", id="news_history", classes="trend_footer nums")
                with Vertical(classes="trend_footer sparkline"):
                    yield Sparkline([0], id="news_sparkline", classes="sparkline")
                    yield Static(self.get_days_of_week(), classes="trend_label")

    def on_mount(self):

        self.can_focus = True
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

    def action_switch_to_newspage(self):
        self.app.push_screen(NotImplementedScreen("More pages"))


# TODO Make PeopleWidget


class ImageViewerWidget(Container):
    """widget that displays an image in a container. Used in a couple places to display images.
    Nested in: toot.TootContentContainer.
    Connected to: screens.ImageScreen for fullscreen viewing."""

    def __init__(self, image_url: str, in_card: bool = False, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.url = image_url
        self.in_card = in_card  # If True, the image is displayed in a card.
        self.can_focus = False

    async def on_mount(self):
        
        with self.app.capture_exceptions():
            img_worker = self.load_image_from_url()
            self.img = await img_worker.wait()
        if self.app.error:
            return

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
            await self.fullscreen()

    async def fullscreen(self):
        await self.app.push_screen(ImageScreen(self.img, classes="fullscreen"))

    @on(Worker.StateChanged)
    def worker_state_changed(self, event: Worker.StateChanged) -> None:
        
        if event.state == WorkerState.SUCCESS:
            self.log(Text(f"Worker {event.worker.name} completed successfully", style="green"))
        elif event.state == WorkerState.ERROR:
            self.log.error(Text(f"Worker {event.worker.name} encountered an error", style="red"))
        elif event.state == WorkerState.CANCELLED:
            self.log(Text(f"Worker {event.worker.name} was cancelled", style="yellow"))


class ProfileWidget(MiscMastoWidget):
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
