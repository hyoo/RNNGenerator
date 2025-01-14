from __future__ import print_function
import os
import sys
import argparse
import pandas as pd
import numpy as np
from tqdm import tqdm
from openeye import oechem
from openeye import oeomega
from openeye import oefastrocs

def FromString(smiles, isomer=True, num_enantiomers=1):
    """
    Generates an set of conformers from a SMILES string
    """
    mol = oechem.OEMol()
    if not oechem.OESmilesToMol(mol, smiles):
        print("SMILES invalid for string", smiles)
        return None
    else:
        return FromMol(mol, isomer, num_enantiomers)


def FromMol(mol, isomer=True, num_enantiomers=-1):
    """
    Generates a set of conformers as an OEMol object
    Inputs:
        mol is an OEMol
        isomers is a boolean controling whether or not the various diasteriomers of a molecule are created
        num_enantiomers is the allowable number of enantiomers. For all, set to -1
    """
    omegaOpts = oeomega.OEOmegaOptions()
    omegaOpts.SetMaxConfs(10)
    omega = oeomega.OEOmega(omegaOpts)
    out_conf = []
    ofs = oechem.oemolostream("test.sdf")
    if not isomer:
        ret_code = omega.Build(mol)
        if ret_code == oeomega.OEOmegaReturnCode_Success:
            out_conf.append(mol)
        else:
            oechem.OEThrow.Warning("%s: %s" % (mol.GetTitle(), oeomega.OEGetOmegaError(ret_code)))

    elif isomer:
        for enantiomer in oeomega.OEFlipper(mol.GetActive(), 12, True):
            enantiomer = oechem.OEMol(enantiomer)
            ret_code = omega.Build(enantiomer)
            if ret_code == oeomega.OEOmegaReturnCode_Success:
                out_conf.append(enantiomer)
                num_enantiomers -= 1
                oechem.OEWriteMolecule(ofs, mol)
                if num_enantiomers == 0:
                    break
            else:
                oechem.OEThrow.Warning("%s: %s" % (mol.GetTitle(), oeomega.OEGetOmegaError(ret_code)))

    return out_conf


oepy = os.path.join(os.path.dirname(__file__), "..", "python")
sys.path.insert(0, os.path.realpath(oepy))

def getargs():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', type=str, required=True)
    parser.add_argument('-i', type=str, required=True)
    parser.add_argument('-o', type=str, required=True)
    return parser.parse_args()

def main():
    if not oefastrocs.OEFastROCSIsGPUReady():
        oechem.OEThrow.Info("No supported GPU available!")
        return 0


    args = getargs()

    dbname = args.d
    # read in database
    ifs = oechem.oemolistream()
    if not ifs.open(dbname):
        oechem.OEThrow.Fatal("Unable to open '%s'" % dbname)

    print("Opening database file %s ..." % dbname)
    timer = oechem.OEWallTimer()
    opts = oefastrocs.OEShapeDatabaseOptions()
    opts.SetLimit(1)
    dbase = oefastrocs.OEShapeDatabase()
    moldb = oechem.OEMolDatabase()




    if not moldb.Open(ifs):
        oechem.OEThrow.Fatal("Unable to open '%s'" % dbname)

    dots = oechem.OEThreadedDots(10000, 200, "conformers")
    if not dbase.Open(moldb, dots):
        oechem.OEThrow.Fatal("Unable to initialize OEShapeDatabase on '%s'" % dbname)

    dots.Total()
    print("%f seconds to load database" % timer.Elapsed())


    df = pd.read_csv(args.i)
    res = []
    for smile in tqdm(df.loc[:, 'smiles'].tolist()):
        resn = len(res)
        try:
            q = FromString(smile)[0]

            for score in dbase.GetSortedScores(q, 1):
                res.append(score.GetTanimotoCombo())
                break
        except KeyboardInterrupt:
            print("caught")
            exit()
        except:
            res.append(np.nan)
        if len(res) == resn:
            res.append(np.nan)

    df['fastroc'] = res
    print(df.head)
    df.to_csv(args.o, sep=',', index=False)

    return 0


if __name__ == '__main__':
    main()