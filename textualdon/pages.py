# Standard library imports
from __future__ import annotations
from typing import TYPE_CHECKING, Callable #, cast

if TYPE_CHECKING:
    from textual.app import ComposeResult
    from textual.widget import Widget

# Third party imports
from textual_pyfiglet import FigletWidget
from rich.text import Text
# from mastodon import Mastodon

# Textual imports
from textual import on, work
from textual.message import Message
from textual.worker import Worker, WorkerState
from textual.containers import Horizontal, Container
from textual.widget import Widget
from textual.widgets import Static

# TextualDon imports
from textualdon.widgets import (
    HashtagWidget,
    NewsWidget,
    TimelineSelector,
    ProfileWidget
)
from textualdon.settings import Settings, DevSettings
from textualdon.toot import TootWidget
from textualdon.oauth import OAuthWidget
from textualdon.widgets import WelcomeWidget
from textualdon.simplebutton import SimpleButton
from textualdon.messages import UpdateBannerMessage, SuperNotify, SwitchMainContent
from textualdon.screens import NotImplementedScreen


class PageHeader(Horizontal):

    class RefreshPage(Message):
        """This message is sent when the refresh button is pressed in the PageHeader widget."""
        def __init__(self) -> None:
            super().__init__()

    def __init__(self, page: str, refresh_visible: bool = True, **kwargs) -> None:
        super().__init__(**kwargs)
        self.page = page
        self.refresh_visible = refresh_visible

    def compose(self):
        yield FigletWidget(self.page, justify="left")
        yield SimpleButton("Refresh", id="refresh_button", classes="header_button")

    def on_mount (self):
        self.query_one("#refresh_button").can_focus = False
        if not self.refresh_visible:
            self.query_one("#refresh_button").visible = False

    @on(SimpleButton.Pressed, "#refresh_button")
    async def start_refresh_page(self) -> None:
        self.post_message(self.RefreshPage())   

class Page(Container):

    limit = 10
    refresh_allowed = True      # most are allowed. Set to false on Login and About pages
    populated = False

    @on(PageHeader.RefreshPage)
    async def start_refresh_page(self):

        if not self.refresh_allowed:
            self.notify("This page cannot be refreshed.")
            return

        if self.app.safe_mode:
            self.post_message(SuperNotify("Please disable safe mode to refresh."))
            return
        
        if not self.app.mastodon:
            self.post_message(SuperNotify("You are not logged in."))
            return
        
        self.log(Text(f"{self.app.breaker_figlet}", style="green"))

        self.log.debug(f"Refreshing {self.timeline} page")
        self.post_message(UpdateBannerMessage(f"Refreshing {self.timeline} page"))

        with self.app.capture_exceptions():
            self.refresh_page()

    async def _refresh_page(
        self,
        widget_type: Widget,
        method: Callable,
        *args,
        **kwargs
    ):
        """*args and **kwargs are passed to the method that is called on the Mastodon object."""

        css_dict = {
            TootWidget: "toot",
            HashtagWidget: "hashtag",
            NewsWidget: "news",
            ProfileWidget: "profile",
        }
        css_class = css_dict[widget_type]

        method_obj = getattr(self.app.mastodon, method)
        json_response = None
        with self.app.capture_exceptions():
            json_response = await method_obj(*args, **kwargs)
        if json_response:
        
            children = list(self.query_children().results())
            self.log.debug(f"children: {children}")
            to_remove = []
            for child in children:
                if isinstance(child, PageHeader) or isinstance(child, TimelineSelector):
                    pass                 # dont want to remove the headers
                else:
                    to_remove.append(child)
            await self.remove_children(to_remove)  

            if not self.app.error:
                widgets = [
                    widget_type(name=f"{widget_type}_{index}", json=json, classes=f"page_box {css_class}") 
                    for index, json in enumerate(json_response)
                ]
                await self.mount_all(widgets)

    @on(Worker.StateChanged)
    def worker_state_changed(self, event: Worker.StateChanged) -> None:
        
        if event.state == WorkerState.SUCCESS:
            self.log(Text(f"Worker {event.worker.name} completed successfully", style="green"))
        elif event.state == WorkerState.ERROR:
            self.log.error(Text(f"Worker {event.worker.name} encountered an error", style="red"))
        elif event.state == WorkerState.CANCELLED:
            self.log(Text(f"Worker {event.worker.name} was cancelled", style="yellow"))


class LoginPage(Container):

    refresh_allowed = False

    def compose(self) -> ComposeResult:
        
        yield PageHeader("login & settings", refresh_visible=self.refresh_allowed)
        yield WelcomeWidget(classes="page_box message")
        yield OAuthWidget(id="oauth_widget")                          # these both have IDs so they can be queried
        yield Settings(id="settings_widget", classes="settings")           # by the main app.
        with Container(classes="page_box footer"):
            yield SimpleButton("About TextualDon", id="about_button")

    @on(SimpleButton.Pressed, selector="#about_button")
    def show_about_page(self) -> None:
        self.post_message(SwitchMainContent("about"))


class HomePage(Page):

    timeline = "home"

    def compose(self) -> ComposeResult:
        yield PageHeader(self.timeline)

    @work
    async def refresh_page(self):

        await self._refresh_page(
            widget_type = TootWidget,
            method = "timeline",
            limit = self.limit,
            timeline = self.timeline
        )

class NotificationsPage(Page):

    timeline = "notifications"
    refresh_allowed = False
    
    def compose(self) -> ComposeResult:
        yield PageHeader(self.timeline)
        yield Static("Notifications page is a work in progress", classes="page_box wip")

    @work
    async def refresh_page(self):

        return    #! WIP
    
        json_response = await self.app.mastodon.notifications()


class ExplorePage(Page):

    page = "explore"
    timeline = "explore_posts"

    timeline_list = [
        ('Posts', 'explore_posts'),         # 0
        ('Hashtags', 'explore_hashtags'),   # 1
        ('People', 'explore_people'),       # 2
        ('News', 'explore_news')            # 3
    ]
    
    def compose(self) -> ComposeResult:
        yield PageHeader(self.page)
        yield TimelineSelector(self.timeline_list)

    @on(TimelineSelector.ChangeTimeline)
    def change_timeline(self, event: TimelineSelector.ChangeTimeline) -> None:
        self.timeline = event.timeline
        self.log.debug(f"self.timeline is set to: {self.timeline}")       

    @work
    async def refresh_page(self):

        if self.timeline == "explore_hashtags":
            await self._refresh_page(HashtagWidget, "trending_tags", limit=self.limit)

        if self.timeline == "explore_news":
            await self._refresh_page(NewsWidget, "trending_links", limit=self.limit)

        if self.timeline == "explore_posts":
            await self._refresh_page(TootWidget, "trending_statuses", limit=self.limit)

        if self.timeline == "explore_people":
            self.app.push_screen(NotImplementedScreen("More pages"))


class LiveFeeds(Page):

    page = "livefeeds"
    timeline = "local"

    timeline_list = [
        ('This Server', 'local'),         # 0
        ('Other Servers', 'public'),      # 1
    ]

    def compose(self) -> ComposeResult:
        yield PageHeader(self.page)
        yield TimelineSelector(self.timeline_list)

    @on(TimelineSelector.ChangeTimeline)
    def change_timeline(self, event: TimelineSelector.ChangeTimeline) -> None:
        self.timeline = event.timeline
        self.log.debug(f"self.timeline is set to: {self.timeline}")

    @work
    async def refresh_page(self):

        await self._refresh_page(
            widget_type = TootWidget,
            method = "timeline",
            limit = self.limit,
            timeline = self.timeline
        )


class PrivateMentionsPage(Page):

    timeline = "private mentions"
    refresh_allowed = False
    
    def compose(self) -> ComposeResult:
        yield PageHeader(self.timeline)
        yield Static("Private Mentions page is a work in progress", classes="page_box wip")

    @work
    async def refresh_page(self):

        return    #! WIP

        # json_response = await self.app.mastodon.notifications(mentions_only=True)    


class BookmarksPage(Page):

    timeline = "bookmarks"
    
    def compose(self) -> ComposeResult:
        yield PageHeader(self.timeline)

    @work
    async def refresh_page(self):

        await self._refresh_page(
            widget_type = TootWidget,
            method = "bookmarks",
        )


class FavoritesPage(Page):

    timeline = "favorites"
    
    def compose(self) -> ComposeResult:
        yield PageHeader(self.timeline)

    @work
    async def refresh_page(self):

        await self._refresh_page(
            widget_type = TootWidget,
            method = "favourites",
        )


class ListsPage(Page):

    timeline = "lists"
    refresh_allowed = False
    
    def compose(self) -> ComposeResult:
        yield PageHeader(self.timeline)
        yield Static("Lists page is a work in progress", classes="page_box wip")

    @work
    async def refresh_page(self):

        return    #! WIP

        # json_response = await self.app.mastodon.lists()       


class TootPage(Page):

    timeline = "toot"            
    main_toot_id: int | None = None

    def compose(self) -> ComposeResult:
        yield PageHeader(self.timeline)

    @work
    async def refresh_page(self):
        """The logic here is too compex to re-use the _refresh_page method."""

        json_single, json_response = None, None
        with self.app.capture_exceptions():
            json_single   = await self.app.mastodon.status(self.main_toot_id)
            json_response = await self.app.mastodon.status_context(self.main_toot_id)  
        if json_single and json_response:

            await self.remove_children()

            # first mount the main toot
            self.mount(TootWidget(name=f"toot_{self.main_toot_id}", json=json_single, classes="page_box toot"))     

            # ancestors = json_response["ancestors"]       #! TODO not implemented yet
            descendants = json_response["descendants"]

            # mount 'Replies' label
            self.mount(FigletWidget('Replies', font="small", classes="page_box figlet"))

            widgets = [
                TootWidget(name=f"toot_{index}", json=json, classes="page_box toot") 
                for index, json in enumerate(descendants)
            ]
            
            await self.mount_all(widgets)

class UserProfilePage(Page):

    timeline = "user profile" 
    account:  dict | None = None
    relation: dict | None = None     

    def compose(self) -> ComposeResult:
        yield PageHeader(self.timeline)
        yield Static("User Profile page is a work in progress", classes="page_box wip")

    def update_user(self, account_dict: dict, relation_dict: dict) -> None:
        self.account = account_dict
        self.relation = relation_dict

    @work
    async def refresh_page(self):

        self.log.debug("Refreshing user profile page")

        await self.remove_children()

        # This page does not make any API calls itself. Pure dependency injection.

        self.mount(
            ProfileWidget(account_dict=self.account, relation_dict=self.relation, classes="page_box toot")
        )

        # TODO get user's toots and display them here


class TooSmallPage(Container):

    refresh_allowed = False

    def compose(self) -> ComposeResult:
        yield FigletWidget("too small", justify="left", classes="page_header figlet")
        yield Static("The window is too small to display the app. Please resize the window.", classes="page_box small")


class DevelopmentPage(Container):

    refresh_allowed = False

    def compose(self) -> ComposeResult:

        yield PageHeader("Development Settings", refresh_visible=self.refresh_allowed)
        yield DevSettings(classes="settings dev")


class AboutPage(Container):

    refresh_allowed = False
    git_repo = "http://www.github.com/edward-jazzhands/textualdon"

    about_text = f"""TextualDon - by Edward Jazzhands © Copyright 2024 \n
TextualDon is a Mastodon client built with the Textual framework for Python. \n
It is a work in progress and is not yet feature complete. \n
The code is available on GitHub at {git_repo} \n"""
    
    refresh_allowed = False

    # TODO add link buttons to this page, and more info 

    def compose(self):
        yield PageHeader("about", refresh_visible=self.refresh)
        yield Static(self.about_text, classes="page_box")