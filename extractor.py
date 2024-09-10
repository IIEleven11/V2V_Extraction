#!/bin/python3

import json
import sys
import os
import zipfile
import re
import glob
import traceback
import logging
import tqdm

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable):
        return iterable

SCRIPT_VERSION = '2.1'

# logging.getLogger().setLevel(logging.WARNING)
logging.getLogger().setLevel(logging.INFO)


def update_dict(d, fn, key=None):
    if isinstance(d, dict):
        for k, v in d.items():
            d[k] = update_dict(v, fn, k)
        # return not needed to update dicts by reference, but used
        # here to assist in assigning subtrees
        return d
    elif isinstance(d, list):
        return [update_dict(i, fn) for i in d]
    else:
        return fn(d, key)


def update_dict_selfname(d, self_name):
    def update_fn(v, key=None):
        if key == 'id' and isinstance(v, str):
            return v.replace("SELF:/", self_name + ":/")
        else:
            return v

    update_dict(d, update_fn)


def getPersonAtoms(scenejson):
    for atom in scenejson['atoms']:
        if atom['type'] == "Person":
            yield atom


class BaseExtractor(object):
    """docstring for BaseExtractor"""
    out_dir_verify = "./Custom/Atom/Person/"

    def __init__(self, noclobber=False):
        super(BaseExtractor, self).__init__()
        self.noclobber = noclobber
        self.dupes = set()
        self.out_dir = self.getOutDir()

        os.makedirs(self.out_dir, exist_ok=True)

    def getOutDir(self):
        if not os.path.isdir(self.out_dir_verify):
            logging.error("Script is not being run from the VaM root directory!")
            logging.warning("Can't cleanly merge into Person/Appearance presets; making ExtractedAppearance folder instead.")
            return self.out_dir_fallback
        else:
            return self.out_dir_wanted

    def extractFromVar(self, var):
        __, filename = os.path.split(var)
        self_name, __ = os.path.splitext(filename)

        author = self_name.split('.')[0]

        try:
            with zipfile.ZipFile(var) as varzip:
                infodict = {
                    zi.filename: zi
                    for zi in varzip.infolist()
                }
                zip_scenes = {
                    k: v for k, v in infodict.items()
                    if k.startswith("Saves/scene") and k.endswith(".json")
                }
                for scenejsonpath in zip_scenes.keys():
                    logging.debug("%s:%s", var, scenejsonpath)

                    __, sjp_filename = os.path.split(scenejsonpath)
                    sjp_plain, sjp_ext = os.path.splitext(sjp_filename)

                    with varzip.open(scenejsonpath, 'r') as fp:
                        scenejson = json.load(fp)

                    if False:
                        update_dict_selfname(scenejson, self_name)
                    else:
                        # This method is potentially inaccurate but MUCH faster:
                        scenejson = json.loads(json.dumps(scenejson).replace("SELF:/", self_name + ":/"))

                    def readthumb():
                        return varzip.open(scenejsonpath.replace('.json', '.jpg'), 'r')

                    def outnameFn(atom):
                        return f"Preset_{self_name}.{sjp_plain}{atom['id'].replace('Person', '')}".replace('#', '').replace('/', '-')

                    self.extractFromSceneJson(scenejson, outnameFn, readthumb)

        except json.JSONDecodeError:
            print(var)
            traceback.print_exc()
            os.rename(var, var + '.invalid')
        except zipfile.BadZipFile:
            print(var)
            traceback.print_exc()
            os.rename(var, var + '.invalid')

    def extractFromSceneJsonPath(self, scenejsonpath):
        __, sjp_filename = os.path.split(scenejsonpath)
        sjp_plain, sjp_ext = os.path.splitext(sjp_filename)

        def readthumb():
            return open(scenejsonpath.replace('.json', '.jpg'), 'rb')

        def outnameFn(atom):
            return f"Preset_!local.{sjp_plain}{atom['id'].replace('Person', '')}".replace('#', '').replace('/', '-')

        with open(scenejsonpath, 'r', encoding='utf-8') as fp:
            self.extractFromSceneJson(json.load(fp), outnameFn, readthumb)

    def presetOutname(self, outname, ext):
        return os.path.join(self.out_dir, outname + ext)

    def extractFromSceneJson(self, scenejson, outnameFn, readthumb):
        # print([atom['id'] for atom in scenejson['atoms'] if atom['type'] == 'Person'])

        for atom in getPersonAtoms(scenejson):
            outname = outnameFn(atom)
            if self.noclobber and os.path.isfile(self.presetOutname(outname, '.vap')):
                logging.info(f"Skipping {outname!r}")
                continue

            # print(atom['id'])
            preset = {
                "setUnlistedParamsToDefault": "true",
                'storables': self.filterPersonStorables(atom)
            }

            self.savePreset(preset, outname, readthumb)

    def savePreset(self, preset, outname, readthumb):
        preset_hash = json.dumps(preset, sort_keys=True)
        if preset_hash not in self.dupes:
            outpath = self.presetOutname(outname, '.vap')
            with open(outpath, 'w', encoding='utf-8') as fp:
                logging.info("-> %s", outpath)
                fp.write(json.dumps(preset, indent=3, ensure_ascii=False))
            try:
                img_outpath = self.presetOutname(outname, '.jpg')
                with open(img_outpath, 'wb') as fp:
                    with readthumb() as fp2:
                        fp.write(fp2.read())
            except (KeyError, FileNotFoundError):
                # No image in archive
                pass
            self.dupes.add(preset_hash)
        else:
            # logging.warn("Skip duplicate %s", outname)
            pass

    def filterPersonStorables(self, atom):
        raise NotImplementedError()

class AppearanceExtractor(BaseExtractor):
    out_dir_wanted = "./Custom/Atom/Person/Appearance/extracted/"
    out_dir_fallback = "./ExtractedAppearance/"

    def filterPersonStorables(self, atom):
        storables = atom['storables']
        storables_new = []
        for storable in storables:
            storable.pop("position", None)
            storable.pop("rotation", None)

            # Remove all keys containing these substrings
            for key in [*storable.keys()]:
                if any(ss in key.lower() for ss in ['position', 'rotation']):
                    storable.pop(key)

            # Remove all storables whose ids contain these substrings
            if any(ss in storable['id'].lower() for ss in ["control", "trigger", "plugin", "preset", "animation"]):
                # print("pop", storable['id'])
                storables.remove(storable)
                continue

            # Remove transient morphs
            if storable['id'] == "geometry" and 'morphs' in storable:
                for morph in [*storable['morphs']]:
                    if any(re.match(ss, morph.get('uid', '')) for ss in [
                        r'Breast Impact',
                        r'^OpenXXL$',
                        r'^Eyelids (Top|Bottom) (Down|Up) (Left|Right)$', r'Brow .*(Up|Down)', r'^(Left|Right) Fingers',
                        r'^Mouth Open', r'Tongue In-Out', r'^Smile',
                        'Shock', 'Surprise', 'Fear', 'Pain', 'Concentrate', 'Eyes Closed', r'^Flirting',
                    ]):
                        # print(morph)
                        storable['morphs'].remove(morph)

            # Remove storables with just an id and no properties
            if len(storable.keys()) > 1:
                storables_new.append(storable)

        return storables_new


class OutfitExtractor(BaseExtractor):
    out_dir_wanted = "./Custom/Atom/Person/Clothing/extracted/"
    out_dir_fallback = "./ExtractedOutfits/"

    def filterPersonStorables(self, atom):
        storables = atom['storables']

        clothing_master = next(filter(lambda v: v['id'] == 'geometry' and 'clothing' in v.keys(), storables))
        clothing = clothing_master['clothing']
        try:
            clothing_ids = [c.get('internalId', c['id']) for c in clothing]
        except KeyError:
            print(clothing)
            raise

        storables_new = [
            {
                "id": "geometry",
                "clothing": clothing
            }
        ]
        for storable in storables:
            if any(storable['id'].startswith(id_) for id_ in clothing_ids):
                storables_new.append(storable)
            # else:
            #     print(storable['id'], clothing_ids)

        # print(storables_new)
        return storables_new

def add_bool_arg(parser, name, default=False, **kwargs):
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--' + name, dest=name, action='store_true', **kwargs)
    group.add_argument('--no-' + name, dest=name, action='store_false')
    parser.set_defaults(**{name: default})


def parse_args():
    import argparse
    parser = argparse.ArgumentParser(
        description="Exports presets",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('input_globs', help="Input files or fileglobs", nargs='+')
    add_bool_arg(parser, 'appearance', default=True, help="Extract appearance (body) presets")
    add_bool_arg(parser, 'outfit', default=False, help="Extract outfit (clothing) presets")

    parser.add_argument('--no-clobber', action='store_true', help="If set, don't overwrite files.", default=False)
    return parser.parse_args()


def main():
    print('Appearance Preset Extractor', SCRIPT_VERSION,)

    # Interactive CLI
    print("\nWelcome to the Appearance Preset Extractor!")
    
    # Get input files, fileglobs, or folder path
    input_path = input("Enter input files, fileglobs, or folder path: ")
    
    # Check if the input is a directory
    if os.path.isdir(input_path):
        # If it's a directory, get all .var and .json files in it
        input_globs = [os.path.join(input_path, '*.var'), os.path.join(input_path, '*.json')]
    else:
        # If it's not a directory, split the input as before
        input_globs = input_path.split()
    
    # Get appearance option
    appearance = input("Extract appearance (body) presets? (y/n): ").lower().startswith('y')
    
    # Get outfit option
    outfit = input("Extract outfit (clothing) presets? (y/n): ").lower().startswith('y')
    
    # Get no-clobber option
    no_clobber = input("Overwrite existing files? (y/n): ").lower().startswith('n')

    # Create a namespace object to mimic argparse's behavior
    from types import SimpleNamespace
    args = SimpleNamespace(
        input_globs=input_globs,
        appearance=appearance,
        outfit=outfit,
        no_clobber=no_clobber
    )

    extractors = []
    if args.appearance:
        extractors.append(AppearanceExtractor)
    if args.outfit:
        extractors.append(OutfitExtractor)

    try:
        for etype in extractors:
            extractor = etype(noclobber=args.no_clobber)
            iterable = sum((glob.glob(a, recursive=True) for a in args.input_globs), [])
            for filepath in tqdm(iterable, desc="Processing files", unit="file"):
                __, filename = os.path.split(filepath)
                self_name, ext = os.path.splitext(filename)

                try:
                    if ext.lower() == ".var":
                        extractor.extractFromVar(filepath)
                    elif ext.lower() == ".json":
                        extractor.extractFromSceneJsonPath(filepath)
                    else:
                        print(f"Skipping unsupported file: {filepath}")
                except KeyError:
                    pass

    except KeyboardInterrupt:
        return

    print("\nExtraction complete!")
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
