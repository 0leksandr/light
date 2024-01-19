from __future__ import annotations
from datetime import datetime
import subprocess
import sys
import traceback
import transition

from bulb import Bulb, ColorBulb, BulbProvider, Wiz, Yeelight
from command import (ArgumentSelect,
                     PercentsArgument,
                     TimeArgument,
                     Commander,
                     SingleCommander,
                     ArgumentsCommander,
                     ListCommander,
                     BulbCommand,
                     MultiCommand)
from mode import Mode


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


class TransitionCommander(ArgumentsCommander):
    def __init__(self, bulbs: list[BulbProvider], modes: dict[str, WhiteMode]) -> None:
        super().__init__(bulbs,
                         [ArgumentSelect(modes),
                          TimeArgument(),
                          ArgumentSelect(modes),
                          TimeArgument()])

    @staticmethod
    def get_mode(arguments: list) -> Mode:
        return TransitionMode(*arguments)


class WhiteBetweenCommander(ArgumentsCommander):
    def __init__(self, bulbs: list[BulbProvider], modes: dict[str, WhiteMode]) -> None:
        super().__init__(bulbs,
                         [ArgumentSelect(modes),
                          ArgumentSelect(modes),
                          PercentsArgument()])

    @staticmethod
    def get_mode(arguments: list) -> Mode:
        return WhiteBetweenMode(*arguments)


def main() -> None:
    table = BulbProvider(lambda: Yeelight.get())
    corridor = BulbProvider(lambda: Wiz.get("d8a0110a1bd4"))

    white_modes: dict[str, WhiteMode] = {
        "day":      WhiteMode(2700, 100),
        "twilight": WhiteMode(2700, 60),
        "evening":  WhiteMode(2700, 30),
        "night":    WhiteMode(1700, 1),
    }

    color_modes: dict[str, ColorMode] = {
        "red":   ColorMode(255, 61, 0, 1),
        "green": ColorMode(155, 255, 0, 1),
        "blue":  ColorMode(0, 254, 255, 1),
    }

    common_modes: dict[str, Mode] = {
        **white_modes,
        "on":     StateMode(True),
        "off":    StateMode(False),
        "toggle": ToggleMode(),
    }

    bulb_modes: dict[str, Mode] = {
        "info":       InfoMode(),
        "brightness": BrightnessInfoMode(),
    }

    def dynamic_commander(bulbs: list[BulbProvider]) -> dict[str, ArgumentsCommander]:
        return {
            "transition": TransitionCommander(bulbs, white_modes),
            "between":    WhiteBetweenCommander(bulbs, white_modes),
        }

    def bulb_commands(bulb: BulbProvider, modes: list[dict[str, Mode]]) -> ListCommander:
        dic: dict[str, Commander] = {name: SingleCommander(BulbCommand(bulb, mode))
                                     for modes_dic in modes
                                     for name, mode in modes_dic.items()}
        dic |= dynamic_commander([bulb])
        return ListCommander(dic)

    commands = ListCommander({
        **{name: SingleCommander(MultiCommand([BulbCommand(bulb, mode) for bulb in [corridor, table]]))
           for name, mode in common_modes.items()},
        **dynamic_commander([corridor, table]),
        "table":    bulb_commands(table, [color_modes, common_modes, bulb_modes]),
        "corridor": bulb_commands(corridor, [common_modes, bulb_modes]),
    })

    command = commands.get(sys.argv[1:])
    try:
        command.run()
    except Exception as e:
        e_str = str(e).replace("'", "'\\''")
        print(e_str, file=sys.stderr)  # TODO: remove
        print(traceback.format_exc())
        subprocess.call(f"alert 'bulb: {e_str}'", shell=True)


if __name__ == '__main__':
    main()
