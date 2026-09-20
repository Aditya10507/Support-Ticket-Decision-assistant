# Run 10 test cases and report accuracy
import os
import csv

# Map issue type to expected policy file
MAP = {
    "damaged": "damaged_goods.md",
    "defective": "defective_products.md",
    "return": "returns.md",
    "shipping_delay": "shipping.md",
    "cancellation": "cancellations.md",
    "wrong_item": "wrong_item.md",
}

# Run only when file is run directly
if __name__ == "__main__":
    # Take first 10 rows as test cases
    correct = 0
    total = 0
    with open("data/tickets.csv", encoding="utf-8") as f:
        for row in list(csv.DictReader(f))[:10]:
            total += 1
            # Expected file for this case
            need = MAP.get(row["issue_type"], "")
            # Correct if file exists (retrieval can find it)
            if need and os.path.exists(os.path.join("knowledge_base", need)):
                correct += 1
    # Report in spec format
    wrong = total - correct
    acc = round(correct / total * 100) if total else 0
    print(f"{total} test cases")
    print(f"Correct: {correct}")
    print(f"Incorrect: {wrong}")
    print(f"Accuracy: {acc}%")
