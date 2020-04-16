import sys
import argparse
import json
from typing import Any, List, Optional, Sequence, Union
from fontTools.ufoLib import fontInfoAttributesVersion3ValueData as infoAttrValueData
from ufoLib2 import Font

INFO_ATTR_BITLIST = {
    "openTypeHeadFlags": (0, 16),
    "openTypeOS2Selection": (0, 16),
    "openTypeOS2CodePageRanges": (0, 63),
    "openTypeOSUnicodeRanges": (0, 127),
}


def process_fontinfo(font, options):
    for key, value_data in sorted(infoAttrValueData.items()):
        data_type = value_data["type"]
        if not hasattr(options, key):
            continue
        value = getattr(options, key)
        if value is not None:
            if value == "":
                setattr(font.info, key, None)
            elif data_type in (int, str):
                setattr(font.info, key, data_type(value))
            elif isinstance(data_type, tuple) and float in data_type:
                setattr(font.info, key, float(value))
            elif data_type == "integerList" and key in INFO_ATTR_BITLIST:
                setattr(font.info, key, _parse_bitlist(value))
            elif data_type == "integerList":
                setattr(font.info, key, _parse_list(value))
            elif data_type =="dictList":
                setattr(font.info, key, _parse_dict(value))


def process_glyph(font, options):
    if options.drop:
       glyph_names = options.drop.replace(", ", ",").split(",")
       for glyph_name in glyph_names:
           if glyph_name in font:
            del font[glyph_name]
    if options.set_unicode:
        glyphs_unicodes = options.set_unicode.split(",")
        for glyph_unicodes in glyphs_unicodes:
            glyph_name, unicodes = glyph_unicodes.split("=")
            font[glyph_name].unicodes = [
                int(c, 16) for c in unicodes.split(":")
            ]
            print(glyph_name, unicodes.split(":"))
            print(glyph_name, font[glyph_name].unicodes)


def process_lib(font, options):
    if options.update:
        print(options.update)
        lib = json.loads(options.update)
        font.lib.update(lib)
    if options.drop:
        keys = options.drop.replace(", ", ",").split(",")
        for key in keys:
            del font.lib[key]


def main(args=None):
    if not args:
        args = sys.argv[1:]
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(
        dest="command",
        description="Get help for commands with ufotweak COMMAND --help",
    )

    # UFO fontinfo command
    parser_fontinfo = subparsers.add_parser(
        "fontinfo",
        description="UFO fontinfo",
    )
    # info_group = parser.add_argument_group("Info")
    for key, value_data in sorted(infoAttrValueData.items()):
        data_type = value_data["type"]
        if data_type == str:
            parser_fontinfo.add_argument("--%s" % key, type=data_type, metavar="STRING")
        elif data_type == int:
            parser_fontinfo.add_argument("--%s" % key, type=data_type, metavar="INT")
        elif isinstance(data_type, tuple) and float in data_type:
            parser_fontinfo.add_argument("--%s" % key, type=float, metavar="FLOAT")
        elif data_type == "integerList":
            if key in INFO_ATTR_BITLIST:
                parser_fontinfo.add_argument("--%s" % key, metavar="BITLIST")
            else:
                parser_fontinfo.add_argument("--%s" % key, type=str, metavar="INTLIST")
        else:
            continue
    parser_fontinfo.add_argument(
        "ufos", metavar="UFO", nargs="*",
        help="UFOs to be tweaked.",
    )

    # UFO glyph command
    parser_glyph = subparsers.add_parser(
        "glyph",
        description="UFO glyph",
    )
    parser_glyph.add_argument(
        "--drop", metavar="STRING",
        help="Comma-separated list of glyph names to drop",
        )
    parser_glyph.add_argument(
        "--set-unicode", metavar="STRING",
        help="<name>=<unicode>[:<unicode>:...][,<name>=...]",
        )
    parser_glyph.add_argument(
        "ufos", metavar="UFO", nargs="*",
        help="UFOs to be tweaked.",
    )

    # UFO lib command
    parser_lib = subparsers.add_parser(
        "lib",
        description="UFO lib",
    )
    parser_lib.add_argument(
        "--update", metavar="JSON",
        help="JSON formatted lib data "
        "'{key: value, [...]}'",
    )
    parser_lib.add_argument(
        "--drop", metavar="STRING",
        help="Comma separated list of lib keys to drop.",
    )
    parser_lib.add_argument(
        "ufos", metavar="UFO", nargs="*",
        help="UFOs to be tweaked.",
    )

    options = parser.parse_args(args)

    def _parse_bitlist(string):
        assert string.startswith("[") and string.endswith("]")
        return sum([1 << int(i.strip()) for i in string[1:-1].split(",")])
    def _parse_list(string):
        assert string.startswith("[") and string.endswith("]")
        return [int(i) for i in string[1:-1].split(",")]
    def _parse_dict(string):
        pass

    print(options.command)

    for path in options.ufos:
        print(path)
        font = Font(path)
        if options.command == "fontinfo":
            process_fontinfo(font, options)
        elif options.command == "glyph":
            process_glyph(font, options)
        elif options.command == "lib":
            process_lib(font, options)

        font.save()


if __name__ == "__main__":
    main()
