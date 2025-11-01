"""
Risk scoring service for document validation.
"""

from typing import Dict, List, Optional

try:
    from backend.models.document import (
        FormatAnalysisResult, AuthenticityCheck,
        RiskJustification, RiskAssessment
    )
except ModuleNotFoundError:
    from models.document import (
        FormatAnalysisResult, AuthenticityCheck,
        RiskJustification, RiskAssessment
    )


class RiskScoringService:
    """Service for calculating deterministic risk scores."""

    def calculate_format_risk(
        self,
        format_result: FormatAnalysisResult,
        template: Dict
    ) -> tuple[float, List[RiskJustification]]:
        """Calculate risk score from format analysis.

        Args:
            format_result: Format analysis results
            template: Document template with rules

        Returns:
            Tuple of (risk_score, justifications)
        """
        justifications = []
        score = 0.0

        # Get formatting rules from template
        formatting_rules = template.get("spacing_rules", {})
        max_spell_error = template.get("spelling_error_rate_max", 0.05)

        # Check spelling error rate
        if format_result.spell_error_rate > max_spell_error:
            severity = min(int((format_result.spell_error_rate / max_spell_error) * 10), 10)
            score += severity * 3
            justifications.append(RiskJustification(
                category="format",
                severity=severity,
                reason=f"Spelling error rate {format_result.spell_error_rate:.2%} exceeds threshold {max_spell_error:.2%}",
                evidence={"spell_error_rate": format_result.spell_error_rate}
            ))

        # Check double spaces
        max_double_spaces = formatting_rules.get("max_double_space_ratio", 0.05)
        if format_result.double_space_count > 0:
            severity = min(format_result.double_space_count // 5, 5)
            score += severity * 2
            justifications.append(RiskJustification(
                category="format",
                severity=severity,
                reason=f"Found {format_result.double_space_count} double space occurrences",
                evidence={"double_space_count": format_result.double_space_count}
            ))

        # Check tabs
        max_tabs = formatting_rules.get("max_tabs", 20)
        if format_result.tab_count > max_tabs:
            severity = min((format_result.tab_count - max_tabs) // 5, 5)
            score += severity * 2
            justifications.append(RiskJustification(
                category="format",
                severity=severity,
                reason=f"Excessive tabs ({format_result.tab_count} > {max_tabs})",
                evidence={"tab_count": format_result.tab_count}
            ))

        # Check section coverage
        if format_result.section_coverage < 0.7:
            severity = int((1.0 - format_result.section_coverage) * 10)
            score += severity * 4
            justifications.append(RiskJustification(
                category="format",
                severity=severity,
                reason=f"Low section coverage: {format_result.section_coverage:.0%} (missing: {', '.join(format_result.missing_sections)})",
                evidence={
                    "section_coverage": format_result.section_coverage,
                    "missing_sections": format_result.missing_sections
                }
            ))

        # Apply risk overrides from template
        risk_overrides = template.get("risk_overrides", {})
        if risk_overrides and format_result.missing_sections:
            severity = risk_overrides.get("missing_section", 3)
            score += severity * len(format_result.missing_sections)

        return min(score, 100.0), justifications

    def calculate_authenticity_risk(
        self,
        auth_check: Optional[AuthenticityCheck]
    ) -> tuple[float, List[RiskJustification]]:
        """Calculate risk score from authenticity check.

        Args:
            auth_check: Authenticity check results

        Returns:
            Tuple of (risk_score, justifications)
        """
        if not auth_check or not auth_check.applicable:
            return 0.0, []

        justifications = []
        score = 0.0

        # Check EXIF
        if auth_check.exif:
            if not auth_check.exif.present:
                score += 15
                justifications.append(RiskJustification(
                    category="authenticity",
                    severity=5,
                    reason="No EXIF metadata present",
                    evidence={"exif_present": False}
                ))
            elif auth_check.exif.anomalies:
                severity = min(len(auth_check.exif.anomalies) * 2, 8)
                score += severity * 3
                justifications.append(RiskJustification(
                    category="authenticity",
                    severity=severity,
                    reason=f"EXIF anomalies detected: {', '.join(auth_check.exif.anomalies)}",
                    evidence={"anomalies": auth_check.exif.anomalies}
                ))

        # Check pHash duplicates
        if auth_check.phash and auth_check.phash.duplicates_found:
            severity = min(len(auth_check.phash.duplicates_found) * 3, 10)
            score += severity * 4
            justifications.append(RiskJustification(
                category="duplication",
                severity=severity,
                reason=f"Found {len(auth_check.phash.duplicates_found)} duplicate/similar images in corpus",
                evidence={
                    "duplicates": auth_check.phash.duplicates_found,
                    "similarities": auth_check.phash.similarity_scores
                }
            ))

        # Check ELA tampering
        if auth_check.ela and auth_check.ela.anomaly_detected:
            severity = int(auth_check.ela.confidence * 10)
            score += severity * 5
            justifications.append(RiskJustification(
                category="authenticity",
                severity=severity,
                reason=f"Tampering detected via ELA (mean: {auth_check.ela.mean_score:.1f}, var: {auth_check.ela.variance:.1f})",
                evidence={
                    "ela_mean": auth_check.ela.mean_score,
                    "ela_variance": auth_check.ela.variance
                }
            ))

        # Check reverse image search
        if auth_check.reverse_search and auth_check.reverse_search.total_matches > 0:
            severity = min(auth_check.reverse_search.total_matches, 10)
            score += severity * 3
            justifications.append(RiskJustification(
                category="duplication",
                severity=severity,
                reason=f"Image found on {auth_check.reverse_search.total_matches} external sites",
                evidence={
                    "total_matches": auth_check.reverse_search.total_matches,
                    "exact_matches": len(auth_check.reverse_search.exact_matches)
                }
            ))

        # Check AI generation
        if auth_check.ai_generation and auth_check.ai_generation.likelihood > 0.5:
            severity = int(auth_check.ai_generation.likelihood * 10)
            score += severity * 4
            justifications.append(RiskJustification(
                category="authenticity",
                severity=severity,
                reason=f"AI generation likelihood: {auth_check.ai_generation.likelihood:.0%} ({', '.join(auth_check.ai_generation.indicators)})",
                evidence={
                    "likelihood": auth_check.ai_generation.likelihood,
                    "indicators": auth_check.ai_generation.indicators
                }
            ))

        return min(score, 100.0), justifications

    def aggregate_risk_score(
        self,
        format_risk: float,
        format_justifications: List[RiskJustification],
        authenticity_risk: float,
        authenticity_justifications: List[RiskJustification]
    ) -> RiskAssessment:
        """Aggregate format and authenticity risks into overall score.

        Args:
            format_risk: Format risk score (0-100)
            format_justifications: Format risk justifications
            authenticity_risk: Authenticity risk score (0-100)
            authenticity_justifications: Authenticity justifications

        Returns:
            RiskAssessment with overall score and level
        """
        # Weighted average (60% format, 40% authenticity)
        overall_score = (format_risk * 0.6) + (authenticity_risk * 0.4)

        # Determine risk level
        if overall_score < 30:
            risk_level = "Low"
        elif overall_score < 60:
            risk_level = "Med"
        else:
            risk_level = "High"

        # Combine justifications
        all_justifications = format_justifications + authenticity_justifications

        # Sort by severity (highest first)
        all_justifications.sort(key=lambda j: j.severity, reverse=True)

        return RiskAssessment(
            overall_score=overall_score,
            risk_level=risk_level,
            format_risk=format_risk,
            authenticity_risk=authenticity_risk,
            justifications=all_justifications
        )


# Singleton instance
risk_scoring_service = RiskScoringService()
