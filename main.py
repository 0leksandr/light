from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
import asyncio
import math
import re
import subprocess
import sys
import time
import transition

import pywizlight
import yeelight


class Bulb(ABC):
    @staticmethod
    @abstractmethod
    def get() -> Bulb:
        raise Exception("abstract method")

    @abstractmethod
    def turn_on(self) -> None:
        raise Exception("abstract method")

    @abstractmethod
    def turn_off(self) -> None:
        raise Exception("abstract method")

    @abstractmethod
    def white(self, temperature: int, brightness: int) -> None:
        raise Exception("abstract method")

    @abstractmethod
    def general_info(self) -> None:
        raise Exception("abstract method")

    @abstractmethod
    def state_info(self) -> None:
        raise Exception("abstract method")


class ColorBulb(Bulb):
    @abstractmethod
    def color(self, red: int, green: int, blue: int, brightness: int) -> None:
        raise Exception("abstract method")

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
        exceptions = []
        ips = range(100, 105)
        nr_tries = 10
        for i in range(nr_tries):
            for ip in ips:
                try:
                    bulb = yeelight.Bulb(f"192.168.0.{ip}")
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

    def state_info(self) -> None:
        print(self.__bulb.get_properties())

    def color(self, red: int, green: int, blue: int, brightness: int) -> None:
        self.__bulb.set_rgb(red, green, blue)
        self.__bulb.set_brightness(brightness)


class Wiz(Bulb):
    def __init__(self, bulb: pywizlight.bulb) -> None:
        self.__bulb = bulb

    @staticmethod
    def get() -> Wiz:
        return Wiz(pywizlight.wizlight("192.168.0.105"))

    def turn_on(self) -> None:
        self.__bulb.turn_on()

    def turn_off(self) -> None:
        self.__bulb.turn_off()

    def white(self, temperature: int, brightness: int) -> None:
        brightness = max(0, math.floor(brightness * 2.5656 - 1.5656))
        self.__bulb.turn_on(pywizlight.PilotBuilder(brightness=brightness, colortemp=temperature))

    def general_info(self) -> None:
        async def f():
            bulb_type = await self.__bulb.get_bulbtype()
            print(bulb_type.features.brightness)  # returns True if brightness is supported
            print(bulb_type.features.color)  # returns True if color is supported
            print(bulb_type.features.color_tmp)  # returns True if color temperatures are supported
            print(bulb_type.features.effect)  # returns True if effects are supported
            print(bulb_type.kelvin_range.max)  # returns max kelvin in INT
            print(bulb_type.kelvin_range.min)  # returns min kelvin in INT
            print(bulb_type.name)  # returns the module name of the bulb
        asyncio.run(f())


class Mode(ABC):
    @abstractmethod
    def apply(self, bulb: yeelight.Bulb) -> None:
        raise Exception("abstract method")


# class ComboMode(Mode):
#     def __init__(self, modes: list) -> None:
#         self.modes = modes
#
#     def apply(self, bulb: yeelight.Bulb) -> None:
#         for mode in self.modes:
#             mode.apply(bulb)


class WhiteMode(Mode):
    def __init__(self, temperature: int, brightness: int) -> None:
        self.__temperature = temperature
        self.__brightness = brightness

    def apply(self, bulb: yeelight.Bulb) -> None:
        bulb.turn_on()
        bulb.set_brightness(self.__brightness)
        bulb.set_color_temp(self.__temperature)

    @staticmethod
    def avg(a: WhiteMode, b: WhiteMode, weight_a: float) -> WhiteMode:
        def value(_a: int, _b: int) -> int:
            return int(_a * weight_a + _b * (1 - weight_a))
        return WhiteMode(value(a.__temperature, b.__temperature),
                               value(a.__brightness, b.__brightness))


class StateMode(Mode):
    def __init__(self, state: bool) -> None:
        self.state = state

    def apply(self, bulb: yeelight.Bulb) -> None:
        if self.state:
            bulb.turn_on()
        else:
            bulb.turn_off()


class ToggleMode(Mode):
    def apply(self, bulb: yeelight.Bulb) -> None:
        bulb.toggle()


class InfoMode(Mode):
    def apply(self, bulb: yeelight.Bulb) -> None:
        print(bulb.get_properties())


class BrightnessInfoMode(Mode):
    def apply(self, bulb: yeelight.Bulb) -> None:
        _property = "bright"
        print(bulb.get_properties([_property])[_property])


class ColorMode(Mode):
    def __init__(self, red: int, green: int, blue: int, brightness: int) -> None:
        self.__red = red
        self.__green = green
        self.__blue = blue
        self.__brightness = brightness

    def apply(self, bulb: yeelight.Bulb) -> None:
        bulb.turn_on()
        bulb.set_rgb(self.__red, self.__green, self.__blue)
        bulb.set_brightness(self.__brightness)

    @staticmethod
    def avg(a: ColorMode, b: ColorMode, weight_a: float) -> ColorMode:
        def value(_a: int, _b: int) -> int:
            return int(_a * weight_a + _b * (1 - weight_a))
        return ColorMode(value(a.__red, b.__red),
                         value(a.__green, b.__green),
                         value(a.__blue, b.__blue),
                         value(a.__brightness, b.__brightness))

    @staticmethod
    def to_rgb(rgb: int) -> str:
        red = math.floor(rgb / 256 / 256)
        rgb -= red * 256 * 256
        green = math.floor(rgb / 256)
        rgb -= green * 256
        blue = rgb

        return f"{red}, {green}, {blue}"


class ErrorMode(Mode):
    def __init__(self, description: str) -> None:
        self.__description = description

    def apply(self, bulb: yeelight.Bulb) -> None:
        print(self.__description, file=sys.stderr)


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

    def apply(self, bulb: yeelight.Bulb) -> None:
        timeout_seconds = 60

        interval_seconds = (self.__to_time - self.__from_time).total_seconds()
        if interval_seconds < 0:
            self.__tick(bulb, 0)
            return
        last_update: Optional[datetime] = None
        while True:
            now = datetime.now()
            progress = (now - self.__from_time).total_seconds() / interval_seconds
            if progress < 0:
                raise "progress < 0"
            if progress >= 1:
                self.__tick(bulb, 1)
                return
            if last_update is None or (now - last_update).total_seconds() >= timeout_seconds:
                if self.__tick(bulb, progress):
                    last_update = now
            time.sleep(1)

    def __tick(self, bulb: yeelight.Bulb, progress: float) -> bool:
        light_mode = WhiteMode.avg(self.__from_mode, self.__to_mode, 1 - progress)
        try:
            light_mode.apply(bulb)
            return True
        except Exception:
            return False


def get_bulb() -> yeelight.Bulb:
    exceptions = []
    ips = range(100, 105)
    nr_tries = 10
    for i in range(nr_tries):
        for ip in ips:
            try:
                bulb = yeelight.Bulb(f"192.168.0.{ip}")
                # bulb.get_capabilities()
                bulb.get_properties()
                # if run_with_timeout(bulb.get_properties, 1):
                return bulb
            except Exception as exception:
                exceptions.append(exception)
        # time.sleep(1)
    raise exceptions[-1]


def parse_time(_time: str) -> datetime:
    if re.match("^\\d+$", _time):
        return datetime.fromtimestamp(int(_time))
    match_hm = re.match("^(\\d{2}):(\\d{2})$", _time)
    if match_hm:
        return datetime.now().replace(hour=int(match_hm[1]), minute=int(match_hm[2]), second=0)
    raise Exception(f"Cannot parse time from {_time}")


if __name__ == '__main__':
    light_modes = {
        "day":      WhiteMode(3500, 100),
        "twilight": WhiteMode(3000, 60),
        "evening":  WhiteMode(3000, 30),
        "night":    WhiteMode(1700, 1),
        # "night":    ColorMode(190, 100, 0, 1),  # 16736512
    }

    color_modes = {
        "red":   ColorMode(255, 61, 0, 1),
        "green": ColorMode(155, 255, 0, 1),
        "blue":  ColorMode(0, 254, 255, 1),
    }

    modes = {
        **light_modes,
        **color_modes,
        "on":         StateMode(True),
        "off":        StateMode(False),
        "toggle":     ToggleMode(),
        "info":       InfoMode(),
        "brightness": BrightnessInfoMode(),
        # "movie":      color_modes(sys.argv[2]) if len(sys.argv) >= 3 else ErrorMode("Select movie color"),
        "transition": TransitionMode(light_modes[sys.argv[2]],
                                     parse_time(sys.argv[3]),
                                     light_modes[sys.argv[4]],
                                     parse_time(sys.argv[5]))
        if len(sys.argv) >= 6 else ErrorMode("Not enough arguments for transition"),
    }

    # yeelight.discover_bulbs()

    mode = sys.argv[1] if len(sys.argv) > 1 else None
    if mode in modes:
        try:
            modes[mode].apply(get_bulb())
        except Exception as e:
            e_str = str(e).replace("'", "\\'")
            subprocess.call(f"alert 'bulb: {e_str}'", shell=True)
    else:
        print("Options:", " ".join(modes.keys()))

    pass
