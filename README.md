# MiMo Autonomous Research Agent

An AI-powered autonomous research agent that searches the web, extracts information from multiple sources, cross-references findings, and produces comprehensive research reports with citations — all without human intervention.

## Features

- **Autonomous Research Loop** — Agent independently plans, searches, reads, analyzes, and writes
- **Multi-Source Search** — Wikipedia, ArXiv, HackerNews for diverse perspectives
- **Content Extraction** — Reads and processes full web pages
- **AI-Powered Analysis** — Uses LLM to identify key findings, gaps, and connections
- **Quality Self-Review** — Agent reviews its own report and revises if quality is below threshold
- **Real-Time Progress** — Watch the agent think, search, and write in real-time
- **Citation Support** — All claims linked to numbered sources
- **Beautiful UI** — Dark-themed responsive interface with live progress tracking

## Architecture

```
User Input (Topic)
       │
       ▼
┌─────────────────────────────────────┐
│         PLANNING PHASE              │
│  LLM decomposes topic into:        │
│  - Sub-questions                    │
│  - Search queries                   │
│  - Expected report sections         │
└─────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│         SEARCH PHASE                │
│  Multi-source parallel search:      │
│  - Wikipedia API                    │
│  - ArXiv (academic papers)          │
│  - HackerNews (tech community)     │
│  - Direct webpage extraction        │
└─────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│         ANALYSIS PHASE              │
│  LLM synthesizes findings:          │
│  - Key facts with source refs       │
│  - Multiple perspectives            │
│  - Information gaps                 │
│  - Cross-source connections         │
│  - Follow-up research if needed     │
└─────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│         REPORT GENERATION           │
│  LLM writes structured report:      │
│  - Executive summary                │
│  - Sectioned analysis               │
│  - Source citations [N]             │
│  - Minimum 1500 words              │
└─────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│         QUALITY REVIEW              │
│  LLM self-evaluates:               │
│  - Score 1-10                       │
│  - Strengths & weaknesses           │
│  - Auto-revise if score < 6         │
└─────────────────────────────────────┘
       │
       ▼
   Final Report + Sources
```

## Tech Stack

- **Backend**: Python + aiohttp (async web server)
- **AI Engine**: MiMo-compatible LLM via OpenAI-compatible API
- **Search**: Wikipedia API, ArXiv API, HackerNews Algolia API
- **Frontend**: Vanilla HTML/CSS/JS (no build step, no dependencies)
- **Deployment**: Single-file server, runs anywhere

## Quick Start

```bash
# Clone
git clone https://github.com/Gacormek/mimo-research-agent.git
cd mimo-research-agent

# Configure
echo "your-api-key" > .api_key

# Run
pip install aiohttp
python3 server.py

# Open http://localhost:80
```

## Live Demo

🔗 **https://moms-leaf-included-voices.trycloudflare.com**

## Configuration

Edit `server.py` to configure:

```python
LLM_ENDPOINT = "http://your-llm-endpoint/v1/chat/completions"
LLM_MODEL = "your-model-name"
PORT = 80
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web UI |
| POST | `/api/research` | Start new research `{"topic": "..."}` |
| GET | `/api/research/{id}` | Get research status & report |
| GET | `/api/research` | List all research sessions |

## Example Output

**Topic**: "Zero-knowledge proofs in blockchain scalability"

- **Report Length**: 25,000+ characters
- **Sources**: 17 (Wikipedia, ArXiv papers, HackerNews articles)
- **Quality Score**: 7/10 (self-evaluated)
- **Time**: ~3 minutes (autonomous, no human input)
- **Agent Steps**: 30 (plan → search → read → analyze → write → review)

## How It Works

1. **You** enter a research topic
2. **Agent** creates a research plan (sub-questions, search queries)
3. **Agent** searches Wikipedia, ArXiv, and HackerNews
4. **Agent** reads and extracts content from found pages
5. **Agent** analyzes findings — identifies patterns, gaps, conflicts
6. **Agent** conducts follow-up research if gaps are found
7. **Agent** writes a comprehensive report with citations
8. **Agent** self-reviews and revises if quality is insufficient
9. **You** get a publication-ready research report

## License

MIT
