from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from my import AbstractMethodException
from typing import TypeVar
import time


class State(ABC):
    @abstractmethod
    def __eq__(self, other: State) -> bool:
        raise AbstractMethodException()

    @abstractmethod
    def apply(self) -> None:
        raise AbstractMethodException()

    @staticmethod
    @abstractmethod
    def avg(a: TheState, b: TheState, weight_a: float) -> TheState:
        raise AbstractMethodException()

    @staticmethod
    def _value(_a: int, _b: int, weight_a: float) -> int:
        return int(_a * weight_a + _b * (1 - weight_a))


TheState = TypeVar('TheState', bound=State)


class Transition:
    def __init__(self,
                 from_state: TheState,
                 from_time: datetime,
                 to_state: TheState,
                 to_time: datetime) -> None:
        self.__from_state = from_state
        self.__from_time = from_time
        self.__to_state = to_state
        self.__to_time = to_time
        self.__state: TheState | None = None

    def run(self) -> None:
        interval_seconds = (self.__to_time - self.__from_time).total_seconds()
        if interval_seconds < 0:
            self.__tick(0)
            return
        while True:
            now = datetime.now()
            progress = (now - self.__from_time).total_seconds() / interval_seconds
            if progress < 0:
                raise Exception("progress < 0")
            if progress >= 1:
                self.__tick(1)
                return
            self.__tick(progress)
            time.sleep(1)

    def __tick(self, progress: float) -> None:
        state = self.__from_state.avg(self.__from_state, self.__to_state, 1 - progress)
        if self.__state is None or self.__state != state:
            try:
                state.apply()
            except Exception:
                return
            self.__state = state
