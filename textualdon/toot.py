# Standard Library imports
from __future__ import annotations
from typing import TYPE_CHECKING, cast, Optional
from textwrap import shorten
import datetime as dt
from enum import Enum

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

# Third Party imports
from mastodon.Mastodon import Mastodon
from tzlocal import get_localzone
import humanize
from rich.emoji import Emoji
from rich.text import Text

# Textual imports
from textual.dom import NoScreen
from textual.binding import Binding
from textual import on, work # events
from textual.message import Message
from textual.containers import Horizontal, Vertical,  Container  # VerticalScroll, Grid
from textual.widget import Widget
from textual.widgets import (
    Pretty,
    Static,
    ContentSwitcher,
    TextArea,
)

# TextualDon imports
from textualdon.simplebutton import SimpleButton
from textualdon.widgets import ImageViewerWidget
from textualdon.tootbox import TootBox
from textualdon.messages import (
    ExamineToot,
    ScrollToWidget,
    SuperNotify
)
from textualdon.bs4_parser import BS4Parser
from textualdon.screens import ConfirmationScreen
from textualdon.tootscreens import (
    TootOptionsMainUser,
    TootOptionsOtherUser,
    UserPopup,
    MuteScreen,
    BlockScreen,
)


class TootWidget(Horizontal):

    class DeleteToot(Message):
        """Used by TootOptionsScreen to trigger deleting a toot."""
        def __init__(self, redraft: bool = False) -> None:
            super().__init__()
            self.redraft = redraft

    class MuteUser(Message):
        """Used by TootOptionsScreen to trigger muting a user."""
        pass

    class BlockUser(Message):
        """Used by TootOptionsScreen to trigger blocking a user."""
        pass


    BINDINGS = [
        Binding("r", "reply", "Reply", show=True),
        Binding("b", "boost", "Boost", show=True),
        Binding("f", "favourite", "Favourite", show=True),
        Binding("m", "bookmark", "Bookmark", show=True),
        Binding("o", "options", "More Options", show=True),
        Binding("enter", "switch_to_tootpage", "Expand toot", show=True),
    ]

    def __init__(self, json: dict, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.can_focus = True       #? ~ notes/widget_focus.md ~

        self.option_handler = TootOptionHandler(self)         
        self.json: dict = json

        self.json_on       = False        # for the JSON view
        self.replybox_on   = False        # toggles reply box
        self.morebox_on    = False        # toggles options box
        self.edit_mode     = False        # toggles edit mode

        # NOTE: It won't request the relationship dict until the user clicks either
        # the 'More' button (options box) or the user name (user popup).
        # If it auto requested it for every single toot, you'd probably get rate limited.

        self.reblog: dict | None = self.json["reblog"]   

        # reblog is the nested json of boosted toot; None if not boosted
        # So if reblogged/boosted, set the main json to the nested reblog json,
        # after extracting the booster's account info.

        if self.reblog:
            self.boosted_by = f"{self.json['account']['display_name']} boosted"
            self.boosted_by_id = self.json["account"]["id"]
            self.boosted_by_account_dict = self.json["account"]
            self.json = self.reblog         #* replace json with nested json
        else:
            self.boosted_by = None

        self.in_reply_to_id:         int | None = self.json["in_reply_to_id"]
        self.in_reply_to_account_id: int | None = self.json["in_reply_to_account_id"]
        self.media_attachments: list = self.json["media_attachments"]
        self.card: dict | None = self.json["card"]
        self.poll: dict | None = self.json["poll"]

    def compose(self):

        self.mastodon = cast(Mastodon, self.app.mastodon)          
        self.loading = True         # always starts with loading screen

        yield Static(id="in_reply_markerbar")
        with Container(id="toot_container", classes="content_container"):
            if self.reblog:
                yield SimpleButton(self.boosted_by, id="boosted_by_button", classes="toot_element")
            if self.in_reply_to_id:
                yield SimpleButton(id="in_reply_to_button", classes="toot_element")

            with Container(classes="toot_header"):
                yield SimpleButton(id="toot_username_button", classes="toot_element")
                yield Static(id="toot_time_label", classes="toot_element b")
                yield SimpleButton(id="toot_user_url_button", classes="toot_element")
                yield Static(id="toot_followers_label", classes="toot_element b")

            with ContentSwitcher(id="toot_content_switcher", initial="toot_content_container"):
                yield TootContentContainer(self, id="toot_content_container")  # note passing in self
                yield Pretty("", id='toot_json_container', classes="toot_extra")
                yield TootEditContainer(self, id="toot_edit_container")  # note passing in self

            with Horizontal(classes="toot_footer"):
                yield SimpleButton(id="toot_reply_button", classes="toot_element")
                yield SimpleButton(id="toot_boost_button", classes="toot_element")
                yield SimpleButton(id="toot_favourite_button", classes="toot_element")
                yield SimpleButton(id="toot_bookmark_button", classes="toot_element")
                yield SimpleButton("More", id="more", classes="toot_element")

            yield SimpleButton(id="toot_url_button", classes="toot_element")

    def on_mount(self):
        """The widget is originally composed with all the fields empty.
        This allows the program to draw the widget first and then fill in the data later."""

        self.call_after_refresh(self.load_toot_data)

    def load_toot_data(self):

        self.account = self.json["account"]

        self.toot_id: int  = self.json["id"]
        self.user_id: int  = self.account["id"]
        self.username: str = self.account["username"]
        self.display_name:   str = self.account["display_name"]
        self.toot_user_url:  str = self.account["url"]
        self.toot_url:       str = self.json["url"]
        self.toot_time: dt.datetime = self.json["created_at"]
        self.toot_followers: int = f"Followers: {self.json['account']['followers_count']}"
        self.toot_reply:     int = f"{Emoji('right_arrow_curving_left')} {self.json['replies_count']} Reply"
        self.tags:     list = self.json["tags"]
        self.emojis:   list = self.json["emojis"]     
        self.mentions: list = self.json["mentions"]
        self.visibility:  str = self.json["visibility"]
        self.sensitive:  bool = self.json["sensitive"]
        self.favourited: bool = self.json["favourited"] 
        self.reblogged:  bool = self.json["reblogged"]   
        self.muted:      bool = self.json["muted"]           
        self.bookmarked: bool = self.json["bookmarked"]
        self.relation_dict = [] # this is lazy loaded when the user popup is opened. Here as safety.

        # These are set in __init__ but we need to refresh them anyway.
        self.in_reply_to_id:         int | None = self.json["in_reply_to_id"]
        self.in_reply_to_account_id: int | None = self.json["in_reply_to_account_id"]
        self.media_attachments: list = self.json["media_attachments"]
        self.card: dict | None = self.json["card"]
        self.poll: dict | None = self.json["poll"]

        self.is_main_user = self.determine_if_main_user()

        self.toot_container = self.query_one("#toot_container")   

        self.toot_switcher          = cast(ContentSwitcher,      self.query_one("#toot_content_switcher"))   
        self.toot_content_container = cast(TootContentContainer, self.query_one("#toot_content_container"))

        in_reply_markerbar = self.query_one("#in_reply_markerbar")
        if self.in_reply_to_id:
            self.query_one("#in_reply_to_button").update(f"{Emoji('arrow_upper_left')} Continued Thread")                                  # this controls the black bar on the side that appears
        else:
            in_reply_markerbar.display = False

        self.toot_username_button = self.query_one("#toot_username_button")
        self.toot_user_url_button = self.query_one("#toot_user_url_button")
        self.toot_time_label      = self.query_one("#toot_time_label")
        self.toot_followers_label = self.query_one("#toot_followers_label")
        self.toot_reply_button    = self.query_one("#toot_reply_button")
        self.toot_favorite_button = self.query_one("#toot_favourite_button")
        self.toot_boost_button    = self.query_one("#toot_boost_button")
        self.toot_bookmark_button = self.query_one("#toot_bookmark_button")
        self.toot_url_button      = self.query_one("#toot_url_button")

        self.toot_username_button.update(f"{self.display_name} (@{self.username})")
        self.toot_user_url_button.update(f"{Emoji('link')} {self.toot_user_url}")
        self.toot_followers_label.update(self.toot_followers)
        self.toot_reply_button.update(self.toot_reply)

        self.set_time()

        self.toot_username_button.tooltip = (f"{self.display_name} (@{self.username}) \n\n"
                                    "Click to open user pop-up.")
        
        user_url_display = f"{Emoji('link')} {self.toot_user_url}"
        self.toot_user_url_button.update(user_url_display)

        toot_url_display = f"{Emoji('link')} {self.toot_url}"
        self.toot_url_button.update(toot_url_display)

        if self.favourited:
            toot_favourite = f"{Emoji('star2')} {self.json['favourites_count']} Favourited"
            toot_favourite_tooltip = "Click to unfavourite."
        else:
            toot_favourite = f"{Emoji('star')} {self.json['favourites_count']} Favourite"
            toot_favourite_tooltip = "Click to favourite."
        self.toot_favorite_button.update(toot_favourite)
        self.toot_favorite_button.tooltip = toot_favourite_tooltip

        if self.bookmarked:
            toot_bookmark = f"{Emoji('bookmark')} Bookmarked"
            toot_bookmark_tooltip = "Click to remove bookmark."
        else:
            toot_bookmark = f"{Emoji('bookmark')} Bookmark"
            toot_bookmark_tooltip = "Click to bookmark."
        self.toot_bookmark_button.update(toot_bookmark)
        self.toot_bookmark_button.tooltip = toot_bookmark_tooltip

        # Boosted/reblogged logic
        if self.reblogged:
            toot_boost = f"{Emoji('rocket')} {self.json['reblogs_count']} Boosted"
            toot_boost_tooltip = "Click to remove boost."
        else:
            toot_boost = f"{Emoji('crescent_moon')} {self.json['reblogs_count']} Boost"
            toot_boost_tooltip = "Click to boost."
        self.toot_boost_button.update(toot_boost)
        self.toot_boost_button.tooltip = toot_boost_tooltip

        self.query_one("#toot_json_container").update(self.json)

        for child in self.children:
            self.recursive_no_focus(child)

        self.loading = False

    def recursive_no_focus(self, child = None):
        """Set can_focus to False for every child in the toot widget.
        The only thing in a toot widget that's allowed to focus is the edit container,
        so we just turn that back on manually when needed."""

        if child is None:
            self.log.error("No child passed to recursive_no_focus")
            return

        child.can_focus = False
        if child.children:
            for subchild in child.children:
                self.recursive_no_focus(subchild)

    def set_time(self):

        timezone: ZoneInfo = get_localzone()    
        current_time = dt.datetime.now(timezone)
        elapsed_time: dt.timedelta = current_time - self.toot_time

        if elapsed_time.days > 3:
            time_label = humanize.naturaldate(self.toot_time)
        else:
            time_label = humanize.naturaltime(elapsed_time)

        self.toot_time_label.update(time_label)
        self.toot_time_label.tooltip = self.toot_time.strftime("%d %b %Y %H:%M")

    def on_focus(self):
        self.log.debug(f"{self.name} focused. ")
        self.styles.border = ('dashed', self.app.theme_variables["primary"])

        # TODO Need note about doing this through the code and not CSS

    def on_blur(self):
        self.styles.border = ('blank', 'transparent')

    def determine_if_main_user(self) -> bool:

        # Technically speaking, it's possible to encounter a user on a different instance with
        # the same user_id as the logged in user. This is highly unlikely, but it's possible.

        user_id = self.user_id
        if user_id == self.app.logged_in_user_id:
            return True
        else:
            return False

    def switch_content(self, switch_to: str) -> None:
        """This is used by more box (TootOptions). Switches normal/html/json mode"""

        self.toot_switcher.current = switch_to

    def edit_toot(self):
        """This is used by TootOptions. Switches to edit mode"""

        if not self.edit_mode:
            self.switch_content("toot_edit_container")
            self.query_one("#toot_edit_container").edit_toot()
            self.query_one("#toot_edit_container").focus()
            self.edit_mode = True
        else:
            self.switch_content("toot_content_container")
            self.edit_mode = False

    @work
    async def refresh_toot(self, delay: int = 0.5) -> None:
        """ This is called by:
        ```
        - tootscreens.TootOptionsScreen.refresh_toot
        - toot.TootEditContainer.save_edit             # refresh after edit
        - toot.TootOptionHandler.handle_toot_action    # refresh after actions like boost, favourite, etc.
        - toot.TootBox.post_toot                       # when Tootbox is a reply  """

        self.log.debug("Refreshing Toot.")
        self.loading = True

        async def refresh_internal():

            json = None
            with self.app.capture_exceptions():
                json = await self.mastodon.status(self.toot_id)
                if json:
                    self.json = json
                    self.call_after_refresh(self.load_toot_data)
                    self.call_after_refresh(self.toot_content_container.load_toot_content)
        self.set_timer(delay, refresh_internal)   # half second delay to give server time to refresh.


    async def view_image(self):
        await self.toot_content_container.imgviewer_widget.fullscreen()

    @on(SimpleButton.Pressed, selector='#toot_username_button')
    @work
    async def open_user_popup(self) -> None:

        # lazy load the relation_dict every time the user popup is opened
        relation_list = None
        with self.app.capture_exceptions():
            relation_list = await self.mastodon.account_relationships(self.user_id)
        if relation_list:
    
            self.log.debug(relation_list)
            self.relation_dict = relation_list[0]

            await self.app.push_screen(UserPopup(self.json['account'], self.relation_dict, classes="modal_screen"))

    @on(SimpleButton.Pressed, selector='#boosted_by_button')
    @work
    async def open_booster_popup(self) -> None:

        # lazy load the relation_dict every time the booster popup is opened
        relation_list = None
        with self.app.capture_exceptions():
            relation_list = await self.mastodon.account_relationships(self.boosted_by_id)
        if relation_list:

            relation_dict = relation_list[0]
            self.log.debug(relation_dict)

        await self.app.push_screen(UserPopup(self.boosted_by_account_dict, relation_dict, classes="modal_screen"))  

    @on(SimpleButton.Pressed, selector='#toot_user_url_button')
    def open_user_url(self) -> None:

        self.app.handle_link(self.toot_user_url)

    @on(SimpleButton.Pressed, selector='#more')
    async def show_more_options(self) -> None:

        # lazy loading the relation_dict every time the options screen is opened
        relation_list = None
        with self.app.capture_exceptions():
            relation_list = await self.mastodon.account_relationships(self.user_id)
        if relation_list:   

            self.log.debug(relation_list)
            self.relation_dict = relation_list[0]

            if self.is_main_user:
                await self.app.push_screen(TootOptionsMainUser(self, name="toot_options", classes="modal_screen"))
            else:
                await self.app.push_screen(TootOptionsOtherUser(self, name="toot_options", classes="modal_screen"))

    @on(SimpleButton.Pressed, selector='#toot_url_button')
    def open_toot_url(self) -> None:

        self.app.handle_link(self.toot_url)

    @on(SimpleButton.Pressed, selector="#toot_boost_button")
    async def boost_toot(self) -> None:
        action          = "status_unreblog" if self.reblogged else "status_reblog"
        success_message = "Boost removed"  if self.reblogged else "Toot boosted."
        failure_message = "FAILED to remove boost." if self.reblogged else "FAILED to boost toot."

        await self.option_handler.handle_toot_action(
            action=action,
            success_message=success_message,
            failure_message=failure_message,
            toggle_status=self.reblogged,
            key=self.option_handler.StatusKey.REBLOGGED
        )

    @on(SimpleButton.Pressed, selector="#toot_favourite_button")
    async def favorite_toot(self) -> None:
        action          = "status_unfavourite" if self.favourited else "status_favourite"
        success_message = "Toot Unfavourited"  if self.favourited else "Toot favourited."
        failure_message = "FAILED to Unfavourite toot." if self.favourited else "FAILED to favourite toot."

        await self.option_handler.handle_toot_action(
            action=action,
            success_message=success_message,
            failure_message=failure_message,
            toggle_status=self.favourited,
            key=self.option_handler.StatusKey.FAVOURITED,
        )

    @on(SimpleButton.Pressed, selector='#toot_bookmark_button')
    async def bookmark_toot(self) -> None:
        action         = "status_unbookmark" if self.bookmarked else "status_bookmark"
        success_message = "Toot unbookmarked." if self.bookmarked else "Toot bookmarked."
        failure_message = "FAILED to unbookmark toot." if self.bookmarked else "FAILED to bookmark toot."

        await self.option_handler.handle_toot_action(
            action=action,
            success_message=success_message,
            failure_message=failure_message,
            toggle_status=self.bookmarked,
            key=self.option_handler.StatusKey.BOOKMARKED
        )

    @on(SimpleButton.Pressed, selector='#toot_reply_button')
    async def reply_to_toot(self, event: SimpleButton.Pressed = None) -> None:

        if event:
            self.log.debug(f"Button: {event.button.id}")

        if not self.replybox_on:
            self.toot_container.mount(TootBox(toot_widget=self, id="reply_box"))
            self.replybox_on = True
        else:
            self.query_one("#reply_box").remove()
            self.replybox_on = False

    @on(SimpleButton.Pressed, selector='#in_reply_to_button')
    def switch_to_inreplyto(self) -> None:
        """This will bubble up to the main app and switch to the toot page with the toot_id"""

        self.post_message(ExamineToot(self.in_reply_to_id))


    ###~ TOOT OPTIONS CALLBACKS ~###

    @on(DeleteToot)
    async def delete_toot(self, event: DeleteToot) -> None:

        self.log.debug("Delete toot callback.")
        self.app.push_screen(
            ConfirmationScreen(classes = "modal_screen", forward=event.redraft),
            self._delete_toot
        )

    async def _delete_toot(self, redraft: bool = False) -> None:
        """ Callback from `delete_toot` (above). \n
        `redraft` is `True` if the user wants to redraft the toot after deletion."""

        await self.option_handler.handle_toot_action(
            action = "status_delete",
            success_message = "Toot deleted.",
            failure_message = "FAILED to delete toot!",
            toggle_status=False      # doesn't matter whether this is true or false. Just need to pass something.
        )
        await self.remove()

        if redraft:
            self.log.debug("Redrafting toot.")
            self.app.main_tootbox.set_text(self.toot_content_container.parsed_content)

    @on(MuteUser)
    async def mute_user(self) -> None:

        self.log.debug("Mute user callback.")

        mute_status = self.relation_dict['muting']
        if mute_status:     # dont need confirmation if unmuting
            await self._mute_user(mute_status)
        else:
            self.app.push_screen(
                MuteScreen(self.username, mute_status, classes = "modal_screen"),
                self._mute_user
            )

    async def _mute_user(self, mute_status:bool) -> None:

        action          = "account_unmute" if mute_status else "account_mute"
        success_message = f"@{self.username} unmuted." if mute_status else f"@{self.username} muted."
        failure_message = f"FAILED to unmute @{self.username}." if mute_status \
                            else f"FAILED to mute @{self.username}."

        await self.option_handler.handle_toot_action(
            action=action,
            success_message=success_message,
            failure_message=failure_message,
            toggle_status=mute_status,
            key=self.option_handler.StatusKey.MUTING,
            on_user=True
        )

    @on(BlockUser)
    async def block_user(self) -> None:

        self.log.debug("Block user callback.")

        block_status = self.relation_dict['blocking']
        if block_status:
            await self._block_user(block_status)
        else:
            self.app.push_screen(
                BlockScreen(self.username, block_status, classes = "modal_screen"),
                self._block_user
            )

    async def _block_user(self, block_status: bool) -> None:
        
        action          = "account_unblock" if block_status else "account_block"
        success_message = f"@{self.username} unblocked." if block_status else f"@{self.username} blocked."
        failure_message = f"FAILED to unblock @{self.username}." if block_status \
                            else f"FAILED to block @{self.username}."

        await self.option_handler.handle_toot_action(
            action=action,
            success_message=success_message,
            failure_message=failure_message,
            toggle_status=block_status,
            key=self.option_handler.StatusKey.BLOCKING,
            on_user=True
        )

    ###~ ACTIONS ~###

    async def action_reply(self):
        await self.reply_to_toot()

    async def action_boost(self):
        await self.boost_toot()

    async def action_favourite(self):
        await self.favorite_toot()

    async def action_bookmark(self):
        await self.bookmark_toot()

    async def action_options(self):
        await self.show_more_options()

    def action_switch_to_tootpage(self):
        self.refresh_bindings()
        self.post_message(ExamineToot(self.toot_id))

    def check_action(
        self, action: str, parameters: tuple[object, ...]
    ) -> bool | None:  
        """Check if an action may run."""
        if action == "switch_to_tootpage":
            if self.toot_switcher.current == "toot_edit_container":
                return False
            if self.replybox_on and self.query_one("#reply_box").has_focus_within:
                return False
        return True


class TootContentContainer(Vertical):

    def __init__(self, toot_widget: TootWidget, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.toot_widget = toot_widget
        self.bs4_parser = BS4Parser()
        self.media = self.toot_widget.media_attachments
        self.image_url = self.media[0]["preview_url"] if self.media else None
        self.image_on: bool = False
        self.parsed_content = None

        # TODO Maybe should not be using preview_url for images. But it seems to work for now.
        # We can't exactly display a very high res image in a terminal anyway.

    def compose(self):
        yield SimpleButton('', id='toot_content_button', classes="toot_content", no_wrap=None, overflow=None)

        if self.app.show_images and self.image_url:
            self.image_on = True
            yield ImageViewerWidget(
                self.image_url,
                id="imgviewer_widget",
                classes="toot_image"
            )
        yield Static("", id='media_description', classes="toot_extra")

        if self.toot_widget.card:
            yield TootCardWidget(self.toot_widget, id="toot_card_widget", classes="toot_card")

    def on_mount(self):

        self.imgviewer_widget = self.query_one("#imgviewer_widget") if self.image_on else None
        self.call_after_refresh(self.load_toot_content)

    def load_toot_content(self):

        self.parsed_content = self.bs4_parser.parser(self.toot_widget.json["content"])
        self.query_one("#toot_content_button").update(self.parsed_content)
    
        if self.image_url:
            description1 = f"Image description: {self.media[0]['description']}"
            self.query_one("#media_description").update(description1)

            # There might be more than 1 attachment, but we just want the first one.
            # TODO maybe add option to load more than one image

    @on(SimpleButton.Pressed, selector='#toot_content_button')
    def switch_to_tootpage(self):
        self.post_message(ExamineToot(self.toot_widget.toot_id))


class TootOptionHandler(Widget):

    class StatusKey(str, Enum):
        """These are the keys that are checked in the returned JSON dict to see if the action was successful."""
        PINNED = "pinned"
        MUTED = "muted"             # muted is for the status / conversation. 'mute this conversation'
        REBLOGGED = "reblogged"
        FAVOURITED = "favourited"
        BOOKMARKED = "bookmarked"
        MUTING = "muting"           # muting is for the user. 'mute this user'
        BLOCKING = "blocking"

    def __init__(self, toot_widget: TootWidget) -> None:
        super().__init__()
        self.toot_widget = toot_widget

    async def handle_toot_action(
        self,
        action: str,                     # The name of the Mastodon API method to call (e.g., 'status_pin').
        success_message: str,            # Message to display on success.
        failure_message: str,            # Message to display on failure.
        toggle_status: bool,             # The ingoing status of the toggle.
        key: Optional[StatusKey] = None, # The key in the returned JSON dict to check for success.
        on_user: bool = False            # Whether the action is on the user or the status
    ) -> None:
        """Every Mastodon action passed into this method must take either a toot_id 
        or a user_id as its first argument. This is determined by the
        `on_user` parameter. If `on_user` is True, the action is on the user (toot author).
        If `on_user` is False, the action is on the status (the toot itself).
        
        'key' is the entry in the returned JSON dict that will be checked to see if the action
        was successful. If the action is successful, the value of the key should be different
        from the ingoing status. If the action is unsuccessful, the value of the key should be the same."""
        
        self.log.debug(
            f"Handling action: {action} \n"
            f"toggle_status: {toggle_status} \n"
            f"key: {key} \n"
            f"on_user: {on_user} \n"
        )
        
        if on_user:
            id_to_action = self.toot_widget.user_id    # user actions are mute, block, etc
        else:
            id_to_action = self.toot_widget.toot_id    # status actions are boost, favourite, etc

        attribute = None
        with self.app.capture_exceptions():
            attribute = getattr(self.app.mastodon, action)
        if self.app.error:
            return
        if attribute:

            status = None
            with self.app.capture_exceptions():
                status = await attribute(id_to_action)
            if self.app.error:
                return
            if status:

                self.log.debug(
                    f"{action.capitalize()} status: {status} \n"
                    f"{action.capitalize()} status isinstance of dict?:  {isinstance(status, dict)}"
                )
                if isinstance(status, dict):
                    if key and status[key] != toggle_status:  # check returned dict is different from ingoing status
                        self.post_message(SuperNotify(success_message))
                    if not key:
                        self.post_message(SuperNotify(success_message))
                else:
                    self.post_message(SuperNotify(failure_message))
                
                if action == "status_delete":
                    return
                else:
                    self.toot_widget.refresh_toot()


class TextAreaEdit(TextArea):

    class Submit(Message):
        pass

    BINDINGS = [
        Binding("ctrl+e", "submit", "Save edit", show=True),
        Binding("escape", "cancel", "Cancel edit", key_display='Esc', show=True),
        Binding("enter", "pass", "Create new line", show=False),
    ]

    def focus(self, scroll_visible: bool = True):
        """Copied from Widget.focus() but with scroll_visible set to False and removed
        the call_later thing. (it gave issues, no idea why.)"""

        try:        
            self.screen.set_focus(self, scroll_visible=False)
        except NoScreen:
            pass

        return self

    def action_submit(self):
        self.post_message(self.Submit())

    def action_cancel(self):
        self.parent.cancel_edit()

    def action_pass(self):
        pass


class TootEditContainer(Container):
    """Unlike the reply box, this is not added and removed. It's composed in the widget,
    and switched to using the ContentSwitcher."""

    def __init__(self, toot_widget: TootWidget, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.toot_widget = toot_widget
        self.content = None

    def compose(self):
        yield TextAreaEdit("", id='toot_edit_box')
        with Horizontal(classes="reply_footer"):
            yield SimpleButton("Save edit", id="toot_edit_save", classes="toot_box_button")
            yield SimpleButton("Cancel", id="toot_edit_cancel", classes="toot_box_button")

    def on_mount(self):
        self.input_box = cast(TextArea, self.query_one("#toot_edit_box"))

    def edit_toot(self) -> None:

        self.input_box.can_focus = True    # this has to be here and not in on_mount.      
        self.content = self.toot_widget.toot_content_container.parsed_content
        self.set_timer(self.app.text_insert_time, self.set_content)   # to solve text glitching

    def set_content(self) -> None:
        self.input_box.text = self.content
        self.input_box.focus()
        self.input_box.action_cursor_line_end()
        self.app.post_message(ScrollToWidget(self.input_box))


    @on(TextAreaEdit.Submit)
    @on(SimpleButton.Pressed, selector="#toot_edit_save")
    async def save_edit(self) -> None:
        # I did this because the arguments here are too different
        # from the normal option handler to justify using it.

        with self.app.capture_exceptions():
            await self.app.mastodon.status_update(
                id=self.toot_widget.toot_id,
                status=self.input_box.text,
                spoiler_text=None,                      #! TODO implement these
                sensitive=None,                         # Roadmap: More tooting options
                media_ids=None,
                poll=None
            )
        
        self.toot_widget.switch_content("toot_content_container")
        if not self.app.error:
            self.toot_widget.refresh_toot()

    @on(SimpleButton.Pressed, selector="#toot_edit_cancel")
    def cancel_edit(self) -> None:
        self.toot_widget.switch_content("toot_content_container")
        self.toot_widget.edit_mode = False
        self.toot_widget.focus()


class TootCardWidget(Vertical):

    def __init__(self, toot_widget: dict, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.toot_widget = toot_widget
        self.card_json = toot_widget.card

        self.url        = f"{self.card_json['url']} \n"
        self.card_title = f"{self.card_json['title']} \n"
        self.image_url  =  self.card_json["image"]
        self.image_description = self.card_json["image_description"]        

        img_desc:str = shorten(self.card_json["description"], width=100)

        if self.app.link_behavior == 0:
            self.tooltip = f"{img_desc} \n\n Click to open in browser"
        elif self.app.link_behavior == 1:
            self.tooltip = f"{img_desc} \n\n Click to copy link to clipboard"
        elif self.app.link_behavior == 2:
            self.tooltip = f"{img_desc} \n\n Click to open link helper popup"

    def compose(self):

        # If there's both media attachments and a toot card, we only want to show the
        # media attachments. Because otherwise its just too much image.

        if self.app.show_images and self.image_url and not self.toot_widget.media_attachments:
            yield ImageViewerWidget(self.image_url, in_card=True, classes="toot_image")
        yield Static("", id="toot_card_title", classes="toot_card_data")
        yield Static("", id="toot_card_url", classes="toot_card_data")
        yield Static("", id="toot_card_image_desc", classes="toot_card_data")

    def on_mount(self):
        
        # This uses the Rich Text class to make the URL crop if it's too long
        rich_url = Text(self.url, no_wrap=True, overflow="crop")
        self.query_one("#toot_card_url").update(rich_url)

        self.query_one("#toot_card_title").update(self.card_title)
        if self.image_description:
            self.query_one("#toot_card_image_desc").update(f"Image description: {self.image_description}")

    def on_click(self) -> None:

        self.app.handle_link(self.card_json["url"])

    # This is a trick to make it light up the entire card and all children on hover.
    def on_enter(self):
        self.styles.background = self.app.theme_variables["panel-lighten-1"]

    def on_leave(self):
        self.styles.background = self.app.theme_variables["surface-lighten-1"]





