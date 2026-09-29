"""
DataMedic agent demo: profiler -> Nemotron -> FixProposals
-----------------------------------------------------------
Connects the profiler to NVIDIA Nemotron on Nebius Token Factory.

    1. The profiler finds the issues (free, runs locally)
    2. We send Nemotron a compact summary: issues + business rules + dataset context
    3. Nemotron replies with FixProposals (the team's agreed format)
    4. Our code checks every proposal before anything is applied (guardrails)

This script only PROPOSES fixes. It never changes the data. Applying fixes is
the repair tools' job (Role 3).

Setup (once):
    pip install openai
    Create a file called .env next to this script containing:
        NEBIUS_API_KEY=your-key-here
        NEBIUS_MODEL=the-nemotron-model-id-from-your-dashboard
    (.env is in .gitignore, so your key never goes to GitHub)

Usage:
    python agent_demo.py --list-models                       # see which models your key can use
    python agent_demo.py ../data/messy_retail.csv --rules rules.json --dry-run   # show prompt, no credits used
    python agent_demo.py ../data/messy_retail.csv --rules rules.json            # real call to Nemotron
"""

import json
import os
import re
import sys

from profiler import load_data, profile_dataset

BASE_URL = "https://api.tokenfactory.nebius.com/v1/"

CONTEXT = ("Canadian retail sales orders. Each row is one order. Revenue is in CAD. "
           "Province should be the full official Canadian province name.")

# Repair tools the agent may choose from. Names/params must match Role 3's tools.
TOOLS = {
    "standardize_category": "params: {column, mapping: {raw_value: standard_value}}. "
                            "Copy raw values EXACTLY from the issue's `values` (keep spaces and case).",
    "parse_currency": "params: {column}. Converts '$1,200', '1200$', '1,200' to plain numbers.",
    "standardize_date": "params: {column}. Converts unambiguous dates to YYYY-MM-DD.",
    "trim_whitespace": "params: {column}. Removes leading/trailing spaces.",
    "remove_duplicate_rows": "params: {}. Deletes rows that exactly repeat an earlier row.",
    "flag_for_review": "params: {column, reason}. Makes no change; asks a human to decide.",
}

# Guardrails enforced by CODE, whatever the model says
ALWAYS_NEEDS_APPROVAL = {"ambiguous_date", "missing_values", "duplicate_key", "duplicate_rows",
                         "suspicious_negative", "outlier", "rule_violation", "future_date"}
DESTRUCTIVE_TOOLS = {"remove_duplicate_rows"}
AUTO_FIX_MIN_CONFIDENCE = 0.90


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------

def load_env(path=".env"):
    """Read KEY=value lines from .env into environment variables."""
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def client():
    from openai import OpenAI
    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        sys.exit("NEBIUS_API_KEY is missing. Put it in a .env file next to this script.")
    return OpenAI(base_url=BASE_URL, api_key=key)


# ---------------------------------------------------------------------------
# Build the prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are DataMedic, a careful junior data engineer.
You receive data-quality issues found by a profiler, plus the user's business rules.
For each issue, propose ONE repair using only the allowed tools.

Allowed tools:
{tools}

Rules:
- Never invent data. Missing values, negative revenue, outliers, duplicate IDs, future dates
  and business-rule violations cannot be safely guessed: use flag_for_review.
- Ambiguous dates (like 03/04/26) must NOT be guessed: use flag_for_review.
- "key" must be copied from the issue's `key` field (e.g. "Province:category_variants:Ontario"),
  and "issue_id" from its `id` field (e.g. "iss_009"). Do not put the id in "key".
- For standardize_category, copy raw values exactly from the issue's `values` field.
- confidence is 0.0-1.0: 0.90+ high, 0.70-0.89 medium, below 0.70 low.
- needs_approval is true unless the fix is a safe, high-confidence formatting change.
- Several issues may describe the same rows; you may propose one fix per issue anyway.

Reply with ONLY a JSON object, no other text:
{{"proposals": [{{"key": "...", "issue_id": "...", "rule_id": null, "tool": "...",
  "params": {{...}}, "confidence": 0.0, "rationale": "...", "needs_approval": true}}]}}"""


def compact_issues(issues):
    """Send the model only what it needs (keeps prompts small and credits low)."""
    keep = ("id", "key", "column", "type", "severity", "row_count", "evidence", "values",
            "rule_id", "suggested_standard", "main_format", "expected_range")
    return [{k: i[k] for k in keep if k in i} for i in issues]


def build_messages(profile, rules, context):
    tools = "\n".join(f"- {name}: {desc}" for name, desc in TOOLS.items())
    user = {
        "dataset_context": context,
        "rows": profile["summary"]["rows"],
        "columns": [{"name": c["column"], "kind": c["kind"]} for c in profile["columns"]],
        "business_rules": rules or [],
        "issues": compact_issues(profile["issues"]),
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT.format(tools=tools)},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False, indent=1)},
    ]


# ---------------------------------------------------------------------------
# Read and check the model's answer
# ---------------------------------------------------------------------------

def parse_json(text):
    """Pull the JSON object out of the reply, even if wrapped in ``` fences or extra text."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)  # drop reasoning, if any
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Model reply contained no JSON object")
    return json.loads(text[start:end + 1])


def check_proposals(proposals, issues):
    """Guardrails. Returns (checked_proposals, warnings). Never trusts the model blindly."""
    by_key = {i["key"]: i for i in issues}
    by_id = {i["id"]: i for i in issues}
    checked, warnings = [], []

    for p in proposals:
        # Match on the stable key; fall back to the short id if the model mixed them up
        issue = (by_key.get(p.get("key")) or by_id.get(p.get("key"))
                 or by_id.get(p.get("issue_id")) or by_key.get(p.get("issue_id")))
        if issue is None:
            warnings.append(f"Dropped proposal for unknown issue {p.get('key')!r}")
            continue
        p["key"] = key = issue["key"]  # always store the real stable key
        if p.get("tool") not in TOOLS:
            warnings.append(f"{key}: unknown tool {p.get('tool')!r}, changed to flag_for_review")
            p["tool"], p["params"] = "flag_for_review", {"column": issue["column"],
                                                         "reason": "Model chose an invalid tool"}
        p["issue_id"] = issue["id"]
        p["rule_id"] = issue.get("rule_id")
        conf = float(p.get("confidence", 0) or 0)
        p["confidence"] = max(0.0, min(1.0, conf))

        # Mapping keys must be real values from the data (catches retyped/mangled values)
        incomplete = False
        if p["tool"] == "standardize_category":
            mapping = p.get("params", {}).get("mapping", {})
            real = issue.get("values", {})
            bad = [k for k in mapping if k not in real]
            if bad:
                warnings.append(f"{key}: mapping keys not found in data {bad}, removed")
                for k in bad:
                    mapping.pop(k)
            missing = [v for v in real if v not in mapping and v != issue.get("suggested_standard")]
            if missing:
                warnings.append(f"{key}: mapping skips values {missing}")
            incomplete = bool(bad or missing)

        # Approval policy enforced in code
        must_ask = (incomplete
                    or issue["type"] in ALWAYS_NEEDS_APPROVAL
                    or p["tool"] in DESTRUCTIVE_TOOLS
                    or p["confidence"] < AUTO_FIX_MIN_CONFIDENCE)
        if must_ask and not p.get("needs_approval"):
            warnings.append(f"{key}: model said auto-fix, policy requires approval")
        p["needs_approval"] = bool(p.get("needs_approval")) or must_ask
        checked.append(p)

    proposed = {p["key"] for p in checked}
    for i in issues:
        if i["key"] not in proposed:
            warnings.append(f"No proposal for issue {i['key']}")
    return checked, warnings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def arg(flag):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else None


def main():
    load_env()

    if "--list-models" in sys.argv:
        for m in client().models.list().data:
            print(m.id)
        return

    if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
        print(__doc__)
        return

    rules = json.load(open(arg("--rules"), encoding="utf-8")) if arg("--rules") else None
    profile = profile_dataset(load_data(sys.argv[1]), rules)
    messages = build_messages(profile, rules, arg("--context") or CONTEXT)

    if "--dry-run" in sys.argv:
        print(messages[0]["content"])
        print("\n----- USER MESSAGE -----\n")
        print(messages[1]["content"])
        print(f"\n(dry run: {len(profile['issues'])} issues, "
              f"~{sum(len(m['content']) for m in messages) // 4} tokens, nothing sent)")
        return

    model = os.environ.get("NEBIUS_MODEL")
    if not model:
        sys.exit("NEBIUS_MODEL is missing. Run with --list-models, then add it to .env")

    print(f"Asking {model} about {len(profile['issues'])} issues...")
    resp = client().chat.completions.create(model=model, messages=messages, temperature=0.1)
    reply = resp.choices[0].message.content
    usage = resp.usage

    try:
        proposals = parse_json(reply)["proposals"]
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        print(f"Could not read the model's reply ({e}). Raw reply:\n{reply}")
        return

    checked, warnings = check_proposals(proposals, profile["issues"])

    print(f"\n{len(checked)} proposals:")
    for p in checked:
        action = "NEEDS APPROVAL" if p["needs_approval"] else "auto-fix"
        print(f"  [{action:<14}] {p['key']:<40} {p['tool']:<22} conf {p['confidence']:.2f}")
        print(f"                   {p.get('rationale', '')}")
    if warnings:
        print("\nGuardrail warnings:")
        for w in warnings:
            print(f"  - {w}")
    if usage:
        print(f"\nTokens used: {usage.prompt_tokens} in + {usage.completion_tokens} out")

    with open("proposals.json", "w", encoding="utf-8") as f:
        json.dump({"proposals": checked, "warnings": warnings}, f, indent=2, ensure_ascii=False)
    print("Saved to proposals.json")


if __name__ == "__main__":
    main()
