"""Rate limiter for Anthropic API calls."""

import logging
import time


logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter for API calls with configurable token threshold.

    Implements throttling based on input tokens to prevent hitting
    Anthropic's rate limits (30,000 tokens per minute).
    """

    def __init__(
        self, rate_limit_tpm: int = 30000, token_threshold: int = 10000, safety_buffer: float = 1.1
    ):
        """
        Initialize rate limiter.

        Args:
            rate_limit_tpm: Tokens per minute rate limit
            token_threshold: Throttle if previous call exceeded this
            safety_buffer: Multiply calculated delay by this factor
        """
        self.rate_limit_tpm = rate_limit_tpm
        self.token_threshold = token_threshold
        self.safety_buffer = safety_buffer
        self.previous_tokens = 0

    def record_usage(self, input_tokens: int) -> None:
        """
        Record token usage from most recent API call.

        Args:
            input_tokens: Number of input tokens used
        """
        self.previous_tokens = input_tokens

    def calculate_delay(self, tokens: int) -> float:
        """
        Calculate delay needed for given token count.

        Args:
            tokens: Number of tokens used

        Returns:
            Delay in seconds (0 if below threshold)
        """
        if tokens <= self.token_threshold:
            return 0.0

        # (tokens / rate_limit) * 60 seconds * safety_buffer
        calculated_delay = (tokens / self.rate_limit_tpm) * 60
        return calculated_delay * self.safety_buffer

    def throttle_if_needed(self) -> None:
        """
        Throttle (sleep) if previous call exceeded token threshold.

        Logs delay information when throttling occurs.
        """
        if self.previous_tokens <= self.token_threshold:
            return

        delay = self.calculate_delay(self.previous_tokens)
        calculated_delay = (self.previous_tokens / self.rate_limit_tpm) * 60

        logger.info(
            f"Rate limiting: Previous call used {self.previous_tokens:,} tokens "
            f"(>{self.token_threshold:,} threshold). "
            f"Waiting {delay:.1f} seconds to avoid rate limit "
            f"(calculated: {calculated_delay:.1f}s + "
            f"{(self.safety_buffer - 1) * 100:.0f}% safety buffer)"
        )
        time.sleep(delay)
