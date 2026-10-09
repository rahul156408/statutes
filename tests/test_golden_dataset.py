import json
import os

def test_load_golden_dataset():
    path = "data/golden/conflicts_golden.json"
    assert os.path.exists(path), f"Golden dataset file not found at {path}"
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    assert isinstance(data, list), "Golden dataset must be a JSON list of conflict cases."
    print(f"Successfully loaded {len(data)} conflict case(s) from golden dataset.")
    
    for item in data:
        assert "conflict_id" in item
        assert "jurisdictions" in item
        assert "is_jointly_unsatisfiable" in item
        print(f"Verified schema for: {item['conflict_id']}")

if __name__ == "__main__":
    test_load_golden_dataset()