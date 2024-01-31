from __future__ import annotations
import sys

from bulb import BulbProvider, Wiz, Yeelight
from command import (BulbCommand,
                     SceneCommand,
                     MultiCommand,
                     Commander,
                     SingleCommander,
                     JoinedCommander,
                     ArgumentsCommander,
                     TreeCommander,
                     TransitionCommander,
                     WhiteBetweenCommander)
from err import alert_exception
from mode import (Mode,
                  BulbMode,
                  StateMode,
                  ToggleMode,
                  WhiteMode,
                  ColorMode,
                  InfoMode,
                  BrightnessInfoMode,
                  Scene)


def main() -> None:
    table = BulbProvider("table", lambda: Yeelight.get())
    corridor = BulbProvider("corridor", lambda: Wiz.get("d8a0110a1bd4"))

    all_bulbs = [corridor, table]

    white_scenes: dict[str, Scene] = {
        "day":      Scene([BulbMode(table, WhiteMode(2700, 100)),
                           BulbMode(corridor, WhiteMode(2700, 100))]),
        "twilight": Scene([BulbMode(table, WhiteMode(2700, 60)),
                           BulbMode(corridor, WhiteMode(2700, 80))]),
        "evening":  Scene([BulbMode(table, WhiteMode(2700, 30)),
                           BulbMode(corridor, WhiteMode(2700, 60))]),
        "night":    Scene([BulbMode(table, WhiteMode(1700, 1)),
                           BulbMode(corridor, WhiteMode(1700, 1))]),
    }

    color_modes: dict[str, ColorMode] = {
        "red":   ColorMode(255, 61, 0, 1),
        "green": ColorMode(155, 255, 0, 1),
        "blue":  ColorMode(0, 254, 255, 1),
    }

    common_modes: dict[str, Mode] = {
        "off": StateMode(False),
    }

    bulb_modes: dict[str, Mode] = {
        **common_modes,
        "on":         StateMode(True),
        "toggle":     ToggleMode(),
        "info":       InfoMode(),
        "brightness": BrightnessInfoMode(),
    }

    def dynamic_commander(bulbs: list[BulbProvider]) -> dict[str, ArgumentsCommander]:
        return {
            "transition": TransitionCommander(bulbs, white_scenes),
            "between":    WhiteBetweenCommander(bulbs, white_scenes),
        }

    def bulb_commands(bulb: BulbProvider, modes: list[dict[str, Mode]]) -> TreeCommander:
        dic: dict[str, Commander] = {name: SingleCommander(BulbCommand(bulb, mode))
                                     for modes_dic in modes
                                     for name, mode in modes_dic.items()}
        dic |= dynamic_commander([bulb])
        return TreeCommander(dic)

    commands = JoinedCommander([
        TreeCommander({
            **{name: SingleCommander(SceneCommand(scene)) for name, scene in white_scenes.items()},
            **dynamic_commander(all_bulbs),
            **{name: SingleCommander(MultiCommand([BulbCommand(bulb, mode) for bulb in all_bulbs]))
               for name, mode in common_modes.items()},
            "table":    bulb_commands(table, [color_modes, bulb_modes]),
            "corridor": bulb_commands(corridor, [bulb_modes]),
        }),
        JoinedCommander([TreeCommander({
            bulb_mode.bulb.name(): TreeCommander({name: SingleCommander(BulbCommand(bulb_mode.bulb, bulb_mode.mode))}),
        })
            for name, scene in white_scenes.items()
            for bulb_mode in scene.bulbs_modes()]),
    ])

    command = commands.get(sys.argv[1:])
    try:
        command.run()
    except Exception as e:
        alert_exception(e)


if __name__ == '__main__':
    main()
