"""
Data models for the Golf.nl scraper.
"""

from dataclasses import dataclass


@dataclass
class GolfScore:
    """Data class representing a golf score entry."""

    date: str
    course_name: str
    score: int
    differential: float
    status: str


@dataclass
class ScraperConfig:
    """Configuration for the golf scraper."""

    email: str
    password: str
    base_url: str = "https://mijn.golf.nl"
    login_url: str = "https://mijn.golf.nl/login"
    scores_url: str = "https://mijn.golf.nl/mijn-spel/scores"
    timeout: int = 10
    retry_attempts: int = 3
    implicit_wait: int = 5
    headless: bool = False
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    window_size: str = "1920x1080"
    disable_images: bool = True
    disable_javascript: bool = False
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    score_pattern: str = r"<div>SD([\d,]+)\xa0"


@dataclass
class ScoreDetails:
    """Data class representing a score details entry."""

    tee: str
    qualifying: bool
    tournament: bool
    comment: str
    score_card_link: str
    course_handicap: int
    stableford: int
    total_strokes: int
    adjusted_gross_score: int
    playing_conditions_correction: int
    score_differential: float
    handicap: float
    marker: str
    signed: bool


@dataclass
class ScrapingResult:
    """Result of a scraping operation."""

    success: bool
    score_details: list[ScoreDetails]
    error_message: str | None = None
    timestamp: str | None = None
    total_scores_found: int = 0

    def __post_init__(self):
        """Set total_scores_found after initialization."""
        if self.score_details is None:
            self.score_details = []
        self.total_scores_found = len(self.score_details)

    def get_score_details(self) -> list[float]:
        """
        Extract score details values from scores.
        Works with both List[float] and List[Dict] formats.

        Returns:
            List of score details values
        """
        if not self.score_details:
            return []

        # If scores are already floats, return them
        if isinstance(self.score_details[0], (int, float)):
            return [float(s) for s in self.score_details]

        # If scores are dicts, try to extract differential
        score_details = []
        for score_detail in self.score_details:
            if isinstance(score_detail, dict):
                # Try common keys for differential
                for key in [
                    "differential",
                    "SD",
                    "score_differential",
                    "handicap_differential",
                ]:
                    if key in score_detail:
                        try:
                            value = score_detail[key]
                            # Handle string values with commas
                            if isinstance(value, str):
                                value = value.replace(",", ".")
                            score_details.append(float(value))
                            break
                        except ValueError, TypeError:
                            continue

        return score_details


@dataclass
class LoginResult:
    """Result of a login attempt."""

    success: bool
    error_message: str | None = None
    timestamp: str | None = None
