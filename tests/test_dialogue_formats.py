import io
import hashlib
import struct
import unittest
import zlib
from PIL import Image
import dialogue_formats as df


def bank(fmt=0x10, width=64, height=64, mips=False):
    """Synthetic surfaces only; no retail image or game text in fixtures."""
    level_count = max(width, height).bit_length() if mips else 1
    image = Image.new("RGBA", (width, height), (0, 0, 0, 204))
    for x in range(width):
        image.putpixel((x, 0), (255, 160, 20, 255))
        image.putpixel((x, height - 1), (20, 160, 255, 255))
    payload = bytearray(128)
    struct.pack_into("<I", payload, 0, fmt | (0x10000000 if mips else 0))
    struct.pack_into("<2f", payload, 28, width, height)
    struct.pack_into("<i", payload, 40, 128 - 40)
    current = image
    for _ in range(level_count):
        if fmt == 0x10:
            payload += current.tobytes("raw", "BGRA")
        else:
            px = current.load()
            for by in range(0, current.height, 4):
                for bx in range(0, current.width, 4):
                    block = [px[min(bx + x, current.width - 1), min(by + y, current.height - 1)] for y in range(4) for x in range(4)]
                    payload += df._encode_block(block, fmt)
        current = current.resize((max(1, current.width // 2), max(1, current.height // 2)))
    data = bytearray(256)
    data[:4] = b"xobx"
    struct.pack_into("<I", data, 4, 4)
    struct.pack_into("<II", data, 12, 2, 256)
    struct.pack_into("<I4sII", data, 64, len(payload), b"surf", 128, len(payload))
    struct.pack_into("<I4sII", data, 80, 20, b"wave", 4, len(payload) + 20)
    data += payload
    data += bytes(range(20))
    table = len(data)
    names = [b"loc/french/popups/test00.tif\0", b"loc/french/popups/test00-snd\0"]
    data += struct.pack("<4I", 0, 0, 1, len(names[0]))
    pool = len(data)
    data += b"".join(names)
    struct.pack_into("<4I", data, 0x2C, 2, table, pool, sum(map(len, names)))
    return bytes(data)


def png(image):
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def decode_mip(data, level):
    section = df.read_sections(data)[0]
    fmt, mips = df._surface(data, section)
    offset, width, height, _ = mips[level]
    view = bytearray(data)
    struct.pack_into("<I", view, section.offset, fmt)
    struct.pack_into("<2f", view, section.offset + 28, width, height)
    struct.pack_into("<i", view, section.offset + 40, offset - section.offset - 40)
    return df._decode_image(bytes(view), section)


class DialogueTests(unittest.TestCase):
    def test_names_bind_exact_index_and_voice(self):
        data = bank()
        table = struct.unpack_from("<I", data, 0x30)[0]
        swapped = bytearray(data)
        swapped[table:table + 16] = data[table + 8:table + 16] + data[table:table + 8]
        rows = df.scan_dialogues(bytes(swapped))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["voiceIndex"], 1)
        self.assertEqual(rows[0]["sourceKind"], "bitmap")
        self.assertIsNone(rows[0]["text"])

    def test_preview_flips_original(self):
        image = Image.open(io.BytesIO(df.decode_popup_png(bank(), 0)))
        self.assertEqual(image.getpixel((0, 0)), (20, 160, 255, 255))
        raw = Image.open(io.BytesIO(df.decode_popup_png(bank(), 0, display=False)))
        self.assertEqual(raw.getpixel((0, 0)), (255, 160, 20, 255))

    def test_retail_last_end_sentinel(self):
        data = bytearray(bank())
        struct.pack_into("<I", data, 80 + 12, 0)
        self.assertEqual(len(df.read_sections(bytes(data))), 2)
        struct.pack_into("<I", data, 64 + 12, 0)
        with self.assertRaises(ValueError):
            df.read_sections(bytes(data))

    def test_edit_preserves_offsets_other_resources_and_frame(self):
        original = bank(width=256, height=256)
        patched = df.replace_popup_text(original, 0, "A manually authored test.")
        self.assertEqual(len(original), len(patched))
        sections = df.read_sections(original)
        self.assertEqual(original[:sections[0].offset + 128], patched[:sections[0].offset + 128])
        end = sections[0].offset + sections[0].size
        self.assertEqual(original[end:], patched[end:])
        original_image = Image.open(io.BytesIO(df.decode_popup_png(original, 0)))
        patched_image = Image.open(io.BytesIO(df.decode_popup_png(patched, 0)))
        self.assertEqual(original_image.crop((0, 0, 256, 40)).tobytes(), patched_image.crop((0, 0, 256, 40)).tobytes())
        self.assertEqual(original_image.crop((0, 212, 256, 256)).tobytes(), patched_image.crop((0, 212, 256, 256)).tobytes())
        self.assertNotEqual(original, patched)

    def test_dxt3_mips_preserve_untouched_fullsize_blocks(self):
        data = bank(fmt=0x40, width=256, height=256, mips=True)
        patched = df.replace_popup_text(data, 0, "The new text.")
        self.assertEqual(len(data), len(patched))
        section = df.read_sections(data)[0]
        _, mips = df._surface(data, section)
        self.assertEqual(len(mips), 9)
        first, width, height, extent = mips[0]
        # first four block rows are far outside the editable body.
        self.assertEqual(data[first:first + 64 * 16 * 4], patched[first:first + 64 * 16 * 4])
        for offset, width, height, extent in mips[:3]:
            self.assertNotEqual(data[offset:offset + extent], patched[offset:offset + extent])
        self.assertEqual(df.resource_names(data), df.resource_names(patched))

    def test_refuse_unbounded_or_nonpopup_changes(self):
        data = bank(width=256, height=256)
        invalid = bytearray(data)
        struct.pack_into("<i", invalid, 256 + 40, -300)
        with self.assertRaises(ValueError):
            df.decode_popup_png(bytes(invalid), 0)
        for resource, text, opts in [(1, "text", None), (0, "", None), (0, "text\0", None), (0, "word " * 1000, None), (0, "text", {"rect": [-1, 0, 10, 10]})]:
            with self.assertRaises(ValueError):
                df.replace_popup_text(data, resource, text, opts)

    def test_missing_name_and_invalid_catalog(self):
        data = bank()
        bad = bytearray(data)
        struct.pack_into("<I", bad, 0x2C, 1000)
        with self.assertRaises(ValueError):
            df.resource_names(bytes(bad))
        with self.assertRaises(ValueError):
            df.decode_popup_png(data, "missing")

    def test_manifest_has_verifiable_before_after(self):
        data = bank(width=256, height=256)
        patched, change = df.popup_change(data, 0, "Written by the user.")
        self.assertTrue(change["sameLength"])
        self.assertEqual(change["text"], "Written by the user.")
        self.assertNotEqual(change["beforeSha256"], change["afterSha256"])
        self.assertEqual(change["resourceIndex"], 0)

    def test_image_import_resize_orientation_and_preserve_other_resources(self):
        data = bank(width=64, height=64)
        authored = Image.new("RGBA", (16, 8), (255, 0, 0, 85))
        for y in range(4, 8):
            for x in range(16):
                authored.putpixel((x, y), (0, 0, 255, 204))
        source_png = png(authored)
        source_hash = hashlib.sha256(source_png).hexdigest()
        preview = Image.open(io.BytesIO(df.render_popup_image(data, 0, source_png)))
        expected = authored.resize((64, 64), Image.Resampling.LANCZOS)
        self.assertEqual(preview.size, (64, 64))
        self.assertEqual(preview.convert("RGBA").tobytes(), expected.tobytes())
        patched = df.replace_popup_image(data, 0, source_png)
        displayed = Image.open(io.BytesIO(df.decode_popup_png(patched, 0)))
        raw = Image.open(io.BytesIO(df.decode_popup_png(patched, 0, display=False)))
        self.assertEqual(displayed.tobytes(), expected.tobytes())
        self.assertEqual(raw.getpixel((0, 0)), expected.getpixel((0, 63)))
        self.assertEqual(raw.getpixel((0, 63)), expected.getpixel((0, 0)))
        section = df.read_sections(data)[0]
        self.assertEqual(patched[:section.offset + 128], data[:section.offset + 128])
        self.assertEqual(patched[section.offset + section.size:], data[section.offset + section.size:])
        self.assertEqual(len(patched), len(data))
        self.assertEqual(df.resource_names(patched), df.resource_names(data))
        self.assertEqual(hashlib.sha256(source_png).hexdigest(), source_hash)
        # Whole-image import deliberately changes the former frame pixels.
        original = Image.open(io.BytesIO(df.decode_popup_png(data, 0)))
        self.assertNotEqual(original.getpixel((0, 0)), displayed.getpixel((0, 0)))

    def test_image_import_rebuilds_every_mip_in_each_supported_format(self):
        for fmt, color in ((0x10, (255, 0, 0, 85)), (0x20, (255, 0, 0, 255)),
                           (0x40, (255, 0, 0, 85))):
            with self.subTest(format=fmt):
                data = bank(fmt=fmt, width=32, height=16, mips=True)
                patched = df.replace_popup_image(data, 0, png(Image.new("RGBA", (32, 16), color)))
                section = df.read_sections(data)[0]
                _, mips = df._surface(data, section)
                self.assertEqual(len(mips), 6)
                for level, (offset, width, height, extent) in enumerate(mips):
                    image = decode_mip(patched, level)
                    self.assertEqual(image.size, (width, height))
                    self.assertEqual(set(image.getdata()), {color})
                    self.assertNotEqual(data[offset:offset + extent], patched[offset:offset + extent])
                self.assertEqual(data[:section.offset + 128], patched[:section.offset + 128])
                self.assertEqual(data[section.offset + section.size:], patched[section.offset + section.size:])
                self.assertEqual(len(patched), len(data))

    def test_image_import_dxt1_preserves_binary_transparency(self):
        data = bank(fmt=0x20, width=8, height=8, mips=True)
        image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        for y in range(8):
            for x in range(4):
                image.putpixel((x, y), (255, 0, 0, 255))
        patched = df.replace_popup_image(data, 0, png(image))
        shown = Image.open(io.BytesIO(df.decode_popup_png(patched, 0)))
        self.assertEqual(shown.getpixel((0, 0)), (255, 0, 0, 255))
        self.assertEqual(shown.getpixel((7, 7))[3], 0)

    def test_image_import_rejects_invalid_oversized_animated_and_nonpopup(self):
        data = bank()
        image = Image.new("RGBA", (8, 8), (255, 0, 0, 255))
        valid = png(image)
        jpeg = io.BytesIO()
        image.convert("RGB").save(jpeg, "JPEG")
        animated = io.BytesIO()
        image.save(animated, "PNG", save_all=True,
                   append_images=[Image.new("RGBA", (8, 8), (0, 255, 0, 255))], duration=100, loop=0)
        too_wide = bytearray(valid)
        struct.pack_into(">I", too_wide, 16, 4097)
        struct.pack_into(">I", too_wide, 29, zlib.crc32(too_wide[12:29]))
        bad_crc = bytearray(valid)
        bad_crc[29] ^= 1
        cases = [b"", b"fake PNG", "not bytes", jpeg.getvalue(), valid[:-12],
                 bytes(bad_crc), bytes(too_wide), animated.getvalue(),
                 b"\x89PNG\r\n\x1a\n" + b"0" * df.MAX_POPUP_PNG_BYTES]
        for source in cases:
            with self.subTest(source_type=type(source).__name__, size=len(source)):
                with self.assertRaises(ValueError):
                    df.replace_popup_image(data, 0, source)
        with self.assertRaises(ValueError):
            df.replace_popup_image(data, 1, valid)

    def test_image_change_manifest_has_source_hash_and_native_dimensions(self):
        data = bank(width=64, height=64)
        source = png(Image.new("RGB", (128, 32), (255, 0, 0)))
        patched, change = df.popup_image_change(data, 0, source)
        self.assertEqual(change["kind"], "dialogue-image")
        self.assertEqual(change["imageSha256"], hashlib.sha256(source).hexdigest())
        self.assertEqual((change["inputWidth"], change["inputHeight"]), (128, 32))
        self.assertEqual((change["width"], change["height"]), (64, 64))
        self.assertTrue(change["resized"])
        self.assertTrue(change["sameLength"])
        self.assertTrue(change["replacesWholePanel"])
        self.assertEqual(change["afterSha256"], hashlib.sha256(patched).hexdigest())
        self.assertEqual(change["resourceIndex"], 0)


if __name__ == "__main__":
    unittest.main()
