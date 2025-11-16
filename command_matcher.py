import csv
from rapidfuzz import process

def load_commands(csv_path):
    commands = {}
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if len(row) < 3:
                    continue
                key = row[0].strip()
                variants = [v.strip().lower() for v in row[1].split("|") if v.strip()]
                action = row[2].strip()
                commands[key] = {
                    "variants": variants,
                    "action": action
                }
        print(f"[LOADED] {len(commands)} commands from {csv_path}")
    except Exception as e:
        print(f"[ERROR CSV] {e}")
    return commands


def find_best_match(input_text, command_dict, cutoff=70):
    input_text = input_text.lower().strip()
    all_variants = []
    variant_map = {}

    for key, data in command_dict.items():
        for variant in data["variants"]:
            all_variants.append(variant)
            variant_map[variant] = key

    # Use score_cutoff for safety
    result = process.extractOne(input_text, all_variants, score_cutoff=cutoff)
    if result is None:
        return None

    best_variant, score, _ = result  # unpack safely
    matched_key = variant_map[best_variant]
    action = command_dict[matched_key]["action"]
    return matched_key, action, score
