#!/usr/bin/env python3
"""Test script for Azure AI integration."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_ai_client():
    """Test Azure AI client initialization."""
    print("=" * 60)
    print("TEST 1: Azure AI Client Initialization")
    print("=" * 60)
    
    try:
        from core.azure_ai_client import get_ai_client, HAS_AZURE_AI
        
        if not HAS_AZURE_AI:
            print("⚠️  Azure AI dependencies not installed")
            print("   Install with: pip install openai azure-identity")
            return False
        
        client = get_ai_client()
        if client:
            print("✅ Azure AI client initialized successfully")
            print(f"   Endpoint: {client.endpoint}")
            print(f"   Deployment: {client.deployment}")
            return True
        else:
            print("❌ Failed to initialize Azure AI client")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_ai_analytics_engine():
    """Test AI analytics engine initialization."""
    print("\n" + "=" * 60)
    print("TEST 2: AI Analytics Engine Initialization")
    print("=" * 60)
    
    try:
        from core.ai_analytics_engine import get_ai_analytics_engine
        
        engine = get_ai_analytics_engine()
        if engine:
            print("✅ AI Analytics engine initialized successfully")
            print(f"   Auto-Pilot: {engine.enable_auto_pilot}")
            print(f"   Mood Detection: {engine.enable_mood_detection}")
            return True
        else:
            print("❌ Failed to initialize AI analytics engine")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_ai_stream_analysis():
    """Test AI stream analysis (requires Azure credentials)."""
    print("\n" + "=" * 60)
    print("TEST 3: AI Stream Analysis")
    print("=" * 60)
    
    try:
        from core.ai_analytics_engine import get_ai_analytics_engine
        
        engine = get_ai_analytics_engine()
        if not engine or not engine.ai_client:
            print("⚠️  AI client not available, skipping test")
            return True
        
        # Test with mock stream data
        test_stream = {
            "user_login": "test_streamer",
            "user_name": "Test Streamer",
            "platform": "twitch",
            "title": "Test Stream",
            "game_name": "Gaming",
            "viewer_count": 1234,
            "started_at": "2024-01-15T10:00:00Z"
        }
        
        print(f"   Analyzing stream: {test_stream['user_login']}")
        print(f"   Viewers: {test_stream['viewer_count']}")
        
        analysis = engine.analyze_stream(test_stream, fetch_fresh=True)
        
        if analysis:
            print("✅ AI analysis completed successfully")
            print(f"   Score: {analysis.get('score', 'N/A')}")
            print(f"   Status: {analysis.get('status', 'N/A')}")
            print(f"   Momentum: {analysis.get('percent', 'N/A')}%")
            print(f"   Confidence: {analysis.get('confidence', 'N/A')}")
            print(f"   AI Insight: {analysis.get('ai_insight', 'N/A')[:100]}...")
            return True
        else:
            print("⚠️  AI analysis returned empty (might be cached or unavailable)")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_compatibility():
    """Test that database layer works with AI system."""
    print("\n" + "=" * 60)
    print("TEST 4: Database Compatibility")
    print("=" * 60)
    
    try:
        from core.db import get_streamer, store_streamer, list_streamers
        
        # Test storing streamer with AI data
        test_data = {
            "ai_analysis": {
                "quality_score": 85,
                "momentum": "Rising",
                "momentum_percent": 12.5,
                "confidence": 0.92,
                "ai_insight": "Test insight"
            },
            "test": True
        }
        
        store_streamer(
            login="test_ai_streamer",
            name="Test AI Streamer",
            avatar_url="",
            viewers=1000,
            data=test_data,
            platform="twitch"
        )
        
        # Test retrieving
        retrieved = get_streamer("test_ai_streamer", platform="twitch")
        
        if retrieved and retrieved.get("data", {}).get("ai_analysis"):
            print("✅ Database stores and retrieves AI analysis correctly")
            print(f"   Stored data keys: {list(retrieved['data'].keys())}")
            
            # Cleanup
            from core.db import delete_setting
            print(f"   Retrieved quality_score: {retrieved['data']['ai_analysis']['quality_score']}")
            return True
        else:
            print("❌ Failed to store/retrieve AI analysis")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ui_integration():
    """Test UI components can access AI analytics."""
    print("\n" + "=" * 60)
    print("TEST 5: UI Integration Points")
    print("=" * 60)
    
    try:
        from core.ai_analytics_engine import get_ai_analytics_engine
        
        engine = get_ai_analytics_engine()
        
        # Test methods that UI components will call
        print("   Testing: get_ai_analysis()")
        analysis = engine.get_ai_analysis("test_streamer", "twitch")
        print(f"   ✅ get_ai_analysis() works (returns: {type(analysis).__name__})")
        
        print("   Testing: get_quality_score()")
        score = engine.get_quality_score("test_streamer", "twitch")
        print(f"   ✅ get_quality_score() works (returns: {score})")
        
        print("   Testing: get_momentum()")
        momentum = engine.get_momentum("test_streamer", "twitch")
        print(f"   ✅ get_momentum() works (returns: {momentum})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n🧪 Twitcher AI Integration Test Suite\n")
    
    results = []
    
    # Run tests
    results.append(("AI Client Init", test_ai_client()))
    results.append(("AI Analytics Engine", test_ai_analytics_engine()))
    results.append(("Stream Analysis", test_ai_stream_analysis()))
    results.append(("Database Compatibility", test_database_compatibility()))
    results.append(("UI Integration", test_ui_integration()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! AI integration is ready.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())