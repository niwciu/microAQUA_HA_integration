from dataclasses import dataclass


@dataclass
class MicroAQUACommandState:
    """Mutable state for microAQUA command helpers."""

    no_reg_time: int = 0
