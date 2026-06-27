"""Compression codecs for binary data."""

import struct

from binforge.errors import DecompressionError


# ── LZ10 (Nintendo GBA) ──────────────────────────────────────────────────────


def decompress_lz10(data: bytes) -> bytes:
    """Decompress LZ10-compressed data (Nintendo GBA format).

    :param data: Compressed data with 0x10 magic byte
    :returns: Decompressed bytes
    :raises DecompressionError: If magic byte is not 0x10 or data is invalid
    """
    if not data or data[0] != 0x10:
        raise DecompressionError("LZ10 magic byte 0x10 not found")
    size = data[1] | (data[2] << 8) | (data[3] << 16)
    out = bytearray()
    pos = 4
    while len(out) < size:
        try:
            flags = data[pos]
        except IndexError as exc:
            raise DecompressionError("LZ10 truncated: missing control byte") from exc
        pos += 1
        try:
            for bit in range(7, -1, -1):
                if len(out) >= size:
                    break
                if flags & (1 << bit):
                    block = (data[pos] << 8) | data[pos + 1]
                    pos += 2
                    length = ((block >> 12) & 0xF) + 3
                    disp = (block & 0xFFF) + 1
                    for _ in range(length):
                        out.append(out[-disp])
                else:
                    out.append(data[pos])
                    pos += 1
        except (IndexError, struct.error) as exc:
            raise DecompressionError(str(exc)) from exc
    return bytes(out[:size])


def compress_lz10(data: bytes) -> bytes:
    """Compress data using Nintendo LZ10 (GBA) sliding-window format.

    Uses a 4096-byte sliding window with match lengths of 3–18 bytes.
    Flag byte bit=1 means back-reference; bit=0 means literal (matching
    the decompressor's convention).

    :param data: Raw bytes to compress.
    :returns: LZ10-compressed bytes including the 4-byte header.
    """
    src_len = len(data)
    header = bytes([0x10, src_len & 0xFF, (src_len >> 8) & 0xFF, (src_len >> 16) & 0xFF])

    compressed = bytearray()
    # `decoded` tracks what the decompressor would have produced — used as the search window.
    decoded = bytearray()
    src_pos = 0

    while src_pos < src_len:
        flag_pos = len(compressed)
        compressed.append(0)  # placeholder for flag byte
        flag = 0

        for bit_idx in range(8):
            if src_pos >= src_len:
                break

            # Search window: up to 4096 bytes of decoded history.
            win_start = max(0, len(decoded) - 4096)
            window = decoded[win_start:]
            win_len = len(window)

            best_len = 0
            best_disp = 0

            for w_off in range(win_len):
                mlen = 0
                span = win_len - w_off  # bytes from w_off to end of window
                while mlen < 18 and (src_pos + mlen) < src_len:
                    # Allow overlapping matches (run-length encoding style).
                    win_idx = w_off + (mlen % span)
                    if window[win_idx] != data[src_pos + mlen]:
                        break
                    mlen += 1

                if mlen >= 3 and mlen > best_len:
                    best_len = mlen
                    best_disp = span  # 1-based displacement = win_len - w_off

            if best_len >= 3:
                # Back-reference: set flag bit to 1.
                flag |= 1 << (7 - bit_idx)
                rl = best_len - 3        # 0–15, fits in 4 bits
                rd = best_disp - 1      # 0–4095, fits in 12 bits
                compressed.append((rl << 4) | (rd >> 8))
                compressed.append(rd & 0xFF)
                decoded.extend(data[src_pos : src_pos + best_len])
                src_pos += best_len
            else:
                # Literal: flag bit stays 0.
                compressed.append(data[src_pos])
                decoded.append(data[src_pos])
                src_pos += 1

        compressed[flag_pos] = flag

    return header + bytes(compressed)


# ── LZ11 (Nintendo 3DS) ──────────────────────────────────────────────────────


def decompress_lz11(data: bytes) -> bytes:
    """Decompress LZ11-compressed data (Nintendo 3DS format).

    :param data: Compressed data with 0x11 magic byte
    :returns: Decompressed bytes
    :raises DecompressionError: If magic byte is not 0x11 or data is invalid
    """
    if not data or data[0] != 0x11:
        raise DecompressionError("LZ11 magic byte 0x11 not found")
    size = data[1] | (data[2] << 8) | (data[3] << 16)
    out = bytearray()
    pos = 4
    while len(out) < size:
        try:
            flags = data[pos]
        except IndexError as exc:
            raise DecompressionError("LZ11 truncated: missing control byte") from exc
        pos += 1
        try:
            for bit in range(7, -1, -1):
                if len(out) >= size:
                    break
                if flags & (1 << bit):
                    b0 = data[pos]
                    indicator = (b0 >> 4) & 0xF
                    if indicator == 0:
                        length = ((b0 & 0xF) << 4) | ((data[pos + 1] >> 4) & 0xF)
                        length += 17
                        disp = ((data[pos + 1] & 0xF) << 8) | data[pos + 2]
                        pos += 3
                    elif indicator == 1:
                        b1_hi = data[pos + 1] << 4
                        b2_hi = (data[pos + 2] >> 4) & 0xF
                        length = ((b0 & 0xF) << 12) | b1_hi | b2_hi
                        length += 273
                        disp = ((data[pos + 2] & 0xF) << 8) | data[pos + 3]
                        pos += 4
                    else:
                        length = indicator + 1
                        disp = ((b0 & 0xF) << 8) | data[pos + 1]
                        pos += 2
                    disp += 1
                    for _ in range(length):
                        out.append(out[-disp])
                else:
                    out.append(data[pos])
                    pos += 1
        except (IndexError, struct.error) as exc:
            raise DecompressionError(str(exc)) from exc
    return bytes(out[:size])


def compress_lz11(data: bytes) -> bytes:
    """Compress data using LZ11 format (Nintendo 3DS).

    Simple literal-only compression. Valid but unoptimized.

    :param data: Data to compress
    :returns: Compressed bytes with 0x11 magic byte
    """
    size = len(data)
    header = bytes([0x11, size & 0xFF, (size >> 8) & 0xFF, (size >> 16) & 0xFF])
    out = bytearray(header)
    i = 0
    while i < size:
        chunk = data[i : i + 8]
        out.append(0x00)
        out.extend(chunk)
        i += len(chunk)
    return bytes(out)


# ── RLE (SNES) ───────────────────────────────────────────────────────────────


def decompress_rle(data: bytes) -> bytes:
    """Decompress RLE-compressed data (SNES format).

    :param data: RLE-compressed bytes
    :returns: Decompressed bytes
    """
    out = bytearray()
    pos = 0
    while pos < len(data):
        b = data[pos]
        pos += 1
        if b & 0x80:
            count = (b & 0x7F) + 3
            val = data[pos]
            pos += 1
            out.extend(bytes([val]) * count)
        else:
            count = (b & 0x7F) + 1
            out.extend(data[pos : pos + count])
            pos += count
    return bytes(out)


def compress_rle(data: bytes) -> bytes:
    """Compress data using RLE format (SNES).

    Simple literal-run RLE. Valid for decompressor above.

    :param data: Data to compress
    :returns: RLE-compressed bytes
    """
    out = bytearray()
    i = 0
    while i < len(data):
        chunk = data[i : i + 128]
        out.append(len(chunk) - 1)  # literal run, high bit clear
        out.extend(chunk)
        i += len(chunk)
    return bytes(out)
