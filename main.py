from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Callable, TypeVar
import asyncio
import math
import re
import subprocess
import sys
import traceback
import transition

import pywizlight
import yeelight

from my import AbstractMethodException, dump

class Bulb(ABC):
    @staticmethod
    @abstractmethod
    def get() -> Bulb:
        raise AbstractMethodException()

    @abstractmethod
    def turn_on(self) -> None:
        raise AbstractMethodException()

    @abstractmethod
    def turn_off(self) -> None:
        raise AbstractMethodException()

    @abstractmethod
    def white(self, temperature: int, brightness: int) -> None:
        raise AbstractMethodException()

    @abstractmethod
    def toggle(self) -> None:
        raise AbstractMethodException()

    @abstractmethod
    def general_info(self) -> None:
        raise AbstractMethodException()

    @abstractmethod
    def state_info(self) -> None:
        raise AbstractMethodException()

    @abstractmethod
    def brightness(self) -> int:
        raise AbstractMethodException()


class ColorBulb(Bulb):
    @abstractmethod
    def color(self, red: int, green: int, blue: int, brightness: int) -> None:
        raise AbstractMethodException()

    @staticmethod
    def to_rgb(rgb: int) -> str:
        red = math.floor(rgb / 256 / 256)
        rgb -= red * 256 * 256
        green = math.floor(rgb / 256)
        rgb -= green * 256
        blue = rgb

        return f"{red}, {green}, {blue}"


_Bulb = TypeVar("_Bulb", bound=Bulb)
def discover(get_bulb: Callable[[str], _Bulb | None]) -> _Bulb:
    nr_tries = 1
    for i in range(nr_tries):
        for ip0 in range(100, 105):  # TODO: parallel
            if bulb := get_bulb(f"192.168.0.{ip0}"):
                return bulb

        # bulbs = parallel([(get_bulb, f"192.168.0.{ip0}") for ip0 in range(100, 105)])
        # dump(); print(bulbs)
        # bulbs = list(filter(lambda a: a, bulbs))
        # if bulbs:
        #     return bulbs[0]

        # time.sleep(1)
    raise Exception("can not discover bulb")


class Yeelight(ColorBulb):
    def __init__(self, bulb: yeelight.Bulb) -> None:
        self.__bulb = bulb

    @staticmethod
    def get() -> Yeelight:
        # yeelight.discover_bulbs()

        def get(ip: str) -> Yeelight | None:
            bulb = yeelight.Bulb(ip)
            try:
                # bulb.get_capabilities()
                bulb.get_properties()
                # if run_with_timeout(bulb.get_properties, 1):
            except Exception as exception:
                dump(exception)
                return None
            return Yeelight(bulb)

        return discover(get)

    def turn_on(self) -> None:
        self.__bulb.turn_on()

    def turn_off(self) -> None:
        self.__bulb.turn_off()

    def white(self, temperature: int, brightness: int) -> None:
        self.__bulb.set_brightness(brightness)
        self.__bulb.set_color_temp(temperature)

    def toggle(self) -> None:
        dump()
        self.__bulb.toggle()

    def general_info(self) -> None:
        self.__bulb.get_capabilities()
        self.__bulb.get_model_specs()

    def state_info(self) -> None:
        print(self.__bulb.get_properties())

    def brightness(self) -> int:
        _property = "bright"
        return self.__bulb.get_properties([_property])[_property]

    def color(self, red: int, green: int, blue: int, brightness: int) -> None:
        self.__bulb.set_rgb(red, green, blue)
        self.__bulb.set_brightness(brightness)


def parallel(functions: list):
    dump(len(functions))

    async def coroutine(function):
        if callable(function):
            function()
        else:
            (function[0])(function[1:])

    async def f():
        return await asyncio.gather(*[coroutine(function) for function in functions])
    return asyncio.run(f())


class Wiz(Bulb):
    def __init__(self, bulb: pywizlight.bulb) -> None:
        self.__bulb = bulb

    @staticmethod
    def get() -> Wiz:
        # return Wiz(pywizlight.wizlight("192.168.0.103"))
        # ...
        #
        # async def discover(ip) -> list[pywizlight.wizlight]:
        #     return await pywizlight.discovery.discover_lights(broadcast_space=ip)
        #
        # def join(lists: list[list]) -> list:
        #     return [value for _list in lists for value in _list]
        #
        # if bulbs := join(await asyncio.gather([discover(f"192.168.0.{ip0}") for ip0 in (range(100, 109))])):
        #     return Wiz(bulbs[0])
        # else:
        #     raise Exception("Wiz bulb not found")

        def get(ip: str) -> Wiz | None:
            bulb = pywizlight.wizlight(ip)
            try:
                Wiz.__await_ip(ip, bulb.get_bulbtype)
            # except pywizlight.exceptions.WizLightConnectionError:
            #     return None
            except Exception as exception:
                dump(exception)
                return None
            return Wiz(bulb)

        return discover(get)

    def turn_on(self) -> None:
        self.__await(self.__bulb.turn_on)

    def turn_off(self) -> None:
        self.__await(self.__bulb.turn_off)

    def white(self, temperature: int, brightness: int) -> None:
        brightness = max(0, math.floor(brightness * 2.5656 - 1.5656))
        # await self.__bulb.turn_on(pywizlight.PilotBuilder(brightness=brightness, colortemp=temperature))
        self.__await(self.__bulb.turn_on, [brightness, temperature])

    def toggle(self) -> None:
        self.__await(self.__bulb.lightSwitch)

    def general_info(self) -> None:
        for _callable in [self.__bulb.get_bulbtype,
                          # self.__bulb.getBulbConfig,
                          self.__bulb.getModelConfig]:
            print(self.__await(_callable))

    def state_info(self) -> None:  # TODO: implement
        methods = [method_name for method_name in dir(self.__bulb)
                   # if callable(getattr(self.__bulb, method_name))
                   ]
        dump(methods)

    def brightness(self) -> int:  # TODO: implement
        raise Exception("method not implemented")

    @staticmethod
    def __await_ip(ip: str, method, args: list | None = None) -> str:
        args = [sys.executable,
                re.sub("/[^/]+$", "/wiz.py", sys.argv[0]),
                ip,
                method.__name__,
                *[str(arg) for arg in (args or [])]]
        dump(args)
        res = subprocess.run(args, capture_output=True, text=True)
        if res.stderr:
            raise Exception(res.stderr)
        else:
            return res.stdout

        # result = None
        # def f0():
        #     async def f1():
        #         return await getattr(pywizlight.wizlight(ip), method.__name__)()
        #     nonlocal result
        #     result = asyncio.get_event_loop().run_until_complete(f1())
        # thread = Thread(target=f0)
        # thread.start()
        # thread.join()
        # return result

    def __await(self, method, args: list | None = None) -> str:
        return Wiz.__await_ip(self.__bulb.ip, method, args)


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
        # print(bulb.state_info())
        print(bulb.general_info())


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


class ErrorMode(Mode):
    def __init__(self, description: str) -> None:
        self.__description = description

    def apply(self, bulb: Bulb) -> None:
        print(self.__description, file=sys.stderr)


class WhiteState(transition.State):
    def __init__(self, temperature: int, brightness: int, bulb: Bulb) -> None:
        self.__temperature = temperature
        self.__brightness = brightness
        self.__bulb = bulb

    def __eq__(self, other: WhiteState) -> bool:
        return (self.__temperature == other.__temperature
                and self.__brightness == other.__brightness)

    def apply(self) -> None:
        self.__bulb.white(self.__temperature, self.__brightness)

    @staticmethod
    def avg(a: WhiteState, b: WhiteState, weight_a: float) -> WhiteState:
        return WhiteState(
            WhiteState._value(a.__temperature, b.__temperature, weight_a),
            WhiteState._value(a.__brightness, b.__brightness, weight_a),
            a.__bulb,
        )


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
        transition.Transition()


def parse_time(_time: str) -> datetime:
    if re.match("^\\d+$", _time):
        return datetime.fromtimestamp(int(_time))
    match_hm = re.match("^(\\d{2}):(\\d{2})$", _time)
    if match_hm:
        return datetime.now().replace(hour=int(match_hm[1]), minute=int(match_hm[2]), second=0)
    raise Exception(f"Cannot parse time from {_time}")


class BulbProvider:
    def __init__(self, get_bulb: Callable[[], Bulb]) -> None:
        self.__get = get_bulb

    def get(self) -> Bulb:
        return self.__get()


class Command(ABC):
    @abstractmethod
    def run(self) -> None:
        raise AbstractMethodException()


class BulbCommand(Command):
    def __init__(self, bulb: BulbProvider, mode: Mode) -> None:
        self.__bulb = bulb
        self.__mode = mode

    def run(self) -> None:
        self.__mode.apply(self.__bulb.get())


class CommandGroup(Command):
    def __init__(self, commands: list[Command]) -> None:
        self.__commands = commands

    def run(self) -> None:
        # for command in self.__commands:
        #     command.run()
        parallel([command.run for command in self.__commands])


class Commander(ABC):
    @abstractmethod
    def get(self, keys: list[str]) -> Command:
        raise AbstractMethodException()


class SingleCommand(Commander):
    def __init__(self, command: Command) -> None:
        self.__command = command

    def get(self, keys: list[str]) -> Command:
        if len(keys) == 0:
            return self.__command
        else:
            raise Exception("Unknown option(s): " + " ".join(keys))


class CommandsList(Commander):
    def __init__(self, commands: dict[str, Commander]) -> None:
        self.__commands = commands

    def get(self, keys: list[str]) -> Command:
        if len(keys) > 0 and keys[0] in self.__commands:
            return self.__commands[keys[0]].get(keys[1:])
        else:
            return CommandOptions(list(self.__commands.keys()))


class CommandOptions(Command):
    def __init__(self, options: list[str]) -> None:
        self.__options = options

    def run(self) -> None:
        print("Options:", " ".join(self.__options))


def main() -> None:
    table = BulbProvider(lambda: Yeelight.get())
    corridor = BulbProvider(lambda: Wiz.get())

    white_modes: dict[str, WhiteMode] = {
        "day":      WhiteMode(3500, 100),
        "twilight": WhiteMode(3000, 60),
        "evening":  WhiteMode(3000, 30),
        "night":    WhiteMode(1700, 1),
        # "midnight": ColorMode(190, 100, 0, 1),  # 16736512
    }

    color_modes: dict[str, ColorMode] = {
        "red":   ColorMode(255, 61, 0, 1),
        "green": ColorMode(155, 255, 0, 1),
        "blue":  ColorMode(0, 254, 255, 1),
    }

    transitions: dict[str, TransitionMode] = {
        "transition": TransitionMode(white_modes[sys.argv[2]],
                                     parse_time(sys.argv[3]),
                                     white_modes[sys.argv[4]],
                                     parse_time(sys.argv[5]))
        if len(sys.argv) >= 6 else ErrorMode("Not enough arguments for transition"),
    }

    common_modes: dict[str, Mode] = {
        **white_modes,
        **transitions,
        "on":         StateMode(True),
        "off":        StateMode(False),
        "toggle":     ToggleMode(),
        "info":       InfoMode(),
        "brightness": BrightnessInfoMode(),
    }

    commands = CommandsList({
        **{name: SingleCommand(CommandGroup([BulbCommand(bulb, mode) for bulb in [corridor, table]]))
           for name, mode in common_modes.items()},
        "table": CommandsList({name: SingleCommand(BulbCommand(table, mode)) for name, mode in {
            **color_modes,
            **common_modes,
            # "movie":      color_modes(sys.argv[2]) if len(sys.argv) >= 3 else ErrorMode("Select movie color"),
        }.items()}),
        "corridor": CommandsList({name: SingleCommand(BulbCommand(corridor, mode))
                                  for name, mode in common_modes.items()}),
    })

    command = commands.get(sys.argv[1:])
    command = commands.get(["corridor", "night"])
    command = commands.get(["toggle"])
    command = commands.get(["table", "off"])
    try:
        command.run()
    except Exception as e:
        e_str = (str(e).replace("'", "'\\''"))
        print(e_str, file=sys.stderr)  # TODO: remove
        print(traceback.format_exc())
        subprocess.call(f"alert 'bulb: {e_str}'", shell=True)

    pass


if __name__ == '__main__':
    main()
