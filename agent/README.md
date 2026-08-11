# Twitcher Analytics Agent

AI-powered hosted agent providing analytics data about Twitch streamers using Microsoft Agent Framework.

## Features

- **Streamer Analytics**: Get comprehensive data about Twitch streamers including AI-generated quality scores
- **Viewer Trends**: Analyze viewer count history and growth patterns
- **Quality Metrics**: Access AI predictions for momentum, viral potential, and churn risk
- **Leaderboards**: Rank streamers by various metrics
- **Comparisons**: Compare performance between streamers

## Prerequisites

- Azure Developer CLI (azd) >= 1.25.1
- Azure AI Agents extension >= 0.1.35-preview
- Azure subscription with Cognitive Services access

## Installation

### 1. Install Azure Developer CLI

```powershell
winget install microsoft.azd
```

### 2. Install Agent Extension

```powershell
azd extension install azure.ai.agents --version 0.1.35-preview
```

## Deployment

### Initialize the Agent

```powershell
cd agent
azd init -t python
```

### Provision and Deploy

```powershell
azd up
```

This will:
1. Create Azure resources (App Service, Storage, PostgreSQL, Key Vault)
2. Deploy the FastAPI application
3. Configure the hosted agent with custom MCP tools
4. Set up monitoring with Application Insights

### Access the Agent

After deployment, you can chat with your agent at:
```
https://<your-agent-name>.azurewebsites.net
```

## Project Structure

```
agent/
├── app.py                          # FastAPI application
├── agent.yaml                      # Agent definition
├── azure.yaml                      # Deployment configuration
├── requirements.txt                 # Python dependencies
├── infra/
│   └── main.bicep                  # Azure infrastructure
└── mcp_servers/
    ├── streamer_tool.py            # Streamer data access
    ├── analytics_tool.py           # Analytics queries
    └── viewer_tool.py              # Viewer history
```

## MCP Tools

The agent has access to the following custom tools:

### Streamer Tools
- `get_streamer_data` - Retrieve streamer information with AI analysis
- `search_streamers` - Search for streamers by name
- `refresh_analysis` - Trigger fresh AI analysis

### Analytics Tools
- `get_quality_metrics` - Get AI-generated quality scores and predictions
- `get_viewer_trends` - Analyze viewer count trends
- `get_leaderboard` - Get ranked streamers by metrics
- `generate_profile` - Generate comprehensive AI profile

### Viewer Tools
- `get_viewer_history` - Get historical viewer data
- `get_current_viewers` - Get current viewer counts
- `get_top_streamers` - Get top streamers by viewers
- `compare_streamers` - Compare two streamers

## Environment Variables

The deployment uses these environment variables:

- `AZURE_OPENAI_ENDPOINT` - Azure OpenAI endpoint
- `AZURE_OPENAI_DEPLOYMENT` - Model deployment name
- `TWITCHER_DB_PATH` - Path to SQLite database
- `LOG_LEVEL` - Logging level

## Integration with Twitcher

The agent connects to the existing Twitcher infrastructure:

- **Database**: Reads from `watcher.db` (SQLite) with streamer data and viewer history
- **AI Engine**: Uses existing Azure OpenAI setup for analytics
- **Platform APIs**: Can integrate with Twitch/Kick/YouTube APIs

## Monitoring

The deployment includes:
- Application Insights for application monitoring
- Log Analytics for centralized logging
- Agent telemetry for tracking usage and performance

## Development

### Run Locally

```powershell
cd agent
pip install -r requirements.txt
python app.py
```

The API will be available at `http://localhost:8000`

### Test MCP Tools

```powershell
# Test streamer endpoint
curl http://localhost:8000/api/mcp/streamers/{login}

# Test analytics endpoint
curl http://localhost:8000/api/mcp/analytics/{login}/quality

# Test viewer endpoint
curl http://localhost:8000/api/mcp/viewers/{login}/history
```

## Cost Estimate

- **App Service (B1)**: ~$13/month
- **Storage**: ~$1/month
- **PostgreSQL (B_Gen5_1)**: ~$15/month
- **Application Insights**: Pay-per-use (~$5-10/month)
- **Azure OpenAI**: Pay-per-token (varies by usage)

**Total estimated cost**: ~$35-50/month for basic usage

## Next Steps

1. Deploy the agent with `azd up`
2. Chat with the agent to test analytics queries
3. Monitor usage and costs in Azure Portal
4. Customize the agent prompt in `agent.yaml` for specific use cases

## License

MIT License - see LICENSE file for details.