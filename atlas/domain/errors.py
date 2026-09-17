"""Business-rule violations are first-class errors: they are logged and shipped like crashes."""

from __future__ import annotations


class BusinessRuleViolation(Exception):
    """A request that is well-formed but violates a rule of the business."""

    def __init__(self, rule: str, detail: str, customer_impact: int = 1):
        super().__init__(f"{rule}: {detail}")
        self.rule = rule
        self.detail = detail
        self.customer_impact = customer_impact
