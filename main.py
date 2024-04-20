from __future__ import annotations
import sys

from bulb import BulbProvider, Wiz, Yeelight, YeelightBt
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
                  BrightMode,
                  BrightWarmMode,
                  ColorMode,
                  InfoMode,
                  BrightnessInfoMode,
                  Scene)


def main() -> None:
    desk = BulbProvider("desk", lambda: Yeelight.get())
    corridor = BulbProvider("corridor", lambda: Wiz.get("d8a0110a1bd4"))
    candela = BulbProvider("candela", lambda: YeelightBt("f8:24:41:c3:b8:43"))

    all_bulbs = [corridor, desk, candela]

    class HouseScene:
        def __init__(self,
                     desk_mode: BrightWarmMode,
                     corridor_mode: BrightWarmMode,
                     candela_mode: BrightMode) -> None:
            self.__desk_mode = desk_mode
            self.__corridor_mode = corridor_mode
            self.__candela_mode = candela_mode

        def to_scene(self) -> Scene:
            return Scene([BulbMode(desk, self.__desk_mode),
                          BulbMode(corridor, self.__corridor_mode),
                          BulbMode(candela, self.__candela_mode)])

    house_scenes: dict[str, HouseScene] = {
        "day":      HouseScene(desk_mode=BrightWarmMode(2700, 0),
                               corridor_mode=BrightWarmMode(2700, 100),
                               candela_mode=BrightMode(0)),
        "twilight": HouseScene(desk_mode=BrightWarmMode(2700, 60),
                               corridor_mode=BrightWarmMode(2700, 80),
                               candela_mode=BrightMode(0)),
        "evening":  HouseScene(desk_mode=BrightWarmMode(2700, 30),
                               corridor_mode=BrightWarmMode(2700, 60),
                               candela_mode=BrightMode(0)),
        "night":    HouseScene(desk_mode=BrightWarmMode(1700, 1),
                               corridor_mode=BrightWarmMode(1700, 1),
                               candela_mode=BrightMode(1)),
        "darkness": HouseScene(desk_mode=BrightWarmMode(1700, 0),  # TODO: `StateMode(False)`
                               corridor_mode=BrightWarmMode(1700, 0),
                               candela_mode=BrightMode(10)),
        "midnight": HouseScene(desk_mode=BrightWarmMode(1700, 0),  # TODO: `None`
                               corridor_mode=BrightWarmMode(1700, 0),
                               candela_mode=BrightMode(1)),
    }

    white_scenes: dict[str, Scene] = {name: house_scene.to_scene() for name, house_scene in house_scenes.items()}

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
            "desk":     bulb_commands(desk, [color_modes, bulb_modes]),
            "corridor": bulb_commands(corridor, [bulb_modes]),
            "candela":  bulb_commands(candela, [bulb_modes]),
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
