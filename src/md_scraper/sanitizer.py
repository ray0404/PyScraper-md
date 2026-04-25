import re

class MarkdownSanitizer:
    """
    Post-processor to clean and normalize Markdown output.
    Focuses on removing noise and ensuring GFM compliance.
    """

    def __init__(self):
        # Patterns for cleaning
        self.patterns = [
            # 1. Remove excessive newlines (more than 2)
            (r'
{3,}', '

'),
            
            # 2. Strip trailing whitespace from lines
            (r'[ 	]+$', ''),
            
            # 3. Fix headers that don't have a space after #
            (r'^(#+)([^#\s])', r'\1 \2'),
            
            # 4. Remove empty links/images
            (r'\[\]\([^\)]*\)', ''),
            (r'!\[\]\([^\)]*\)', ''),
            
            # 5. Clean up residue HTML comments if they weren't stripped
            (r'<!--.*?-->', ''),
            
            # 6. Normalize list markers (sometimes mixed * and -)
            # (Optional: might be too opinionated, but GFM prefers - or *)
        ]

    def sanitize(self, markdown: str) -> str:
        """
        Applies a series of transformations to clean the Markdown.
        """
        cleaned = markdown
        
        # Apply regex patterns
        for pattern, replacement in self.patterns:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.MULTILINE | re.DOTALL if '<!--' in pattern else re.MULTILINE)

        # 7. Specific Table Fixes
        cleaned = self._fix_tables(cleaned)

        return cleaned.strip()

    def _fix_tables(self, markdown: str) -> str:
        """
        Attempts to fix common issues in Markdown tables, 
        like missing alignment separators or inconsistent columns.
        """
        lines = markdown.split('
')
        fixed_lines = []
        
        in_table = False
        for i, line in enumerate(lines):
            # Very basic check for a table row: starts and ends with |
            is_row = line.strip().startswith('|') and line.strip().endswith('|')
            
            if is_row:
                if not in_table:
                    in_table = True
                
                # If this is the second row of a table, ensure it's a separator
                # markdownify usually handles this, but sometimes it's missing
                # Check if it looks like |---|---|
                pass # Placeholder for more complex table logic
            else:
                in_table = False
            
            fixed_lines.append(line)
            
        return '
'.join(fixed_lines)

    @staticmethod
    def strip_non_ascii(text: str) -> str:
        """
        Removes non-printable/junk characters.
        """
        return "".join(i for i in text if ord(i) < 128)
