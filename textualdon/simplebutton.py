# Standard library imports
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.events import Click

from rich.console import RenderableType
from rich.text import Text #, TextType

from textual.widgets import Static
from textual.reactive import reactive
from textual.message import Message
from textual.binding import Binding



class SimpleButton(Static):
    """A simple button widget. Note that this does not inherit from Button, but from Static.

    This is designed to copy the basic functionality of the Textual button, but in a
    more minimalistic way that changes some of the core functionality and appearance.

    It can be any size (down to 1x1). It copies the `Pressed` event from normal buttons.
    It also renders itself using the rich Text class, so you can set
    the overflow and no_wrap properties.

    By default, no_wrap is `True` and overflow is `crop`. This meas the button
    text will not wrap and will be cropped if it is too long. You can change this by using
    the 'no_wrap' and 'overflow' arguments in the constructor.

    It also contains the `HoverEnter` and `HoverLeave` events, which are triggered when the
    mouse enters or leaves the button. These provide convenient messages for hovering over the button,
    so that the hover event can be handled by the parent widget.

    EXAMPLE USAGE:
    - yield button:
    ```
    yield SimpleButton("your_button_text", id="sample_id")
    ```
    - In some cases you'll want word wrap enabled, without overflow:
    ```
    yield SimpleButton("your_button_text", no_wrap=None, overflow=None)
    ```
    - message handler:
    ```
    @on(SimpleButton.Pressed)   
    def on_button_pressed(self, message: SimpleButton.Pressed) -> None:   
        print("Button was pressed!")
    ```
    """

    BINDINGS = [Binding("enter", "press", "Press button", show=False)]

    ### MESSAGES ###

    class Pressed(Message):
        """Event sent when a `SimpleButton` is pressed.   

        Can be handled using `on_simple_button_pressed` (in a subclass of
        [`Button`][textual.widgets.Button] or in a parent widget in the DOM.)   
        OR   
        by using @on(SimpleButton.Pressed)"""

        def __init__(self, button: SimpleButton) -> None:
            super().__init__()

            self.button: SimpleButton = button
            """The button that was pressed.   
            Note that it is a SimpleButton object.   
            You can access the button's properties:
            - button.id
            - button.name
            - button.index   (if you set an index)
            - etc"""

        @property
        def control(self) -> SimpleButton:
            """This is required to be able to use the 'selector' property
            when using the message handler."""

            return self.button
        
    class HoverEnter(Message):
        def __init__(self, button: SimpleButton) -> None:
            self.button: SimpleButton = button
            """The button that was entered (hovered over)."""
            super().__init__()

        @property
        def control(self) -> SimpleButton:
            return self.button

    class HoverLeave(Message):
        def __init__(self, button: SimpleButton) -> None:
            self.button: SimpleButton = button
            """The button that was left."""
            super().__init__()

        @property
        def control(self) -> SimpleButton:
            return self.button

    ### END MESSAGES ###
    ###  SimpeButton MAIN  ###

    def __init__(
            self,
            *args,
            justify:  str | None = None,
            overflow: str | None = "crop",
            no_wrap: bool | None = True,
            index:    int | None = None,
            **kwargs
        ) -> None:
        """
        Custom constructor for SimpleButton. Adds 'justify', 'overflow', and 'no_wrap' arguments for
        the Rich Text class. args and kwargs are passed to the Static constructor.

        Args:
            renderable: A Rich renderable, or string containing console markup.
            justify (str, optional): Justify method: "left", "center", "full", "right". Defaults to None.
            overflow (str, optional): Overflow method: "crop", "fold", "ellipsis". Defaults to None.
            no_wrap (bool, optional): Disable text wrapping, or None for default. Defaults to None.
            index (int, optional): Allows setting index for the button. This is useful if the button
                is part of a list of buttons. Defaults to None.
            expand: Expand content if required to fill container.
            shrink: Shrink content if required to fill container.
            markup: True if markup should be parsed and rendered.
            name: Name of widget.
            id: ID of Widget.
            classes: Space separated list of class names.
            disabled: Whether the static is disabled or not."""

        super().__init__(*args, **kwargs)
        self.can_focus = True
        self.no_wrap = no_wrap
        self.overflow = overflow
        self.justify = justify
        self.index = index

    def render(self) -> RenderableType:
        """Pass the options from the constructor into the Rich Text class."""
        return Text(
            text=str(self.renderable),
            justify=self.justify,
            no_wrap=self.no_wrap,
            overflow=self.overflow
            )
    
    def watch_mouse_hover(self, value: bool) -> None:
        """OVERRIDE: Update from CSS if mouse over state changes.
        Textual addition: posts HoverEnter / HoverLeave messages."""

        if self._has_hover_style:
            self._update_styles()
        if value:
            self.post_message(self.HoverEnter(self))
        else:
            self.post_message(self.HoverLeave(self))
        
    def on_click(self, event: Click) -> None:
        """Called when the button is clicked. Posts a message 'Pressed'.
        Use the message handler to handle the event:   
        ```
        @on(SimpleButton.Pressed)   
        def on_button_pressed(self, message: SimpleButton.Pressed) -> None:   
            print("Button was pressed!")
        ``` """
        self.post_message(self.Pressed(self))

    def action_press(self) -> None:
        self.post_message(self.Pressed(self))