# Standard library imports
from __future__ import annotations
from typing import TYPE_CHECKING, cast
from queue import Queue
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import time
import re

if TYPE_CHECKING:
    from textual.app import ComposeResult 

# Third party imports
from mastodon import Mastodon
from rich.text import Text

# Textual imports
from textual import on, work
from textual.worker import Worker, WorkerCancelled, WorkerState
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Static
from textual.widgets import Input

# TextualDon imports
from textualdon.messages import (
    SuperNotify,
    LoginStatus,
    LoginComplete,
    CallbackSuccess,
)
from textualdon.simplebutton import SimpleButton
from textualdon.sql import SQLite    # only for casting
from textualdon.html_templates import html_success_msg, html_failure_msg
from textualdon.screens import CallbackScreen
from textualdon.savedusers import SavedUsersManager


class OAuthInput(Input):

    BINDINGS = [
        Binding("enter", "submit", "Submit", show=True)
    ]

    # @on(OAuthInput.Submitted)
    # async def submit_input(self, event: OAuthInput.Submitted) -> None:
    #     """This is here to allow submitting with the enter button. Custom binding on OAuthInput."""

    #     self.log.debug("Trigger function: submit_input in oauth.py")
    #     await self.oauth_flow()

class OAuthWidget(Container):


    client_id = None
    client_secret = None
    queue = Queue()
    callback_active = False

    def compose(self) -> ComposeResult:

        self.db = cast(SQLite, self.app.sqlite)

        self.callback_wait_time:    int = self.app.config.getint('MAIN', 'callback_wait_time')
        self.redirect_uri_template: str = self.app.config.get('MAIN', 'redirect_uri')

        with Horizontal(id="login_form"):
            yield OAuthInput(placeholder="mastodon.social", id="instance_url")
            yield SimpleButton("Connect", id="connect_button")
        yield SavedUsersManager(id="saved_users_manager")
        yield Static("Enter an instance URL or choose from saved logins.", id="login_status")

    async def on_mount(self) -> None:

        self.saved_users_manager = cast(SavedUsersManager, self.query_one(SavedUsersManager))
        self.login_status = cast(Static, self.query_one("#login_status"))
        self.login_input  = cast(Input, self.query_one("#instance_url"))
        self.query_one("#connect_button").can_focus = False

        # NOTE: app data only needs to be created once per Mastodon server instance.

        query = "SELECT * FROM app_data"
        app_data = self.db.fetchall(query)
        self.log.debug(f"Existing app data: {app_data}")

        await self.saved_users_manager.start_process()

    @on(SavedUsersManager.TriggerLogin)
    async def trigger_login(self, event: SavedUsersManager.TriggerLogin) -> None:
        """This is triggered by the SavedUsersManager widget when a user is selected."""

        self.log.debug("Trigger function: trigger_login in OAuthWidget")
        with self.app.capture_exceptions():
            await self.login_stage5(event.instance_url)

    # @on(OAuthInput.Submitted)
    # async def submit_input(self, event: OAuthInput.Submitted) -> None:

    #     self.log.debug("Trigger function: submit_input in oauth.py")
    #     await self.oauth_flow()

    ###~ Oauth Flow ~###

    @on(OAuthInput.Submitted) #! TEST THIS
    @on(SimpleButton.Pressed, '#connect_button')
    async def oauth_flow(self) -> None:

        if self.app.safe_mode:
            self.notify("Please disable safe mode first.", timeout=7)
            return

        stage1_passed = False
        stage2_passed = False
        stage3_passed = False
        stage4_passed = False

        stage1_result = None
        stage2_result = None
        stage3_result = None
        stage4_result = None

        instance_url:str = self.login_input.value
        self.login_input.value = ""   # clear the input field

        validated = True if re.match(r'\w+\.\w+', instance_url) else False
        if not validated:
            self.notify("Please enter a valid URL.")
            return

        port:str = self.db.fetchone("SELECT value FROM settings WHERE name = ?", ('callback_port',))[0]
        redirect_uri = self.redirect_uri_template.format(port=port)

        # check if app credentials are already saved for this instance
        app_data = self.db.fetchone("SELECT * FROM app_data WHERE instance_url = ?", (instance_url,))
        self.log.debug(f"app_data: \n{app_data}")
        
        if app_data:
            client_id = app_data[2]
            client_secret = app_data[3]
            self.log("App credentials found. Skipping stage 1.")
            stage1_passed = True

        else:
            self.log("Registering a new app wih the instance.")  

            with self.app.capture_exceptions():
                stage1: Worker = self.login_stage1(instance_url, redirect_uri)
                await stage1.wait()
                stage1_result: tuple[str, str] = stage1.result
            if self.app.error:
                return
            else:
                # Stage 1 result is a tuple of client ID:str and client secret:str
                self.log.debug(f"STAGE 1 RESULT: \n {stage1_result}")
                with self.app.capture_exceptions():
                    stage1_result[0].strip()
                    stage1_result[1].strip()
                if self.app.error:
                    return
                else:
                    stage1_passed = True
                    client_id, client_secret = stage1_result
                    self.db.insert_one(
                        'app_data',
                        ['instance_url', 'client_id', 'client_secret'],
                        [instance_url, client_id, client_secret]
                    )

        if stage1_passed is True:
            with self.app.capture_exceptions():                      
                stage2: Worker = self.login_stage2(client_id, client_secret, instance_url, redirect_uri)
                await stage2.wait()
                stage2_result: tuple[Mastodon, str] = stage2.result
            if self.app.error:
                return
            else:
                # Stage 2 result is a tuple of Mastodon object and auth URL
                self.log.debug(f"STAGE 2 RESULT: \n {stage2_result}")
                with self.app.capture_exceptions():
                    self.log(stage2_result[0].client_id)    # checks if we can access an attribute of the Mastodon object
                    self.log(stage2_result[1].strip())
                if self.app.error:
                    return
                else:
                    self.app.attach_mastodon(stage2_result[0])    #~ This is where the mastodon object becomes 
                    stage2_passed = True                          #~ globally accessible to the app.

        if stage2_passed is True:
            with self.app.capture_exceptions():    
                stage3_result = await self.login_stage3(stage2_result[1], int(port))
            if self.app.error:
                return
            else:
                # Stage 3 result is the temporary auth code from the callback server
                self.log.debug(f"STAGE 3 RESULT: \n {stage3_result}")
                with self.app.capture_exceptions():
                    stage3_result.strip()
                if self.app.error:
                    return
                else:
                    stage3_passed = True                 

        if stage3_passed is True:   
            self.post_message(CallbackSuccess())                      
            with self.app.capture_exceptions():    
                stage4_result: str = await self.login_stage4(stage3_result, redirect_uri)
            if self.app.error:
                return
            else:
                # Stage 4 result is the access token
                self.log.debug(f"STAGE 4 RESULT: \n {stage4_result}")
                with self.app.capture_exceptions():
                    stage4_result.strip()
                if self.app.error:
                    return
                else:
                    stage4_passed = True                 

        if stage4_passed is True:
            with self.app.capture_exceptions():
                await self.login_stage5(instance_url, access_token=stage4_result)

    # Stages 1 and 2 are both in the group 'login', and exclusive=True.
    # it probably doesn't matter much but it might help prevent it being
    # run twice at the same time for some reason.

    @work(thread=True, exclusive=True, exit_on_error=False, group="login")
    def login_stage1(self, instance_url: str, redirect_uri: str) -> tuple[str, str]:
        """Stage 1: Registers the app with the Mastodon instance.   
        This should only be run once and it will save the app profile to a file.
        
        Returns:
            tuple[str, str]: The client ID and client secret."""

        self.log("Starting Worker: Login Stage 1")

        if instance_url is None:
            raise ValueError("Instance URL not provided.")  # this shouldn't ever happen

        try:
            client_id, client_secret = Mastodon.create_app(
                "TextualDon",
                redirect_uris = redirect_uri,
                api_base_url = instance_url,
            )
        except Exception as e:
            raise e
        
        client_id: str
        client_secret: str
        return client_id, client_secret         # Passed into stage 2

    @work(thread=True, exclusive=True, exit_on_error=False, group="login")
    def login_stage2(
            self,
            client_id: str,
            client_secret: str,
            instance_url: str,
            redirect_uri: str
        ) -> tuple[Mastodon, str]:
        """Stage 2: Submits app credentials to the Mastodon instance.   
        Requests an auth URL from the instance, opens the browser.  
        
        Returns:
            tuple[Mastodon, str]: The Mastodon object and the auth url."""
        
        self.log("Starting Worker: Login Stage 2")
        self.log.debug(f"Client ID: {client_id} | Client Secret: {client_secret}")

        if not client_id or not client_secret:
            raise ValueError("Client ID or Client Secret not found.")
    
        try:
            mastodon = Mastodon(              #~ Here we create the Mastodon object that will be used,
                client_id = client_id,          # But only if its the first time logging in to this server.
                client_secret= client_secret,       # Following times are handled in savedusers.py
                api_base_url = instance_url,
                version_check_mode='none',
                request_timeout=3
            )     
        except Exception as e:
            raise e                                       

        try:            #! TODO: I think this wants 'state' for idempotency
            auth_url = mastodon.auth_request_url(redirect_uris = redirect_uri)
        except Exception as e:
            raise e

        return mastodon, auth_url

    async def login_stage3(self, auth_url: str, port: int) -> str:

        self.log("Starting Worker: Login stage 3")

        await self.app.push_screen(CallbackScreen(auth_url, id="callback_screen", classes='modal_screen'))

        try:
            callback: Worker = self.run_callback_server(port)
            await callback.wait()
        except WorkerCancelled as e:
            raise e
        except Exception as e:
            raise e
        else:
            if isinstance(callback.result, str):
                return callback.result
            else:
                raise ValueError("Callback result is not a string.")
        finally:
            self.log(f"callback:  {callback}  |  callback.result:  {callback.result}")

    async def login_stage4(self, auth_code: str, redirect_uri: str) -> str:
        """Stage 4: Logs in with the auth code received from the callback server.
        
        Returns:
            str: The access token."""

        self.log("Starting Worker: Login Stage 4")
        if not auth_code:
            raise ValueError("No auth code received.")

        access_token = await self.app.mastodon.log_in(redirect_uri = f'{redirect_uri}', code=auth_code)

        if not isinstance(access_token, str):
            raise ConnectionError(f"Could not log in, recieved: {access_token}")

        return access_token

    async def login_stage5(self, instance_url: str, access_token: str | None = None) -> None:
        """Stage 5: Updates the UI and Database.

        THIS FUCTION IS CALLED BY:
        - OauthWidget.oauth_flow
        - OauthWidget.trigger_login

        Passing in an access token means its the first time logging in with that account.   
        
        Returns:
            str: The display name of the logged in user. """

        self.log("Starting Login Stage 5")


        app_cred = await self.app.mastodon.app_verify_credentials()
        account_cred = await self.app.mastodon.account_verify_credentials()

        if not isinstance(app_cred, dict) or not isinstance(account_cred, dict):
            raise ValueError("Could not verify credentials.")

        app_id = app_cred["id"]
        app_scopes = app_cred["scopes"]

        self.log(
            f"Mastodon object: {type(self.app.mastodon)} \n"
            f"Connected App ID: {app_id} | Scopes: {app_scopes}"
        )
        
        username = account_cred["username"]
        user_id = account_cred["id"]
        display_name = account_cred["display_name"]

        self.log(f"Logged in as {display_name} (@{username}) on {instance_url}")

        existing_user = self.db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
        if existing_user:
            self.log.debug(f"User already exists in the database: {existing_user}")
        else:
            self.log.debug(f"User not detected in db: {existing_user}")
            columns = ["id", "username", "display_name", "instance_url", "access_token"]
            values = [user_id, username, display_name, instance_url, access_token]
            self.db.insert_one('users', columns, values)

        # NOTE: Technically, the user_id is not unique across the entire Mastodon network.
        # But since this is a client-side app, we can assume it is unique for our purposes.
        # The probability of a user having the same ID number on two instances is astronomically low.

        self.post_message(SuperNotify(f"Logged in as {display_name} (@{username})"))
        self.post_message(LoginStatus(
            statusbar=username,
            instance_url=instance_url,
            loginpage_message=f"Logged in as {display_name} (@{username}) on {instance_url}",
        ))

        self.log(f"Logged in successfully to {username}, user ID: {user_id}")

        self.app.logged_in_user_id = user_id
        self.db.update_column('settings', 'value', user_id, 'name', 'last_logged_in')

        # Refresh the display name every time we use a saved log in.
        if access_token is None:
            self.db.update_column('users', 'display_name', display_name, 'id', user_id)

        await self.saved_users_manager.start_process()  # refresh the saved users list
        self.app.instance_url = instance_url            # make accessible at app level

        self.log(Text(f"Login Successful. \n {self.app.breaker_figlet}", style="green"))
        self.app.post_message(LoginComplete()) 

    ###~ Callback Server ~###

    @work(thread=True, exclusive=True, exit_on_error=False, group='callback')
    async def run_callback_server(self, port: int) -> str:

        self.log("Starting Worker: callback server.")

        server_address = ('', port)
        OAuthCallbackHandler.queue = self.queue          # dependency inject the queue
        httpd = HTTPServer(server_address, OAuthCallbackHandler)
        httpd.timeout = 5                       # Set a low timeout to periodically exit handle_request
        start_time = time.time()

        self.log.debug(f"Callback server address: {httpd.server_address}")

        self.callback_active = True # this is a flag we can modify in another method to stop the loop

        # this will time out every 5 seconds and restart. It makes it more reliable/responsive.
        try:
            while (time.time() - start_time) < self.callback_wait_time and self.callback_active:
                httpd.handle_request()  # Handles a single request or timeout
                if self.queue.qsize() > 0:
                    self.log.debug("Queue size > 0; exiting callback server.")
                    break
                self.log.debug("No OAuth callback yet; retrying...")
        except Exception as e:
            raise e
        finally:
            httpd.server_close()
            self.callback_active = False
            self.log.debug("Callback server closed.")

        if self.queue.qsize() > 0:
            return self.queue.get()

    def cancel_callback(self) -> None:

        cancelled = self.workers.cancel_node(self.query().node)
        self.callback_active = False   # required to make the loop exit after the worker is cancelled

        self.log.debug(Text("Cancelling callback server. \n"
                        f"Cancelled workers: {cancelled}", style="yellow"))
        

    ###~ Worker Debug stuff ~###

    @on(Worker.StateChanged)
    def worker_state_changed(self, event: Worker.StateChanged) -> None:

        self.log.debug(Text(
                f"Worker state: {event.state}\n"
                f"Worker.name: {event.worker.name}",
                style="cyan"
        ))

        if event.state == WorkerState.SUCCESS:
            self.log(Text(f"Worker {event.worker.name} completed successfully", style="green"))
        elif event.state == WorkerState.ERROR:
            self.log.error(Text(f"Worker {event.worker.name} encountered an error", style="red"))
        elif event.state == WorkerState.CANCELLED:
            self.log(Text(f"Worker {event.worker.name} was cancelled", style="yellow"))


#* Will be run in the thread with run_callback_server:
class OAuthCallbackHandler(BaseHTTPRequestHandler):

    queue = None

    def do_GET(self):
        parsed_url = urlparse(self.path)       
        params = parse_qs(parsed_url.query)
        
        if 'code' in params:       
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.queue.put(params['code'][0])
            
            message = html_success_msg
        else:
            self.send_response(400)
            self.end_headers()
            message = html_failure_msg

        self.wfile.write(message.encode('utf-8'))













