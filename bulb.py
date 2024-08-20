from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable
import ctypes
import json
import math
import os
import re
import signal
import subprocess
import sys
import time

import pywizlight
import yeelight

from parallel import parallel_first
from my import AbstractMethodException, dump, err


class SwitchableBulb(ABC):
    @abstractmethod
    def turn_on(self) -> None:
        raise AbstractMethodException()

    @abstractmethod
    def turn_off(self) -> None:
        raise AbstractMethodException()

    @abstractmethod
    def toggle(self) -> None:
        raise AbstractMethodException()

    @abstractmethod
    def print_info(self) -> None:
        raise AbstractMethodException()


class BrightBulb(SwitchableBulb, ABC):
    @abstractmethod
    def white(self, brightness: int) -> None:
        raise AbstractMethodException()

    @abstractmethod
    def brightness(self) -> int:
        raise AbstractMethodException()


class BrightWarmBulb(SwitchableBulb, ABC):
    @abstractmethod
    def white(self, temperature: int, brightness: int) -> None:
        raise AbstractMethodException()

    @abstractmethod
    def brightness(self) -> int:
        raise AbstractMethodException()


class ColorBulb(BrightWarmBulb):
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
            for ip0 in range(100, 110):
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


class WizException(Exception):
    pass


class Wiz(BrightWarmBulb):
    __bulb = pywizlight.wizlight

    def __init__(self, ip: str) -> None:
        self.__ip = ip

    @staticmethod
    def get(mac: str) -> Wiz:
        def get(ip: str) -> Wiz | None:
            # noinspection PyUnresolvedReferences
            try:
                result = Wiz.__await_ip(ip, pywizlight.wizlight.getMac)
            except pywizlight.exceptions.WizLightConnectionError:
                return None
            except WizException:
                return None
            return Wiz(ip) \
                if mac == result \
                else None

        # TODO: implement normal timeout in `parallel` - in order to not wait for timeout, when all callables fail
        def timeout() -> False:
            time.sleep(2)
            return False

        if bulb := parallel_first([(lambda ip=ip0: get(f"192.168.0.{ip}"))
                                   for ip0 in range(100, 110)] + [timeout]):
            return bulb
        else:
            raise Exception("can not discover Wiz bulb")

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

    def __await(self, method, args: list | None = None, post: list | None = None) -> str:
        return Wiz.__await_ip(self.__ip, method, args, post)

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
            raise WizException(res.stderr)
        else:
            return res.stdout.rstrip("\n")

    @staticmethod
    def __convert_brightness(value: int, to_percents: bool) -> int:
        if to_percents:
            # return round(value * 99/254 + 155/254)
            return round(value / 255 * 100)
        else:
            # return max(0, math.floor(value * 2.5656 - 1.5656))
            # return round(value * 254/99 - 155/99)
            return round(value / 100 * 255)


# class YeelightBt(BrightBulb):
#     def __init__(self, mac: str) -> None:
#         import yeelightbt  # TODO: move
#         self.__lamp = yeelightbt.Lamp(mac)
#         self.__lamp.connect()
#
#     def turn_on(self) -> None:
#         self.__lamp.turn_on()
#
#     def turn_off(self) -> None:
#         self.__lamp.turn_off()
#
#     def white(self, brightness: int) -> None:
#         raise AbstractMethodException()
#
#     def toggle(self) -> None:
#         raise AbstractMethodException()
#
#     def print_info(self) -> None:
#         print(self.__lamp)
#         dump(self.__lamp.brightness)
#         dump(self.__lamp.temperature)
#         dump(self.__lamp.mode)
#         dump(self.__lamp.state())
#
#     def brightness(self) -> int:
#         raise AbstractMethodException()


class YeelightBt(BrightBulb):
    def __init__(self, mac: str) -> None:
        self.__mac = mac

    def turn_on(self) -> None:
        self.__call("on")

    def turn_off(self) -> None:
        self.__call("off")

    def white(self, brightness: int) -> None:
        self.__call(f"brightness {brightness}")

    def toggle(self) -> None:
        if self.__call()[0]:
            self.turn_off()
        else:
            self.turn_on()

    def print_info(self) -> None:
        self.__call(stdout=True)

    def brightness(self) -> int:
        modes = {
            "Color": 1,
            "White": 2,
            "Flow":  3,
        }
        mode = self.__call()[1]
        return modes[mode] \
            if mode in modes \
            else int(mode)

    def __call(self, cmd: str = "device-info", stdout: bool = False) -> tuple[bool, str]:
        def fn() -> tuple[bool, str]:
            _dir = os.path.dirname(__file__) + "/../python-yeelightbt"
            args = [f"{_dir}/venv/3.11/bin/python",
                    f"{_dir}/yeelightbt/cli.py",
                    "--mac",
                    self.__mac,
                    *(cmd.split(" "))]

            process = subprocess.Popen(args,
                                       text=True,
                                       env={"PYTHONPATH": _dir},
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,
                                       # https://stackoverflow.com/a/19448096/12446338
                                       preexec_fn=lambda: ctypes.CDLL("libc.so.6").prctl(1, signal.SIGTERM))
            _stdout, _stderr = process.communicate()

            if stdout:
                if _stdout: dump(_stdout)
                if _stderr: err(_stderr)

            for line in _stdout.split("\n"):
                if match := re.match(f"^Got notif: <Lamp {self.__mac} is_on\\(([^()]+)\\) mode\\(([^()]+)\\) " +
                                     "rgb\\(\\(2, 7, 8, 0\\)\\) brightness\\(0\\) colortemp\\(0\\)>$",
                                     line):
                    return match[1] == "True", match[2]
            raise Exception("yeelightbt failed")

        def timeout() -> False:
            time.sleep(5)
            return False

        for _ in range(3):
            if result := parallel_first([fn, timeout]):
                return result
        raise Exception(f"cannot call `{cmd}` on yeelightbt")


# MAYBE: use templates
class BulbProvider:
    def __init__(self, name: str, get_bulb: Callable[[], SwitchableBulb]) -> None:
        self.__name = name
        self.__get = get_bulb

    def __eq__(self, other: BulbProvider) -> bool:
        return self.__name == other.__name

    def get(self) -> SwitchableBulb:
        return self.__get()

    def name(self) -> str:
        return self.__name
