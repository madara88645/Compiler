import re

def validate_human_input(original_template: str, new_template: str) -> bool:
    """
    Validates that the new template preserves all variable placeholders
    (e.g., {{variable}}) found in the original template.
    
    Args:
        original_template: The source prompt template.
        new_template: The modified prompt template (e.g. from user input).
        
    Returns:
        True if valid (all placeholders preserved), False otherwise.
    """
    # Regex to find patterns like {{variable_name}}
    # We use non-greedy matching .*? inside braces.
    # Handles potential whitespace inside braces if needed: {{\s*[\w_]+\s*}}
    # But generally standard is {{var}}. Let's be reasonably flexible.
    pattern = r"\{\{\s*[\w_]+\s*\}\}"
    
    # Find all unique placeholders in original
    required_placeholders = set(re.findall(pattern, original_template))
    
    if not required_placeholders:
        return True
        
    for ph in required_placeholders:
        if ph not in new_template:
            print(f"Warning: Missing required placeholder '{ph}' in new template.")
            return False
            
    return True
