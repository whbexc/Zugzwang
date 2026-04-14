
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Mocking the radius mapping logic
def get_radius_index(radius):
    radius_map = {
        0: 0,
        10: 1,
        15: 2,
        25: 3,
        50: 4,
        100: 5,
        200: 6
    }
    best_match = min(radius_map.keys(), key=lambda x: abs(x - radius))
    return radius_map[best_match], best_match

def test_radius_mapping():
    test_cases = [
        (0, 0, 0),
        (10, 1, 10),
        (15, 2, 15),
        (20, 2, 15), # 20 is closer to 15 or 25? 25-20=5, 20-15=5. min() picks first if equal.
        (25, 3, 25),
        (40, 4, 50), # 40 closer to 50
        (50, 4, 50),
        (100, 5, 100),
        (200, 6, 200),
        (500, 6, 200), # capped at max
    ]
    
    for val, expected_idx, expected_match in test_cases:
        idx, match = get_radius_index(val)
        print(f"Radius {val}km -> Index {idx}, Match {match}km (Expected Index {expected_idx}, Match {expected_match}km)")
        assert idx == expected_idx
        assert match == expected_match

if __name__ == "__main__":
    print("Testing Radius Mapping Logic...")
    test_radius_mapping()
    print("\nMapping Logic Check: PASSED")
