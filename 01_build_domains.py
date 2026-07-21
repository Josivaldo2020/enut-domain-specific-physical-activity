#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
code/01_build_domains.py

Reconstructs the five physical activity energy expenditure domains
(exercise, unpaid domestic work, direct caregiving, paid work, travel)
from the Chilean Second National Time Use Survey (II ENUT 2023), assigning
metabolic equivalent (MET) values from the 2024 Adult Compendium of Physical
Activities, and writes a person-level analytic file for the survey analysis
in 02_survey_analysis.R.

Input : II ENUT 2023 public microdata CSV (comma-separated, latin-1).
Output: enut_analytic.csv  (analytic sample, CUT respondents)

Energy expenditure is expressed in MET-hours per typical day, where a typical
day combines weekday and weekend-day reports as (5/7 * weekday) + (2/7 * weekend).
Population means treat non-participation in an activity as a genuine zero.

Author: J. de Souza-Lima and collaborators. License: MIT.
"""

import numpy as np
import pandas as pd
import os

# ---------------------------------------------------------------------------
# 0. CONFIG: point this to the ENUT 2023 public CSV on your machine.
#    The public microdata are distributed as a single comma-separated file
#    (latin-1 encoding). Missing value code 96 is recoded to NaN.
# ---------------------------------------------------------------------------
ENUT_CSV = "250403-ii-enut-bdd-csv-v2.csv"   # <-- edit path as needed
OUT_CSV  = "enut_analytic.csv"

df = pd.read_csv(ENUT_CSV, sep=",", encoding="latin-1",
                 dtype={"id_persona": str, "id_hog": str,
                        "varstrat": str, "varunit": str})
df = df.replace(96, np.nan)

# ---------------------------------------------------------------------------
# 1. HOUSEHOLD INCOME QUINTILES (household level, then merged to persons)
#    Weighted by the household expansion factor fe_ch over per-capita income.
# ---------------------------------------------------------------------------
df["ing_t_pc"] = pd.to_numeric(df["ing_t_pc"], errors="coerce")
hog = df.dropna(subset=["ing_t_pc"]).drop_duplicates("id_hog")[
    ["id_hog", "ing_t_pc", "fe_ch"]].copy()
hog["fe_ch"] = pd.to_numeric(hog["fe_ch"], errors="coerce").fillna(0)
hog = hog.sort_values("ing_t_pc")
cw = (hog["fe_ch"].cumsum() / hog["fe_ch"].sum()).to_numpy()
hog["quintil"] = np.searchsorted([.2, .4, .6, .8, 1.0001], cw) + 1
df = df.merge(hog[["id_hog", "quintil"]], on="id_hog", how="left")

# ---------------------------------------------------------------------------
# 2. AGE GROUP and RECIPIENT-AGE MAP (for recipient-specific caregiving MET)
# ---------------------------------------------------------------------------
df["edad_num"] = pd.to_numeric(df["edad"], errors="coerce")
df["grupo_edad"] = np.select(
    [df["edad_num"].between(12, 17), df["edad_num"].between(18, 29),
     df["edad_num"].between(30, 44), df["edad_num"].between(45, 59),
     df["edad_num"] >= 60],
    ["12-17", "18-29", "30-44", "45-59", "60+"], default=None)

edad_map = (df.dropna(subset=["n_linea_p"])
              .assign(_n=lambda x: pd.to_numeric(x["n_linea_p"], errors="coerce"))
              .set_index(["id_hog", "_n"])["edad"].to_dict())

def edad_receptor(id_hog, nlin):
    """Age of a care recipient given household id and household line number."""
    out = np.full(len(id_hog), np.nan)
    for i, (h, n) in enumerate(zip(id_hog, nlin)):
        if pd.notna(n):
            out[i] = edad_map.get((h, int(n)), np.nan)
    return out

# ---------------------------------------------------------------------------
# 3. TYPICAL-DAY TIME helper: (5/7 weekday) + (2/7 weekend), zero if not done.
#    Participation flag p==2 means "did not do the activity" -> time set to 0.
# ---------------------------------------------------------------------------
def dia_tipo(p_ds, t_ds, p_fds, t_fds):
    def leg(p, t):
        t = t.copy(); t[p == 2] = 0.0; return t
    return leg(p_ds, t_ds) * 5/7 + leg(p_fds, t_fds) * 2/7

# ---------------------------------------------------------------------------
# 4. DOMAIN 1 - UNPAID DOMESTIC WORK (td items; MET from 2024 Compendium)
#    Composite item td5 uses the arithmetic mean of its component METs (~2.76).
# ---------------------------------------------------------------------------
MET_DOM = {"td1": 2.0, "td2": 2.3, "td3": 2.0, "td4": 3.3, "td5": 2.76,
           "td6": 2.5, "td7": 2.3, "td8": 1.8, "td9": 1.3, "td10": 2.5,
           "td11": 2.0, "td12": 1.3, "td25": 2.3, "td26": 2.0}
dom_cols = []
for td, met in MET_DOM.items():
    cs = [f"{td}_p_ds", f"{td}_t_ds", f"{td}_p_fds", f"{td}_t_fds"]
    if all(c in df.columns for c in cs):
        df[f"{td}_t_dt"] = dia_tipo(df[f"{td}_p_ds"], df[f"{td}_t_ds"],
                                    df[f"{td}_p_fds"], df[f"{td}_t_fds"])
        df[f"{td}_meth"] = df[f"{td}_t_dt"] * met
        dom_cols.append(f"{td}_meth")
df["dom_meth_dt"] = df[dom_cols].sum(axis=1, min_count=1)

# ---------------------------------------------------------------------------
# 5. DOMAIN 2 - DIRECT CAREGIVING (recipient-age-specific MET: child <15 vs adult)
#    MET_CUID[tc] = (MET_if_child, MET_if_adult). Time disaggregated per recipient.
# ---------------------------------------------------------------------------
MET_CUID = {"tc1": (2.0, 3.0), "tc2": (2.0, 3.0), "tc3": (2.0, 3.0),
            "tc4": (2.0, 1.8), "tc5": (3.0, 3.0), "tc6": (2.3, 1.8),
            "tc7": (2.3, 2.3), "tc8": (2.0, 1.8), "tc16": (2.3, 2.3),
            "tc17": (2.3, 2.3)}

def cuid_actividad(tc):
    met_n, met_a = MET_CUID[tc]
    ds = np.zeros(len(df)); fds = np.zeros(len(df))
    anyd = np.zeros(len(df), bool)
    for k in (1, 2, 3, 4):
        for per, acc in (("ds", "d"), ("fds", "f")):
            nc, tcl = f"{tc}_n{k}_{per}", f"{tc}_t_n{k}_{per}"
            if nc not in df.columns or tcl not in df.columns:
                continue
            er = edad_receptor(df["id_hog"], df[nc])
            t = pd.to_numeric(df[tcl], errors="coerce")
            met = np.where(er < 15, met_n, np.where(er >= 15, met_a, np.nan))
            contrib = t.values * met
            v = ~np.isnan(contrib); anyd |= v
            if acc == "d":
                ds = np.where(v, ds + np.nan_to_num(contrib), ds)
            else:
                fds = np.where(v, fds + np.nan_to_num(contrib), fds)
    dt = ds * 5/7 + fds * 2/7
    return np.where(anyd, dt, np.nan)

cuid_cols = []
for tc in MET_CUID:
    df[f"{tc}_meth_dt"] = cuid_actividad(tc)
    cuid_cols.append(f"{tc}_meth_dt")
df["cuid_meth_dt"] = df[cuid_cols].sum(axis=1, min_count=1)

# ---------------------------------------------------------------------------
# 6. DOMAIN 3 - LEISURE-TIME EXERCISE (vs6; sex-specific MET calibrated from
#    the 2024 National Survey of Physical Activity and Sport, ENAFyD)
#    ENUT sex coding: 1 = men, 2 = women.
# ---------------------------------------------------------------------------
df["vs6_t_dt"] = dia_tipo(df["vs6_p_ds"], df["vs6_t_ds"],
                          df["vs6_p_fds"], df["vs6_t_fds"])
df["met_vs6"] = df["sexo"].map({1: 6.84, 2: 6.12})
df["ejer_meth_dt"] = df["vs6_t_dt"] * df["met_vs6"]

# ---------------------------------------------------------------------------
# 7. DOMAIN 4 - PAID WORK (occupation-group MET via CIUO-08.CL; missing = 999)
#    Time = main (to5) + secondary (to9) occupation. No occupation code but
#    positive time -> generic light value 2.0.
# ---------------------------------------------------------------------------
MET_CIUO = {1: 1.5, 2: 1.8, 3: 2.0, 4: 4.0, 5: 4.5, 6: 3.3, 7: 3.5, 999: np.nan}
df["ciuo_num"] = pd.to_numeric(df["ciuo_agrupada"], errors="coerce")
df["met_ocup"] = df["ciuo_num"].map(MET_CIUO)

def dt_time(col):
    ds = pd.to_numeric(df.get(f"{col}_ds"), errors="coerce").fillna(0)
    fds = pd.to_numeric(df.get(f"{col}_fds"), errors="coerce").fillna(0)
    return ds * 5/7 + fds * 2/7

df["t_trabajo_dt"] = dt_time("to5_t") + dt_time("to9_t")
df["trab_meth_dt"] = df["t_trabajo_dt"] * df["met_ocup"].fillna(2.0)

# ---------------------------------------------------------------------------
# 8. DOMAIN 5 - TRAVEL (door-to-door, predominant declared mode)
#    Modes: 1 public 1.3 | 2 car 2.0 | 3 taxi 1.3 | 4 bicycle 6.8 | 5 walk 3.5
#    Active travel = walking + cycling (modes 4, 5).
#    Eight trip batteries, each with an origin and a destination leg.
# ---------------------------------------------------------------------------
MET_MODO = {1: 1.3, 2: 2.0, 3: 1.3, 4: 6.8, 5: 3.5, 6: np.nan, 7: np.nan}
ACT = {4, 5}
BAT = {"trabajo": ("to3", "to4", "to7", "to8"),
       "educacion": ("ed2", "ed3", "ed5", "ed6"),
       "compras": ("td20", "td21", "td23", "td24"),
       "tramites": ("td14", "td15", "td17", "td18"),
       "salud": ("cp7", "cp8", "cp10", "cp11"),
       "ce": ("tc12", "tc10", "tc15", "tc13"),
       "cs": ("tc21", "tc19", "tc25", "tc23"),
       "ct": ("tc31", "tc29", "tc34", "tc32")}

df["transp_meth_dt"] = 0.0
df["transp_activo_meth_dt"] = 0.0
anyt = pd.Series(False, index=df.index)
for nom, (ti, mi, tv, mv) in BAT.items():
    bat = pd.Series(0.0, index=df.index)
    ba = pd.Series(False, index=df.index)
    act = pd.Series(0.0, index=df.index)
    for tb, mb in [(ti, mi), (tv, mv)]:
        for per, w in [("ds", 5/7), ("fds", 2/7)]:
            modo = pd.to_numeric(df.get(f"{mb}_m_{per}"), errors="coerce")
            t = pd.to_numeric(df.get(f"{tb}_t_{per}"), errors="coerce")
            met = modo.map(MET_MODO)
            contrib = (t * met)
            dt_c = contrib.fillna(0) * w
            bat = bat.add(dt_c, fill_value=0)
            ba |= contrib.notna()
            act += np.where(modo.isin(list(ACT)), dt_c, 0.0)
    df["transp_meth_dt"] += np.where(ba, bat, 0.0)
    df["transp_activo_meth_dt"] += act
    anyt |= ba
df["transp_meth_dt"] = np.where(anyt, df["transp_meth_dt"], np.nan)

# ---------------------------------------------------------------------------
# 9. POPULATION COLUMNS (non-participant = 0) and TOTAL
# ---------------------------------------------------------------------------
df["dom_pob"]    = df["dom_meth_dt"]
df["cuid_pob"]   = df["cuid_meth_dt"].fillna(0.0)
df["ejer_pob"]   = df["ejer_meth_dt"].fillna(0.0)
df["trab_pob"]   = np.where(df["t_trabajo_dt"] > 0, df["trab_meth_dt"], 0.0)
df["transp_pob"] = df["transp_meth_dt"].fillna(0.0)
df["gasto_total"] = df[["dom_pob", "cuid_pob", "ejer_pob",
                        "trab_pob", "transp_pob"]].sum(axis=1)
df["obligado_no_lab"] = df["dom_pob"] + df["cuid_pob"]
df["obligado_total"]  = df["dom_pob"] + df["cuid_pob"] + df["trab_pob"]

# ---------------------------------------------------------------------------
# 10. WHO AEROBIC-EQUIVALENT ATTAINMENT (>=8.33 MET-h/week from >=3 MET only)
#     under three progressively inclusive definitions.
# ---------------------------------------------------------------------------
dom3 = df["td4_meth"] if "td4_meth" in df.columns else 0.0  # only td4 (3.3) is >=3

def cuid_ge3(tc):
    met_n, met_a = MET_CUID[tc]
    tot = np.zeros(len(df)); anyd = np.zeros(len(df), bool)
    for k in (1, 2, 3, 4):
        for per, w in [("ds", 5/7), ("fds", 2/7)]:
            nc, tcl = f"{tc}_n{k}_{per}", f"{tc}_t_n{k}_{per}"
            if nc not in df.columns or tcl not in df.columns:
                continue
            er = edad_receptor(df["id_hog"], df[nc])
            t = pd.to_numeric(df[tcl], errors="coerce")
            met = np.where(er < 15, met_n, np.where(er >= 15, met_a, np.nan))
            keep = np.where(met >= 3, t.values * met, 0.0) * w
            anyd |= ~np.isnan(t.values)
            tot = tot + np.nan_to_num(keep)
    return np.where(anyd, tot, 0.0)

cuid3 = np.zeros(len(df))
for tc in MET_CUID:
    cuid3 += cuid_ge3(tc)
trab3   = np.where(df["met_ocup"].fillna(2.0) >= 3, df["trab_pob"], 0.0)
ejer3   = df["ejer_pob"]                              # 6.12/6.84, always >=3
transp3 = df["transp_activo_meth_dt"].fillna(0.0)     # walk 3.5 / bike 6.8

wk_A = ejer3 * 7
wk_B = (ejer3 + transp3) * 7
wk_C = (ejer3 + transp3 + dom3 + cuid3 + trab3) * 7
df["cumple_A"] = (wk_A >= 8.33).astype(float)
df["cumple_B"] = (wk_B >= 8.33).astype(float)
df["cumple_C"] = (wk_C >= 8.33).astype(float)

# ---------------------------------------------------------------------------
# 11. WRITE ANALYTIC FILE (CUT respondents, i.e. valid person expansion factor)
# ---------------------------------------------------------------------------
keep_cols = ["varstrat", "varunit", "fe_cut", "sexo", "grupo_edad", "quintil",
             "dom_pob", "cuid_pob", "ejer_pob", "trab_pob", "transp_pob",
             "transp_activo_meth_dt", "obligado_no_lab", "obligado_total",
             "gasto_total", "cumple_A", "cumple_B", "cumple_C"]
out = df[df["fe_cut"].notna()][keep_cols].copy()
out.to_csv(OUT_CSV, index=False)
print(f"Wrote {OUT_CSV}: {out.shape[0]} rows, {out.shape[1]} columns.")
print("Crude population means by sex (1=men, 2=women):")
print(out.groupby("sexo")[["ejer_pob", "trab_pob", "dom_pob", "cuid_pob",
                           "transp_pob", "gasto_total"]].mean().round(2))
Move Python script to code directory
