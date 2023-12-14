from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Callable
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
                try:
                    bulb = yeelight.Bulb(f"192.168.0.{ip0}")
                    # bulb.get_capabilities()
                    bulb.get_properties()
                    # if run_with_timeout(bulb.get_properties, 1):
                    return Yeelight(bulb)
                except Exception as exception:
                    exceptions.append(exception)
            # time.sleep(1)
        raise exceptions[-1]

    def turn_on(self) -> None:
        self.__bulb.turn_on()

    def turn_off(self) -> None:
        self.__bulb.turn_off()

    def white(self, temperature: int, brightness: int) -> None:
        self.__bulb.set_brightness(brightness)
        self.__bulb.set_color_temp(temperature)

    def toggle(self) -> None:
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


def parallel_all(functions: list) -> list:
    results = []

    def run_function(func):
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


class Wiz(Bulb):
    __bulb = pywizlight.wizlight

    def __init__(self, ip: str) -> None:
        self.__ip = ip

    @staticmethod
    def get() -> Wiz:
        def get(ip: str) -> Wiz | None:
            try:
                Wiz.__await_ip(ip, pywizlight.wizlight.get_bulbtype)
            except Exception:
                return None
            return Wiz(ip)

        nr_tries = 10
        for i in range(nr_tries):
            bulb = parallel_first([(lambda ip=ip0: get(f"192.168.0.{ip}"))
                                   for ip0 in range(100, 105)])
            if bulb:
                return bulb

            # time.sleep(1)
        raise Exception("can not discover bulb")

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
        res = subprocess.run(args, capture_output=True, text=True)
        if res.stderr:
            raise Exception(res.stderr)
        else:
            return res.stdout

    def __await(self, method, args: list | None = None) -> str:
        return Wiz.__await_ip(self.__ip, method, args)


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


class TransitionCommander(Commander):
    def __init__(self, bulbs: list[BulbProvider], modes: dict[str, WhiteMode]) -> None:
        self.__bulbs = bulbs
        self.__arguments = [ArgumentSelect(modes),
                            TimeArgument(),
                            ArgumentSelect(modes),
                            TimeArgument()]

    def get(self, keys: list[str]) -> Command:
        arguments = []
        for i in range(len(keys)):
            argument = self.__arguments[i].convert(keys[i])
            if argument is None:
                return OptionsCommand(self.__arguments[i].options())
            else:
                arguments.append(argument)
        if len(arguments) < len(self.__arguments):
            return OptionsCommand(self.__arguments[len(arguments)].options())
        return MultiCommand([BulbCommand(bulb, TransitionMode(*arguments))
                             for bulb in self.__bulbs])


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

    common_modes: dict[str, Mode] = {
        **white_modes,
        "on":         StateMode(True),
        "off":        StateMode(False),
        "toggle":     ToggleMode(),
        "info":       InfoMode(),
        "brightness": BrightnessInfoMode(),
    }

    def transition_commander(bulbs: list[BulbProvider]) -> dict[str, TransitionCommander]:
        return {"transition": TransitionCommander(bulbs, white_modes)}

    def bulb_commands(bulb: BulbProvider, modes: list[dict[str, Mode]]) -> ListCommander:
        dic: dict[str, Commander] = {name: SingleCommander(BulbCommand(bulb, mode))
                                     for modes_dic in modes
                                     for name, mode in modes_dic.items()}
        dic |= transition_commander([bulb])
        return ListCommander(dic)

    commands = ListCommander({
        **{name: SingleCommander(MultiCommand([BulbCommand(bulb, mode) for bulb in [corridor, table]]))
           for name, mode in common_modes.items()},
        **transition_commander([corridor, table]),
        "table": bulb_commands(table, [color_modes, common_modes]),
        "corridor": bulb_commands(corridor, [common_modes]),
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
    start = datetime.now()
    main()
    dump(datetime.now() - start)
