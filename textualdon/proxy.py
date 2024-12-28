from mastodon import Mastodon

from rich.text import Text
from textual import work
from textual.app import App
from textual.dom import DOMNode

from textualdon.error_handler import SafeModeError


class MastodonProxy(DOMNode):
    """ A proxy class for the Mastodon API wrapper. Makes the API async.
    Runs all API calls in a worker."""

    def __init__(self, mastodon_instance: Mastodon):
        self.mastodon = mastodon_instance
        # self.mastodon.session.
        # self.app = app
        self.api_runner = APIRunner()
        print(f"Proxy class initialized for Mastodon object: {type(self.mastodon)}")
    
    def __getattr__(self, name):
        print(f"Proxy class __getattr__ was called for {name}")

        if self.app.safe_mode:
            def no_op(*args, **kwargs):     # this swallows the call and does nothing.
                with self.app.capture_exceptions():
                    raise SafeModeError("Safe Mode is enabled.")
            return no_op
        
        try:
            attribute = getattr(self.mastodon, name)
        except Exception as e:
            raise e
        
        if callable(attribute):

            async def wrapped_method(*args, **kwargs):
                try:
                    worker = self.api_runner.run_api_call(attribute, *args, **kwargs)
                    await worker.wait()
                except Exception as e:
                    self.app.log.error(Text("Mastodon API Worker encountered an error", style="red"))
                    raise e
                else:
                    self.app.log(Text("Mastodon API Worker completed successfully", style="green"))
                    return worker.result

            return wrapped_method
        else:
            return attribute    # If it's not callable, return the attribute directly

class APIRunner(DOMNode):

    @work(thread=True, exit_on_error=False, group="api_call", exclusive=True)    
    async def run_api_call(self, attr, *args, **kwargs):

        print(f"Running API call: {attr} with args: {args}, kwargs: {kwargs}")
        try:
            return attr(*args, **kwargs)
        except Exception as e:
            raise e

        # NOTE: This does not handle any errors here because we want the Proxy class
        # to behave exactly like the normal Mastodon class. All errors are simply raised,
        # and handled in the function where the API call is made.
