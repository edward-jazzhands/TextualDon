# Standard Library imports
from __future__ import annotations
from typing import cast, TYPE_CHECKING
from textwrap import shorten

if TYPE_CHECKING:
    from textualdon.toot import TootWidget

# Textual imports
from textual import on
from textual.message import Message
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Label, Button

# TextualDon imports
from textualdon.simplebutton import SimpleButton
from textualdon.messages import ExamineToot, UserPopupMessage
from textualdon.screens import NotImplementedScreen, TextualdonModalScreen
from textualdon.sql import SQLite
from textualdon.bs4_parser import BS4Parser



class TootOptionsScreen(ModalScreen):

    class Dismiss(Message):
        pass

    BINDINGS = [
        Binding("escape", "dismiss", key_display='Esc', description="Close the pop-up screen.", show=True),
        Binding("up", "focus_previous", description="Focus the previous button."),
        Binding("down", "focus_next", description="Focus the next button."),
    ]

    controls = "Arrow keys (or tab): navigate | Enter: select |  Esc or click anywhere: close."

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = cast(SQLite, self.app.sqlite)

        sql_query = "SELECT value FROM settings WHERE name = ?"
        row1 = self.db.fetchone(sql_query, ("view_json_active",))
        self.view_json_active: bool = ('True' == row1[0])

    def on_mount(self):
        
        options_container = self.query_one("#options_container")
        options_list = []

        # NOTE: this might seem like kind of a mess, but they have to go in a specific order.
        # So its either this or insert them in the right order, which is more error-prone.

        if self.toot_widget.toot_content_container.image_on:
            options_list.append(SimpleButton(    'View image in full size', id='view_image_button', classes="screen_button"))
        options_list.append(SimpleButton(  'Copy link to toot to clipboard', id='copy_link_button', classes="screen_button"))
        if self.toot_widget.card and self.toot_widget.card['url']:
            options_list.append(SimpleButton("Open mentioned URL / Website.", id="open_url_button", classes="screen_button"))
        if self.toot_widget.in_reply_to_id:
            options_list.append(SimpleButton(        "View conversation", id="view_parent_button",  classes="screen_button"))
        options_list.append(SimpleButton(       'View details of author', id='view_profile_button', classes="screen_button"))
        if self.toot_widget.boosted_by:
            options_list.append(SimpleButton(  "View details of booster", id="view_booster_button", classes="screen_button"))
        if self.view_json_active:
            if self.toot_widget.toot_switcher.current == "toot_json_container":
                options_list.append(SimpleButton(  "Back to normal mode", id="toggle_json_button",  classes="screen_button"))
            else:
                options_list.append(SimpleButton(            "View JSON", id="toggle_json_button",  classes="screen_button"))
        options_list.append(SimpleButton('Refresh Toot', id='refresh_button', classes="screen_button"))

        options_container.mount_all(options_list)

        self.mount(
            Container(Label(self.controls, classes='screen_label'), classes='screen_container wide help')
        )     

    # NOTE: Every single thing a person can click or press enter on here should result in the
    # options screen being dismissed. So here that behavior is centralized.

    def on_click(self):
        self.dismiss()

    @on(SimpleButton.Pressed, selector="#view_image_button")
    async def view_image(self) -> None:
        await self.toot_widget.view_image()

    @on(SimpleButton.Pressed, selector="#copy_link_button")
    def copy_link(self) -> None:
        self.app.copy_to_clipboard(self.toot_widget.toot_url)

    @on(SimpleButton.Pressed, selector="#open_url_button")
    def open_url(self) -> None:
        self.app.handle_link(self.toot_widget.card['url'])

    @on(SimpleButton.Pressed, selector="#view_parent_button")
    def view_parent(self) -> None:
        self.post_message(ExamineToot(self.toot_widget.in_reply_to_id))

    @on(SimpleButton.Pressed, selector="#view_profile_button")
    def view_profile(self) -> None:
        self.toot_widget.open_user_popup()

    @on(SimpleButton.Pressed, selector="#view_booster_button")
    def view_booster(self) -> None:
        self.toot_widget.open_booster_popup()

    @on(SimpleButton.Pressed, selector="#refresh_button")
    def refresh_toot(self) -> None:
        self.toot_widget.refresh_toot()
        
    def action_focus_previous(self):
        self.focus_previous()
    
    def action_focus_next(self):
        self.focus_next()

    @on(SimpleButton.Pressed, selector="#toggle_json_button")
    def toggle_json(self) -> None:

        if self.toot_widget.toot_switcher.current == "toot_json_container":
            self.toot_widget.switch_content("toot_content_container")
        else:
            self.toot_widget.switch_content("toot_json_container")


class TootOptionsMainUser(TootOptionsScreen):

    def __init__(self, toot_widget: TootWidget, **kwargs):
        super().__init__(**kwargs)
        self.toot_widget = toot_widget
        self.option_handler = toot_widget.option_handler

        if self.toot_widget.is_main_user:
            self.pin_status = self.toot_widget.json["pinned"]       #! must refresh between toots?
            self.pin_label = "Unpin from Profile" if self.pin_status else "Pin on Profile"
            self.mute_status = self.toot_widget.json["muted"]
            self.mute_label = "Unmute conversation" if self.mute_status else "Mute conversation"

    def compose(self):
        with Vertical(id="options_container", classes='screen_container'):
            yield SimpleButton(self.pin_label, id="pin_button", classes="screen_button")
            yield SimpleButton("Edit",   id="edit_button",      classes="screen_button")
            yield SimpleButton("Delete", id="delete_button",    classes="screen_button")
            yield SimpleButton("Delete & Redraft", id="delete_redraft_button", classes="screen_button")

            yield SimpleButton(self.mute_label, id='mute_button', classes="screen_button")  #! exists between other user? 

    # This is identical in both classes but it has to be on the actual instance and not
    # the parent class. Don't fully understand why. But it didn't work when it was in the parent class.
    @on(SimpleButton.Pressed)
    def close_screen(self):
        self.dismiss()

    # NOTE: The options are handled by the TootOptionsHandler class, attached to the TootWidget.

    @on(SimpleButton.Pressed, selector="#pin_button")
    async def pin_toot(self) -> None:
        action          = "status_unpin"   if self.pin_status else "status_pin"
        success_message = "Toot unpinned." if self.pin_status else "Toot pinned."
        failure_message = "FAILED to unpin toot." if self.pin_status else "FAILED to pin toot."

        await self.toot_widget.option_handler.handle_toot_action(
            action=action,
            success_message=success_message,
            failure_message=failure_message,
            toggle_status=self.pin_status,
            key=self.option_handler.StatusKey.PINNED,
        )
        
    @on(SimpleButton.Pressed, selector="#mute_button")
    async def mute_toot(self) -> None:
        action          = "status_unmute"     if self.mute_status else "status_mute"
        success_message = "Toot unmuted."     if self.mute_status else "Toot muted."
        failure_message = "FAILED to unmute toot." if self.mute_status else "FAILED to mute toot."

        await self.toot_widget.option_handler.handle_toot_action(
            action=action,
            success_message=success_message,
            failure_message=failure_message,
            toggle_status=self.mute_status,
            key=self.option_handler.StatusKey.MUTED,
        )
        
    @on(SimpleButton.Pressed, selector="#delete_button")
    def delete_toot_button(self) -> None:

        # NOTE: Because some methods like here require a callback from a confirmation 
        # screen, they need to be handled by the toot widget itself. 

        self.toot_widget.post_message(self.toot_widget.DeleteToot())
        
    @on(SimpleButton.Pressed, selector="#delete_redraft_button")
    def delete_redraft_toot(self) -> None:

        self.toot_widget.post_message(self.toot_widget.DeleteToot(redraft=True)) 
        
    @on(SimpleButton.Pressed, selector="#edit_button")
    def edit_toot(self) -> None:
        self.toot_widget.edit_toot()     # toot_widget contains the text edit box.
        

class TootOptionsOtherUser(TootOptionsScreen):

    def __init__(self, toot_widget: TootWidget, **kwargs):
        super().__init__(**kwargs)
        self.toot_widget = toot_widget
        # self.option_handler = toot_widget.option_handler

        self.toot_username = toot_widget.username
        self.mention_label = f"Mention @{self.toot_username}"

        self.mute_status = self.toot_widget.relation_dict['muting']
        self.mute_label = f"Unmute @{self.toot_username}" if self.mute_status else f"Mute @{self.toot_username}"

        self.block_status = self.toot_widget.relation_dict['blocking']
        self.block_label = f"Unblock @{self.toot_username}" if self.block_status else f"Block @{self.toot_username}"

        self.report_label = f"Report @{self.toot_username}"

    def compose(self):
        with Vertical(id="options_container", classes='screen_container'):
            yield SimpleButton(self.mention_label, id="mention_button", classes="screen_button")
            yield SimpleButton(self.mute_label,    id="mute_button",    classes="screen_button")
            yield SimpleButton(self.block_label,   id="block_button",   classes="screen_button")
            yield SimpleButton(self.report_label,  id="report_button",  classes="screen_button")
            yield SimpleButton("Filter post",      id="filter_button",  classes="screen_button")

    @on(SimpleButton.Pressed)
    def close_screen(self):
        self.dismiss()   

    @on(SimpleButton.Pressed, selector="#mention_button")
    def mention_handler(self):
        self.app.main_tootbox.set_text(f"@{self.toot_username} ")
        
    @on(SimpleButton.Pressed, selector="#mute_button")
    def mute_button_handler(self):

        self.toot_widget.post_message(self.toot_widget.MuteUser())
            
    @on(SimpleButton.Pressed, selector="#block_button")
    def block_button_handler(self):

        self.toot_widget.post_message(self.toot_widget.BlockUser())
        
    @on(SimpleButton.Pressed, selector="#report_button")
    def report_user(self) -> None:
        self.app.push_screen(NotImplementedScreen('Reporting system', classes="modal_screen"))

    @on(SimpleButton.Pressed, selector="#filter_button")
    def filter_toot(self) -> None:
        self.app.push_screen(NotImplementedScreen('Filter toot', classes="modal_screen"))
        

class MuteScreen(TextualdonModalScreen):
    """Called by:
    - TootWidget.mute_user
    
    Callback: TootWidget._mute_user"""

    def __init__(self, username: str, mute_status: bool, **kwargs):
        self.username = username
        self.mute_status = mute_status
        super().__init__(**kwargs)        

    def compose(self):
        with Container(classes='screen_container'):
            yield Label(f'Are you sure you want to mute @{self.username}? \n', classes='screen_label')
            with Horizontal(classes='screen_buttonbar'):
                yield Button('Yes', id='confirm_yes_button')                
                yield Button('No', id='close_button')           

    @on(Button.Pressed, selector='#confirm_yes_button')
    def confirm_yes(self):

        self.dismiss(self.mute_status)

    @on(Button.Pressed, selector='#close_button')
    def report_close(self):
        self.action_pop_screen()


class BlockScreen(TextualdonModalScreen):
    """Called by:
    - TootWidget.block_user
    
    Callback: TootWidget._block_user"""

    def __init__(self, username: str, block_status: bool, **kwargs):
        self.username = username
        self.block_status = block_status
        super().__init__(**kwargs)

    def compose(self):
        with Container(classes='screen_container'):
            yield Label(f'Are you sure you want to block @{self.username}? \n', classes='screen_label')
            with Horizontal(classes='screen_buttonbar'):
                yield Button('Yes', id='confirm_yes_button')                
                yield Button('No', id='close_button')            

    @on(Button.Pressed, selector='#confirm_yes_button')
    def confirm_yes(self):

        self.dismiss(self.block_status)

    @on(Button.Pressed, selector='#close_button')
    def report_close(self):

        self.action_pop_screen()


class UserPopup(TextualdonModalScreen):
    """ Called by:
    - TootWidget.open_user_popup
    - TootWidget.open_booster_popup
    
    Callback: None (sends UserPopupMessage instead)"""

    controls = "Arrow keys (or tab): navigate | Enter: select | Esc or click anywhere: close"
    
    bs4_parser = BS4Parser()

    def __init__(self, account_dict: dict, relation_dict: dict, **kwargs):
        super().__init__(**kwargs)
        self.account = account_dict
        self.relation = relation_dict
        self.parsed_bio = self.bs4_parser.parser(self.account["note"])
        self.disable_follow = False

        if self.account['id'] == self.app.logged_in_user_id:
            self.relation_note1 = 'This is you.'
            self.relation_note2 = ''
            self.disable_follow = True
            return

        if self.relation['following']:
            self.relation_note1 = 'You [green]are following[/green] this user.'
        else:
            self.relation_note1 = 'You are [red]not following[/red] this user.'
        if self.relation['followed_by']:
            self.relation_note2 = 'They [green]are following[/green] you \n'
        else:
            self.relation_note2 = 'They are [red]not following[/red] you \n'

    def compose(self):

        user_label = (
            f"{self.account['display_name']}\n"
            f"@{self.account['acct']}\n\n"
            f"{self.account['followers_count']} Followers \n\n"
            f"{shorten(self.parsed_bio, width=80)}\n\n"
            f"{self.relation_note1}\n"
            f"{self.relation_note2}"
        )
        with Container(classes="screen_container"):
            yield Label(user_label, classes='screen_label')
            with Horizontal(classes='screen_buttonbar'):
                yield SimpleButton(
                    'Follow',
                    id='user_follow_button',
                    classes='screen_button',
                    disabled=self.disable_follow
                )
                yield SimpleButton(
                    'Go to Profile',
                    id='go_to_profile_button',
                    classes='screen_button',
                )             

    def on_mount(self):

        self.follow_button = self.query_one('#user_follow_button')
        self.profile_button = self.query_one('#go_to_profile_button')

        if self.relation['following']:
            self.follow_button.update('Unfollow')
        if self.disable_follow:
            self.follow_button.visible = False
    
    def on_click(self):
        self.dismiss()

    @on(SimpleButton.Pressed, selector='#user_follow_button')
    def follow_user(self):
        self.post_message(UserPopupMessage('follow', self.account, self.relation))
        self.dismiss()

        # NOTE: Message is handled in the main app.

    @on(SimpleButton.Pressed, selector='#go_to_profile_button')
    def go_to_profile(self):
        self.post_message(UserPopupMessage('profile', self.account, self.relation))
        self.dismiss()    
