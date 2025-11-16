# LlamaIndex Multi-Agent Architecture Usage

## Overview

The LlamaIndex integration provides enhanced reasoning through three specialized sub-agents:

1. **PlayerEvaluatorAgent** - Assesses player droppability using RAG over league knowledge
2. **StrategyPlannerAgent** - Creates optimal streaming plans
3. **HistoricalAnalystAgent** - Learns from past recommendations via semantic search

## Quick Start

### Run with LlamaIndex

```bash
python3 fantasy_hockey_agent.py --use-llamaindex
```

### Dry Run (No Email)

```bash
python3 fantasy_hockey_agent.py --use-llamaindex --dry-run
```

## Environment Variables

Required:
- `ANTHROPIC_API_KEY` - For Claude LLM calls
- `OPENAI_API_KEY` - For embeddings (text-embedding-3-small)

## Architecture

```
MasterOrchestrator (ReActAgent)
├── PlayerEvaluatorAgent
│   └── RAG: league_knowledge
├── StrategyPlannerAgent
│   └── RAG: league_knowledge
└── HistoricalAnalystAgent
    └── RAG: recommendations_archive
```

## Data Ingestion

Vector indexes are created from:
- `recommendations_history.json` → `recommendations_archive` collection
- League knowledge (scoring, rules) → `league_knowledge` collection

Storage: `./data/vector_db/` (ChromaDB)

## Performance

- Initial ingestion: ~5-10 seconds
- Per-recommendation: 3-5 LLM calls (~10-15 seconds)
- Cost: ~2-3x original agent (sub-agent reasoning overhead)

## Testing

Run integration tests:
```bash
pytest tests/test_integration_llamaindex.py -v -m integration
```

## Comparison: Original vs LlamaIndex

| Feature | Original | LlamaIndex |
|---------|----------|------------|
| LLM calls/run | 1-2 | 3-5 |
| Historical learning | File read only | Semantic search |
| Reasoning transparency | Single agent | Per-domain explanations |
| Latency | ~3-5s | ~10-15s |
| Cost | Baseline | 2-3x |
