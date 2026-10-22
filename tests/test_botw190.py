"""Retain the 1.9.0 texture namespace when transferring an older mod's title logos."""
import importlib.util
from pathlib import Path
import struct
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('second_wind_port',ROOT/'tools/port_botw190.py')
port=importlib.util.module_from_spec(spec);spec.loader.exec_module(port)

def bank(mod=False):
 b=bytearray(4096);b[:8]=b'BNTX\0\0\0\0';struct.pack_into('<IQ',b,36,3,128);regions={}
 items=[('Logo3DGameTitle_00^l',412,306,638976,0xb01 if mod else 0xb06,4),
        ('LogoDLC^q',414,314,212992,0x1c01 if mod else 0x1c06,4 if mod else 3),
        ('OldOnly' if mod else 'RequiredBy190',16,16,4096,0xb06,0)]
 for i,(name,w,h,size,fmt,tile) in enumerate(items):
  p=512+i*160;struct.pack_into('<Q',b,128+i*8,p);b[p:p+4]=b'BRTI';struct.pack_into('<I',b,p+28,fmt)
  struct.pack_into('<5I',b,p+36,w,h,1,1,tile);struct.pack_into('<II',b,p+80,size,512);struct.pack_into('<I',b,p+88,0x05040302)
  n=1100+i*64;struct.pack_into('<Q',b,p+96,n);struct.pack_into('<H',b,n,len(name));b[n+2:n+3+len(name)]=name.encode()+b'\0'
  ptr=1400+i*8;struct.pack_into('<Q',b,p+112,ptr);struct.pack_into('<Q',b,ptr,len(b));lo=len(b)
  b.extend(bytes([0x90+i if mod else 0x10+i])*size);regions[name]=(p,lo,len(b))
 return bytes(b),regions

class SecondWindPort(unittest.TestCase):
 def test_new_game_textures_are_retained_and_only_logo_data_changes(self):
  stock,regions=bank();mod,_=bank(True);out,report=port.rebase_bank(stock,mod)
  self.assertEqual(len(out),len(stock));self.assertEqual(dict(port.texture_rows(out)).keys(),dict(port.texture_rows(stock)).keys())
  self.assertEqual(report['retained_190_textures'],['RequiredBy190']);self.assertEqual(report['omitted_old_only_textures'],['OldOnly'])
  p,lo,hi=regions['RequiredBy190'];self.assertEqual(out[lo:hi],stock[lo:hi])
  restored=bytearray(out)
  for name in port.LOGOS:
   p,lo,hi=regions[name];self.assertNotEqual(out[lo:hi],stock[lo:hi]);restored[lo:hi]=stock[lo:hi];restored[p+28:p+32]=stock[p+28:p+32]
  self.assertEqual(bytes(restored),stock)
 def test_unknown_logo_geometry_is_refused(self):
  stock,_=bank();mod,r=bank(True);mod=bytearray(mod);struct.pack_into('<I',mod,r['LogoDLC^q'][0]+36,415)
  with self.assertRaisesRegex(AssertionError,'dimensions'):port.rebase_bank(stock,bytes(mod))
