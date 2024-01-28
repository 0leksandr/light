from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
import re

from bulb import BulbProvider
from mode import Mode, TransitionMode, WhiteMode, WhiteBetweenMode, Scene
from parallel import parallel_all
from my import AbstractMethodException


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


class SceneCommand(Command):
    def __init__(self, scene: Scene) -> None:
        self.__scene = scene

    def run(self) -> None:
        self.__scene.apply()


class MultiCommand(Command):
    def __init__(self, commands: list[Command]) -> None:
        self.__commands = commands

    def run(self) -> None:
        parallel_all([command.run for command in self.__commands])


class OptionsCommand(Command):
    def __init__(self, options: list[str]) -> None:
        self.__options = options

    def run(self) -> None:
        print("Options: " + " ".join(self.__options))

    def __add__(self, other: OptionsCommand) -> OptionsCommand:
        return OptionsCommand(list(set(self.__options + other.__options)))


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
            return datetime.now().replace(hour=int(match_hms[1]), minute=int(match_hms[2]), second=int(match_hms[3]))
        else:
            return None

    def options(self) -> list[str]:
        return [datetime.now().strftime("%H:%M")]


class PercentsArgument(Argument):
    def convert(self, value: str) -> int | None:
        if re.match("^\\d+$", value):
            int_val = int(value)
            if int_val <= 100:
                return int_val
        return None

    def options(self) -> list[str]:
        return ["25", "50", "75"]


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
        elif keys == ["help"]:
            return OptionsCommand([])
        else:
            raise Exception("Unknown option(s): " + " ".join(keys))


class TreeCommander(Commander):
    def __init__(self, commanders: dict[str, Commander]) -> None:
        self.__commanders = commanders

    def get(self, keys: list[str]) -> Command:
        if len(keys) > 0 and keys[0] in self.__commanders:
            return self.__commanders[keys[0]].get(keys[1:])
        else:
            return OptionsCommand(list(self.__commanders.keys()))


class JoinedCommander(Commander):
    def __init__(self, commanders: list[Commander]) -> None:
        self.__commanders = commanders

    def get(self, keys: list[str]) -> Command:
        options = OptionsCommand([])
        for commander in self.__commanders:
            command = commander.get(keys)
            if isinstance(command, OptionsCommand):  # MAYBE: refactor
                options += command
            else:
                return command
        return options


class ArgumentsCommander(Commander):
    @staticmethod
    @abstractmethod
    def get_mode(bulb: BulbProvider, arguments: list) -> Mode:
        raise AbstractMethodException()

    def __init__(self, bulbs: list[BulbProvider], arguments: list[Argument]) -> None:
        self.__bulbs = bulbs
        self.__arguments = arguments

    def get(self, keys: list[str]) -> Command:
        if len(keys) > len(self.__arguments):
            return OptionsCommand([])
        arguments = []
        for i in range(len(keys)):
            argument = self.__arguments[i].convert(keys[i])
            if argument is None:
                return OptionsCommand(self.__arguments[i].options())
            else:
                arguments.append(argument)
        if len(arguments) < len(self.__arguments):
            return OptionsCommand(self.__arguments[len(arguments)].options())
        return MultiCommand([BulbCommand(bulb, self.get_mode(bulb, arguments))
                             for bulb in self.__bulbs])


class TransitionCommander(ArgumentsCommander):
    def __init__(self, scenes: dict[str, Scene]) -> None:
        bulbs = [bulb for scene in scenes.values() for bulb in scene.bulbs()]
        # bulbs = list(set(bulbs))
        bulbs = list({id(bulb): bulb for bulb in bulbs}.values())
        super().__init__(bulbs,
                         [ArgumentSelect(scenes),
                          TimeArgument(),
                          ArgumentSelect(scenes),
                          TimeArgument()])

    @staticmethod
    def get_mode(bulb: BulbProvider, arguments: list) -> Mode:
        def scene_to_mode(scene: Scene) -> WhiteMode:
            for bulb_mode in scene.bulbs_modes:
                if bulb_mode.bulb == bulb:
                    mode = bulb_mode.mode
                    if isinstance(mode, WhiteMode):
                        return mode
                    else:
                        raise Exception(f"Mode for bulb {bulb.name()} is not a WhiteMode")  # MAYBE: refactor
            raise Exception(f"Can not define mode for bulb {bulb.name()}")

        return TransitionMode(scene_to_mode(arguments[0]),
                              arguments[1],
                              scene_to_mode(arguments[2]),
                              arguments[3])


class WhiteBetweenCommander(ArgumentsCommander):
    def __init__(self, bulbs: list[BulbProvider], modes: dict[str, WhiteMode]) -> None:
        super().__init__(bulbs,
                         [ArgumentSelect(modes),
                          ArgumentSelect(modes),
                          PercentsArgument()])

    @staticmethod
    def get_mode(bulb: BulbProvider, arguments: list) -> Mode:
        return WhiteBetweenMode(*arguments)
