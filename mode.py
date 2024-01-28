from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime

from bulb import Bulb, ColorBulb, BulbProvider
from parallel import parallel_all
import transition

from my import AbstractMethodException


class Mode(ABC):
    @abstractmethod
    def apply(self, bulb: Bulb) -> None:
        raise AbstractMethodException()


class WhiteMode(Mode):
    def __init__(self, temperature: int, brightness: int) -> None:
        self.__temperature = temperature
        self.__brightness = brightness

    def apply(self, bulb: Bulb) -> None:
        # bulb.turn_on()
        bulb.white(self.__temperature, self.__brightness)

    def to_state(self, bulb: Bulb) -> WhiteState:
        return WhiteState(self.__temperature, self.__brightness, bulb)


class WhiteBetweenMode(Mode):
    def __init__(self, _from: WhiteMode, to: WhiteMode, progress_percents: int) -> None:
        self.__from = _from
        self.__to = to
        self.__progress_percents = progress_percents

    def apply(self, bulb: Bulb) -> None:
        (WhiteState
         .avg(self.__from.to_state(bulb),
              self.__to.to_state(bulb),
              1 - self.__progress_percents / 100)
         .apply())


class StateMode(Mode):
    def __init__(self, state: bool) -> None:
        self.state = state

    def apply(self, bulb: Bulb) -> None:
        if self.state:
            bulb.turn_on()
        else:
            bulb.turn_off()


class ToggleMode(Mode):
    def apply(self, bulb: Bulb) -> None:
        bulb.toggle()


class InfoMode(Mode):
    def apply(self, bulb: Bulb) -> None:
        bulb.print_info()


class BrightnessInfoMode(Mode):
    def apply(self, bulb: Bulb) -> None:
        print(bulb.brightness())


class ColorMode(Mode):
    def __init__(self, red: int, green: int, blue: int, brightness: int) -> None:
        self.__red = red
        self.__green = green
        self.__blue = blue
        self.__brightness = brightness

    def apply(self, bulb: ColorBulb) -> None:
        bulb.turn_on()
        bulb.color(self.__red, self.__green, self.__blue, self.__brightness)


class TransitionMode(Mode):
    def __init__(self,
                 from_mode: WhiteMode,
                 from_time: datetime,
                 to_mode: WhiteMode,
                 to_time: datetime) -> None:
        self.__from_mode = from_mode
        self.__from_time = from_time
        self.__to_mode = to_mode
        self.__to_time = to_time

    def apply(self, bulb: Bulb) -> None:
        trans = transition.Transition(self.__from_mode.to_state(bulb),
                                      self.__from_time,
                                      self.__to_mode.to_state(bulb),
                                      self.__to_time)
        trans.run()


class WhiteState(transition.State):
    def __init__(self, temperature: int, brightness: int, bulb: Bulb) -> None:
        self.__temperature = temperature
        self.__brightness = brightness
        self.__bulb = bulb  # MAYBE: remove

    def __eq__(self, other: WhiteState) -> bool:
        return (self.__temperature == other.__temperature
                and self.__brightness == other.__brightness)

    def apply(self) -> None:
        self.__bulb.white(self.__temperature, self.__brightness)

    @staticmethod
    def avg(a: WhiteState, b: WhiteState, weight_a: float) -> WhiteState:
        return WhiteState(WhiteState._value(a.__temperature, b.__temperature, weight_a),
                          WhiteState._value(a.__brightness, b.__brightness, weight_a),
                          a.__bulb)


class ScenePart(ABC):
    def apply(self) -> None:
        raise AbstractMethodException()


class BulbMode(ScenePart):  # TODO: rename
    def __init__(self, bulb: BulbProvider, mode: WhiteMode) -> None:
        self.bulb = bulb
        self.mode = mode

    def apply(self) -> None:
        self.mode.apply(self.bulb.get())


class Scene(ScenePart):
    def __init__(self, bulbs_modes: list[BulbMode]) -> None:
        self.__bulbs_modes = bulbs_modes

    def apply(self) -> None:
        parallel_all([mode.apply for mode in self.__bulbs_modes])

    def bulbs_modes(self) -> list[BulbMode]:
        return self.__bulbs_modes

    def get_mode_for_bulb(self, bulb: BulbProvider) -> WhiteMode:
        for bulb_mode in self.__bulbs_modes:
            if bulb_mode.bulb == bulb:
                return bulb_mode.mode
        raise Exception(f"Can not define mode for bulb {bulb.name()}")
