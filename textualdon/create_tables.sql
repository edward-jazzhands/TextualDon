CREATE TABLE app_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_url TEXT NOT NULL,
    client_id TEXT NOT NULL,
    client_secret TEXT NOT NULL
) STRICT;

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    instance_url TEXT NOT NULL,
    username TEXT NOT NULL,
    display_name TEXT NOT NULL,
    access_token TEXT NOT NULL
) STRICT;

CREATE TABLE settings (
    name TEXT PRIMARY KEY NOT NULL,
    value TEXT NOT NULL
) STRICT;

INSERT INTO settings (name, value) VALUES
('first_launch', 'True'),
('current_theme', 'gruvbox'),
('last_logged_in', '0'),
('auto_login', 'True'),
('auto_load', 'False'),
('show_on_startup', 'login_page'),
('show_images', 'True'),
('link_behavior', '0'),
('copypaste_engine', '0'),
('hatching', 'none'),
('warning_checkbox_wsl', 'False'),
('warning_checkbox_first', 'False'),
('show_welcome_message', 'True'),
('callback_port', '0'),
('view_json_active', 'False');


