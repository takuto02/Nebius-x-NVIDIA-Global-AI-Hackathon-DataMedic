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

## Pitch

DataMedic is an autonomous AI data reliability engineer that detects data-quality issues, reasons about safe repairs, executes fixes, validates its own work, and involves humans when confidence is low.

## Roles

**Role 1: Project Lead / Product & Pitch**  
Jason Thai + Jesika

**Role 2: Agent Architect (LLM & Reasoning Lead)**  
Ria Chahar

**Role 3: Repair Tools Engineer**  
Ria Chahar

**Role 4: Profiling, Validation & Health Score Engineer**  
Jason Thai

**Role 5: Backend & Infrastructure Engineer**  
Nashwa

**Role 6: Frontend Engineer**  
Prabal

**Role 7: Data, Evaluation & QA Engineer**  
Jason Thai

---

## System Overview

DataMedic is an autonomous AI data reliability agent that profiles datasets, identifies data-quality problems, reasons about appropriate repairs, executes approved repairs, validates the results, and maintains an audit trail of its actions.

### High-Level Workflow

```text id="lcb0pn"
Upload Dataset
      ↓
Profile Dataset
      ↓
Detect Issues & Rule Violations
      ↓
Nemotron Agent Reasoning
      ↓
Generate FixProposal
      ↓
Human Approval (when required)
      ↓
Execute Repair
      ↓
Re-run Profiler & Validate
      ↓
Keep Fix or Roll Back
      ↓
Generate AuditEntry
      ↓
Continue Until Remaining Issues Require Review
```

---

## Shared Data Contracts

### Issue — Profiler → Agent

The profiler produces structured Issues that are passed to the Nemotron agent.

Core fields:

```text id="cy1n9a"
id
key
column
rows
row_count
type
severity
evidence
values
rule_id
```

Depending on the issue type, additional fields may include:

```text id="x7kn1h"
suggested_standard
main_format
expected_range
```

`key` is the stable identifier used to track an Issue throughout the repair process.

`id` identifies an Issue within a specific profiler run and may change after repairs and re-profiling. Components should therefore use `key` for persistent tracking.

`rows` contains example affected rows and may be capped at 50. `row_count` contains the actual number of affected rows.

Repair logic should use the exact raw values or matching criteria supplied by the Issue rather than assuming that `rows` contains every affected record.

Mappings and other raw-value parameters must be generated programmatically from the Issue `values` field rather than reconstructed from the `evidence` text. This preserves exact capitalization, spacing, punctuation, and formatting.

---

### FixProposal — Agent → Repair Tools

Nemotron generates a FixProposal describing the recommended action for a profiler Issue.

```json id="45y8o8"
{
  "key": "Province:category_variants:Ontario",
  "issue_id": "iss_009",
  "rule_id": null,
  "tool": "standardize_category",
  "params": {
    "column": "Province",
    "mapping": {}
  },
  "confidence": 0.99,
  "rationale": "The raw values are formatting and abbreviation variants of Ontario.",
  "needs_approval": false
}
```

`key` is the primary stable link back to the profiler Issue.

`issue_id` may be retained as a reference to the specific profiler run.

`rule_id` carries over from the Issue when applicable.

Mappings should be constructed directly from the Issue `values` field in code rather than manually retyped.

The exact `tool` names and `params` must match the Repair Tools interface once finalized.

---

### AuditEntry — Repair Result

Each executed repair produces an AuditEntry describing what happened.

```json id="t3pbh7"
{
  "key": "Province:category_variants:Ontario",
  "issue_id": "iss_009",
  "rule_id": null,
  "row": 4,
  "column": "Province",
  "old_value": "ON",
  "new_value": "Ontario",
  "tool": "standardize_category",
  "confidence": 0.99,
  "status": "applied"
}
```

Possible statuses:

- `applied`
- `rolled_back`
- `pending_review`

Audit entries provide traceability between the original Issue, the agent's decision, and the resulting data modification.

---

## Business Rules

Business rules are supplied through `rules.json`.

Example:

```json id="vwyc4b"
{
  "id": "R2",
  "column": "Revenue",
  "type": "min_value",
  "value": 0,
  "description": "Revenue cannot be negative"
}
```

The profiler is responsible for detecting business-rule violations.

When a rule is violated, the profiler generates an Issue containing:

```json id="ctsdm6"
{
  "type": "rule_violation",
  "rule_id": "R2"
}
```

Nemotron does not determine whether a business rule has been violated. It receives the detected violation from the profiler and reasons about the appropriate repair or next action.

---

## Confidence & Human Approval

Initial confidence ranges:

- `0.90–1.00` — High
- `0.70–0.89` — Medium
- `<0.70` — Low

Approval depends on both confidence and repair risk.

High-confidence, non-destructive operations may be eligible for automatic repair, including:

- Category normalization
- Whitespace cleanup
- Deterministic formatting corrections

Ambiguous or potentially destructive operations should require human approval even when model confidence is high, including:

- Ambiguous date interpretation
- Duplicate deletion
- Missing-value imputation
- Outlier modification or removal
- Business-rule violations where the correct replacement value is unknown

Confidence thresholds and approval rules may be adjusted based on evaluation results.

---

## Agent & Repair Workflow

Only one FixProposal should be applied before re-profiling and re-scoring.

```text id="4t8xk6"
Profile Dataset
      ↓
Select Current Issue
      ↓
Confirm Issue key still exists
      ↓
Nemotron Reasoning
      ↓
Generate FixProposal
      ↓
Human Approval (if required)
      ↓
Execute Repair
      ↓
Re-run Profiler
      ↓
Re-score / Validate
      ↓
Keep Fix or Roll Back
      ↓
Create AuditEntry
      ↓
Process Next Existing Issue
```

### Overlapping Issues

Some Issues may represent the same underlying data problem.

After every repair, the profiler is run again. Before processing the next Issue, the system checks whether its stable `key` still exists in the latest profiler output.

If the `key` no longer exists, the Issue is skipped because the previous repair already resolved it.

This prevents DataMedic from attempting to fix the same underlying problem twice.

---

## Repair Matching

Repair tools should operate using exact raw values or Issue criteria rather than relying only on the example rows supplied by the profiler.

Because `rows` may contain only the first 50 examples, repairs should use `values`, mappings, or other matching criteria to identify all affected records.

Mappings must be constructed directly from the Issue `values` field in code. They should not be manually reconstructed from the human-readable `evidence` field.

Where appropriate, Repair Tools may also trim whitespace before matching as an additional safety measure.

---

## Re-Testing & Rollback

Every applied FixProposal is followed by a new profiler run and validation step.

The resulting data-quality state is compared with the state immediately before the repair.

If the repair produces the expected improvement without causing a regression, it is retained.

If the repair causes a regression, that specific repair is rolled back.

The rollback is recorded in the AuditEntry:

```json id="vhg6pi"
{
  "status": "rolled_back"
}
```

Re-testing after each individual repair allows a regression to be attributed to the specific FixProposal that caused it rather than requiring multiple successful repairs to be undone.

---

## Evaluation & Testing

DataMedic is tested using datasets containing intentionally planted data-quality errors.

The current profiler detects 100% of planted errors across 13 tested error types:

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

As development continues, evaluation will also cover agent repair decisions, confidence scoring, human-approval routing, successful repairs, regression detection, and rollback behavior.

---

## Repair Tool Contract

The Repair Tools interface defines the valid `tool` names and required `params` that Nemotron may generate in a FixProposal.

Once finalized, each Repair Tool should be documented using the following format:

```text id="gzy2h8"
Tool: <tool_name>
Purpose: <what the tool does>

Required parameters:
- <parameter>
- <parameter>
```

The Agent Architect and Repair Tools Engineer should use the same tool names and parameter structures so FixProposals can be executed directly by the repair layer.

---

## End-to-End Traceability

The stable Issue `key` is maintained throughout the repair lifecycle:

```text id="e9gb95"
Issue key
    ↓
FixProposal key
    ↓
Repair
    ↓
Re-profile / Re-test
    ↓
AuditEntry key
```

This provides an auditable record of:

- What data-quality problem was detected
- Which business rule was involved, if applicable
- What repair the agent proposed
- The agent's confidence and rationale
- Whether human approval was required
- What data was changed
- Whether validation improved after the repair
- Whether the repair was retained or rolled back





