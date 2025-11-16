"""Custom document loaders for fantasy hockey data."""

import json
import logging
from pathlib import Path

from llama_index.core import Document

logger = logging.getLogger(__name__)


class RecommendationHistoryLoader:
    """Load recommendations_history.json into LlamaIndex documents."""

    def __init__(self, file_path: str):
        """
        Initialize loader.

        Args:
            file_path: Path to recommendations_history.json
        """
        self.file_path = Path(file_path)

    def load(self) -> list[Document]:
        """
        Load recommendation history as documents.

        Returns:
            List of LlamaIndex Document objects
        """
        if not self.file_path.exists():
            logger.warning(f"History file not found: {self.file_path}")
            return []

        with open(self.file_path) as f:
            data = json.load(f)

        documents = []
        for rec in data.get("recommendations", []):
            # Create rich text representation
            text = f"""
Date: {rec.get('date', 'unknown')}
Pickups: {', '.join(rec.get('pickups', []))}
Drops: {', '.join(rec.get('drops', []))}
Reasoning: {rec.get('reasoning', '')}
Strategy: {rec.get('strategy', '')}
            """.strip()

            doc = Document(
                text=text,
                metadata={
                    "date": rec.get("date"),
                    "pickups": rec.get("pickups", []),
                    "drops": rec.get("drops", []),
                    "source": "recommendations_history",
                },
            )
            documents.append(doc)

        logger.info(f"Loaded {len(documents)} recommendations from history")
        return documents


class LeagueKnowledgeLoader:
    """Load league rules and strategy documents."""

    def __init__(self, knowledge_text: str):
        """
        Initialize with league knowledge.

        Args:
            knowledge_text: League rules, scoring, strategy text
        """
        self.knowledge_text = knowledge_text

    def load(self) -> list[Document]:
        """
        Create document from league knowledge.

        Returns:
            Single document with league knowledge
        """
        doc = Document(
            text=self.knowledge_text,
            metadata={"source": "league_knowledge", "type": "static"},
        )
        return [doc]


def load_league_knowledge() -> str:
    """
    Get league knowledge text from system prompt.

    Returns:
        League knowledge string
    """
    return """
LEAGUE SCORING: Goals(5), Assists(2), PPP(2-stack), SHG(3), SOG/Hit/Block(0.5) | Goalie: W(6), GA(-3.5), Save(0.5), SO(6)
ROSTER: 6F, 4D, 1U, 2G, 6Bench, 2IR | Weekly limits: 4 acquisitions, 3 goalie starts minimum

STRATEGY PRINCIPLES:
- Maximize games played via strategic streaming of MID-TIER and STREAMABLE players only
- Elite talent (Makar, McDavid, etc.) should NEVER be dropped for schedule reasons
- Elite talent > extra games always
- Balance hot streaks vs established value
- Avoid making major decisions based on small sample sizes (1-2 weeks)
    """.strip()
