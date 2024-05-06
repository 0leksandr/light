from __future__ import annotations
import subprocess
import sys

from command import TimeArgument
import transition


(channel,
 from_brightness,
 from_time,
 to_brightness,
 to_time) = sys.argv[1:6]


class BrightnessState(transition.State):
    def __init__(self, brightness: int) -> None:
        self.__brightness = brightness

    def __eq__(self, other: BrightnessState) -> bool:
        return self.__brightness == other.__brightness

    def apply(self) -> None:
        subprocess.run(["brightness", "set", channel, str(self.__brightness)])

    @staticmethod
    def avg(a: BrightnessState, b: BrightnessState, weight_a: float) -> BrightnessState:
        return BrightnessState(BrightnessState._value(a.__brightness,
                                                      b.__brightness,
                                                      weight_a))


def main() -> None:
    trans = transition.Transition(BrightnessState(int(from_brightness)),
                                  TimeArgument().convert(from_time),
                                  BrightnessState(int(to_brightness)),
                                  TimeArgument().convert(to_time))
    trans.run()


if __name__ == "__main__":
    main()
