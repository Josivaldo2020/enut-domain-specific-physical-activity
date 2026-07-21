#!/usr/bin/env Rscript
# 02_survey_analysis.R
#
# Complex-survey estimation for the ENUT 2023 physical activity energy
# expenditure analysis. Reads enut_analytic.csv (from 01_build_domains.py)
# and reproduces the manuscript tables: domain and aggregate means with
# standard errors, WHO aerobic-equivalent attainment with 95% confidence
# intervals, and total expenditure by age group and income quintile.
#
# Requires the 'survey' package.
# Author: J. de Souza-Lima and collaborators. License: MIT.

library(survey)
options(survey.lonely.psu = "certainty")

d <- read.csv("enut_analytic.csv", stringsAsFactors = FALSE)
d$varstrat <- as.factor(d$varstrat)
d$varunit  <- as.factor(d$varunit)
d$fe_cut   <- as.numeric(d$fe_cut)

dis <- svydesign(ids = ~varunit, strata = ~varstrat,
                 weights = ~fe_cut, data = d, nest = TRUE)

# --- Table 1 & 2: domain and aggregate means by sex, with SE -----------------
pm <- function(v) {
  s <- svyby(as.formula(paste0("~", v)), ~sexo, dis, svymean, na.rm = TRUE)
  cat(sprintf("  %-16s M=%.2f (SE %.3f)  W=%.2f (SE %.3f)  ratio W/M=%.3f\n",
      v, s[s$sexo==1,2], s[s$sexo==1,3],
         s[s$sexo==2,2], s[s$sexo==2,3], s[s$sexo==2,2]/s[s$sexo==1,2]))
}
cat("=== Tables 1 & 2: domains, aggregates, total (mean, SE) ===\n")
for (v in c("ejer_pob","trab_pob","dom_pob","cuid_pob","transp_pob",
            "obligado_no_lab","obligado_total","gasto_total")) pm(v)

# --- Table 3: WHO aerobic-equivalent attainment by sex, with 95% CI ----------
cat("\n=== Table 3: WHO-equivalent attainment (%, 95% CI) ===\n")
prop_sexo <- function(v) {
  cat(sprintf("%s:\n", v))
  for (s in c(1, 2)) {
    sub <- subset(dis, sexo == s)
    ci  <- svyciprop(as.formula(paste0("~", v)), sub, method = "logit")
    lab <- ifelse(s == 1, "M", "W")
    cat(sprintf("  %s = %.1f%% (95%% CI %.1f-%.1f)\n",
        lab, as.numeric(ci)*100, attr(ci,"ci")[1]*100, attr(ci,"ci")[2]*100))
  }
}
for (v in c("cumple_A","cumple_B","cumple_C")) prop_sexo(v)

# --- Table 5a: total expenditure by sex x age group (mean, SE) ---------------
cat("\n=== Table 5a: total by sex x age group ===\n")
se <- svyby(~gasto_total, ~sexo+grupo_edad, dis, svymean, na.rm = TRUE)
for (g in unique(se$grupo_edad)) {
  s <- se[se$grupo_edad == g, ]
  cat(sprintf("  %-6s M=%.2f (SE %.3f)  W=%.2f (SE %.3f)  ratio=%.3f\n",
      g, s[s$sexo==1,3], s[s$sexo==1,4],
         s[s$sexo==2,3], s[s$sexo==2,4], s[s$sexo==2,3]/s[s$sexo==1,3]))
}

# --- Table 5b: total expenditure by sex x income quintile (mean, SE) ---------
cat("\n=== Table 5b: total by sex x income quintile ===\n")
sq <- svyby(~gasto_total, ~sexo+quintil, dis, svymean, na.rm = TRUE)
for (q in sort(unique(sq$quintil[!is.na(sq$quintil)]))) {
  s <- sq[!is.na(sq$quintil) & sq$quintil == q, ]
  cat(sprintf("  Q%s M=%.2f (SE %.3f)  W=%.2f (SE %.3f)  ratio=%.3f\n",
      q, s[s$sexo==1,3], s[s$sexo==1,4],
         s[s$sexo==2,3], s[s$sexo==2,4], s[s$sexo==2,3]/s[s$sexo==1,3]))
}
