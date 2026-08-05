"""Configuration loader for Twitch API settings.

Loads timing, credentials, and endpoint configuration from config.yaml.
"""

import yaml
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.yaml')

_config_cache = None


def load_config():
    """Load configuration from YAML file.
    
    Returns:
        dict: Configuration dictionary with timing, credentials, and endpoints
    """
    global _config_cache
    
    if _config_cache is not None:
        return _config_cache
    
    if not os.path.exists(CONFIG_PATH):
        _config_cache = {
            'timing': {
                'refresh_interval': 7000,
                'retry_attempts': 3,
                'retry_delay': 2000
            },
            'credentials': {
                'username': 'default_user',
                'token': 'default_token'
            },
            'endpoints': {
                'stream_info': 'https://api.twitch.tv/helix/streams',
                'user_info': 'https://api.twitch.tv/helix/users'
            }
        }
        return _config_cache
    
    with open(CONFIG_PATH, 'r') as f:
        _config_cache = yaml.safe_load(f)
    
    return _config_cache


def get_refresh_interval():
    """Get the refresh interval in milliseconds.
    
    Returns:
        int: Refresh interval in milliseconds
    """
    return load_config()['timing']['refresh_interval']


def get_retry_attempts():
    """Get the number of retry attempts.
    
    Returns:
        int: Number of retry attempts
    """
    return load_config()['timing']['retry_attempts']


def get_retry_delay():
    """Get the retry delay in milliseconds.
    
    Returns:
        int: Retry delay in milliseconds
    """
    return load_config()['timing']['retry_delay']


def get_credentials():
    """Get API credentials.
    
    Returns:
        dict: Dictionary with username and token
    """
    return load_config()['credentials']


def get_endpoints():
    """Get API endpoints.
    
    Returns:
        dict: Dictionary with endpoint URLs
    """
    return load_config()['endpoints']


def get_never_request_scopes():
    """Get the list of scopes that should never be requested.
    
    Returns:
        list: Scopes that are forbidden to request
    """
    config = load_config()
    # Support both 'forbidden' (new) and 'never_request' (legacy) keys
    return config.get('scopes', {}).get('forbidden', 
           config.get('scopes', {}).get('never_request', []))


def get_request_scopes():
    """Get the list of scopes that Watcher needs.
    
    Returns:
        list: Scopes that Watcher should request
    """
    config = load_config()
    return config.get('scopes', {}).get('request', [])


def get_available_scopes():
    """Get all scopes safe for a non-moderator viewer.
    
    Returns:
        list: All available scopes for a logged-in viewer
    """
    config = load_config()
    return config.get('scopes', {}).get('available', [])


def reload_config():
    """Force reload of configuration from file."""
    global _config_cache
    _config_cache = None
    return load_config()
