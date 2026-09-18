from rdkit import Chem
from rdkit.Chem import rdMolDescriptors


def validate_smiles(raw: str | None) -> dict:
    result = {
        "raw_smiles": raw or None,
        "canonical_smiles": None,
        "isomeric_smiles": None,
        "formula": None,
        "validation": {"rdkit_valid": False, "valence_valid": False, "stereochemistry": "unavailable", "error": None},
    }
    if not raw:
        result["validation"]["error"] = "No SMILES returned by OCSR"
        return result
    try:
        mol = Chem.MolFromSmiles(raw, sanitize=True)
        if mol is None:
            raise ValueError("RDKit could not parse or sanitize SMILES")
        stereo = Chem.FindMolChiralCenters(mol, includeUnassigned=True)
        result["canonical_smiles"] = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=False)
        result["isomeric_smiles"] = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
        result["formula"] = rdMolDescriptors.CalcMolFormula(mol)
        result["validation"].update(
            rdkit_valid=True,
            valence_valid=True,
            stereochemistry=("unassigned" if any(label == "?" for _, label in stereo) else "assigned" if stereo else "none"),
        )
    except Exception as exc:
        result["validation"]["error"] = str(exc)
    return result