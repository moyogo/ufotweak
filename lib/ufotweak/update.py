from argparse import ArgumentParser
from ufoLib2 import Font



class Updater():
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
        print("all_glyphs before", self._all_glyphs)
        self._update_glyphs()
        print("all_glyphs after", self._all_glyphs)

    def _update_glyphs(self):
        # TODO different layers
        self._collect_glyphs()
        all_glyphs = self._all_glyphs
        for glyph in self.source:
            name = glyph.name
            if name in all_glyphs:
                layer = self._font.layers.defaultLayer
                layer.insertGlyph(glyph, name)

    def _collect_glyphs(self):
        for glyph in self.source:
            if glyph.name in self.glyphs:
                self._collect_components(glyph)

    def _collect_components(self, glyph):
        all_glyphs = self._all_glyphs
        print("> all_glyphs", all_glyphs)
        for component in glyph.components:
            name = component.baseGlyph
            if name in all_glyphs:
                continue
            if name in self._font and not self.overwrite_components:
                continue
            all_glyphs.add(name)
            self._collect_components(self.source[name])
        all_glyphs.add(glyph.name)


def main(args=None):
    parser = ArgumentParser(description="Update UFO with data from another UFO.")
    parser.add_argument("source", metavar="SOURCE", help="Source UFO with data")
    parser.add_argument("target", metavar="TARGET", help="Target UFO to update")
    # glyphs_group = parser.add_mutually_exclusive_group()
    parser.add_argument("--glyphs", metavar="GLYPHLIST",
                        help="Comma-separated list of glyphs to update.")
    parser.add_argument("--layers", metavar="LAYERLIST",
                        help="Comma-separated list of layers to update.")
    parser.add_argument(
        "--overwrite-components",
        action="store_true",
        help="Overwrite component glyphs when used in glyphs to update."
    )
    options = parser.parse_args(args)

    source = Font(options.source)
    target = Font(options.target)
    if options.glyphs:
        options.glyphs = options.glyphs.split(",")
    glyphs = options.glyphs
    if options.layers:
        options.layers = options.layers.split(",")
    layers = options.layers
    overwrite_components = options.overwrite_components

    updater = Updater(source, target, glyphs, layers, overwrite_components)
    print("# Saving")
    updater.font.save()

if __name__ == "__main__":
    main()