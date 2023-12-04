from __future__ import annotations
import subprocess
import transition


class BrightnessState(transition.State):
    def __init__(self, brightness: int) -> None:
        self.__brightness = brightness

    def __eq__(self, other: BrightnessState) -> bool:
        return self.__brightness == other.__brightness

    def apply(self) -> None:
        subprocess.run(["brightness", str(self.__brightness)])

    @staticmethod
    def avg(a: BrightnessState, b: BrightnessState, weight_a: float) -> BrightnessState:
        return BrightnessState(BrightnessState._value(a.__brightness,
                                                      b.__brightness,
                                                      weight_a))
