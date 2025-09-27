import pandas as pd, numpy as np, re
from pathlib import Path
from typing import Optional, Tuple

def _norm_text(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _norm_code(s) -> str:
    if pd.isna(s):
        return ""
    return re.sub(r"\s+", "", str(s)).upper()

def load_addendum_b(path: str, hcpcs_col: Optional[str]=None, apc_col: Optional[str]=None) -> pd.DataFrame:
    """
    Loads CMS Addendum B (CSV or XLSX) and returns a 2-col DataFrame: ['HCPCS','APC'].
    It auto-detects the header row that contains 'HCPCS Code' and 'APC'.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    ext = p.suffix.lower()
    if ext in [".xlsx", ".xls"]:
        raw = pd.read_excel(p, header=None, dtype=str)
    else:
        raw = None
        for enc in ["utf-8-sig","latin1","utf-16","utf-16le","utf-16be"]:
            try:
                raw = pd.read_csv(p, header=None, dtype=str, encoding=enc)
                break
            except Exception:
                pass
        if raw is None:
            raise UnicodeDecodeError("Unable to read CSV with common encodings", b"", 0, 0, "decode failure")

    # find header row
    header_idx = None
    for i in range(min(80, len(raw))):
        row_vals = [str(x).strip() if pd.notna(x) else "" for x in list(raw.iloc[i].values)]
        if any("HCPCS Code" in v for v in row_vals) and any(v.strip()=="APC" for v in row_vals):
            header_idx = i
            break
    if header_idx is None:
        header_idx = 0

    df = pd.read_excel(p, header=header_idx, dtype=str) if ext in [".xlsx",".xls"] else pd.read_csv(p, header=header_idx, dtype=str, encoding="latin1")

    if hcpcs_col is None:
        hcpcs_candidates = [c for c in df.columns if "HCPCS" in str(c)]
        if not hcpcs_candidates:
            raise ValueError("Could not find HCPCS column in Addendum B")
        hcpcs_col = hcpcs_candidates[0]
    if apc_col is None:
        apc_candidates = [c for c in df.columns if str(c).strip().upper()=="APC" or "APC" in str(c).upper()]
        if not apc_candidates:
            raise ValueError("Could not find APC column in Addendum B")
        apc_col = apc_candidates[0]

    cross = df[[hcpcs_col, apc_col]].copy()
    cross.columns = ["HCPCS","APC"]
    cross["HCPCS"] = cross["HCPCS"].map(_norm_code)
    cross["APC"] = cross["APC"].map(_norm_code)
    cross = cross[(cross["HCPCS"]!="") & (cross["APC"]!="")].drop_duplicates()
    return cross

def map_prices_to_hcpcs(df_hospital: pd.DataFrame, crosswalk: pd.DataFrame, expand: bool=False) -> pd.DataFrame:
    """
    Maps payer/plan/pricing from APC rows onto CPT/HCPCS rows using a CMS Addendum B crosswalk.
    - expand=False: keep original shape (same number of rows/columns). Fill min/max pricing for mapped APCs;
                    fill estimated_amount only when unambiguous (single payer value).
    - expand=True:  duplicate CPT/HCPCS rows across all payer/plan rows tied to the mapped APC (payer-specific view).

    Returns a DataFrame with the SAME columns as df_hospital.
    """
    code_cols = sorted([c for c in df_hospital.columns if re.fullmatch(r"code\|\d+", c)])
    type_cols = sorted([c for c in df_hospital.columns if re.fullmatch(r"code\|\d+\|type", c)])

    APC = {"apc", "ambulatory payment classification"}
    CH  = {"cpt","hcpcs","hcpcs/cpt","hcpcs ii","hcpcs level ii","hcpcs level 2"}

    def has_type(row, targets):
        for tcol in type_cols:
            t = row.get(tcol)
            if isinstance(t, str) and _norm_text(t) in targets:
                return True
        return False

    def first_code_preferring_ch(row):
        # Prefer CPT/HCPCS code; else APC; else blank.
        for ccol, tcol in zip(code_cols, type_cols):
            t = str(row.get(tcol,"")).lower()
            if t.startswith(("cpt","hcpcs")):
                return str(row.get(ccol,"")), row.get(tcol,"")
        for ccol, tcol in zip(code_cols, type_cols):
            t = str(row.get(tcol,"")).lower()
            if t.startswith("apc"):
                return str(row.get(ccol,"")), row.get(tcol,"")
        return "", ""

    df = df_hospital.copy()
    df["__is_apc"] = df.apply(lambda r: has_type(r, APC), axis=1)
    df["__is_ch"]  = df.apply(lambda r: has_type(r, CH), axis=1)
    df[["__row_code","__row_type"]] = df.apply(lambda r: pd.Series(first_code_preferring_ch(r)), axis=1)
    df["__row_code_norm"] = df["__row_code"].map(_norm_code)

    # APC pricing table
    pricing_cols = [c for c in df.columns if c.startswith("standard_charge|")] + ["estimated_amount"]
    carrier_cols = ["payer_name","plan_name"]
    apc_prices = df.loc[df["__is_apc"], ["__row_code_norm"] + carrier_cols + pricing_cols].rename(columns={"__row_code_norm":"apc_code_norm"})

    # Crosswalk normalization
    cw = crosswalk.copy()
    cw["HCPCS_norm"] = cw["HCPCS"].map(_norm_code)
    cw["APC_norm"]   = cw["APC"].map(_norm_code)
    cw = cw[["HCPCS_norm","APC_norm"]].drop_duplicates()

    # Map CPT/HCPCS rows -> APC code
    df["__mapped_apc"] = np.where(df["__is_ch"], df["__row_code_norm"], "")
    df = df.merge(cw, left_on="__mapped_apc", right_on="HCPCS_norm", how="left")
    df["__mapped_apc"] = df["APC_norm"].fillna("")
    df.drop(columns=["HCPCS_norm","APC_norm"], inplace=True, errors="ignore")

    if expand:
        # Explode CPT rows across all payer/plan rows for that APC
        ch_rows = df[df["__is_ch"]].copy()
        non_ch = df[~df["__is_ch"]].copy()

        apc_prices_suf = apc_prices.add_prefix("__apc__")
        apc_prices_suf.rename(columns={"__apc__apc_code_norm":"apc_code_norm"}, inplace=True)

        ch_rows = ch_rows.merge(apc_prices_suf, left_on="__mapped_apc", right_on="apc_code_norm", how="left")

        # Fill CPT rows with APC pricing values where null
        for c in carrier_cols + pricing_cols:
            apc_c = "__apc__" + c
            if apc_c in ch_rows.columns:
                ch_rows[c] = ch_rows[c].combine_first(ch_rows[apc_c])

        # Drop helper columns and return only original columns
        drop_cols = [c for c in ch_rows.columns if c.startswith("__apc__")] + ["apc_code_norm"]
        ch_rows.drop(columns=drop_cols, inplace=True, errors="ignore")

        out_cols = list(df_hospital.columns)
        expanded = pd.concat([non_ch[out_cols], ch_rows[out_cols]], axis=0, ignore_index=True)
        return expanded

    else:
        # Preserve original shape: aggregate per-APC min/max (payer-agnostic) and fill CPT rows
        def _to_num(s): return pd.to_numeric(s, errors="coerce")
        agg = apc_prices.groupby("apc_code_norm", dropna=False).agg({
            "standard_charge|gross": lambda s: _to_num(s).min(),
            "standard_charge|discounted_cash": lambda s: _to_num(s).min(),
            "standard_charge|negotiated_dollar": lambda s: _to_num(s).min(),
            "standard_charge|min": lambda s: _to_num(s).min(),
            "standard_charge|max": lambda s: _to_num(s).max(),
            "estimated_amount": lambda s: _to_num(s).min(),
        })

        dfp = df.merge(agg, left_on="__mapped_apc", right_index=True, how="left", suffixes=("","__agg"))

        # Fill only where original is NaN
        for col in ["standard_charge|gross","standard_charge|discounted_cash","standard_charge|negotiated_dollar","standard_charge|min","standard_charge|max","estimated_amount"]:
            if col in dfp.columns:
                dfp[col] = dfp[col].fillna(dfp[col+"__agg"]) if (col+"__agg") in dfp.columns else dfp[col]

        out = dfp[[c for c in df_hospital.columns]].copy()
        return out
