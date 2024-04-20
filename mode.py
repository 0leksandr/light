from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime

from bulb import SwitchableBulb, BrightBulb, Bulb, ColorBulb, BulbProvider
from parallel import parallel_all
import transition

from my import AbstractMethodException


class Mode(ABC):
    @abstractmethod
    def apply(self, bulb: SwitchableBulb) -> None:
        raise AbstractMethodException()


class TransitiveMode(Mode, ABC):
    @abstractmethod
    def to_state(self, bulb: SwitchableBulb) -> transition.State:
        raise AbstractMethodException()


class BrightMode(TransitiveMode):
    def __init__(self, brightness: int) -> None:
        self.__brightness = brightness

    def apply(self, bulb: BrightBulb) -> None:
        if self.__brightness == 0:
            bulb.turn_off()
        else:
            bulb.white(self.__brightness)

    def to_state(self, bulb: BrightBulb) -> BrightState:
        return BrightState(self.__brightness, bulb)


class WhiteMode(TransitiveMode):
    def __init__(self, temperature: int, brightness: int) -> None:
        self.__temperature = temperature
        self.__brightness = brightness

    def apply(self, bulb: Bulb) -> None:
        if self.__brightness == 0:
            bulb.turn_off()
        else:
            # bulb.turn_on()
            bulb.white(self.__temperature, self.__brightness)

    def to_state(self, bulb: Bulb) -> WhiteState:
        return WhiteState(self.__temperature, self.__brightness, bulb)


class BetweenTransitiveMode(Mode):
    def __init__(self, _from: TransitiveMode, to: TransitiveMode, progress_percents: int) -> None:
        self.__from = _from
        self.__to = to
        self.__progress_percents = progress_percents

    def apply(self, bulb: SwitchableBulb) -> None:
        initial_state = self.__from.to_state(bulb)
        (initial_state
         .avg(initial_state,
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
                 from_mode: TransitiveMode,
                 from_time: datetime,
                 to_mode: TransitiveMode,
                 to_time: datetime) -> None:
        self.__from_mode = from_mode
        self.__from_time = from_time
        self.__to_mode = to_mode
        self.__to_time = to_time

    def apply(self, bulb: SwitchableBulb) -> None:
        trans = transition.Transition(self.__from_mode.to_state(bulb),
                                      self.__from_time,
                                      self.__to_mode.to_state(bulb),
                                      self.__to_time)
        trans.run()


class BrightState(transition.State):
    def __init__(self, brightness: int, bulb: BrightBulb) -> None:
        self.__brightness = brightness
        self.__bulb = bulb

    def __eq__(self, other: BrightState) -> bool:
        return self.__brightness == other.__brightness

    def apply(self) -> None:
        BrightMode(self.__brightness).apply(self.__bulb)

    @staticmethod
    def avg(a: BrightState, b: BrightState, weight_a: float) -> BrightState:
        return BrightState(BrightState._value(a.__brightness, b.__brightness, weight_a),
                           a.__bulb)


class WhiteState(transition.State):
    def __init__(self, temperature: int, brightness: int, bulb: Bulb) -> None:
        self.__temperature = temperature
        self.__brightness = brightness
        self.__bulb = bulb  # MAYBE: remove

    def __eq__(self, other: WhiteState) -> bool:
        return (self.__temperature == other.__temperature
                and self.__brightness == other.__brightness)

    def apply(self) -> None:
        WhiteMode(self.__temperature, self.__brightness).apply(self.__bulb)

    @staticmethod
    def avg(a: WhiteState, b: WhiteState, weight_a: float) -> WhiteState:
        return WhiteState(WhiteState._value(a.__temperature, b.__temperature, weight_a),
                          WhiteState._value(a.__brightness, b.__brightness, weight_a),
                          a.__bulb)


class ScenePart(ABC):
    def apply(self) -> None:
        raise AbstractMethodException()


class BulbMode(ScenePart):  # TODO: rename
    def __init__(self, bulb: BulbProvider, mode: TransitiveMode) -> None:
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

    def get_mode_for_bulb(self, bulb: BulbProvider) -> TransitiveMode:
        for bulb_mode in self.__bulbs_modes:
            if bulb_mode.bulb == bulb:
                return bulb_mode.mode
        raise Exception(f"Can not define mode for bulb {bulb.name()}")
