from dataclasses import dataclass
from typing import List
from datetime import datetime, timezone


@dataclass
class AlertRule:
    symbol_y: str
    symbol_x: str
    threshold: float  # absolute z-score threshold
    direction: str = "both"  # 'above', 'below', 'both'


@dataclass
class AlertEvent:
    ts: datetime
    message: str


class AlertManager:
    def __init__(self):
        self.rules: List[AlertRule] = []
        self.events: List[AlertEvent] = []

    def add_rule(self, rule: AlertRule):
        self.rules.append(rule)

    def clear_rules(self):
        self.rules.clear()

    def clear_events(self):
        self.events.clear()

    def evaluate(self, symbol_y: str, symbol_x: str, z_last: float):
        if z_last is None or z_last != z_last:  # NaN check
            return
        for r in self.rules:
            if r.symbol_y == symbol_y and r.symbol_x == symbol_x:
                fire = False
                if r.direction == "both" and abs(z_last) >= r.threshold:
                    fire = True
                elif r.direction == "above" and z_last >= r.threshold:
                    fire = True
                elif r.direction == "below" and z_last <= -r.threshold:
                    fire = True
                if fire:
                    self.events.append(AlertEvent(datetime.now(timezone.utc), f"Alert {symbol_y}/{symbol_x}: z={z_last:.2f} threshold={r.threshold}"))
