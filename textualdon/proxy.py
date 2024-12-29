from mastodon import Mastodon

from rich.text import Text
from textual.worker import Worker
from textual.dom import DOMNode

from textualdon.error_handler import SafeModeError


class MastodonProxy(DOMNode):
    """ A proxy class for the Mastodon API wrapper. Makes the API async.
    Runs all API calls in a worker."""

    def __init__(self, mastodon_instance: Mastodon):
        self.mastodon = mastodon_instance
        print(f"Proxy class initialized for Mastodon object: {type(self.mastodon)}")
    
    def check_safe_mode(self):

        if self.app.safe_mode:
            with self.app.capture_exceptions():
                raise SafeModeError("Safe Mode is enabled.")

    async def wrapped_method(self, attribute, *args, **kwargs):

        self.check_safe_mode()
        try:
            worker:Worker = self.app.run_api_call(attribute, *args, **kwargs)
            await worker.wait()
        except Exception as e:
            self.log.error(Text(f"Error in API call: {e}", style="bold red"))
            raise e
        else:
            return worker.result
        finally:
            self.log.debug(f"wrapped_method completed with type: {type(worker.result)}")


    # NOTE: I much would have preferred to use __getattr__ here but something about it
    # just doesn't work. It seems to make Textual upset. So had to resort to manual
    # bridge methods for every API call.      
        
    async def app_verify_credentials(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'app_verify_credentials')
        return await self.wrapped_method(attribute, *args, **kwargs)

    async def account_verify_credentials(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'account_verify_credentials')
        return await self.wrapped_method(attribute, *args, **kwargs)        

    async def timeline(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'timeline')
        return await self.wrapped_method(attribute, *args, **kwargs)

    async def trending_tags(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'trending_tags')
        return await self.wrapped_method(attribute, *args, **kwargs)

    async def trending_links(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'trending_links')
        return await self.wrapped_method(attribute, *args, **kwargs)

    async def trending_statuses(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'trending_statuses')
        return await self.wrapped_method(attribute, *args, **kwargs)

    async def bookmarks(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'bookmarks')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def favorites(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'favorites')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def status(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'status')
        return await self.wrapped_method(attribute, *args, **kwargs)

    async def status_context(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'status_context')
        return await self.wrapped_method(attribute, *args, **kwargs)

    async def status_update(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'status_update')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def status_reply(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'status_reply')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def status_post(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'status_post')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def log_in(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'log_in')
        return await self.wrapped_method(attribute, *args, **kwargs)

    async def auth_request_url(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'auth_request_url')
        return await self.wrapped_method(attribute, *args, **kwargs)

    async def account_relationships(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'account_relationships')
        return await self.wrapped_method(attribute, *args, **kwargs)

    async def revoke_access_token(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'revoke_access_token')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def account_follow(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'account_follow')
        return await self.wrapped_method(attribute, *args, **kwargs)

    async def account_unfollow(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'account_unfollow')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def account_block(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'account_block')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def account_unblock(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'account_unblock')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def account_mute(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'account_mute')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def account_unmute(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'account_unmute')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def status_pin(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'status_pin')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def status_unpin(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'status_unpin')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def status_mute(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'status_mute')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def status_unmute(self, *args, **kwargs):    
        attribute = getattr(self.mastodon, 'status_unmute')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def status_delete(self, *args, **kwargs):    
        attribute = getattr(self.mastodon, 'status_delete')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def status_unblog(self, *args, **kwargs):    
        attribute = getattr(self.mastodon, 'status_unblog')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def status_reblog(self, *args, **kwargs):    
        attribute = getattr(self.mastodon, 'status_reblog')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def status_favourite(self, *args, **kwargs):
        attribute = getattr(self.mastodon, 'status_favourite')
        return await self.wrapped_method(attribute, *args, **kwargs)

    async def status_unfavourite(self, *args, **kwargs):    
        attribute = getattr(self.mastodon, 'status_unfavourite')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def status_bookmark(self, *args, **kwargs):    
        attribute = getattr(self.mastodon, 'status_bookmark')
        return await self.wrapped_method(attribute, *args, **kwargs)
    
    async def status_unbookmark(self, *args, **kwargs):    
        attribute = getattr(self.mastodon, 'status_unbookmark')
        return await self.wrapped_method(attribute, *args, **kwargs)


