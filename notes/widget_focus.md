# Toot Widget Focus
--------------------

The app is designed so that individual buttons (SimpleButton) cannot be focused, 
unless the focus ability is specifically turned on. There's more buttons that
can't focus than can, so it defaults to off.
The TootWidget itself is what is allowed to be focused. When the widget is focused,
it will enter the binding namespace and show you the keyboard controls for that toot.

Buttons don't need to be focusable to be able to click them. This system creates 
buttons which can be clicked, but cannot be cycled through with the focus 
(Tab/Shift+Tab) button. Thus, the user can only focus entire toots, which is much faster
than trying to cycle through all the individual buttons.