# Nebius-x-NVIDIA-Global-AI-Hackathon-DataMedic

## The Problem

Every business decision built on data is only as good as the data underneath it. In practice, most real-world datasets are messy: exported from different systems, typed in by hand, and merged from spreadsheets that never agreed on a format.

A single sales file might list the same province as `Ontario`, `ON`, `Ont.` and `ontario`. Revenue might appear as `$1,200`, `1200$` and `1,200`. The same order can be entered twice, a refund can show up as negative revenue, and a date like `03/04/26` could mean March 4 or April 3, and nothing in the file says which.

These errors are small individually but expensive together:

- **Reports go wrong silently.** Duplicates inflate revenue, inconsistent categories split one region into four, and missing values skew averages, often without anyone noticing.
- **Cleaning is slow and manual.** Analysts and data engineers spend hours finding and fixing these issues by hand before any real analysis can begin.
- **Fixes are risky and untracked.** Cleaning scripts apply changes blindly. A wrong guess about an ambiguous date or a deleted "duplicate" can corrupt data further, with no record of what changed or why.

Existing tools don't solve this well. Simple cleaners apply fixed rules without understanding context, while general-purpose AI chatbots can suggest fixes but can't safely apply them, check their own work, or know when they should ask a human instead of guessing.

## Our Solution

**DataMedic is an autonomous AI data reliability agent.** It profiles a messy dataset, diagnoses what's wrong, automatically fixes what it's confident about, asks a human about anything ambiguous, re-tests its own work, and rolls back any fix that makes the data worse. Every change is recorded in a full audit trail, and a Data Health Score shows exactly how much the data improved.

Pitch: The profiler catches 100% of planted errors across 13 error types.

Here are the 13 error types:

1. Province variants
2. Currency text
3. Mixed date formats
4. Missing values
5. Extra spaces
6. Ambiguous dates
7. Duplicate rows
8. Negative revenue
9. Outliers
10. Duplicate IDs
11. Province typos
12. Zero quantity
13. Future dates

Roles:

Role 1: Project Lead / Product & Pitch by Jason Thai + Jesika

Role 2: Agent Architect (LLM & Reasoning Lead) by Ria Chahar

Role 3: Repair Tools Engineer by Omer

Role 4: Profiling, Validation & Health Score Engineer by Jason Thai

Role 5: Backend & Infrastructure Engineer by Nashwa

Role 6: Frontend Engineer by Prabal

Role 7: Data, Evaluation & QA Engineer by Marko





