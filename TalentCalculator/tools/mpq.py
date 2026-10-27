"""Minimal read-only MPQ (v1) reader for WoW 1.12 archives."""
import struct, zlib, bz2, sys

def _build_crypt_table():
    table = [0] * 0x500
    seed = 0x00100001
    for index1 in range(0x100):
        index2 = index1
        for _ in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            high = (seed & 0xFFFF) << 16
            seed = (seed * 125 + 3) % 0x2AAAAB
            low = seed & 0xFFFF
            table[index2] = high | low
            index2 += 0x100
    return table
CRYPT = _build_crypt_table()

def hash_string(text, hash_type):
    seed1, seed2 = 0x7FED7FED, 0xEEEEEEEE
    for character in text.upper().replace('/', '\\'):
        value = ord(character)
        seed1 = (CRYPT[(hash_type << 8) + value] ^ (seed1 + seed2)) & 0xFFFFFFFF
        seed2 = (value + seed1 + seed2 + (seed2 << 5) + 3) & 0xFFFFFFFF
    return seed1

def decrypt(data, key):
    seed = 0xEEEEEEEE
    words = list(struct.unpack('<%dI' % (len(data) // 4), data[:len(data) // 4 * 4]))
    for wordIndex in range(len(words)):
        seed = (seed + CRYPT[0x400 + (key & 0xFF)]) & 0xFFFFFFFF
        value = words[wordIndex] ^ ((key + seed) & 0xFFFFFFFF)
        key = ((((~key) << 0x15) + 0x11111111) | (key >> 0x0B)) & 0xFFFFFFFF
        seed = (value + seed + (seed << 5) + 3) & 0xFFFFFFFF
        words[wordIndex] = value
    return struct.pack('<%dI' % len(words), *words) + data[len(words) * 4:]

def explode(data):
    """PKWARE DCL implode decompression."""
    import io
    raise NotImplementedError("pkware implode")

class Archive:
    def __init__(self, path):
        self.file = open(path, 'rb')
        offset = 0
        while True:
            self.file.seek(offset)
            if self.file.read(4) == b'MPQ\x1a': break
            offset += 0x200
        self.base = offset
        self.file.seek(offset)
        (_, headerSize, archiveSize, version, sectorShift, hashOffset, blockOffset,
         hashCount, blockCount) = struct.unpack('<4sIIHHIIII', self.file.read(32))
        self.sectorSize = 512 << sectorShift
        self.file.seek(offset + hashOffset)
        hashData = decrypt(self.file.read(hashCount * 16), hash_string('(hash table)', 3))
        self.hashes = [struct.unpack_from('<IIHHI', hashData, entry * 16) for entry in range(hashCount)]
        self.file.seek(offset + blockOffset)
        blockData = decrypt(self.file.read(blockCount * 16), hash_string('(block table)', 3))
        self.blocks = [struct.unpack_from('<IIII', blockData, entry * 16) for entry in range(blockCount)]

    def find(self, name):
        hashCount = len(self.hashes)
        start = hash_string(name, 0) % hashCount
        nameA, nameB = hash_string(name, 1), hash_string(name, 2)
        for probe in range(hashCount):
            entryA, entryB, locale, platform, blockIndex = self.hashes[(start + probe) % hashCount]
            if blockIndex == 0xFFFFFFFF: return None
            if entryA == nameA and entryB == nameB and blockIndex != 0xFFFFFFFE:
                return self.blocks[blockIndex]
        return None

    def read(self, name):
        block = self.find(name)
        if block is None: return None
        position, compressedSize, fileSize, flags = block
        if not flags & 0x80000000: return None
        if flags & 0x02000000: return None  # deleted marker in patches
        self.file.seek(self.base + position)
        raw = self.file.read(compressedSize)
        key = None
        if flags & 0x00010000:
            key = hash_string(name.replace('/', '\\').split('\\')[-1], 3)
            if flags & 0x00020000: key = ((key + position) ^ fileSize) & 0xFFFFFFFF
        if flags & 0x01000000 or not flags & 0x00000300:  # single unit or stored
            data = decrypt(raw, key) if key is not None else raw
            if flags & 0x00000300 and compressedSize < fileSize:
                data = self._decompress(data, flags)
            return data[:fileSize]
        sectorCount = (fileSize + self.sectorSize - 1) // self.sectorSize
        tableBytes = raw[:(sectorCount + 1) * 4]
        if key is not None: tableBytes = decrypt(tableBytes, (key - 1) & 0xFFFFFFFF)
        offsets = struct.unpack('<%dI' % (sectorCount + 1), tableBytes)
        output = bytearray()
        for sectorIndex in range(sectorCount):
            sector = raw[offsets[sectorIndex]:offsets[sectorIndex + 1]]
            if key is not None: sector = decrypt(sector, (key + sectorIndex) & 0xFFFFFFFF)
            expected = min(self.sectorSize, fileSize - sectorIndex * self.sectorSize)
            if len(sector) < expected: sector = self._decompress(sector, flags)
            output += sector
        return bytes(output[:fileSize])

    def _decompress(self, data, flags):
        if flags & 0x00000100:  # imploded
            return pkware_explode(data)
        method = data[0]; payload = data[1:]
        if method == 0x02: return zlib.decompress(payload)
        if method == 0x10: return bz2.decompress(payload)
        if method == 0x08: return pkware_explode(payload)
        raise ValueError('unsupported compression 0x%02x' % method)

# ---- PKWARE DCL explode ----
def _decode_table(lengths):
    # returns dict (length, code) -> symbol, codes are bit-reversed canonical per DCL
    return lengths

_LEN_BITS = [3,2,3,3,4,4,4,5,5,5,5,6,6,6,7,7]
_LEN_CODE = [0x05,0x03,0x01,0x06,0x0A,0x02,0x0C,0x14,0x04,0x18,0x08,0x30,0x10,0x20,0x40,0x00]
_EX_LEN_BITS = [0,0,0,0,0,0,0,0,1,2,3,4,5,6,7,8]
_LEN_BASE = [0,1,2,3,4,5,6,7,8,10,14,22,38,70,134,262]
_DIST_BITS = [2,4,4,5,5,5,5,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8]
_DIST_CODE = [0x03,0x0D,0x05,0x19,0x09,0x11,0x01,0x3E,0x1E,0x2E,0x0E,0x36,0x16,0x26,0x06,0x3A,0x1A,0x2A,0x0A,0x32,0x12,0x22,0x42,0x02,0x7C,0x3C,0x5C,0x1C,0x6C,0x2C,0x4C,0x0C,0x74,0x34,0x54,0x14,0x64,0x24,0x44,0x04,0x78,0x38,0x58,0x18,0x68,0x28,0x48,0x08,0xF0,0x70,0xB0,0x30,0xD0,0x50,0x90,0x10,0xE0,0x60,0xA0,0x20,0xC0,0x40,0x80,0x00]

class _Bits:
    def __init__(self, data): self.data = data; self.position = 0; self.buffer = 0; self.count = 0
    def need(self, bitCount):
        while self.count < bitCount:
            byte = self.data[self.position] if self.position < len(self.data) else 0
            self.position += 1
            self.buffer |= byte << self.count; self.count += 8
    def peek(self, bitCount): self.need(bitCount); return self.buffer & ((1 << bitCount) - 1)
    def drop(self, bitCount): self.buffer >>= bitCount; self.count -= bitCount
    def take(self, bitCount): value = self.peek(bitCount); self.drop(bitCount); return value

def _decode(bits, codes, lengths):
    for symbol in range(len(codes)):
        if bits.peek(lengths[symbol]) == codes[symbol]:
            bits.drop(lengths[symbol]); return symbol
    raise ValueError('bad code')

def pkware_explode(data):
    literalCoded, dictBits = data[0], data[1]
    if literalCoded: raise NotImplementedError('coded literals')
    bits = _Bits(data[2:])
    output = bytearray()
    while True:
        if bits.take(1) == 0:
            output.append(bits.take(8)); continue
        lengthSymbol = _decode(bits, _LEN_CODE, _LEN_BITS)
        length = _LEN_BASE[lengthSymbol] + bits.take(_EX_LEN_BITS[lengthSymbol]) + 2
        if length == 519: break
        distSymbol = _decode(bits, _DIST_CODE, _DIST_BITS)
        if length == 2: distance = (distSymbol << 2) | bits.take(2)
        else: distance = (distSymbol << dictBits) | bits.take(dictBits)
        distance += 1
        for _ in range(length): output.append(output[-distance])
    return bytes(output)
