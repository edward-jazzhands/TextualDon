#!/bin/bash

# Use `make tmux` to set permissions and run this script.

# This script is designed for a terminal that is maximized on a wide screen.
# It will, with a single command:
# - starts a new tmux session
# - splits the window horizontally (left and right panes)
# - adjusts the width of the panes to be roughly 2/3 and 1/3 of the screen
# - activates the python environment in both panes
# - runs the textual dev console on the right(small) side
# - then enters 'make run-dev' on the left(large) side, without pressing enter
# - finally it focuses on the left pane and attaches to the session

# Start a new tmux session named "textualdon"
tmux new-session -d -s textualdon     # -d is for detached mode, -s is for session name 'textualdon'

# Rename the first window and split horizontally
tmux rename-window -t textualdon:0 'Main'
tmux split-window -h     # -h splits the window horizontally

tmux resize-pane -t textualdon:0.1 -x 17   # puts it roughly 1/3 of screen

tmux send-keys -t textualdon:0.0 'make activate' C-m     # C-m is for `enter`
tmux send-keys -t textualdon:0.1 'make activate' C-m     # -t is for target window

# sleep is necessary to make it wait for the virtualenv to activate
# could not find a way to make it wait properly
sleep 2                 # might need to adjust this time for your system
tmux send-keys -t textualdon:0.1 'make console' C-m
tmux send-keys -t textualdon:0.0 'make run-dev' C-m

# Select left pane and attach to the session
tmux select-pane -t textualdon:0.0
tmux attach-session -t textualdon
