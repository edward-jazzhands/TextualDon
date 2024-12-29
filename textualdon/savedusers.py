# Standard library imports
from __future__ import annotations
from typing import TYPE_CHECKING, cast, List, Tuple

if TYPE_CHECKING:
    from textual.app import ComposeResult 

# Third party imports
from mastodon import Mastodon

# Textual imports
from textual import on, work
from textual.worker import Worker, WorkerState
from textual.binding import Binding
from textual.message import Message
from textual.containers import Container, Horizontal
from textual.widget import Widget
from textual.widgets import Static
# from textual.reactive import reactive
from rich.text import Text
from rich.emoji import Emoji

# TextualDon imports
from textualdon.simplebutton import SimpleButton
from textualdon.messages import (
    SuperNotify,
    LoginStatus,
)
from textualdon.sql import SQLite    # only for casting
from textualdon.screens import ConfirmationScreen


class UserEntry(Horizontal):

    BINDINGS = [
        Binding(key="delete", action="delete_user", description="Delete highlighted user", key_display="Delete"),
    ]
    class UserSelected(Message):
        def __init__(self, user: UserEntry) -> None:
            super().__init__()
            self.user_entry = user

    class UserDeleted(Message):
        def __init__(self, user: UserEntry) -> None:
            super().__init__()
            self.user_entry = user

    def __init__(
            self,
            user_id: int,
            instance_url: str,
            username: str,
            display_name: str,
            access_token: str,
            *args,
            **kwargs
        ) -> None:
        self.user_id = user_id
        self.instance_url = instance_url
        self.username = username
        self.display_name = display_name
        self.access_token = access_token
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:

        yield SimpleButton(
            f"{self.display_name} (@{self.username}) \n{self.instance_url}",
            # no_wrap=False,
            id="user_select_button"
        )
        yield SimpleButton(f" Delete {Emoji('wastebasket')} ", id="user_delete_button")

    def on_mount(self):
        self.user_select_button = self.query_one("#user_select_button")
        self.user_delete_button = self.query_one("#user_delete_button")
        self.user_delete_button.can_focus = False

        self.log.debug(
            "UserEntry mounted with: \n"
            f"User ID: {self.user_id} \n"
            f"Instance URL: {self.instance_url} \n"
            f"Username: {self.username} \n"
            f"Display Name: {self.display_name} \n"
            f"Access Token: {self.access_token}"
        )

    @on(SimpleButton.Pressed, selector="#user_select_button")
    def user_selected(self) -> None:
        self.log.debug("Messaging function: user_selected in UserEntry class (SimpleButton.Pressed)")
        self.post_message(self.UserSelected(self))

    @on(SimpleButton.Pressed, selector="#user_delete_button")
    def delete_user(self) -> None:
        self.log("Messaging function: delete_user in UserEntry class (SimpleButton.Pressed)")
        self.post_message(self.UserDeleted(self))

    def action_delete_user(self) -> None:
        self.delete_user()


class SavedUsersManager(Widget):
    """Composed onto the Oauth widget to manage saved users. \n
    DOM id = 'saved_users_manager' """

    users_list = []

    class TriggerLogin(Message):
        """Message to trigger the login_stage5 function."""
        def __init__(self, instance_url: str) -> None:
            super().__init__()
            self.instance_url = instance_url


    def compose(self) -> ComposeResult:

        self.db = cast(SQLite, self.app.sqlite)

        with Container(id="users_container"):
            yield Static("No saved logins", classes="users_placeholder")

    def on_mount(self):

        self.users_container = cast(Container, self.query_one("#users_container"))
        self.users_container.border_title = "Saved Logins" 
            
    async def start_process(self):
        """This is activated by the on_mount method in Oauth widget, as well as the 
        user_deleted function in this class to refresh the list."""

        with self.app.capture_exceptions():
            users_list = await self.get_saved_logins()
        if self.app.error:
            return
        else:
            self.log.debug("Saved users list successfully retrieved.")
            if users_list:
                self.users_list = users_list
                await self.mount_saved(users_list)

    async def get_saved_logins(self) -> List[UserEntry]:

        self.log("Starting get_saved_logins in OAuthWidget")

        query = "SELECT * FROM users"
        users = self.db.fetchall(query)     #~ This is the point we query the database to get all the user data.

        users_list = []

        if users:
            self.log(Text(f"Users found in database: {len(users_list)}", style="green"))
            for user in users:
                user_id = user[0]
                instance_url = user[1]
                username = user[2]
                display_name = user[3]
                access_token = user[4]

                user_entry = UserEntry(user_id, instance_url, username, display_name, access_token)
                users_list.append(user_entry)
        return users_list

    async def mount_saved(self, users_list: List[UserEntry]) -> None:

        await self.users_container.remove_children()
        self.users_container.mount_all(users_list)
        self.users_container.refresh(layout=True)

    def check_auto_login(self) -> None:
        """This is the trigger function used by App. This is run at the end of App's on_mount function."""
        if self.app.safe_mode:
            return

        row1 = self.db.fetchone("SELECT value FROM settings WHERE name = ?", ("last_logged_in",))
        last_logged_in: int = int(row1[0])

        row2 = self.db.fetchone("SELECT value FROM settings WHERE name = ?", ("auto_login",))
        autologin_value: bool = (row2[0] == "True")

        if autologin_value and self.users_list:
            for user in self.users_list:
                if user.user_id == last_logged_in:
                    self.post_message(user.UserSelected(user))

    @work(thread=True, group="create_mastodon_instance", exit_on_error=False)
    def create_mastodon_instance(
            self, 
            access_token:str, 
            instance_url:str, 
            app_data:Tuple[str, str]
        ) -> Mastodon:
        """Used by user_selected and user_deleted functions to create a Mastodon object."""

        try:        
            mastodon = Mastodon(                #~ Creates Mastodon instance here.
                client_id = app_data[2],
                client_secret = app_data[3],
                access_token = access_token,
                api_base_url = instance_url,
                version_check_mode='none',
                request_timeout=3
            )          
        except Exception as e:
            e.add_note("SavedUsersManager.create_mastodon_instance failed to create Mastodon object.")
            raise e
        else:
            return mastodon

    @on(UserEntry.UserSelected)
    async def user_selected(self, event: UserEntry.UserSelected) -> None:

        if self.app.safe_mode:
            self.notify("Please disable safe mode first.", timeout=7)
            return        

        access_token: str = event.user_entry.access_token
        instance_url: str = event.user_entry.instance_url

        app_data = self.db.fetchone("SELECT * FROM app_data WHERE instance_url = ?", (instance_url,))
        
        self.log.debug(
            "Starting user_selected in OAuthWidget.\n"
            f"app_data: \n{app_data} \n"
            f"access_token: {access_token} \n"
            f"instance_url: {instance_url}"
        )

        with self.app.capture_exceptions():
            worker = self.create_mastodon_instance(access_token, instance_url, app_data)
            await worker.wait()
            mastodon = worker.result
        if not self.app.error:
            self.app.attach_mastodon(mastodon)                      # we're already logged in, 
            self.post_message(self.TriggerLogin(instance_url))      # no need to pass in access token      

    @on(UserEntry.UserDeleted)
    def user_deleted_confirm(self, event: UserEntry.UserDeleted) -> None:
        if self.app.safe_mode:
            self.notify("Please disable safe mode first.", timeout=7)
            return

        self.app.push_screen(ConfirmationScreen(forward=event, classes="modal_screen"), self.user_deleted)

    async def user_deleted(self, event: UserEntry.UserDeleted) -> None:
        """Triggered by the callback from the ConfirmationScreen."""

        access_token = event.user_entry.access_token
        instance_url = event.user_entry.instance_url
        username = event.user_entry.username
        user_id = event.user_entry.user_id

        self.log.debug(
            "Starting user_deleted function in OAuthWidget. Parameters: \n"
            f"access_token: {access_token} \n"
            f"instance_url: {instance_url} \n"
            f"username: {username} \n"
            f"user_id: {user_id}"
        )

        # If deleting the logged in user, log out first. It's easier to just make it
        # re-validate, because it simplifies the logic.

        # NOTE: self.app.logged_in_user_id is set in login_stage5 in Oauth widget.

        if self.app.logged_in_user_id:
            if user_id == self.app.logged_in_user_id:   
                self.app.mastodon = None               
                self.app.logged_in_user_id = None
                self.post_message(LoginStatus(
                    statusbar="Status: Offline",
                    loginpage_message="Logged out."
                    ))
                self.post_message(SuperNotify("Logged out."))

        app_data = self.db.fetchone("SELECT * FROM app_data WHERE instance_url = ?", (instance_url,))

        worker = self.create_mastodon_instance(access_token, instance_url, app_data)
        await worker.wait()
        mastodon = worker.result
        if not self.app.error:   
            with self.app.capture_exceptions(): 
                mastodon.revoke_access_token()
            if self.app.error:
                return

        self.log(f"Mastodon access token revoked for {username} on {instance_url}")

        self.db.delete_one('users', 'id', user_id)
        await self.start_process()
        self.post_message(SuperNotify(f"Deleted user {username} on {instance_url}"))

    ###~ Worker Debug stuff ~###

    @on(Worker.StateChanged)
    def worker_state_changed(self, event: Worker.StateChanged) -> None:

        if event.state == WorkerState.SUCCESS:
            self.log(Text(f"Worker {event.worker.name} completed successfully", style="green"))
        elif event.state == WorkerState.ERROR:
            self.log.error(Text(f"Worker {event.worker.name} encountered an error", style="red"))
        elif event.state == WorkerState.CANCELLED:
            self.log(Text(f"Worker {event.worker.name} was cancelled", style="yellow"))

