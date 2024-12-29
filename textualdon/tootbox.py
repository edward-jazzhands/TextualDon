# Standard Library Imports
from __future__ import annotations
from typing import cast
import uuid

# Textual Imports
from textual import on
from textual.dom import NoScreen
from textual.message import Message
from textual.binding import Binding
from textual.containers import Horizontal, Container  # VerticalScroll, Grid
from textual.widget import Widget
from textual.widgets import (
    TextArea,
)

# TextualDon Imports
from textualdon.simplebutton import SimpleButton
from textualdon.messages import SuperNotify, ScrollToWidget
from textualdon.screens import NotImplementedScreen
from textualdon.messages import SwitchMainContent


class TextAreaMain(TextArea):

    class Submit(Message):
        pass

    class Search(Message):
        pass

    class Hide(Message):
        pass

    BINDINGS = [
        Binding("ctrl+e", "submit", "Submit", show=True),
        Binding("ctrl+f", "search", "Search", show=True),
        Binding("ctrl+b", "hide", "Hide", show=True),
        Binding(key="f6", action="bookmarks", description="Bookmarks", key_display="F6", show=False),
        Binding(key="f7", action="favorites", description="Favorites", key_display="F7", show=False),
    ]
    
    def action_submit(self):
        self.post_message(self.Submit())

    def action_search(self):
        self.post_message(self.Search())

    def action_hide(self):
        self.screen.focus_next()
        self.post_message(self.Hide())

    # Overwriting F6 and F7 is a really hacky way to solve this problem. I'd prefer to be able
    # to remove the bindings from the list. But I can't find a way to do that.

    def action_bookmarks(self):
        self.post_message(SwitchMainContent("bookmarks"))

    def action_favorites(self):
        self.post_message(SwitchMainContent("favorites"))

    def on_focus(self):
        self.action_cursor_line_end()


class TextAreaReply(TextArea):

    class Submit(Message):
        pass

    BINDINGS = [
        Binding("ctrl+e", "submit", "Submit reply", show=True),
        Binding("escape", "cancel", "Cancel reply", key_display='Esc', show=True),
        # Binding("enter", "pass", show=False),
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

        # This is the original code from Widget.focus(). I'm not sure why it's not working.
        #! TODO Test this

        # def set_focus(widget: Widget) -> None:
        #     """Callback to set the focus."""
        #     try:
        #         widget.screen.set_focus(self, scroll_visible=False)
        #     except NoScreen:
        #         pass

        # self.app.call_later(set_focus, self)
        return self  
        
    def on_focus(self):

        self.log.debug("Triggered: on_focus in TextAreaReply")
        self.parent.parent.toot_widget.on_focus()

        # The parent.parent thing is messier than messages. But sometimes its less effort. ¯\_(ツ)_/¯
        # Especially when you need to do it a bunch of times in a row, like here.
        # This is probably a bad habit though.

    def on_blur(self):
        self.parent.parent.toot_widget.on_blur()

    def action_submit(self):
        self.post_message(self.Submit())

    async def action_cancel(self):
        await self.parent.parent.toot_widget.reply_to_toot()
        

class TootBox(Container):


    def __init__(self, toot_widget=None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.toot_widget = cast(Widget, toot_widget)      # If toot_widget is NOT None, this is a reply
        self.hidden = False
        self.saved_text = None

    def compose(self):
        with Container(id="toot_box_container"):
            if self.toot_widget:        # different Bindings if its a reply vs a main toot
                yield TextAreaReply(id="toot_box_input", classes = "toot_box_input")
            else:
                yield TextAreaMain(id="toot_box_input", classes = "toot_box_input")
        with Horizontal(classes="reply_footer"):
            yield SimpleButton("Post Toot", id="toot_box_reply", classes="toot_box_button")  # always present in center
            if not self.toot_widget:      # no attached widget means this is the main toot box
                yield SimpleButton("Search mode", id="toot_box_search", classes="toot_box_button left")
                yield SimpleButton("Hide", id="toot_box_hide", classes="toot_box_button right")
            else:                  # attached widget means this is a reply, and we want a cancel button
                yield SimpleButton("Cancel", id="toot_box_cancel", classes="toot_box_button")

    def on_mount(self):

        self.query_one("#toot_box_reply").can_focus = False
        if not self.toot_widget:
            self.query_one("#toot_box_search").can_focus = False
            self.query_one("#toot_box_hide").can_focus = False
        else:
            self.query_one("#toot_box_cancel").can_focus = False

        self.toot_box_container = self.query_one("#toot_box_container")

        if self.toot_widget:
            self.input_box = cast(TextAreaReply, self.query_one("#toot_box_input"))
            self.focus_tootbox()
        else:
            self.input_box = cast(TextAreaMain,  self.query_one("#toot_box_input"))


    ###~ UTILITY METHODS ~###

    def focus_tootbox(self) -> None:
        self.input_box.focus()
        self.input_box.action_cursor_line_end()

    def set_text(self, text: str) -> None:
        """Set text in toot box and focus.
        Called by:
        - tootscreens.TootOptionsOtherUser.mention_thingy 
        - toot.TootWidget._delete_toot (when redrafting) """
        self.input_box.text = text
        self.focus_tootbox()

    @on(SimpleButton.Pressed, selector="#toot_box_cancel")
    def cancel_reply(self):
        self.toot_widget.replybox_on = False
        self.remove()

    @on(TextAreaMain.Search)
    @on(SimpleButton.Pressed, selector="#toot_box_search")
    def search_mode(self):
        self.log.debug("Search key pressed")
        self.app.push_screen(NotImplementedScreen('Search mode', classes="modal_screen"))  # TODO Implement


    @on(TextAreaMain.Hide)
    async def key_hide(self):
        self.log.debug("Hide key pressed")
        await self.hide_tootbox()

    @on(TextAreaReply.Submit)
    @on(TextAreaMain.Submit)
    async def key_submit(self):
        self.log.debug("Submit key pressed")
        await self.post_toot()


    ###~ MAIN LOGIC ~###

    @on(SimpleButton.Pressed, selector="#toot_box_reply")
    async def post_toot(self) -> None:

        if self.app.safe_mode:
            self.post_message(SuperNotify("Please disable safe mode to post."))
            return
        if not self.app.mastodon:
            self.post_message(SuperNotify("You're not logged in."))
            return
        if self.hidden:     # this should never happen.
            self.log.error("Tried to post toot with box hidden")
            return
        if self.input_box.text == "":
            self.post_message(SuperNotify("You can't post an empty toot."))
            return
        
        posted_toot = None
        idempotency_key = str(uuid.uuid4())   # good practice. prevents double posting

        if self.toot_widget:          # attached toot widget means this is a reply
            temp_id = self.toot_widget.boosted_id if self.toot_widget.reblog else self.toot_widget.toot_id
            with self.app.capture_exceptions():
                posted_toot = await self.app.mastodon.status_reply(
                    status = self.input_box.text,
                    to_status = self.toot_widget.json,
                    in_reply_to_id = temp_id,
                    idempotency_key = idempotency_key
                )           
        else:               # no attached widget - this is a new toot
            with self.app.capture_exceptions():                          
                posted_toot = await self.app.mastodon.status_post(
                    status = self.input_box.text,
                    idempotency_key = idempotency_key
                )
            
        if posted_toot:
            self.post_message(SuperNotify("Toot posted successfully."))
            self.input_box.text = ""
            if self.toot_widget:    # if this is a reply
                await self.toot_widget.query_one("#reply_box").remove()
                self.toot_widget.replybox_on = False
                self.toot_widget.refresh_toot()

    def set_memory_text(self):
        self.set_text(self.saved_text)
        self.saved_text = None

    @on(SimpleButton.Pressed, selector="#toot_box_hide")
    async def hide_tootbox(self) -> None:
        if self.hidden:
            self.hidden = False
            self.toot_box_container.mount(TextAreaMain(id="toot_box_input", classes="toot_box_input"))
            self.query_one("#toot_box_hide").update("Hide")
            self.query_one("#toot_box_hide").can_focus = False
            self.query_one("#toot_box_reply").visible = True
            self.query_one("#toot_box_search").visible = True
            self.set_styles("height: auto;")
            self.input_box = self.query_one("#toot_box_input")

            # this saves what the user was typing if they hide the box and then show it again
            if self.saved_text:
                self.set_timer(self.app.text_insert_time, self.set_memory_text)
        else:
            if self.input_box.text != "":           # if the input is not empty, save it
                self.log(f"Saving text: {self.input_box.text}")
                self.saved_text = self.input_box.text
            self.hidden = True
            self.query_one("#toot_box_input").remove()
            self.query_one("#toot_box_hide").update("Show")
            self.query_one("#toot_box_hide").can_focus = True
            self.query_one("#toot_box_reply").visible = False
            self.query_one("#toot_box_search").visible = False
            self.set_styles("height: 1;")
