# Experimental compatibility with Switch BotW 1.9.0

Second Wind **v1.9.10a-fix** is the mod release number; it does not mean the package targets game update **1.9.0**.
The existing BNP carries an older `Layout/Common.sblarc` texture bank. Six textures referenced by the 1.9.0 layouts are missing from that bank, causing a null-texture failure after loading a save.

`tools/port_botw190.py` repairs that compatibility problem using the player's original 1.9.0 `Pack/Bootup.pack`. It preserves the complete 1.9.0 texture namespace, transfers Second Wind's title and DLC logos with their correct formats/tiling, and keeps the stock loading mask. All other members of Second Wind's Bootup stay byte-identical. Both the BNP's partial Common archive and a fully merged Common archive are supported; unfamiliar logo geometry or changed layout members are refused.

## Prepare the compatible package

Requirements: Python 3.10 or later, `oead` and 7-Zip (`7z` or `7zz`). Obtain the original `Pack/Bootup.pack` from your own **Switch 1.9.0** RomFS. Do not use a 1.6.0 pack or another mod's pack as the stock input.

From the repository directory:

```sh
python3 -m pip install -r tools/requirements-botw190.txt
7z x /path/to/Second_Wind_v1_9_10a-fix_switch.bnp -osecond-wind-190
python3 tools/port_botw190.py \
  --stock-bootup /path/to/original-1.9.0/Pack/Bootup.pack \
  --second-wind-bootup second-wind-190/01007EF00011E000/romfs/Pack/Bootup.pack \
  --output Bootup-190.pack \
  --report botw190-report.json
cp Bootup-190.pack second-wind-190/01007EF00011E000/romfs/Pack/Bootup.pack
```

The tool writes a new output file and refuses an existing output. Check the report: `retained_190_textures` should list six names, including `LogoDLCPass_Port^d` and `DLCLogoPack12LR_Port2^s`.

Repackage the contents with the original `info.json` and `logs/` at the archive root:

```sh
cd second-wind-190
7z a -t7z ../Second_Wind_v1_9_10a-botw190.bnp .
```

Import the resulting BNP into the mod manager and merge/export against the actual **1.9.0 base and DLC files**. Keep the generated resource-size table and both base/DLC outputs. The BNP's merge logs are still required; copying its unmerged RomFS files directly into the game is insufficient. After changing an existing installation, regenerate its merged output.

The same tool can instead repair a correctly merged Bootup using that merged pack as `--second-wind-bootup`. Apply that output to the installation after the merge; a later remerge will otherwise overwrite it.

### Legacy BCML with oead 1.3.0

During verification, BCML's plain `Parameter(int)` calls with oead 1.3.0 selected the floating-point overload. This exported `DropTable` `TableNum` fields as floats and caused an actor-loading crash. If using that combination, the merger's integer constructor calls must explicitly use `oead.S32(value)` and all mergers must be rerun before export. Do not convert floating-point probabilities to integers. The verified export had all 151 `TableNum` fields represented as integers. This is a merger compatibility issue, separate from the UI repair; the tool does not rewrite drop-table data or modify the mod manager.

## Verification and limits

```sh
python3 -m unittest discover -s tests -v
```

Five synthetic tests cover preservation of the new texture namespace, unrelated texture data, merged game data, partial BNP archives, and refusal of unfamiliar dimensions/layout changes. The tool was also run on the released v1.9.10a-fix BNP and an original 1.9.0 Bootup: its repaired BNTX exactly matched the texture bank used in a successful 1.9.0 world-load test. The Common archive became smaller, and every other original BNP Bootup member remained byte-identical.

This establishes the repaired assets can load on 1.9.0. A full playthrough of Second Wind's quests, shrines and DLC interactions has not been verified, so compatibility remains experimental. No game or mod asset files are included in this change.
