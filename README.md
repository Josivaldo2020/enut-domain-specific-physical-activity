# The invisible physical activity: analysis code

Reproducible analysis code for the study linking the Chilean Second National
Time Use Survey (II ENUT 2023) to the 2024 Adult Compendium of Physical
Activities, to estimate physical activity energy expenditure across five
domains and quantify the gendered measurement of physical activity in urban
Chile.

## What this code does

The pipeline estimates population physical activity energy expenditure
(MET-hours per typical day) across five domains, by sex, age group and
household income quintile, and computes attainment of the WHO aerobic
equivalent under three progressively inclusive definitions.

- **`code/01_build_domains.py`** (Python 3): reads the ENUT 2023 public
  microdata, reconstructs the five domains (leisure-time exercise, unpaid
  domestic work, direct caregiving, paid work, travel), assigns MET values
  from the 2024 Adult Compendium (with recipient-age-specific values for
  caregiving, occupation-group values for paid work, and a sex-specific
  exercise value calibrated from the 2024 National Survey of Physical Activity
  and Sport), builds household income quintiles at the household level and
  merges them to persons, derives the WHO-attainment indicators, and writes a
  person-level analytic file (`enut_analytic.csv`).
- **`code/02_survey_analysis.R`** (R): applies the complex survey design
  (strata, primary sampling units, person expansion factors) and reproduces
  the manuscript tables: domain and aggregate means with standard errors,
  WHO-equivalent attainment with 95% confidence intervals, and total
  expenditure by age group and income quintile.

## How to run

1. Obtain the II ENUT 2023 public microdata CSV from the Chilean National
   Statistics Institute (INE) and set its path in `ENUT_CSV` at the top of
   `01_build_domains.py`. The file is comma-separated, latin-1 encoded.
2. Run the Python builder:
   ```
   python code/01_build_domains.py
   ```
   This writes `enut_analytic.csv`.
3. Run the R analysis:
   ```
   Rscript code/02_survey_analysis.R
   ```

### Dependencies

- Python 3 with `numpy` and `pandas`.
- R with the `survey` package.

## Data availability

This study is a secondary analysis of the II ENUT 2023, produced by the
Chilean National Statistics Institute (INE). The microdata are publicly
available and anonymised, published by INE on its official website; this
repository does not redistribute the microdata. The survey's design,
collection, processing and quality-control procedures are described in the
INE methodological document and field manual. A sex-specific calibration of
the exercise MET value draws on the public microdata of the 2024 National
Survey of Physical Activity and Sport (ENAFyD), produced by the Chilean
Ministry of Sport.

## Ethics statement

This study is a secondary analysis of anonymised, publicly available official
statistics from the II ENUT 2023 (fieldwork 14 September to 29 December 2023),
a nationally representative probability survey of persons aged 12 and over in
private households. The ENUT 2023 was not submitted to an external or
independent ethics committee, as it forms part of the official statistical
operations of the State of Chile. INE operates under Law No. 17,374 (INE
Organic Law), Law No. 19,628 on the Protection of Personal Data, and
international good-practice standards including the ECLAC Regional Code of Good
Practice in Statistics for Latin America and the Caribbean; these frameworks
regulate the use, protection and confidentiality of the data and establish the
principle of statistical secrecy, which prevents the direct or indirect
identification of respondents. Informed consent was verbal, provided before
the interview: accredited interviewers presented official identification, a
household opening letter and informational material explaining the survey's
purpose and public utility, and the agreement of an adult household member was
taken as sufficient consent. Only public, anonymised databases were used,
respecting statistical secrecy and INE's use restrictions.

## Notes on reproducibility

- Energy expenditure is expressed in MET-hours per typical day, where a
  typical day combines weekday and weekend-day reports as
  (5/7 x weekday) + (2/7 x weekend).
- Population means treat non-participation in an activity as a genuine zero.
- Income quintiles are computed at the household level (weighted by the
  household expansion factor) and merged to persons; a small number of
  persons without valid household income carry a missing quintile.
- ENUT sex coding is 1 = men, 2 = women. Note that the ENAFyD survey used for
  MET calibration uses the opposite coding.

## How to cite

If you use this code, please cite the associated article and this software
deposit. See `CITATION.cff` for machine-readable citation metadata.

## License

MIT License. See `LICENSE`.
