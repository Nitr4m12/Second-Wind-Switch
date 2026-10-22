#!/usr/bin/env python3
"""Repair Second Wind v1.9.10a-fix's Common UI for the Switch game update 1.9.0.

Read both packs from the user's extracted game/mod files. Keep the 1.9.0 texture
namespace and loading mask, transferring only the compatible Second Wind logos.
Works on the BNP's Bootup.pack before merging, or on a merged Bootup.pack.
Requires oead 1.3.0; no game data is distributed with this tool.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import oead

LOGOS = {'Logo3DGameTitle_00^l': (412, 306, 4), 'LogoDLC^q': (414, 314, 16)}


def yaz0(data):
    return bytes(oead.yaz0.decompress(data))


def compress_yaz0(data, header):
    packed = bytearray(oead.yaz0.compress(data))
    packed[8:16] = header[8:16]
    return bytes(packed)


def sarc_members(data):
    """name -> (absolute start, end) of every SARC member (as in make_romfs_patches.py)."""
    assert data[:4] == b'SARC' and data[6:8] == b'\xff\xfe'
    header, size, start = struct.unpack_from('<HxxII', data, 4)
    assert size == len(data) and data[header:header + 4] == b'SFAT'
    count = struct.unpack_from('<H', data, header + 6)[0]; names = header + 12 + count * 16
    assert data[names:names + 4] == b'SFNT'; names += 8
    out = {}
    for i in range(count):
        _, attribute, lo, hi = struct.unpack_from('<4I', data, header + 12 + i * 16)
        offset = names + (attribute & 0xffffff) * 4
        out[data[offset:data.index(0, offset, start)].decode()] = (start + lo, start + hi)
    return out

def repack(sarc, name, blob):
    """The SARC with member `name` replaced by `blob`, every other member byte-identical, in the original order and alignment."""
    start = struct.unpack_from('<I', sarc, 12)[0]
    fat = 0x14; count = struct.unpack_from('<H', sarc, fat + 6)[0]
    nodes = [list(struct.unpack_from('<4I', sarc, fat + 12 + i * 16)) for i in range(count)]
    members = sarc_members(sarc); by_range = {(lo, hi): k for k, (lo, hi) in members.items()}
    blobs = [blob if by_range[(start + n[2], start + n[3])] == name else sarc[start + n[2]:start + n[3]] for n in nodes]

    def alignment(offset):
        a = 1
        while offset % (a * 2) == 0 and a < 0x2000:
            a *= 2
        return a
    data, placed = bytearray(), {}
    for i in sorted(range(count), key=lambda i: nodes[i][2]):
        a = alignment(nodes[i][2]) if nodes[i][2] else 1
        while len(data) % a:
            data += b'\0'
        placed[i] = (len(data), len(data) + len(blobs[i])); data += blobs[i]
    head = bytearray(sarc[:start])
    for i in range(count):
        struct.pack_into('<II', head, fat + 12 + i * 16 + 8, *placed[i])
    out = bytearray(bytes(head) + bytes(data)); struct.pack_into('<I', out, 8, len(out)); out = bytes(out)
    check = sarc_members(out)
    for k, (lo, hi) in members.items():
        assert out[check[k][0]:check[k][1]] == (blob if k == name else sarc[lo:hi]), k
    return out

def block_offset(x,y,row,tile):
    bh=1<<tile
    return ((y//(8*bh))*((row+63)//64)+(x//64))*512*bh+(y%(8*bh)//8)*512+(x%64//32)*256+(y%8//2)*64+(x%32//16)*32+(y%2)*16+x%16

def texture_rows(data):
    assert data[:8]==b'BNTX\0\0\0\0'
    table=struct.unpack_from('<Q',data,40)[0]
    for i in range(struct.unpack_from('<I',data,36)[0]):
        at=struct.unpack_from('<Q',data,table+8*i)[0];assert data[at:at+4]==b'BRTI'
        name_at=struct.unpack_from('<Q',data,at+96)[0]
        name=data[name_at+2:data.index(0,name_at+2)].decode()
        yield name,at

def surface(bank,at):
    width,height,depth,layers,tile=struct.unpack_from('<5I',bank,at+36)
    size=struct.unpack_from('<I',bank,at+80)[0];pt=struct.unpack_from('<Q',bank,at+112)[0]
    start=struct.unpack_from('<Q',bank,pt)[0]
    assert depth==layers==1 and start+size<=len(bank),'unknown texture storage'
    return width,height,tile&7,size,start

def rebase_bank(stock,mod):
    original=dict(texture_rows(stock));changed=dict(texture_rows(mod));out=bytearray(stock)
    for name,(width,height,block_bytes) in LOGOS.items():
        dst,src=original[name],changed[name]
        w,h,tile,size,start=surface(stock,dst);mw,mh,mtile,msize,mstart=surface(mod,src)
        assert (w,h)==(mw,mh)==(width,height),'unknown logo dimensions'
        expected=(0xb06,0xb01) if block_bytes==4 else (0x1c06,0x1c01)
        assert (struct.unpack_from('<I',stock,dst+28)[0],struct.unpack_from('<I',mod,src+28)[0])==expected,'unknown logo format'
        assert stock[dst+88:dst+92]==mod[src+88:src+92],'unknown logo component mapping'
        columns=width if block_bytes==4 else (width+3)//4
        rows=height if block_bytes==4 else (height+3)//4;stride=columns*block_bytes
        for y in range(rows):
            for x in range(columns):
                a=block_offset(x*block_bytes,y,stride,tile);b=block_offset(x*block_bytes,y,stride,mtile)
                assert a+block_bytes<=size and b+block_bytes<=msize
                out[start+a:start+a+block_bytes]=mod[mstart+b:mstart+b+block_bytes]
        out[dst+28:dst+32]=mod[src+28:src+32]
    return bytes(out),{'retained_190_textures':sorted(original.keys()-changed.keys()),'logos':sorted(LOGOS),
                       'omitted_old_only_textures':sorted(changed.keys()-original.keys()),'loading_mask':'stock 1.9.0'}

def port_bootup(stock,mod):
    name='Layout/Common.sblarc';sm,mm=sarc_members(stock),sarc_members(mod)
    old=mod[slice(*mm[name])];sc=yaz0(stock[slice(*sm[name])]);mc=yaz0(old);s,m=sarc_members(sc),sarc_members(mc)
    texture='timg/__Combined.bntx'
    assert m.keys() <= s.keys(),'unknown Common UI member set'
    for key in m:
        if key!=texture:assert sc[slice(*s[key])]==mc[slice(*m[key])],f'mod changes {key}; cannot automatically rebase its layout'
    bank,report=rebase_bank(sc[slice(*s[texture])],mc[slice(*m[texture])])
    common=repack(mc,texture,bank)
    assert len(common)<=len(mc),'rebased UI exceeds the merged resource budget'
    packed=compress_yaz0(common,old);assert yaz0(packed)==common
    out=repack(mod,name,packed);new=sarc_members(out)
    for key in mm:
        if key!=name:assert mod[slice(*mm[key])]==out[slice(*new[key])],key
    report.update(common_before=len(mc),common_after=len(common),bootup_sha256=hashlib.sha256(out).hexdigest())
    return out,report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-bootup', type=Path, required=True, help="Bootup.pack from the original Switch 1.9.0 RomFS")
    parser.add_argument('--second-wind-bootup', type=Path, required=True, help="Second Wind's original or merged Bootup.pack")
    parser.add_argument('--output', type=Path, required=True, help="new compatible Bootup.pack; existing files are refused")
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists; choose a new path')
    output, report = port_bootup(args.stock_bootup.read_bytes(), args.second_wind_bootup.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as file:
        file.write(output)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
