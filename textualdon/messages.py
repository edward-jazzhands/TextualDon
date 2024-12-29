from textual.message import Message
from textual.widget import Widget

class UpdateBannerMessage(Message):
    """Message to update the banner with a new message.
    ```
    from textualdon.messages import UpdateBannerMessage
    self.post_message(UpdateBannerMessage(f"Hello, {user}!"))
    ``` """
    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = str(message)

class SuperNotify(Message):
    """Triggers a notification and updates the banner at the same time."""
    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = str(message)

class LoginStatus(Message):
    """Message to update the login status in the Oauth widget.
    ```
    from textualdon.messages import LoginStatus
    self.post_message(LoginStatus("Logged in successfully"))
    ``` """
    def __init__(
        self, 
        statusbar: str,
        loginpage_message: str,
        instance_url: str = None
    ) -> None:
        super().__init__()
        self.statusbar = statusbar
        self.loginpage_message = loginpage_message
        self.instance_url = instance_url

class RefreshCurrentPage(Message):
    """Message to refresh the current page.
    ```
    from textualdon.messages import RefreshCurrentPage
    self.post_message(RefreshCurrentPage())
    ``` """
    pass

class SwitchMainContent(Message):
    """Message to switch the main content.
    ```
    from textualdon.messages import SwitchMainContent
    self.post_message(SwitchMainContent('home'))
    ``` """
    def __init__(self, content: str) -> None:
        super().__init__()
        self.content = content

class ExamineToot(Message):
    """Message to examine a toot.
    ```
    from textualdon.messages import ExamineToot
    self.post_message(ExamineToot(toot_id))
    ``` """
    def __init__(self, toot_id: int) -> None:
        super().__init__()
        self.toot_id = toot_id

class LoginComplete(Message):
    """Message to signal that the login process is complete."""
    pass

class UserPopupMessage(Message):
    """ ``` \n
    message must be either 'follow' or 'profile'

    from textualdon.messages import UserPopupMessage
    self.post_message(UserPopupMessage('follow', self.account, self.relation))
    ``` """
    def __init__(self, message: str, account_dict: dict, relation_dict: dict) -> None:
        super().__init__()
        self.message = message
        self.account = account_dict
        self.relation = relation_dict

class OpenCallbackScreen(Message):
    def __init__(self, auth_url: str) -> None:
        self.auth_url = auth_url
        super().__init__()

class CallbackSuccess(Message):
    """ ``` \n
    from textualdon.messages import CallbackSuccess
    self.post_message(CallbackSuccess())
    ``` """
    pass

class CallbackCancel(Message):
    """ ``` \n
    from textualdon.messages import CallbackCancel
    self.post_message(CallbackCancel())
    ``` """
    pass

class ScrollToWidget(Message):
    def __init__(self, widget: Widget) -> None:
        super().__init__()
        self.widget = widget

class EnableSafeMode(Message):
    pass

class TriggerRandomError(Message):
    pass

class ExceptionMessage(Message):
    def __init__(self, exception: Exception) -> None:
        super().__init__()
        self.exception = exception

class DeleteLogs(Message):
    pass

class OpenRoadmap(Message):
    pass