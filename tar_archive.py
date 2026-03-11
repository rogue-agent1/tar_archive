#!/usr/bin/env python3
"""TAR archive creator/reader — no tarfile module.

Implements POSIX ustar format: create, list, extract archives.

Usage:
    python tar_archive.py create output.tar file1.txt file2.txt
    python tar_archive.py list archive.tar
    python tar_archive.py --test
"""
import os, struct, sys, time

def _make_header(name, size, mtime=None, mode=0o644, typeflag=b'0'):
    """Create a 512-byte ustar tar header."""
    mtime = mtime or int(time.time())
    header = bytearray(512)
    # name (100)
    _put(header, 0, name.encode()[:100])
    # mode (8)
    _put(header, 100, f'{mode:07o}\0'.encode())
    # uid/gid (8 each)
    _put(header, 108, b'0001000\0')
    _put(header, 116, b'0001000\0')
    # size (12)
    _put(header, 124, f'{size:011o}\0'.encode())
    # mtime (12)
    _put(header, 136, f'{mtime:011o}\0'.encode())
    # typeflag
    header[156] = typeflag[0] if isinstance(typeflag, bytes) else ord(typeflag)
    # magic
    _put(header, 257, b'ustar\x0000')
    # version
    # uname/gname
    _put(header, 265, b'user\0')
    _put(header, 297, b'group\0')
    # Compute checksum
    _put(header, 148, b'        ')  # 8 spaces placeholder
    chksum = sum(header)
    _put(header, 148, f'{chksum:06o}\0 '.encode())
    return bytes(header)

def _put(buf, offset, data):
    buf[offset:offset+len(data)] = data

def create_tar(files: dict) -> bytes:
    """Create tar from {name: content_bytes} dict."""
    result = bytearray()
    for name, content in files.items():
        if isinstance(content, str): content = content.encode()
        header = _make_header(name, len(content))
        result.extend(header)
        result.extend(content)
        # Pad to 512-byte boundary
        pad = (512 - len(content) % 512) % 512
        result.extend(b'\0' * pad)
    # End-of-archive: two 512-byte zero blocks
    result.extend(b'\0' * 1024)
    return bytes(result)

def list_tar(data: bytes) -> list:
    """List files in a tar archive."""
    entries = []; pos = 0
    while pos + 512 <= len(data):
        header = data[pos:pos+512]
        if header == b'\0' * 512: break
        name = header[0:100].split(b'\0')[0].decode()
        size = int(header[124:135].split(b'\0')[0], 8)
        mode = header[100:107].split(b'\0')[0].decode()
        mtime = int(header[136:147].split(b'\0')[0], 8)
        typeflag = chr(header[156])
        entries.append({'name': name, 'size': size, 'mode': mode, 'mtime': mtime, 'type': typeflag})
        pos += 512 + size + (512 - size % 512) % 512
    return entries

def extract_tar(data: bytes) -> dict:
    """Extract all files. Returns {name: bytes}."""
    files = {}; pos = 0
    while pos + 512 <= len(data):
        header = data[pos:pos+512]
        if header == b'\0' * 512: break
        name = header[0:100].split(b'\0')[0].decode()
        size = int(header[124:135].split(b'\0')[0], 8)
        pos += 512
        files[name] = data[pos:pos+size]
        pos += size + (512 - size % 512) % 512
    return files

def verify_checksum(header: bytes) -> bool:
    stored = int(header[148:154].split(b'\0')[0], 8)
    h = bytearray(header)
    h[148:156] = b'        '
    return sum(h) == stored

def test():
    print("=== TAR Archive Tests ===\n")

    files = {
        "hello.txt": "Hello, World!\n",
        "data.bin": bytes(range(256)),
        "dir/nested.txt": "Nested file content\n",
    }
    tar = create_tar(files)
    assert len(tar) > 0
    print(f"✓ Created tar: {len(tar)} bytes, {len(files)} files")

    # List
    entries = list_tar(tar)
    assert len(entries) == 3
    names = [e['name'] for e in entries]
    assert "hello.txt" in names
    assert "dir/nested.txt" in names
    for e in entries:
        print(f"  {e['mode']} {e['size']:>6}  {e['name']}")
    print("✓ Listed entries")

    # Extract
    extracted = extract_tar(tar)
    assert extracted["hello.txt"] == b"Hello, World!\n"
    assert extracted["data.bin"] == bytes(range(256))
    assert extracted["dir/nested.txt"] == b"Nested file content\n"
    print("✓ Extracted all files correctly")

    # Checksum
    header = tar[:512]
    assert verify_checksum(header)
    print("✓ Header checksum valid")

    # Empty archive
    empty = create_tar({})
    assert list_tar(empty) == []
    print("✓ Empty archive")

    # Large file
    big = create_tar({"big.dat": b"x" * 100000})
    ext = extract_tar(big)
    assert len(ext["big.dat"]) == 100000
    print(f"✓ Large file: {len(ext['big.dat'])} bytes")

    # Roundtrip
    for name, content in files.items():
        c = content.encode() if isinstance(content, str) else content
        assert extracted[name] == c
    print("✓ Full roundtrip verified")

    print("\nAll tests passed! ✓")

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "--test": test()
    elif args[0] == "list":
        with open(args[1], 'rb') as f: data = f.read()
        for e in list_tar(data): print(f"{e['mode']} {e['size']:>8}  {e['name']}")
    elif args[0] == "create":
        out = args[1]; fls = {}
        for path in args[2:]:
            with open(path, 'rb') as f: fls[path] = f.read()
        with open(out, 'wb') as f: f.write(create_tar(fls))
        print(f"Created {out}")
