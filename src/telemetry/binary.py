"""Small packed-layout reader; all byte order is explicitly little endian.

V0.9.13.0 latency pass: Layout decoding uses index-based reads over the flat
``struct.unpack_from`` tuple.  The old implementation recursively created a
large number of generators/tuples/``next()`` calls for every UDP packet; with
24-car packet bodies that became one of the hottest paths in the process.
"""

import struct


class MalformedPacket(ValueError):
    pass


class UnsupportedPacket(ValueError):
    pass


class Layout:
    def __init__(self, record_type, fields):
        self.record_type = record_type
        self.fields = tuple(fields)
        self.format = ''.join(
            (codec.format if isinstance(codec, Layout) else codec) * count
            for _, codec, count, _ in fields
        )
        self.struct = struct.Struct('<' + self.format)
        self.size = self.struct.size

        # Precompute the small amount of reflection needed by the decoder once at
        # layout-construction time rather than once per decoded field/packet.
        annotations = getattr(record_type, "__annotations__", {})
        self._runtime_fields = tuple(
            (codec, int(count), bool(array), annotations.get(name) is str)
            for name, codec, count, array in self.fields
        )
        # Every Layout has a fixed schema, so the positions of all unpacked tuple
        # values are known at import time. Build a direct constructor once instead
        # of interpreting the schema field-by-field for every UDP datagram. The
        # generic _read_from path is retained for compatibility/tests.
        self._compiled_decode = self._compile_decoder()


    def _compile_decoder(self):
        """Compile this fixed layout into direct tuple-index constructors.

        High-rate F1 packets contain 24 repeated car records. Interpreting the
        schema recursively for every record adds a large amount of Python loop /
        isinstance overhead even though every tuple offset is static. This small
        generated function preserves the same dataclass objects while jumping
        directly to their known tuple indices.
        """
        namespace = {"clean": self._clean_text}
        type_names = {}

        def type_name(layout):
            key = id(layout.record_type)
            name = type_names.get(key)
            if name is None:
                name = f"T{len(type_names)}"
                type_names[key] = name
                namespace[name] = layout.record_type
            return name

        def expression(layout, pos):
            args = []
            for name, codec, count, array in layout.fields:
                count = int(count)
                is_string = getattr(layout.record_type, "__annotations__", {}).get(name) is str
                if isinstance(codec, Layout):
                    children = []
                    for _ in range(count):
                        child, pos = expression(codec, pos)
                        children.append(child)
                    if count == 1:
                        value = f"({children[0]},)" if array else children[0]
                    elif array:
                        value = "(" + ",".join(children) + ",)"
                    else:
                        value = children[0]
                else:
                    if count == 1:
                        value = f"v[{pos}]"
                        pos += 1
                        if array:
                            value = f"({value},)"
                    else:
                        start = pos
                        pos += count
                        value = f"v[{start}:{pos}]" if array else f"v[{start}]"
                    if is_string:
                        value = f"clean({value})"
                args.append(value)
            return f"{type_name(layout)}(" + ",".join(args) + ")", pos

        expr, value_count = expression(self, 0)
        namespace["VALUE_COUNT"] = value_count
        code = "def decode_values(v):\n    return " + expr
        exec(compile(code, "<telemetry-layout>", "exec"), namespace)
        return namespace["decode_values"]

    @staticmethod
    def _clean_text(value):
        text = value.split(b'\0', 1)[0].decode('utf-8', errors='replace')
        return ''.join(c if c.isprintable() else '\ufffd' for c in text)

    def _read_from(self, values, pos: int):
        """Decode one record from an unpacked flat tuple and return (record, pos).

        Using direct tuple indexing/slicing avoids millions of generator and
        ``next`` calls in the generic decoder while preserving the exact public
        typed-record output of the previous implementation.
        """
        result = []
        append = result.append
        for codec, count, array, is_string in self._runtime_fields:
            if isinstance(codec, Layout):
                if count == 1:
                    item, pos = codec._read_from(values, pos)
                    value = (item,) if array else item
                else:
                    items = []
                    item_append = items.append
                    for _ in range(count):
                        item, pos = codec._read_from(values, pos)
                        item_append(item)
                    value = tuple(items) if array else items[0]
            else:
                if count == 1:
                    item = values[pos]
                    pos += 1
                    value = (item,) if array else item
                else:
                    items = values[pos:pos + count]
                    pos += count
                    value = items if array else items[0]

            if is_string:
                value = self._clean_text(value)
            append(value)
        return self.record_type(*result), pos

    # Keep the old private helper contract for any tests/callers that may use it.
    def _read(self, values):
        flat = tuple(values)
        record, _ = self._read_from(flat, 0)
        return record

    def decode(self, data: bytes, offset: int = 29):
        values = self.struct.unpack_from(data, offset)
        return self._compiled_decode(values)
