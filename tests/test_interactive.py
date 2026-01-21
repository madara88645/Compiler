import unittest
from unittest.mock import patch
from app.optimizer.utils import validate_human_input

class TestInteractiveFlow(unittest.TestCase):
    
    def test_validation_logic_basic(self):
        """Verify core validation logic."""
        original = "Hello {{name}}, welcome to {{place}}."
        
        # Valid cases
        self.assertTrue(validate_human_input(original, "Hi {{name}}, welcome to {{place}}."))
        self.assertTrue(validate_human_input(original, "Just {{name}} and {{place}}"))
        
        # Invalid cases
        self.assertFalse(validate_human_input(original, "Hello {{name}}.")) # Missing place
        self.assertFalse(validate_human_input(original, "Welcome to {{place}}.")) # Missing name
        self.assertFalse(validate_human_input(original, "No variables here."))
        
    def test_validation_logic_no_vars(self):
        """Verify validation with no variables in original."""
        original = "Just plain text."
        self.assertTrue(validate_human_input(original, "New text."))
        
    @patch('builtins.input')
    def test_simulated_interaction_loop(self, mock_input):
        """
        Simulate an engine causing a pause for human input.
        Verifies:
        1. Loop prompts user.
        2. Invalid input (missing var) is rejected.
        3. Valid input is accepted.
        """
        original_prompt = "Optimize {{target}}."
        
        # Scenario:
        # 1. User types 'y' to edit.
        # 2. User inputs INVALID template (missing {{target}}).
        # 3. System detects invalid, asks again.
        # 4. User inputs VALID template.
        
        # Define side effects for input()
        # calls:
        # 1. "Do you want to edit? (y/n)" -> 'y'
        # 2. "Enter new prompt:" -> "Optimize something else." (INVALID)
        # 3. "Invalid. Try again:" -> "Better {{target}}." (VALID)
        mock_input.side_effect = ['y', "Optimize something else.", "Better {{target}}."]
        
        # Simulated Engine Logic
        current_prompt = original_prompt
        accepted = False
        
        # Step 1: Check if user wants to interject
        user_choice = input("Do you want to edit? (y/n)")
        
        if user_choice.lower() == 'y':
            # Interactive Loop
            while not accepted:
                # Ask for prompt
                # Note: In real engine, prompt message might differ
                candidate = input("Enter new prompt:")
                
                # VALIDATION STEP
                if validate_human_input(original_prompt, candidate):
                    current_prompt = candidate
                    accepted = True
                else:
                    # Logic should print warning (handled in func) and loop specific prompt
                    # We treat the next input call as the retry receipt
                    pass
        
        # Assertions
        self.assertTrue(accepted)
        self.assertEqual(current_prompt, "Better {{target}}.")
        self.assertEqual(mock_input.call_count, 3) 
        
