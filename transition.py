from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TypeVar, Optional
import time


class State(ABC):
    @abstractmethod
    def __eq__(self, other: State) -> bool:
        raise Exception("abstract method")

    @abstractmethod
    def apply(self) -> None:
        raise Exception("abstract method")

    @abstractmethod
    def avg(self, a: TheState, b: TheState, weight_a: float) -> TheState:
        raise Exception("abstract method")

    @staticmethod
    def _value(_a: int, _b: int, weight_a: float) -> int:
        return int(_a * weight_a + _b * (1 - weight_a))


TheState = TypeVar('TheState', bound=State)


class Transition:
    def __init__(
            self,
            from_state: TheState,
            from_time: datetime,
            to_state: TheState,
            to_time: datetime,
    ) -> None:
        self.__from_state = from_state
        self.__from_time = from_time
        self.__to_state = to_state
        self.__to_time = to_time
        self.__state: TheState | None = None

    async def run(self) -> None:
        timeout_seconds = 60

        interval_seconds = (self.__to_time - self.__from_time).total_seconds()
        if interval_seconds < 0:
            self.__tick(0)
            return
        last_update: Optional[datetime] = None
        while True:
            now = datetime.now()
            progress = (now - self.__from_time).total_seconds() / interval_seconds
            if progress < 0:
                raise "progress < 0"
            if progress >= 1:
                self.__tick(1)
                return
            if last_update is None or (now - last_update).total_seconds() >= timeout_seconds:
                if self.__tick(progress):
                    last_update = now
            time.sleep(1)

    def __tick(self, progress: float) -> bool:
        state = self.__from_state.avg(self.__from_state, self.__to_state, 1 - progress)
        if self.__state == state:
            return True
        else:
            try:
                state.apply()
                self.__state = state
                return True
            except Exception:
                return False
