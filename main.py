from __future__ import annotations
import subprocess
import sys
import traceback

from bulb import BulbProvider, Wiz, Yeelight
from command import (BulbCommand,
                     MultiCommand,
                     Commander,
                     SingleCommander,
                     ArgumentsCommander,
                     ListCommander,
                     TransitionCommander,
                     WhiteBetweenCommander)
from mode import (Mode,
                  StateMode,
                  ToggleMode,
                  WhiteMode,
                  ColorMode,
                  InfoMode,
                  BrightnessInfoMode)


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
