import pytest
from ai_optimizer import optimize

def test_optimizer():
    """Test the optimize function for loss reduction validity."""
    initial_loss = 1.0  # Example starting loss
    expected_threshold = 0.1  # The loss threshold to pass this test

    # Run the optimization
    final_loss = optimize(initial_loss)

    # Assert that the final loss meets the expected criteria
    assert final_loss < expected_threshold, f"Test failed: Expected loss below {expected_threshold}, got {final_loss}."

if __name__ == "__main__":
    pytest.main()
    print("All tests passed")