"""The compatibility repair must retain merged game data and reject layout changes."""
import importlib.util
from pathlib import Path
import unittest
import oead
from test_botw190 import bank

spec = importlib.util.spec_from_file_location('port', Path(__file__).resolve().parents[1]/'tools/port_botw190.py')
port = importlib.util.module_from_spec(spec)
spec.loader.exec_module(port)


def sarc(files):
    writer = oead.SarcWriter(oead.Endianness.Little)
    for name, data in files.items():
        writer.files[name] = data
    return bytes(writer.write()[1])


def bootup(mod=False, changed_layout=False):
    textures, _ = bank(mod)
    common = sarc({'timg/__Combined.bntx': textures, 'blyt/Test.bflyt': b'changed' if changed_layout else b'same layout'})
    return sarc({'Layout/Common.sblarc': bytes(oead.yaz0.compress(common)), 'GameData/Test.sarc': b'merged mod game data' if mod else b'original game data'})


class PackRepair(unittest.TestCase):
    def test_game_data_and_other_members_are_preserved(self):
        stock, mod = bootup(), bootup(True)
        result, report = port.port_bootup(stock, mod)
        members = port.sarc_members(result)
        self.assertEqual(result[slice(*members['GameData/Test.sarc'])], b'merged mod game data')
        common = port.yaz0(result[slice(*members['Layout/Common.sblarc'])])
        self.assertEqual(common[slice(*port.sarc_members(common)['blyt/Test.bflyt'])], b'same layout')
        self.assertLessEqual(report['common_after'], report['common_before'])

    def test_partial_bnp_common_archive_is_supported(self):
        stock = bootup()
        textures, _ = bank(True)
        common = sarc({'timg/__Combined.bntx': textures})
        mod = sarc({'Layout/Common.sblarc': bytes(oead.yaz0.compress(common)), 'GameData/Test.sarc': b'mod data'})
        result, _ = port.port_bootup(stock, mod)
        members = port.sarc_members(result)
        common = port.yaz0(result[slice(*members['Layout/Common.sblarc'])])
        self.assertEqual(set(port.sarc_members(common)), {'timg/__Combined.bntx'})
        self.assertEqual(result[slice(*members['GameData/Test.sarc'])], b'mod data')

    def test_unknown_layout_changes_are_refused(self):
        with self.assertRaisesRegex(AssertionError, 'cannot automatically rebase'):
            port.port_bootup(bootup(), bootup(True, True))
