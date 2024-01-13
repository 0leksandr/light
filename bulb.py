from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable
import json
import math
import subprocess
import sys
import re

import pywizlight
import yeelight

from parallel import parallel_first
from my import AbstractMethodException, dump


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
                                       for ip0 in range(100, 106)]):
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


class BulbProvider:
    def __init__(self, get_bulb: Callable[[], Bulb]) -> None:
        self.__get = get_bulb

    def get(self) -> Bulb:
        return self.__get()
