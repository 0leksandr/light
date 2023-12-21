from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Callable
import json
import math
import multiprocessing
import re
import subprocess
import sys
import traceback
import transition

import pywizlight
import yeelight

from my import AbstractMethodException, dump


def parallel_all(functions: list[callable]) -> list:
    results = []

    def run_function(func: callable):
        try:
            results.append(func())
        except Exception as e:
            dump(e)

    processes = [multiprocessing.Process(target=run_function, args=(func,)) for func in functions]

    for process in processes:
        process.start()

    for process in processes:
        process.join()

    return results


def parallel_first(functions: list[callable]):  # by ChatGPT
    queue = multiprocessing.Manager().Queue()

    def run_function(func):
        try:
            queue.put(func())
        except Exception as e:
            dump(e)

    processes = [multiprocessing.Process(target=run_function, args=(func,)) for func in functions]

    for process in processes:
        process.start()

    # Wait for the first non-empty result
    result = None
    while result is None and any(process.is_alive() for process in processes):
        result = queue.get()

    # Terminate all processes
    for process in processes:
        if process.is_alive():
            process.terminate()

    # Wait for all processes to finish
    for process in processes:
        process.join()

    return result


class Bulb(ABC):
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
    def print_info(self) -> None:
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


class Yeelight(ColorBulb):
    def __init__(self, bulb: yeelight.Bulb) -> None:
        self.__bulb = bulb

    @staticmethod
    def get() -> Yeelight:
        # yeelight.discover_bulbs()

        exceptions = []
        nr_tries = 10
        for i in range(nr_tries):
            for ip0 in range(100, 105):
                bulb = yeelight.Bulb(f"192.168.0.{ip0}")
                try:
                    # bulb.get_capabilities()
                    bulb.get_properties()
                    # if run_with_timeout(bulb.get_properties, 1):
                    return Yeelight(bulb)
                except yeelight.main.BulbException as exception:
                    exceptions.append(exception)
            # time.sleep(1)
        raise exceptions[-1]

    def turn_on(self) -> None:
        self.__bulb.turn_on()

    def turn_off(self) -> None:
        self.__bulb.turn_off()

    def white(self, temperature: int, brightness: int) -> None:
        self.__bulb.turn_on()
        self.__bulb.set_brightness(brightness)
        self.__bulb.set_color_temp(temperature)

    def toggle(self) -> None:
        self.__bulb.toggle()

    def print_info(self) -> None:
        dump(self.__bulb.get_capabilities())
        dump(self.__bulb.get_model_specs())
        # dump(self.__bulb.get_properties())

    def brightness(self) -> int:
        _property = "bright"
        return self.__bulb.get_properties([_property])[_property]

    def color(self, red: int, green: int, blue: int, brightness: int) -> None:
        self.__bulb.set_rgb(red, green, blue)
        self.__bulb.set_brightness(brightness)


class Wiz(Bulb):
    __bulb = pywizlight.wizlight

    def __init__(self, ip: str) -> None:
        self.__ip = ip

    @staticmethod
    def get(mac: str) -> Wiz:
        def get(ip: str) -> Wiz | None:
            try:
                result = Wiz.__await_ip(ip, pywizlight.wizlight.getMac)
            except Exception:
                return None
            return Wiz(ip) \
                if mac == result \
                else None

        nr_tries = 1  # MAYBE: adjust
        for i in range(nr_tries):
            if bulb := parallel_first([(lambda ip=ip0: get(f"192.168.0.{ip}"))
                                       for ip0 in range(100, 105)]):
                return bulb

            # time.sleep(1)
        raise Exception("can not discover bulb")

    def turn_on(self) -> None:
        self.__await(self.__bulb.turn_on)

    def turn_off(self) -> None:
        self.__await(self.__bulb.turn_off)

    def white(self, temperature: int, brightness: int) -> None:
        brightness = self.__convert_brightness(brightness, False)
        self.__await(self.__bulb.turn_on, [brightness, temperature])

    def toggle(self) -> None:
        self.__await(self.__bulb.lightSwitch)

    def print_info(self) -> None:
        # methods = [method_name for method_name in dir(self.__bulb)
        #            if callable(getattr(self.__bulb, method_name))
        #            ]
        # dump(methods)
        for _callable in [self.__bulb.get_bulbtype,
                          # self.__bulb.getBulbConfig,
                          self.__bulb.getModelConfig]:
            print(self.__await(_callable))

    def brightness(self) -> int:
        result = self.__await(self.__bulb.updateState, post=[pywizlight.bulb.PilotParser.get_brightness])
        return self.__convert_brightness(int(result), True)

    @staticmethod
    def __await_ip(ip: str, method, args: list | None = None, post: list | None = None) -> str:
        args = [sys.executable,
                re.sub("/[^/]+$", "/wiz.py", sys.argv[0]),
                ip,
                method.__name__,
                json.dumps(args or []),
                json.dumps([post_method.__name__ for post_method in (post or [])])]
        res = subprocess.run(args, capture_output=True, text=True)
        if res.stderr:
            raise Exception(res.stderr)
        else:
            return res.stdout.rstrip("\n")

    def __await(self, method, args: list | None = None, post: list | None = None) -> str:
        return Wiz.__await_ip(self.__ip, method, args, post)

    @staticmethod
    def __convert_brightness(value: int, to_percents: bool) -> int:
        if to_percents:
            # return round(value * 99/254 + 155/254)
            return round(value / 255 * 100)
        else:
            # return max(0, math.floor(value * 2.5656 - 1.5656))
            # return round(value * 254/99 - 155/99)
            return round(value / 100 * 255)


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


class MultiCommand(Command):
    def __init__(self, commands: list[Command]) -> None:
        self.__commands = commands

    def run(self) -> None:
        # for command in self.__commands:
        #     command.run()
        parallel_all([command.run for command in self.__commands])


class OptionsCommand(Command):
    def __init__(self, options: list[str]) -> None:
        self.__options = options

    def run(self) -> None:
        print("Options: " + " ".join(self.__options))


class Argument(ABC):
    @abstractmethod
    def convert(self, value: str):
        raise AbstractMethodException()

    @abstractmethod
    def options(self) -> list[str]:
        raise AbstractMethodException()


class ArgumentSelect(Argument):
    def __init__(self, options: dict) -> None:
        self.__options = options

    def convert(self, value: str):
        return self.__options[value] \
            if value in self.__options \
            else None

    def options(self) -> list[str]:
        return list(self.__options.keys())


class TimeArgument(Argument):
    def convert(self, value: str) -> datetime | None:
        if re.match("^\\d+$", value):
            return datetime.fromtimestamp(int(value))
        elif match_hm := re.match("^(\\d{2}):(\\d{2})$", value):
            return datetime.now().replace(hour=int(match_hm[1]), minute=int(match_hm[2]), second=0)
        elif match_hms := re.match("^(\\d{2}):(\\d{2}):(\\d{2})$", value):
            return datetime.now().replace(hour=int(match_hms[1]), minute=int(match_hms[2]), second=match_hms[3])
        else:
            return None

    def options(self) -> list[str]:
        return [datetime.now().strftime("%H:%M")]


class PercentsArgument(Argument):
    def convert(self, value: str) -> int | None:
        if re.match("^\\d+$", value):
            int_val = int(value)
            if int_val <= 100:
                return int_val
        return None

    def options(self) -> list[str]:
        return ["25", "50", "75"]


class Commander(ABC):
    @abstractmethod
    def get(self, keys: list[str]) -> Command:
        raise AbstractMethodException()


class SingleCommander(Commander):
    def __init__(self, command: Command) -> None:
        self.__command = command

    def get(self, keys: list[str]) -> Command:
        if len(keys) == 0:
            return self.__command
        elif keys == ["help"]:
            return OptionsCommand([])
        else:
            raise Exception("Unknown option(s): " + " ".join(keys))


class ListCommander(Commander):
    def __init__(self, commanders: dict[str, Commander]) -> None:
        self.__commanders = commanders

    def get(self, keys: list[str]) -> Command:
        if len(keys) > 0 and keys[0] in self.__commanders:
            return self.__commanders[keys[0]].get(keys[1:])
        else:
            return OptionsCommand(list(self.__commanders.keys()))


class ArgumentsCommander(Commander):
    @staticmethod
    @abstractmethod
    def get_mode(arguments: list) -> Mode:
        raise AbstractMethodException()

    def __init__(self, bulbs: list[BulbProvider], arguments: list[Argument]) -> None:
        self.__bulbs = bulbs
        self.__arguments = arguments

    def get(self, keys: list[str]) -> Command:
        if len(keys) > len(self.__arguments):
            return OptionsCommand([])
        arguments = []
        for i in range(len(keys)):
            argument = self.__arguments[i].convert(keys[i])
            if argument is None:
                return OptionsCommand(self.__arguments[i].options())
            else:
                arguments.append(argument)
        if len(arguments) < len(self.__arguments):
            return OptionsCommand(self.__arguments[len(arguments)].options())
        return MultiCommand([BulbCommand(bulb, self.get_mode(arguments))
                             for bulb in self.__bulbs])


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
        e_str = (str(e).replace("'", "'\\''"))
        print(e_str, file=sys.stderr)  # TODO: remove
        print(traceback.format_exc())
        subprocess.call(f"alert 'bulb: {e_str}'", shell=True)


if __name__ == '__main__':
    main()
