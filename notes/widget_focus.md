# Widget Focus
--------------------

The app is designed so many of the SimpleButtons cannot be focused.
For example, most of the widgets are desinged so the widget *itself* is focusable,
while the buttons inside the widget are not.

Buttons don't need to be focusable to be able to click them. This system creates 
buttons which can be clicked, but cannot be cycled through with the focus 
(Tab/Shift+Tab) button. Thus, the user can only focus entire toots, which is much faster
than trying to cycle through all the individual buttons.

The widgets themselves will have the bindings needed when that widget is highlighted.
The highlighted widget will be bordered so its obvious to the user.