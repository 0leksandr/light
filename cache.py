from __future__ import annotations
from bulb import BrightBulb, BrightWarmBulb, ColorBulb


class CachedBrightBulb(BrightBulb):
    def __init__(self, bulb: BrightBulb) -> None:
        self.__bulb = bulb
        self.__state: bool | None = None
        self.__brightness: int | None = None

    def turn_on(self) -> None:
        if self.__state is not True:
            self.__bulb.turn_on()
            self.__state = True

    def turn_off(self) -> None:
        if self.__state is not False:
            self.__bulb.turn_off()
            self.__state = False

    def toggle(self) -> None:
        self.__bulb.toggle()

    def print_info(self) -> None:
        self.__bulb.print_info()

    def white(self, brightness: int) -> None:
        if self.__brightness is not brightness:
            self.__bulb.white(brightness)
            self.__brightness = brightness

    def brightness(self) -> int:
        if self.__brightness is None:
            self.__brightness = self.__bulb.brightness()
        return self.__brightness
