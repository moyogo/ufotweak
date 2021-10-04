from argparse import ArgumentParser
from ufoLib2 import Font


class Updater:
    def __init__(self, source, target, glyphs, layers, overwrite_components=True):
        self.source = source
        self.target = target
        self.glyphs = glyphs
        self.layers = layers
        self._font = None
        self._all_glyphs = set()
        self.overwrite_components = overwrite_components

    @property
    def font(self):
        if not self._font:
            self._update_font()
        return self._font

    def _update_font(self):
        # TODO clone target before changing it
        self._font = self.target
        self._update_glyphs()
        self._update_groups()
        self._update_kerning()

    def _update_glyphs(self):
        # TODO different layers
        self._collect_glyphs()
        all_glyphs = self._all_glyphs
        for glyph in self.source:
            name = glyph.name
            if name in all_glyphs:
                layer = self._font.layers.defaultLayer
                if name in layer:
                    del layer[name]
                layer.insertGlyph(glyph, name)

    def _collect_glyphs(self):
        for glyph in self.source:
            if glyph.name in self.glyphs:
                self._collect_components(glyph)

    def _collect_components(self, glyph):
        all_glyphs = self._all_glyphs
        # print("> all_glyphs", all_glyphs)
        for component in glyph.components:
            name = component.baseGlyph
            if name in all_glyphs:
                continue
            if name in self._font and not self.overwrite_components:
                continue
            all_glyphs.add(name)
            self._collect_components(self.source[name])
        all_glyphs.add(glyph.name)

    def _update_groups(self):
        # Remove glyphs present in destination groups but not in source groups
        for group_name, glyph_list in list(self.target.groups.items()):
            for glyph_name in glyph_list:
                # skip glyphs already in the same source and target groups
                if (
                    group_name in self.source.groups
                    and glyph_name in self.source.groups[group_name]
                ):
                    continue
                # remove glyphs
                elif glyph_name in self.glyphs:
                    glyph_list.remove(glyph_name)
            self.target.groups[group_name] = glyph_list

    def _update_kerning(self):
        # Prune kerning
        for kern_pair, value in list(self.target.kerning.items()):
            left, right = kern_pair
            if (
                left.startswith("public.kern")
                and left in self.target.groups
                and not self.target.groups[left]
            ):
                del self.target.kerning[kern_pair]
            elif (
                right.startswith("public.kern")
                and right in self.target.groups
                and not self.target.groups[right]
            ):
                del self.target.kerning[kern_pair]

        # Add glyphs to groups
        left_groups = {}
        right_groups = {}
        for group_name, group in list(self.source.groups.items()):
            for glyph_name in group:
                if glyph_name not in self.glyphs:
                    continue

                if group_name not in self.target.groups:
                    self.target.groups[group_name] = [glyph_name]
                # else:
                elif glyph_name not in self.target.groups[group_name]:
                    self.target.groups[group_name].append(glyph_name)

        # Add new kerning pairs-values
        for kern_pair, value in list(self.source.kerning.items()):
            left, right = kern_pair
            if (left in left_groups or right in right_groups
                or left in self.glyphs or right in self.glyphs):
                self.target.kerning[(left, right)] = value
        # Prune empty groups
        for group_name, group in list(self.target.groups.items()):
            if not group:
                del self.target.groups[group_name]


def main(args=None):
    parser = ArgumentParser(description="Update UFO with data from another UFO.")
    parser.add_argument("source", metavar="SOURCE", help="Source UFO with data")
    parser.add_argument("target", metavar="TARGET", help="Target UFO to update")
    # glyphs_group = parser.add_mutually_exclusive_group()
    parser.add_argument(
        "--glyphs",
        metavar="GLYPHLIST",
        help="Comma-separated list of glyphs to update.",
    )
    parser.add_argument(
        "--glyphs-txt",
        metavar="GLYPHLISTFILE",
        help="File with line-separated list of glyphs to update.",
    )
    parser.add_argument(
        "--layers",
        metavar="LAYERLIST",
        help="Comma-separated list of layers to update.",
    )
    parser.add_argument(
        "--overwrite-components",
        action="store_true",
        help="Overwrite component glyphs when used in glyphs to update.",
    )
    options = parser.parse_args(args)

    source = Font(options.source)
    target = Font(options.target)
    if options.glyphs:
        glyphs = options.glyphs.split(",")
    elif options.glyphs_txt:
        with open(options.glyphs_txt, "r") as fp:
            glyphs = [n.strip() for n in fp.readlines()]
    if options.layers:
        options.layers = options.layers.split(",")
    layers = options.layers
    overwrite_components = options.overwrite_components

    updater = Updater(source, target, glyphs, layers, overwrite_components)
    print("# Saving")
    updater.font.save(validate=False)


if __name__ == "__main__":
    main()
