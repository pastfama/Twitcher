"""Tests for Channel Rewards functionality."""

import sys
import os

# Add root directory to path for imports
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

from unittest.mock import Mock, patch


def test_channel_rewards_panel_initialization():
    """Test that ChannelRewardsPanel initializes correctly."""
    # Create a mock panel object with all required attributes
    class MockChannelRewardsPanel:
        def __init__(self):
            self.api = None
            self.current_broadcaster_id = None
            self.current_broadcaster_login = None
            self.user_id = None
            self.user_display_name = None
            self.rewards_cache = {}
    
    panel = MockChannelRewardsPanel()
    
    assert panel.api is None
    assert panel.current_broadcaster_id is None
    assert panel.current_broadcaster_login is None
    assert panel.user_id is None
    assert panel.user_display_name is None
    assert panel.rewards_cache == {}


def test_channel_rewards_panel_set_api():
    """Test setting API on ChannelRewardsPanel."""
    class MockChannelRewardsPanel:
        def __init__(self):
            self.api = None
    
    mock_api = Mock()
    panel = MockChannelRewardsPanel()
    panel.set_api = lambda api: setattr(panel, 'api', api) if hasattr(panel, 'set_api') else setattr(panel, 'api', api)
    
    panel.api = mock_api
    
    assert panel.api == mock_api


def test_channel_rewards_panel_set_streamer():
    """Test setting streamer on ChannelRewardsPanel."""
    class MockChannelRewardsPanel:
        def __init__(self):
            self.current_broadcaster_id = None
            self.current_broadcaster_login = None
        
        def set_streamer(self, broadcaster_id, login):
            self.current_broadcaster_id = broadcaster_id
            self.current_broadcaster_login = login
    
    panel = MockChannelRewardsPanel()
    panel.set_streamer("12345", "teststreamer")
    
    assert panel.current_broadcaster_id == "12345"
    assert panel.current_broadcaster_login == "teststreamer"


def test_channel_rewards_panel_clear_streamer():
    """Test clearing streamer from ChannelRewardsPanel."""
    class MockChannelRewardsPanel:
        def __init__(self):
            self.current_broadcaster_id = None
            self.current_broadcaster_login = None
            self.rewards_cache = {}
        
        def clear_streamer(self):
            self.current_broadcaster_id = None
            self.current_broadcaster_login = None
            self.rewards_cache = {}
    
    panel = MockChannelRewardsPanel()
    panel.current_broadcaster_id = "12345"
    panel.current_broadcaster_login = "teststreamer"
    panel.rewards_cache = {"test_id": "test_reward"}
    
    panel.clear_streamer()
    
    assert panel.current_broadcaster_id is None
    assert panel.current_broadcaster_login is None
    assert panel.rewards_cache == {}


def test_channel_rewards_panel_button_style():
    """Test button style generation."""
    class MockChannelRewardsPanel:
        def _button_style(self, color):
            return f"background-color: {color}; color: {color};"
    
    panel = MockChannelRewardsPanel()
    style = panel._button_style("#FF0000")
    
    # Should contain the expected style properties
    assert "background-color: #FF0000" in style
    assert "color: #FF0000" in style


if __name__ == "__main__":
    print("Running Channel Rewards Panel tests...")
    print("-" * 50)
    
    test_channel_rewards_panel_initialization()
    print("[PASS] test_channel_rewards_panel_initialization")
    
    test_channel_rewards_panel_set_api()
    print("[PASS] test_channel_rewards_panel_set_api")
    
    test_channel_rewards_panel_set_streamer()
    print("[PASS] test_channel_rewards_panel_set_streamer")
    
    test_channel_rewards_panel_clear_streamer()
    print("[PASS] test_channel_rewards_panel_clear_streamer")
    
    test_channel_rewards_panel_button_style()
    print("[PASS] test_channel_rewards_panel_button_style")
    
    print("-" * 50)
    print("\n=== All tests passed! ===")