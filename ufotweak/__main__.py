import sys
import argparse
import json
from fontTools.ufoLib import fontInfoAttributesVersion3ValueData as infoAttrValueData
from fontTools import designspaceLib
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.roundingPen import RoundingPen
from ufo2ft.filters.propagateAnchors import PropagateAnchorsFilter
from ufo2ft.filters.decomposeComponents import DecomposeComponentsFilter
from ufoLib2 import Font

try:
    from glyphConstruction import GlyphConstructionBuilder
except ImportError:
    pass
    # print("Cannot use glyphConstruction as it is not installed.")

INFO_ATTR_BITLIST = {
    "openTypeHeadFlags": (0, 16),
    "openTypeOS2Selection": (0, 16),
    "openTypeOS2Type": (0, 16),
    "openTypeOS2CodePageRanges": (0, 63),
    "openTypeOSUnicodeRanges": (0, 127),
}


class Renamer:
    def __init__(self, font, mapping):
        self.font = font
        self.mapping = mapping

    @classmethod
    def from_glyphsdata(cls, font, glyphsdata):
        from ufo2ft.util import makeUnicodeToGlyphNameMapping
        import xml.etree.ElementTree

        with open(glyphsdata) as glyphdata_file:
            glyph_data = xml.etree.ElementTree.parse(glyphdata_file).getroot()
        font_unicodes = makeUnicodeToGlyphNameMapping(font)
        gd_unicodes = dict()
        for glyph in glyph_data:
            name = glyph.attrib["name"]
            uni = glyph.attrib.get("unicode")
            alt_names = glyph.attrib.get("altNames")
            prod_name = glyph.attrib.get("production")
            if uni:
                uni = int(uni, 16)
                gd_unicodes[uni] = []
                if name:
                    gd_unicodes[uni].append(name)
                if alt_names:
                    gd_unicodes[uni].extend(alt_names.split(", "))
                if prod_name:
                    gd_unicodes[uni].append(prod_name)
        mapping = dict()
        for uni, ufo_name in font_unicodes.items():
            if uni in gd_unicodes:
                mapping[ufo_name] = gd_unicodes[uni][0]
        return cls(font, mapping)

    def rename(self):
        glyph_names = set(g.name for g in self.font)
        # Update with glyphOrder and postscriptNames in case the features have old names
        glyph_names.update(set(self.font.lib.get("public.glyphOrder")))
        glyph_names.update(set(self.font.lib.get("public.postscriptNames")))
        for layer in self.font.layers:
            for glyph in [g for g in layer]:
                for component in glyph.components:
                    if component.baseGlyph in self.mapping:
                        component.baseGlyph = self.mapping[component.baseGlyph]
                if glyph.name in self.mapping:
                    new_name = self.mapping[glyph.name]
                    if new_name in layer:
                        print(f"{new_name} already in font")
                        continue
                    layer.renameGlyph(glyph.name, new_name)

                comp_info = glyph.lib.get("com.schriftgestaltung.Glyphs.ComponentInfo")
                if comp_info:
                    for ci in comp_info:
                        name = ci.get("name")
                        if name in self.mapping:
                            ci["name"] = self.mapping[name]

                mks = [f"com.schriftgestaltung.Glyphs.glyph.{m}MetricsKey" for m in ["left", "right", "width"]]
                for mk in mks:
                    value = glyph.lib.get(mk)
                    if not value:
                        continue
                    prefix = ""
                    key = value
                    if value.startswith("="):
                        key = value[1:]
                        prefix = "="
                    elif value.startswith("|="):
                        key = value[2:]
                        prefix = "|="

                    if key in self.mapping:
                        glyph.lib[mk] = prefix + self.mapping[key]

        # Kerning
        group_mapping = dict()
        for group_name, group in list(self.font.groups.items()):
            for old, new in self.mapping.items():
                if old in group:
                    index = group.index(old)
                    group.remove(old)
                    group.insert(index, new)

            for old, new in self.mapping.items():
                if group_name[len("public.kern1.") :] == old:
                    new_group_name = group_name[: len("public.kern1.")] + new
                    del self.font.groups[group_name]
                    self.font.groups[new_group_name] = group
                    group_mapping[group_name] = new_group_name
                    break
        # count = 0
        mapping = self.mapping
        mapping.update(group_mapping)
        for pair in list(self.font.kerning.keys()):
            old_pair = pair
            value = self.font.kerning[old_pair]
            for old, new in mapping.items():
                if (old, old) == pair:
                    pair = (new, new)
                    break
                elif old == pair[0]:
                    pair = (new, pair[1])
                    if pair[1] != old_pair[1]:
                        break
                elif old == pair[1]:
                    pair = (pair[0], new)
                    if pair[0] != old_pair[0]:
                        break

            if old_pair != pair:
                del self.font.kerning[old_pair]
                self.font.kerning[pair] = value
                continue
        from fontTools.feaLib.parser import Parser
        from io import StringIO

        def recursive_fea_glyph_rename(statement):
            if hasattr(statement, "statements"):
                new = []
                for el in statement.statements:
                    s = recursive_fea_glyph_rename(el)
                    new.append(s)
                statement.statements = new

            if hasattr(statement, "glyphs"):
                statement.glyphs = recursive_fea_glyph_rename(statement.glyphs)
            if hasattr(statement, "prefix"):
                statement.prefix = recursive_fea_glyph_rename(statement.prefix)
            if hasattr(statement, "suffix"):
                statement.suffix = recursive_fea_glyph_rename(statement.suffix)
            if hasattr(statement, "old_prefix"):
                statement.suffix = recursive_fea_glyph_rename(statement.old_prefix)
            if hasattr(statement, "old_suffix"):
                statement.suffix = recursive_fea_glyph_rename(statement.old_suffix)
            if hasattr(statement, "replacement"):
                if isinstance(statement.replacement, str):
                    statement.replacement = self.mapping.get(
                        statement.replacement, statement.replacement
                    )
                elif isinstance(statement.replacement, tuple):
                    statement.replacement = recursive_fea_glyph_rename(
                        statement.replacement
                    )
            if hasattr(statement, "replacements"):
                statement.replacements = recursive_fea_glyph_rename(
                    statement.replacements
                )
            if hasattr(statement, "glyph"):
                statement.glyph = self.mapping.get(statement.glyph, statement.glyph)
            if isinstance(statement, (tuple, list)):
                for i, glyph_name in enumerate(statement):
                    if isinstance(glyph_name, str):
                        if glyph_name in self.mapping:
                            if isinstance(statement, tuple):
                                statement = tuple(
                                    [
                                        *statement[:i],
                                        self.mapping[glyph_name],
                                        *statement[i + 1 :],
                                    ]
                                )
                            else:
                                statement.pop(i)
                                statement.insert(i, self.mapping[glyph_name])
                    elif hasattr(glyph_name, "glyph"):
                        if glyph_name.glyph in self.mapping:
                            glyph_name.glyph = self.mapping[glyph_name.glyph]
                    elif hasattr(glyph_name, "glyphs"):
                        glyph_name.glyphs = recursive_fea_glyph_rename(
                            glyph_name.glyphs
                        )
            return statement

        # ast = Parser(StringIO(str(self.font.features)), glyphNames=glyph_names).parse()
        # ast = recursive_fea_glyph_rename(ast)
        # self.font.features.text = ast.asFea()

        glyph_order = [
            self.mapping.get(n, n) for n in self.font.lib.get("public.glyphOrder")
        ]
        if glyph_order:
            self.font.lib["public.glyphOrder"] = glyph_order
        postscript_names = {
            self.mapping.get(k, k): v
            for k, v in self.font.lib.get("public.postscriptNames", {}).items()
        }
        if postscript_names:
            self.font.lib["public.postscriptNames"] = postscript_names


def process_fontinfo(font, options):
    for key, value_data in sorted(infoAttrValueData.items()):
        data_type = value_data["type"]
        if not hasattr(options, key):
            if not (
                options.drop
                and key in options.drop
                or options.update
                and key in options.update
            ):
                continue
        if options.update and key in options.update:
            lib = json.loads(options.update)
            for key, value in lib.items():
                setattr(font.info, key, value)
            continue
        if options.drop and key in options.drop:
            print("drop key", key)
            delattr(font.info, key)
            continue
        else:
            value = getattr(options, key)
        if value is not None:
            if value == "":
                setattr(font.info, key, None)
            elif data_type in (int, str):
                setattr(font.info, key, data_type(value))
            elif isinstance(data_type, tuple) and float in data_type:
                value = float(value)
                if value.is_integer():
                    value = int(value)
                setattr(font.info, key, value)
            elif data_type == "integerList" and key in INFO_ATTR_BITLIST:
                setattr(font.info, key, _parse_bitlist(value))
            elif data_type == "integerList":
                setattr(font.info, key, _parse_list(value))
            elif data_type == "dictList":
                setattr(font.info, key, _parse_dict(value))


def process_glyph(font, options):
    if options.drop:
        glyph_names = options.drop.replace(", ", ",").split(",")
        for glyph_name in glyph_names:
            if glyph_name in font:
                del font[glyph_name]
                # TODO: remove glyph from features, groups and kerning

            if glyph_name in font.lib.get("public.glyphOrder"):
                font.lib["glyphOrder"].remove(glyph_name)

            if glyph_name in font.lib.get("public.postscriptNames"):
                del font.lib["public.postscriptNames"][glyph_name]

            for group_name, values in list(font.groups.items()):
                if glyph_name in values:
                    values.remove(glyph_name)

    if options.set_unicode:
        glyphs_unicodes = options.set_unicode.split(",")
        for glyph_unicodes in glyphs_unicodes:
            glyph_name, unicodes = glyph_unicodes.split("=")
            font[glyph_name].unicodes = [int(c, 16) for c in unicodes.split(":")]
            print(glyph_name, unicodes.split(":"))
            print(glyph_name, font[glyph_name].unicodes)
    if options.drop_unicode:
        glyphs_names = options.drop_unicode.split(",")
        for glyph_name in glyphs_names:
            font[glyph_name].unicodes = None
    if options.set_postscriptName:
        glyphs_poscriptName = {
            k: v
            for (k, v) in [e.split(":") for e in options.set_postscriptName.split(",")]
        }
        if not font.lib.get("public.postscriptNames"):
            font.lib["public.postscriptNames"] = dict()
        font.lib["public.postscriptNames"].update(glyphs_poscriptName)
    if options.drop_postscriptName:
        for glyph_name in options.drop_postscriptName.split(","):
            del font.lib["public.postscriptNames"][glyph_name]
    if options.drop_anchor:
        anchor_name, glyph_names = options.drop_anchor.split(":")
        if glyph_names == "*":
            glyph_names = [g.name for g in font]
        else:
            glyph_names = glyph_names.split(",")
        for glyph_name in glyph_names:
            glyph = font[glyph_name]
            if anchor_name == "*":
                anchors = [a for a in glyph.anchors]
            else:
                anchors = [a for a in glyph.anchors if a.name == anchor_name]
            for anchor in anchors:
                glyph.anchors.remove(anchor)
    if options.rename_anchor:
        mapping = dict(kv.split(":") for kv in options.rename_anchor.split(","))
        for glyph in font:
            for anchor in glyph.anchors:
                if anchor.name in mapping:
                    anchor.name = mapping[anchor.name]
    if options.drop_lib:
        lib_key, glyph_names = options.drop_lib.split(":")
        if glyph_names == "*":
            glyph_names = set()
            for layer in [layer for layer in font.layers]:
                for glyph in layer:
                    glyph_names.add(glyph.name)
        else:
            glyph_names = set(glyph_names.split(","))
        for glyph_name in glyph_names:
            for layer in font.layers:
                if glyph_name in layer:
                    glyph = layer[glyph_name]
                    if lib_key == "*":
                        del glyph.lib
                    elif lib_key in glyph.lib:
                        del glyph.lib[lib_key]
    if options.construction:
        try:
            GlyphConstructionBuilder
        except NameError:
            print("glyphConstruction is not installed.")
        else:
            for construction in options.construction:
                construction_glyph = GlyphConstructionBuilder(construction, font)
                if construction_glyph.name in font:
                    glyph = font[construction_glyph.name]
                    glyph.clear()
                else:
                    glyph = font.newGlyph(construction_glyph.name)
                construction_glyph.draw(glyph.getPen())
                if construction_glyph.unicode:
                    glyph.unicode = construction_glyph.unicode
                glyph.width = construction_glyph.width
    if options.copy_width:
        mapping = dict(kv.split(":") for kv in options.copy_width.split(","))
        for source, target in mapping.items():
            font[target].width = font[source].width
    if options.propagateAnchors:
        glyph_names = options.propagateAnchors.split(",")
        philter = PropagateAnchorsFilter(include=glyph_names)
        print(philter(font))
    if options.decompose:
        glyph_names = options.decompose.split(",")
        philter = DecomposeComponentsFilter(include=glyph_names)
        print(philter(font))
    if options.rename:
        mapping = dict(kv.split(":") for kv in options.rename.split(","))
        renamer = Renamer(font, mapping)
        renamer.rename()
    if options.rename_glyphsdata:
        renamer = Renamer.from_glyphsdata(font, options.rename_glyphsdata)
        renamer.rename()
    if options.swap_unicodes:
        mapping = dict(kv.split(":") for kv in options.swap_unicodes.split(","))
        for old, new in mapping.items():
            unicodes = font[old].unicodes
            font[old].unicodes = font[new].unicodes
            font[new].unicodes = unicodes
    if options.swap_components:
        mapping = dict(kv.split(":") for kv in options.swap_components.split(","))
        glyphs = [
            g
            for g in font
            if g.components and any(c.baseGlyph in mapping for c in g.components)
        ]
        for old, new in mapping.items():
            for glyph in glyphs:
                if glyph.name == new:
                    continue
                for component in glyph.components:
                    if component.baseGlyph == old:
                        component.baseGlyph = new
    if options.round:
        glyphnames = options.round.split(",")
        if "*" in glyphnames:
            glyphnames = [glyph.name for glyph in font]

        def round_glyph(glyph):
            recpen = RecordingPen()
            roundpen = RoundingPen(recpen)
            glyph.draw(roundpen)
            glyph.clearContours()
            glyph.clearComponents()
            recpen.replay(glyph.getPen())
            for anchor in glyph.anchors:
                anchor.x = round(anchor.x)
                anchor.y = round(anchor.y)

        for name in glyphnames:
            round_glyph(font[name])


def process_lib(font, options):
    if options.update:
        print(options.update)
        lib = json.loads(options.update)
        font.lib.update(lib)
    if options.dump_key:
        print(json.dumps(font.lib[options.dump_key]))
    if options.drop:
        keys = options.drop.replace(", ", ",").split(",")
        for key in keys:
            del font.lib[key]


def process_designspace(designspace, options):
    if options.instance:
        instances = dict(a.split(":") for a in options.instance.split(","))


def _parse_bitlist(string):
    assert string.startswith("[") and string.endswith("]")
    if string == "[]":
        return []
    # value = [1 << int(i.strip()) for i in string[1:-1].split(",")]
    value = [int(i) for i in string[1:-1].split(",")]
    print(value)
    return value


def _parse_list(string):
    assert string.startswith("[") and string.endswith("]")
    return [int(i) for i in string[1:-1].split(",")]


def _parse_dict(string):
    pass


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
        "--update",
        metavar="JSON",
        help="JSON formatted fontinfo data " "'{key: value, [...]}'",
    )
    parser_fontinfo.add_argument(
        "--drop",
        metavar="STRING",
        help="Comma separated list of fontinfo keys to drop.",
    )
    parser_fontinfo.add_argument(
        dest="paths",
        metavar="UFO",
        nargs="*",
        help="UFOs to be tweaked.",
    )

    # UFO glyph command
    parser_glyph = subparsers.add_parser(
        "glyph",
        description="UFO glyph",
    )
    parser_glyph.add_argument(
        dest="paths",
        metavar="UFO",
        nargs="*",
        help="UFOs to be tweaked.",
    )
    parser_glyph.add_argument(
        "--drop",
        metavar="STRING",
        help="Comma-separated list of glyph names to drop",
    )
    parser_glyph.add_argument(
        "--set-unicode",
        metavar="STRING",
        help="<name>=<unicode>[:<unicode>:...][,<name>=...]",
    )
    parser_glyph.add_argument(
        "--drop-unicode",
        metavar="STRING",
        help="<name>[,<name>,...]",
    )
    parser_glyph.add_argument(
        "--swap-unicodes",
        metavar="STRING",
        help="<glyph1>:<glyph2>[,<glyph1>:<glyph2>,...]\n"
        "<glyph1> and <glyph2> are glyph that will swap unicodes",
    )
    parser_glyph.add_argument(
        "--set-postscriptName",
        metavar="STRING",
        help="<glyph>:<name>[,<glyph>:<name>,...]",
    )
    parser_glyph.add_argument(
        "--drop-postscriptName",
        metavar="STRING",
        help="<glyph>[,<glyph>,...]",
    )
    parser_glyph.add_argument(
        "--swap-components",
        metavar="STRING",
        help="<glyph1>:<glyph2>[,<glyph1>:<glyph2>,...]\n"
        "Component glyphs will have <glyph1> swapped for <glyph2>,"
        " except <glyphs2> if it uses <glyph1> as a component.",
    )
    parser_glyph.add_argument(
        "--drop-anchor",
        metavar="STRING",
        help="<anchor_name>:<glyph_name>[,<glyph_name>,...]\n"
        "<anchor_name> and <glyph_name> may be '*' for any",
    )
    parser_glyph.add_argument(
        "--rename-anchor",
        metavar="STRING",
        help="<anchor1>:<anchor2>[,<anchor1>:<anchor2>,...]",
    )
    parser_glyph.add_argument(
        "--drop-lib",
        metavar="STRING",
        help="<lib_key>:<glyph_name>[,<glyph_name>,...]\n"
        "<lib_key> and <glyph_name> may be '*' for any",
    )
    parser_glyph.add_argument(
        "--construction",
        metavar="STRING",
        nargs="+",
        help="<glyphConstruction>",
    )
    parser_glyph.add_argument(
        "--copy-width",
        metavar="STRING",
        help="<source>:<target>[,<source>:<target>]\n"
        "<source> is the glyph with the width to copy, <target> is the glyph"
        "where the width is applied.",
    )
    parser_glyph.add_argument(
        "--propagateAnchors",
        metavar="STRING",
        help="<glyph>[,<glyph>,...]",
    )
    parser_glyph.add_argument(
        "--decompose",
        metavar="STring",
        help="<glyph>[,<glyph],...]",
    )
    parser_glyph.add_argument(
        "--rename",
        metavar="STRING",
        help="<old>:<new>[,<old>:<new>,...]\n"
        "<old> is the current name and <new> is the new name",
    )
    parser_glyph.add_argument(
        "--rename-glyphsdata",
        metavar="GLYPHSDATA",
        help="GLYPHSDATA" "GlyphsData.xml file",
    )
    parser_glyph.add_argument(
        "--round",
        metavar="STRING",
        help="<glyph>[,<glyph>,...]\n"
        "<glyph> is a glyph that should be rounded.\n"
        "<glyph> may be '*' for any.",
    )

    # UFO lib command
    parser_lib = subparsers.add_parser(
        "lib",
        description="UFO lib",
    )
    parser_lib.add_argument(
        dest="paths",
        metavar="UFO",
        nargs="*",
        help="UFOs to be tweaked.",
    )
    parser_lib.add_argument(
        "--update",
        metavar="JSON",
        help="JSON formatted lib data " "'{key: value, [...]}'",
    )
    parser_lib.add_argument(
        "--dump-key",
        metavar="KEY",
        help="Print JSON formatted lib data " "'key'",
    )
    parser_lib.add_argument(
        "--drop",
        metavar="STRING",
        help="Comma separated list of lib keys to drop.",
    )

    # designspace command
    parser_designspace = subparsers.add_parser(
        "designspace",
        description="Designspace",
    )
    parser_fontinfo.add_argument(
        "designspace",
        metavar="DESIGNSPACE",
        nargs="*",
        help="DESIGNSPACE to be tweaked.",
    )
    parser_designspace.add_argument(
        "--instance",
        metavar="STRING",
        help="Instance",
    )
    parser_designspace.add_argument(
        "--source",
        metavar="STRING",
        help="Source",
    )
    for attribute in ["name", "familyname", "stylename", "filename", "layer"]:
        parser_designspace.add_argument(
            "--%s" % attribute,
            metavar="STRING",
            help="Source or instance %s attribute" % attribute,
        )
    for instance_attribute in [
        "postscriptfontname",
        "stylemapfamilyname",
        "stylemapstylename",
    ]:
        parser_designspace.add_argument(
            "--%s" % instance_attribute,
            metavar="STRING",
            help="Instance %s attribute" % instance_attribute,
        )

    options = parser.parse_args(args)

    print("command", options.command)
    if not options.command:
        return

    for path in options.paths:
        if options.command != "designspace":
            #     from defcon import Font
            #     font = Font(path)
            # else:
            #     font = Font(path)
            font = Font(path)
        else:
            designspace = None
        if options.command == "fontinfo":
            process_fontinfo(font, options)
        elif options.command == "glyph":
            process_glyph(font, options)
        elif options.command == "lib":
            process_lib(font, options)
        elif options.command == "designspace":
            designspace = designspaceLib.DesignSpaceDocument.fromfile(path)
            process_designspace(designspace, options)

        font.save()


if __name__ == "__main__":
    main()
