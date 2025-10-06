"""
Prompt Analytics & Metrics Module

Tracks prompt compilation history, validation scores, and usage patterns.
Provides insights into prompt quality trends and user behavior.
"""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter


@dataclass
class PromptRecord:
    """Single prompt compilation record"""

    id: Optional[int] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    prompt_text: str = ""
    prompt_hash: str = ""  # SHA256 hash for deduplication
    validation_score: float = 0.0
    domain: str = "general"
    persona: str = "assistant"
    language: str = "en"
    intents: List[str] = field(default_factory=list)
    issues_count: int = 0
    warnings_count: int = 0
    prompt_length: int = 0
    ir_version: str = "v2"
    tags: List[str] = field(default_factory=list)


@dataclass
class AnalyticsSummary:
    """Summary statistics for a time period"""

    total_prompts: int = 0
    avg_score: float = 0.0
    min_score: float = 0.0
    max_score: float = 0.0
    score_std: float = 0.0
    top_domains: List[Tuple[str, int]] = field(default_factory=list)
    top_personas: List[Tuple[str, int]] = field(default_factory=list)
    top_intents: List[Tuple[str, int]] = field(default_factory=list)
    language_distribution: Dict[str, int] = field(default_factory=dict)
    avg_issues: float = 0.0
    avg_prompt_length: int = 0
    improvement_rate: float = 0.0  # Score improvement over time
    most_improved_domain: Optional[str] = None


class AnalyticsManager:
    """Manages prompt analytics storage and retrieval"""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize analytics manager

        Args:
            db_path: Path to SQLite database. Defaults to ~/.promptc/analytics.db
        """
        if db_path is None:
            db_path = Path.home() / ".promptc" / "analytics.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_database()

    def _init_database(self):
        """Initialize database schema"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompt_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                prompt_text TEXT NOT NULL,
                prompt_hash TEXT NOT NULL,
                validation_score REAL NOT NULL,
                domain TEXT NOT NULL,
                persona TEXT NOT NULL,
                language TEXT NOT NULL,
                intents TEXT,  -- JSON array
                issues_count INTEGER DEFAULT 0,
                warnings_count INTEGER DEFAULT 0,
                prompt_length INTEGER DEFAULT 0,
                ir_version TEXT DEFAULT 'v2',
                tags TEXT  -- JSON array
            )
        """)

        # Indexes for common queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON prompt_records(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_domain ON prompt_records(domain)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_persona ON prompt_records(persona)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_validation_score ON prompt_records(validation_score)"
        )

        conn.commit()
        conn.close()

    def record_prompt(self, record: PromptRecord) -> int:
        """
        Save a prompt record

        Args:
            record: PromptRecord to save

        Returns:
            Record ID
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO prompt_records (
                timestamp, prompt_text, prompt_hash, validation_score,
                domain, persona, language, intents, issues_count,
                warnings_count, prompt_length, ir_version, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                record.timestamp,
                record.prompt_text,
                record.prompt_hash,
                record.validation_score,
                record.domain,
                record.persona,
                record.language,
                json.dumps(record.intents),
                record.issues_count,
                record.warnings_count,
                record.prompt_length,
                record.ir_version,
                json.dumps(record.tags),
            ),
        )

        record_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return record_id

    def get_records(
        self,
        limit: int = 100,
        offset: int = 0,
        domain: Optional[str] = None,
        persona: Optional[str] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[PromptRecord]:
        """
        Retrieve prompt records with filters

        Args:
            limit: Maximum number of records
            offset: Offset for pagination
            domain: Filter by domain
            persona: Filter by persona
            min_score: Minimum validation score
            max_score: Maximum validation score
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            List of PromptRecord objects
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        query = "SELECT * FROM prompt_records WHERE 1=1"
        params = []

        if domain:
            query += " AND domain = ?"
            params.append(domain)

        if persona:
            query += " AND persona = ?"
            params.append(persona)

        if min_score is not None:
            query += " AND validation_score >= ?"
            params.append(min_score)

        if max_score is not None:
            query += " AND validation_score <= ?"
            params.append(max_score)

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        records = []
        for row in rows:
            records.append(
                PromptRecord(
                    id=row[0],
                    timestamp=row[1],
                    prompt_text=row[2],
                    prompt_hash=row[3],
                    validation_score=row[4],
                    domain=row[5],
                    persona=row[6],
                    language=row[7],
                    intents=json.loads(row[8]) if row[8] else [],
                    issues_count=row[9],
                    warnings_count=row[10],
                    prompt_length=row[11],
                    ir_version=row[12],
                    tags=json.loads(row[13]) if row[13] else [],
                )
            )

        return records

    def get_summary(
        self,
        days: int = 30,
        domain: Optional[str] = None,
        persona: Optional[str] = None,
    ) -> AnalyticsSummary:
        """
        Get analytics summary for a time period

        Args:
            days: Number of days to analyze
            domain: Filter by domain
            persona: Filter by persona

        Returns:
            AnalyticsSummary object
        """
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        records = self.get_records(
            limit=10000, start_date=start_date, domain=domain, persona=persona
        )

        if not records:
            return AnalyticsSummary()

        scores = [r.validation_score for r in records]
        domains = [r.domain for r in records]
        personas = [r.persona for r in records]
        languages = [r.language for r in records]
        intents_flat = [intent for r in records for intent in r.intents]

        # Calculate statistics
        import statistics

        avg_score = statistics.mean(scores)
        min_score = min(scores)
        max_score = max(scores)
        score_std = statistics.stdev(scores) if len(scores) > 1 else 0.0

        # Top items
        domain_counter = Counter(domains)
        persona_counter = Counter(personas)
        intent_counter = Counter(intents_flat)
        language_counter = Counter(languages)

        # Improvement rate (compare first half vs second half)
        mid = len(records) // 2
        if mid > 0:
            first_half_avg = statistics.mean(scores[:mid])
            second_half_avg = statistics.mean(scores[mid:])
            improvement_rate = ((second_half_avg - first_half_avg) / first_half_avg) * 100
        else:
            improvement_rate = 0.0

        # Most improved domain
        domain_improvements = {}
        for domain_name in set(domains):
            domain_records = [r for r in records if r.domain == domain_name]
            if len(domain_records) > 1:
                domain_mid = len(domain_records) // 2
                domain_first_half = statistics.mean(
                    [r.validation_score for r in domain_records[:domain_mid]]
                )
                domain_second_half = statistics.mean(
                    [r.validation_score for r in domain_records[domain_mid:]]
                )
                domain_improvements[domain_name] = domain_second_half - domain_first_half

        most_improved = (
            max(domain_improvements, key=domain_improvements.get) if domain_improvements else None
        )

        return AnalyticsSummary(
            total_prompts=len(records),
            avg_score=round(avg_score, 2),
            min_score=round(min_score, 2),
            max_score=round(max_score, 2),
            score_std=round(score_std, 2),
            top_domains=domain_counter.most_common(5),
            top_personas=persona_counter.most_common(5),
            top_intents=intent_counter.most_common(5),
            language_distribution=dict(language_counter),
            avg_issues=round(statistics.mean([r.issues_count for r in records]), 2),
            avg_prompt_length=int(statistics.mean([r.prompt_length for r in records])),
            improvement_rate=round(improvement_rate, 2),
            most_improved_domain=most_improved,
        )

    def get_score_trends(self, days: int = 30, bucket_size: int = 1) -> List[Dict[str, Any]]:
        """
        Get score trends over time

        Args:
            days: Number of days to analyze
            bucket_size: Group by N days

        Returns:
            List of {date, avg_score, count} dicts
        """
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        records = self.get_records(limit=10000, start_date=start_date)

        if not records:
            return []

        # Group by date buckets
        from collections import defaultdict

        buckets = defaultdict(list)

        for record in records:
            record_date = datetime.fromisoformat(record.timestamp).date()
            bucket_key = record_date.isoformat()
            buckets[bucket_key].append(record.validation_score)

        # Calculate averages
        trends = []
        for date_str, scores in sorted(buckets.items()):
            import statistics

            trends.append(
                {
                    "date": date_str,
                    "avg_score": round(statistics.mean(scores), 2),
                    "min_score": round(min(scores), 2),
                    "max_score": round(max(scores), 2),
                    "count": len(scores),
                }
            )

        return trends

    def get_domain_breakdown(self, days: int = 30) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed breakdown by domain

        Args:
            days: Number of days to analyze

        Returns:
            Dict of domain -> stats
        """
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        records = self.get_records(limit=10000, start_date=start_date)

        domain_stats = {}

        for domain in set(r.domain for r in records):
            domain_records = [r for r in records if r.domain == domain]

            if domain_records:
                import statistics

                scores = [r.validation_score for r in domain_records]

                domain_stats[domain] = {
                    "count": len(domain_records),
                    "avg_score": round(statistics.mean(scores), 2),
                    "min_score": round(min(scores), 2),
                    "max_score": round(max(scores), 2),
                    "avg_issues": round(
                        statistics.mean([r.issues_count for r in domain_records]), 2
                    ),
                }

        return domain_stats

    def get_stats(self) -> Dict[str, Any]:
        """Get overall database statistics"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM prompt_records")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM prompt_records")
        date_range = cursor.fetchone()

        cursor.execute("SELECT AVG(validation_score) FROM prompt_records")
        avg_score = cursor.fetchone()[0]

        conn.close()

        return {
            "total_records": total,
            "first_record": date_range[0] if date_range[0] else None,
            "last_record": date_range[1] if date_range[1] else None,
            "overall_avg_score": round(avg_score, 2) if avg_score else 0.0,
            "database_path": str(self.db_path),
        }

    def clear_old_records(self, days: int = 90) -> int:
        """
        Delete records older than specified days

        Args:
            days: Keep records from last N days

        Returns:
            Number of deleted records
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("DELETE FROM prompt_records WHERE timestamp < ?", (cutoff_date,))
        deleted = cursor.rowcount

        conn.commit()
        conn.close()

        return deleted


def create_record_from_ir(
    prompt_text: str, ir: Dict[str, Any], validation_result: Optional[Dict[str, Any]] = None
) -> PromptRecord:
    """
    Create a PromptRecord from IR and validation result

    Args:
        prompt_text: Original prompt text
        ir: Compiled IR dictionary
        validation_result: Optional validation result dict

    Returns:
        PromptRecord object
    """
    import hashlib

    prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()[:16]

    score = 0.0
    issues_count = 0
    warnings_count = 0

    if validation_result:
        # Handle ValidationResult object
        if hasattr(validation_result, "score"):
            # It's a ValidationResult object
            score = (
                validation_result.score.total
                if hasattr(validation_result.score, "total")
                else validation_result.score
            )
            issues = validation_result.issues
            issues_count = len(issues)
            warnings_count = validation_result.warnings
        elif isinstance(validation_result.get("score"), dict):
            # It's a dict (backward compatibility)
            score = validation_result["score"].get("total", 0.0)
            issues = validation_result.get("issues", [])
            issues_count = len(issues)
            warnings_count = sum(1 for i in issues if i.get("severity") == "warning")

    return PromptRecord(
        prompt_text=prompt_text[:500],  # Truncate for storage
        prompt_hash=prompt_hash,
        validation_score=score,
        domain=ir.get("domain", "general"),
        persona=ir.get("persona", "assistant"),
        language=ir.get("language", "en"),
        intents=ir.get("intents", []),
        issues_count=issues_count,
        warnings_count=warnings_count,
        prompt_length=len(prompt_text),
        ir_version="v2" if "intents" in ir else "v1",
    )
