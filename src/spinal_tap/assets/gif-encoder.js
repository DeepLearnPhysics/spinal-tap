(function () {
    "use strict";

    const MAX_CODE = 4096;

    function appendWord(bytes, value) {
        bytes.push(value & 0xff, (value >> 8) & 0xff);
    }

    function palette332() {
        const palette = new Uint8Array(256 * 3);
        for (let index = 0; index < 256; index++) {
            palette[index * 3] = Math.round(((index >> 5) & 7) * 255 / 7);
            palette[index * 3 + 1] = Math.round(((index >> 2) & 7) * 255 / 7);
            palette[index * 3 + 2] = (index & 3) * 85;
        }
        return palette;
    }

    function indexedPixels(rgba) {
        const pixels = new Uint8Array(rgba.length / 4);
        for (let source = 0, target = 0; source < rgba.length; source += 4) {
            pixels[target++] = (rgba[source] & 0xe0) |
                ((rgba[source + 1] & 0xe0) >> 3) |
                (rgba[source + 2] >> 6);
        }
        return pixels;
    }

    function lzwEncode(pixels) {
        const output = [];
        let block = 0;
        let bits = 0;
        let codeSize = 9;
        let nextCode = 258;
        let dictionary = new Map();

        const writeCode = code => {
            block |= code << bits;
            bits += codeSize;
            while (bits >= 8) {
                output.push(block & 0xff);
                block >>>= 8;
                bits -= 8;
            }
        };
        const reset = () => {
            dictionary = new Map();
            codeSize = 9;
            nextCode = 258;
        };

        writeCode(256);
        if (pixels.length) {
            let prefix = pixels[0];
            for (let index = 1; index < pixels.length; index++) {
                const suffix = pixels[index];
                const key = prefix * 256 + suffix;
                const known = dictionary.get(key);
                if (known !== undefined) {
                    prefix = known;
                    continue;
                }

                writeCode(prefix);
                if (nextCode < MAX_CODE) {
                    dictionary.set(key, nextCode++);
                    // The decoder adds the entry associated with an emitted
                    // prefix one code later than the encoder. Keep the old
                    // width for that next code, then grow on the following
                    // dictionary insertion. Growing at equality corrupts the
                    // bit stream at the first 9-to-10-bit transition.
                    if (nextCode > (1 << codeSize) && codeSize < 12) {
                        codeSize++;
                    }
                } else {
                    writeCode(256);
                    reset();
                }
                prefix = suffix;
            }
            writeCode(prefix);
        }
        writeCode(257);
        if (bits) output.push(block & 0xff);
        return output;
    }

    function appendSubBlocks(bytes, data) {
        for (let offset = 0; offset < data.length; offset += 255) {
            const size = Math.min(255, data.length - offset);
            bytes.push(size, ...data.slice(offset, offset + size));
        }
        bytes.push(0);
    }

    class Encoder {
        constructor(width, height, delay = 8) {
            this.width = width;
            this.height = height;
            this.delay = delay;
            const header = [
                ...new TextEncoder().encode("GIF89a")
            ];
            appendWord(header, width);
            appendWord(header, height);
            header.push(0xf7, 0, 0, ...palette332());

            // Loop forever using the Netscape application extension.
            header.push(
                0x21, 0xff, 0x0b,
                ...new TextEncoder().encode("NETSCAPE2.0"),
                0x03, 0x01, 0x00, 0x00, 0x00
            );
            this.chunks = [new Uint8Array(header)];
        }

        addFrame(rgba) {
            const bytes = [0x21, 0xf9, 0x04, 0x00];
            appendWord(bytes, this.delay);
            bytes.push(0x00, 0x00);

            bytes.push(0x2c);
            appendWord(bytes, 0);
            appendWord(bytes, 0);
            appendWord(bytes, this.width);
            appendWord(bytes, this.height);
            bytes.push(0x00, 0x08);
            appendSubBlocks(bytes, lzwEncode(indexedPixels(rgba)));
            this.chunks.push(new Uint8Array(bytes));
        }

        finish() {
            return new Blob([...this.chunks, new Uint8Array([0x3b])], {
                type: "image/gif"
            });
        }
    }

    window.spinalTapGif = {Encoder};
})();
