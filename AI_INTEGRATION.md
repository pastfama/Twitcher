# 🤖 Twitcher AI Integration Guide

## Overview

This document describes the Azure AI integration that replaces manual analytics with intelligent AI-powered insights.

## Architecture

### Before (Manual Analytics)
```
Twitch API → ViewerTracker → Manual Calculations → UI
                              ↓
                        SullyGoose Scraping → Manual Metrics → UI
```

### After (AI-Powered)
```
Twitch API → Raw Data Collection → Azure OpenAI AI → Intelligent Insights → UI
                              ↓
                        viewer_history table (raw data)
                        chat_logs table (optional)
                        stream_events table (optional)
```

## Files Created/Modified

### New Files
- **`core/azure_ai_client.py`** - Azure OpenAI client wrapper with caching
- **`core/ai_analytics_engine.py`** - AI-powered analytics engine (replaces v1/v2)
- **`test_ai_integration.py`** - Test suite for AI integration

### Modified Files
- **`mainmenu/main.py`** - Uses AI analytics engine instead of AnalyticsEngine v2
- **`mainmenu/channel_state.py`** - Calls `analyze_stream()` instead of `update_stream()`
- **`mainmenu/currwatching/panel.py`** - Displays AI insights in momentum label
- **`mainmenu/livefollowed/panel.py`** - Uses AI analysis for growth/score
- **`mainmenu/nextstream/panel.py`** - Uses AI recommendations for next stream

## Key Features Implemented

### 1. 🤖 AI Stream Analysis
**Replaces:** Manual score calculation, momentum tracking, SullyGoose metrics

**What it does:**
- Analyzes current stream with viewer history context
- Generates quality score (0-100)
- Determines momentum (Rising/Stable/Declining)
- Provides AI insights and recommendations
- Predicts peak viewers and timing

**Usage:**
```python
from core.ai_analytics_engine import get_ai_analytics_engine

engine = get_ai_analytics_engine()
analysis = engine.analyze_stream(stream_data)
# Returns: {"score": 85, "status": "Rising", "percent": 12.5, 
#           "ai_insight": "Peak viewership expected...", ...}
```

### 2. 🎯 AI Auto-Pilot (Infrastructure Ready)
**Status:** Implemented, needs UI toggle

**What it does:**
- Evaluates switching opportunities every 2 minutes
- Compares current stream vs alternatives
- AI decides: SWITCH / WAIT / STAY
- Confidence-scored decisions

**Usage:**
```python
decision = engine.should_switch_channel(
    current_stream=current,
    alternative_streams=live_channels
)
# Returns: {"action": "SWITCH", "confidence": 0.95, 
#           "reasoning": "Better engagement detected"}
```

### 3. 🧠 Mood Detection (Infrastructure Ready)
**Status:** Implemented, needs chat integration

**What it does:**
- Analyzes user engagement level
- Detects if user is bored/engaged/neutral
- Triggers Auto-Pilot when bored

**Usage:**
```python
mood = engine.detect_user_mood()
# Returns: {"mood": "engaged", "engagement_score": 0.85}
```

## Database Schema

### No Changes Required!
The existing database already supports AI analysis:

**`streamers.data` JSON field** stores:
```json
{
  "ai_analysis": {
    "quality_score": 85,
    "momentum": "Rising",
    "momentum_percent": 12.5,
    "confidence": 0.92,
    "ai_insight": "Peak viewership expected...",
    "reasoning": "Viewer count growing 3x faster than typical...",
    "recommendations": ["Great time to watch", "High engagement"],
    "predicted_peak_viewers": 25000,
    "predicted_peak_time": "in 45 minutes",
    "churn_risk": 0.15,
    "viral_potential": 0.72,
    "last_analyzed": "2024-01-15T10:30:00Z"
  },
  "ai_profile": {
    "psychographic_profile": {...},
    "optimal_strategy": {...},
    "predictive_model": {...}
  }
}
```

**`viewer_history` table** provides raw data for AI analysis.

## Configuration

### Environment Variables
```bash
AZURE_OPENAI_ENDPOINT=https://malovsky99-6011-resource.services.ai.azure.com/openai/v1
AZURE_OPENAI_DEPLOYMENT=gpt-5-mini-1
```

### Settings (stored in database)
```python
# Enable/disable features
set_setting("ai_auto_pilot", "true")      # Enable Auto-Pilot
set_setting("ai_mood_detection", "true")  # Enable Mood Detection
```

## Caching Strategy

To optimize credit usage:

```python
# Stream analysis: 5 minutes
cache_ttl = 300

# Streamer profiles: 24 hours
cache_ttl = 86400

# Auto-Pilot decisions: 2 minutes
cache_ttl = 120
```

## Credit Usage Estimates

With your Azure credits:

| Feature | Requests/Day | Requests/Month |
|---------|-------------|----------------|
| Stream Analysis | ~2880 | ~86,400 |
| Trend Detection | ~144 | ~4,320 |
| Auto-Pilot | ~2880 | ~86,400 |
| Mood Detection | ~288 | ~8,640 |
| **Total** | **~6192** | **~185,760** |

**Cost:** ~$50-200/month with GPT-4o-mini pricing

## Testing

Run the test suite:
```bash
python test_ai_integration.py
```

Tests:
1. ✅ AI Client Initialization
2. ✅ AI Analytics Engine Initialization
3. ✅ Stream Analysis (requires Azure credentials)
4. ✅ Database Compatibility
5. ✅ UI Integration Points

## UI Changes

### CurrentWatchingPanel
**Before:**
```
Momentum: Rising +12.5%
```

**After:**
```
Momentum: Rising +12.5% • Peak viewership expected in 2 hours
```

### LiveFollowedPanel
**Before:**
```
Growth: +12.5%  Score: 85
```

**After:**
```
Growth: +12.5%  Score: 85  (from AI analysis)
```

### NextStreamPanel
**Before:**
```
Reason: Reliable schedule • Growing audience • Active chat
```

**After:**
```
Reason: Great time to watch - high engagement predicted
```

## Error Handling

The AI system has graceful fallbacks:

1. **Azure unavailable** → Falls back to basic manual scoring
2. **AI call fails** → Uses cached data or fallback analysis
3. **JSON parse error** → Logs error, returns fallback
4. **No viewer history** → AI analyzes current stream only

## Next Steps

### Immediate (Ready to Use)
1. ✅ Test with `python test_ai_integration.py`
2. ✅ Run the app: `python twitcher.py`
3. ✅ Verify AI insights appear in UI

### Short-term (1-2 weeks)
1. Add UI toggle for Auto-Pilot
2. Implement mood detection with chat integration
3. Add AI profile generation button
4. Monitor credit usage and adjust caching

### Long-term (1-2 months)
1. Implement all 10 AI features from the plan
2. Add weekly dashboard generation
3. Build chat summarization
4. Create streamer personality profiles

## Troubleshooting

### "Azure AI dependencies not installed"
```bash
pip install openai azure-identity
```

### "AI analysis unavailable"
- Check Azure credentials in environment
- Verify endpoint and deployment name
- Check network connectivity

### "Cache not updating"
- AI results are cached for 5 minutes by default
- Use `fetch_fresh=True` to force refresh
- Check logs for cache hits/misses

## Credits Usage Monitoring

Add to your app to track AI usage:
```python
# In core/azure_ai_client.py
def get_credit_usage(self):
    """Return credit usage statistics."""
    return {
        "total_calls": len(self._cache),
        "cache_hits": sum(1 for r, _ in self._cache.values() if r.get("cached")),
        "estimated_cost": len(self._cache) * 0.001  # Rough estimate
    }
```

## Support

For issues or questions:
1. Check logs: `watcher_output.txt`
2. Run tests: `python test_ai_integration.py`
3. Verify Azure credentials
4. Check network connectivity

## License

MIT License - see LICENSE file for details.