from __future__ import annotations
from abc import ABC, abstractmethod

from bulb import Bulb

from my import AbstractMethodException


class Mode(ABC):
    @abstractmethod
    def apply(self, bulb: Bulb) -> None:
        raise AbstractMethodException()
