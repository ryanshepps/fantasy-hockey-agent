# LlamaIndex Integration Design
**Date:** 2025-10-26
**Status:** Design Phase
**Goal:** Enhance fantasy hockey agent reasoning through specialized sub-agents using LlamaIndex framework

## Executive Summary

Refactor the fantasy hockey agent from a single-agent architecture to an orchestrated multi-agent system powered by LlamaIndex. This enables specialized reasoning across three domains: player evaluation, strategic planning, and historical learning. The hybrid storage approach (files + vector DB) balances operational simplicity with long-term learning capabilities.

## Problem Statement

The current agent (`AgentOrchestrator`) handles all reasoning in a single LLM call with tool access. This limits:
- **Depth of analysis:** No specialization for complex sub-tasks (e.g., player trend analysis, schedule optimization)
- **Historical learning:** Recommendations history exists but isn't semantically queryable
- **Reasoning transparency:** Single agent makes all decisions without domain-specific expertise

## Goals

1. **Enhanced reasoning** through specialized sub-agents with domain expertise
2. **Historical learning** via semantic search over past recommendations and outcomes
3. **Better decision quality** by separating concerns (evaluation vs strategy vs learning)
4. **Maintain simplicity** of the existing email-based output and workflow

## Architecture Overview

### High-Level Structure
```
MasterOrchestrator (LlamaIndex ReActAgent)
├── PlayerEvaluatorAgent (specialist sub-agent)
│   ├── RAG over player stats history
│   └── Tools: assess_player_droppability, analyze_player_trends
├── StrategyPlannerAgent (specialist sub-agent)
│   ├── RAG over league scoring rules, roster constraints
│   └── Tools: find_streaming_matches, optimize_schedule
└── HistoricalAnalystAgent (specialist sub-agent)
    ├── RAG over past recommendations (vector DB)
    └── Tools: query_similar_situations, analyze_past_outcomes
```

### Key Architectural Changes
- Replace `AgentOrchestrator` with LlamaIndex `ReActAgent` as master coordinator
- Existing tools wrapped as `BaseTool` implementations for LlamaIndex compatibility
- Each sub-agent gets dedicated `VectorStoreIndex` and `QueryEngine`
- Prefetch system replaced by LlamaIndex's data ingestion pipeline

## Sub-Agent Design

### 1. PlayerEvaluatorAgent
**Purpose:** Deep analysis of individual players to determine droppability and value

**Data Sources:**
- Vector index over player stats (goals, assists, PPP, etc.) from Yahoo API
- Recent performance trends (last 2-4 weeks)
- Position scarcity data

**Tools:**
- `get_player_stats` - Wraps existing Yahoo API calls
- `analyze_player_trends` - NEW: Uses RAG to compare current stats vs historical patterns
- `assess_position_scarcity` - NEW: Queries indexed roster data

**Output:** Ranked list of droppable players with confidence scores and reasoning

### 2. StrategyPlannerAgent
**Purpose:** High-level game theory - maximize points through schedule optimization

**Data Sources:**
- Vector index over team schedules (NHL API)
- League rules document (scoring, roster limits, acquisition limits)

**Tools:**
- `get_team_schedule` - Existing tool
- `find_optimal_streaming_windows` - ENHANCED: Uses RAG to find similar past schedule patterns
- `validate_roster_constraints` - NEW: Ensures recommendations respect weekly limits

**Output:** Streaming plan with specific dates and expected value gains

### 3. HistoricalAnalystAgent
**Purpose:** Learn from past decisions to avoid mistakes and identify winning patterns

**Data Sources:**
- Vector DB indexed on past `recommendations_history.json` entries
- Outcome data (if tracking whether pickups succeeded)

**Tools:**
- `query_similar_situations` - NEW: Semantic search for "what happened last time we considered dropping X?"
- `analyze_recommendation_outcomes` - NEW: If outcome tracking exists
- `get_recommendation_context` - Wraps existing history reader

**Output:** Context and warnings based on historical patterns

## Data Flow & Orchestration

### Workflow Sequence
```
1. User prompt: "Please proceed with the analysis"

2. MasterOrchestrator receives task

3. Orchestrator delegates to sub-agents:

   a) HistoricalAnalystAgent.query_similar_situations()
      → "Last week you considered dropping Player X but kept them - they scored 12 pts"

   b) PlayerEvaluatorAgent.assess_roster(current_roster, historical_context)
      → Uses RAG to analyze each player's trends
      → [Player A (droppable, confidence: 0.85), Player B (droppable, confidence: 0.62)]

   c) StrategyPlannerAgent.create_streaming_plan(droppable_players, schedule, constraints)
      → Uses RAG to find optimal streaming windows
      → {Mon: drop A for B, Thu: drop B for C, expected_value: +8.5 pts}

4. MasterOrchestrator synthesizes results into email format

5. Calls send_email and save_recommendations tools
```

### Orchestration Principles
- Master agent decides when to consult each sub-agent (not hard-coded sequence)
- Sub-agents can be called multiple times if master needs refinement
- Each sub-agent operates independently with its own context
- Master maintains conversation state and final decision authority

### Hybrid Storage Strategy

**File-based (operational):**
- `recommendations_history.json`, `current_roster.json`
- Read directly by tools for immediate operational needs
- Simple, no infrastructure dependencies

**Vector DB (learning):**
- ChromaDB instance with collections:
  - `player_stats_history` - Semantic search over player performance
  - `recommendations_archive` - Past decisions indexed by context (date, players, reasoning)
  - `league_knowledge` - Scoring rules, strategy guides (static documents)

## Implementation Plan

### Directory Structure
```
fantasy-hockey-test/
├── fantasy_hockey_agent.py (refactored: creates MasterOrchestrator)
├── agents/
│   ├── master_orchestrator.py (LlamaIndex ReActAgent wrapper)
│   ├── player_evaluator_agent.py
│   ├── strategy_planner_agent.py
│   └── historical_analyst_agent.py
├── tools/
│   ├── llama_tools.py (existing tools wrapped as BaseTool)
│   └── yahoo_api_tools.py, nhl_api_tools.py (existing, called by llama_tools)
├── indexing/
│   ├── vector_store_manager.py (ChromaDB setup)
│   ├── data_ingestion.py (populate indexes from Yahoo/NHL APIs)
│   └── document_loaders.py (custom loaders for JSON data)
└── data/
    ├── vector_db/ (ChromaDB persistence)
    └── operational/ (recommendations_history.json, etc.)
```

### Dependencies to Add
```
llama-index-core
llama-index-llms-anthropic  # Use Claude with LlamaIndex
llama-index-embeddings-openai  # For embeddings (or Anthropic when available)
llama-index-vector-stores-chroma
chromadb
```

### Migration Phases

**Phase 1: Foundation**
- Set up ChromaDB vector store
- Create document loaders for existing JSON data
- Build initial indexes from historical data

**Phase 2: Sub-Agents (Incremental)**
- Build PlayerEvaluatorAgent first (most complex)
- Add StrategyPlannerAgent second
- Add HistoricalAnalystAgent last

**Phase 3: Tools Migration**
- Wrap existing tools as LlamaIndex `BaseTool` implementations
- Maintain backward compatibility during transition

**Phase 4: Orchestration**
- Create MasterOrchestrator
- Wire sub-agents together
- Test delegation logic

**Phase 5: Parallel Testing**
- Run both old and new systems for 2-3 weeks
- Compare recommendations
- Track quality metrics

**Phase 6: Cutover**
- Replace old `AgentOrchestrator` completely
- Keep old code for 1-month rollback window

## Error Handling & Resilience

### Failure Modes

**Sub-agent failures:**
- If PlayerEvaluatorAgent fails → Fall back to simpler heuristics (direct tool calls without RAG)
- Log detailed error context for debugging

**Vector DB unavailable:**
- Graceful degradation to file-based only mode
- Log warning, continue with reduced intelligence
- All operational tools still function

**API rate limits:**
- LlamaIndex built-in retry logic with exponential backoff
- Preserve existing Yahoo/NHL API rate limit handling

**Malformed tool responses:**
- Pydantic validation at tool boundaries (preserve existing validation)
- Sub-agent catches and reports validation errors to master

## Testing Strategy

### Unit Tests
```
tests/
├── test_player_evaluator_agent.py
│   └── Test with mock vector store, verify tool selection logic
├── test_strategy_planner_agent.py
│   └── Test streaming window calculation with known schedules
├── test_historical_analyst_agent.py
│   └── Test semantic search retrieval accuracy
└── test_master_orchestrator.py
    └── Integration test: full workflow with mock sub-agents
```

### Validation Strategy
- **Parallel run period:** Both systems run for 2-3 weeks
- **Comparison metrics:**
  - Droppable player lists overlap
  - Streaming recommendation similarity
  - Decision confidence scores
  - Reasoning quality (human evaluation)
- **Rollback plan:** Old `AgentOrchestrator` code intact for 1 month post-cutover

## Performance & Cost Considerations

### Performance Impact
- Vector DB queries: +50-200ms per sub-agent call
- Expected LLM calls: 3-5 per recommendation (vs current 1-2)
- Total latency: +2-5 seconds for full analysis

### Cost Impact
- Estimated 2-3x increase in API costs due to sub-agent reasoning
- Mitigation strategies:
  - LlamaIndex response caching
  - Aggressive prompt optimization
  - Batch similar queries

### Benefits Justifying Cost
- Higher quality recommendations
- Better explainability (per-domain reasoning)
- Historical learning prevents repeated mistakes
- Confidence scores enable risk-appropriate decisions

## Success Metrics

### Quantitative
- Recommendation quality: Track points gained from followed recommendations
- Decision confidence: Measure correlation between confidence scores and outcomes
- System reliability: Uptime and graceful degradation events

### Qualitative
- Reasoning transparency: Can you understand why each recommendation was made?
- Historical learning: Does the system reference and learn from past decisions?
- User trust: Do recommendations feel more thoughtful and well-reasoned?

## Open Questions

1. **Outcome tracking:** Should we add explicit tracking of recommendation outcomes (did the pickup succeed? how many points did they score?)
2. **Interactive mode:** Should the agent support follow-up questions ("Why did you recommend dropping Player X?")?
3. **Multi-week planning:** Should StrategyPlanner look beyond 2-week windows for deeper strategy?
4. **Trade analysis:** Future sub-agent for evaluating trade opportunities?

## References

- [LlamaIndex Framework Docs](https://developers.llamaindex.ai/python/framework/)
- [LlamaIndex Multi-Agent Patterns](https://docs.llamaindex.ai/en/stable/examples/agent/)
- Current agent implementation: `fantasy_hockey_agent.py:155-199`
