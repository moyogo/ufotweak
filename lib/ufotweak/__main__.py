import sys
import argparse
from typing import Any, List, Optional, Sequence, Union
from fontTools.ufoLib import fontInfoAttributesVersion3ValueData as infoAttrValueData
from ufoLib2 import Font

INFO_ATTR_BITLIST = {
    "openTypeHeadFlags": (0, 16),
    "openTypeOS2Selection": (0, 16),
    "openTypeOS2CodePageRanges": (0, 63),
    "openTypeOSUnicodeRanges": (0, 127),
}


def main(args=None):
    if not args:
        args = sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "ufos", metavar="UFO", nargs="*",
        help="UFOs to be tweaked.",
    )
    info_group = parser.add_argument_group("Info")
    for key, value_data in sorted(infoAttrValueData.items()):
        data_type = value_data["type"]
        if data_type == str:
            info_group.add_argument("--%s" % key, type=data_type, metavar="STRING")
        elif data_type == int:
            info_group.add_argument("--%s" % key, type=data_type, metavar="INT")
        elif isinstance(data_type, tuple) and float in data_type:
            info_group.add_argument("--%s" % key, type=float, metavar="FLOAT")
        elif data_type == "integerList":
            if key in INFO_ATTR_BITLIST:
                info_group.add_argument("--%s" % key, metavar="BITLIST")
            else:
                info_group.add_argument("--%s" % key, type=str, metavar="INTLIST")
        else:
            continue
    glyph_group = parser.add_argument_group("Glyph")
    glyph_group.add_argument(
        "--glyph-drop", metavar="STRING",
        help="Comma-separated list of glyph names to drop",
        )
    glyph_group.add_argument(
        "--glyph-unicode", metavar="STRING",
        help="<name>:<unicode>[,<unicode>,...][;<name>:...]",
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

    for path in options.ufos:
        print(path)
        font = Font(path)
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
        if options.glyph_drop:
           glyph_names = options.glyph_drop.replace(", ", ",").split(",")
           for glyph_name in glyph_names:
               if glyph_name in font:
                del font[glyph_name]
        if options.glyph_unicode:
            glyphs_unicodes = options.glyph_unicode.split(";")
            for glyph_unicodes in glyphs_unicodes:
                glyph_name, unicodes = glyph_unicodes.split(":")
                font[glyph_name].unicodes = [
                    int(c, 16) for c in unicodes.split(",")
                ]
                print(glyph_name, unicodes.split(","))
                print(glyph_name, font[glyph_name].unicodes)
        font.save()


if __name__ == "__main__":
    main()
