import re

class MarkdownSanitizer:
    """
    Post-processor to clean and normalize Markdown output.
    Focuses on removing noise and ensuring GFM compliance.
    """

    # Pre-compile patterns at class-level to avoid recompilation on every instantiation
    _RAW_PATTERNS = [
        # 1. Remove excessive newlines (more than 2)
        (r'\n{3,}', '\n\n'),

        # 2. Strip trailing whitespace from lines
        (r'[ \t]+$', ''),

        # 3. Fix headers that don't have a space after #
        (r'^([ \t]{0,3}#+)([^#\s])', r'\1 \2'),

        # 4. Remove empty links/images (only if they are truly empty)
        (r'!?\[\s*\]\(\s*\)', ''),

        # 5. Clean up residue HTML comments if they weren't stripped
        (r'<!--.*?-->', ''),

        # 6. Normalize list markers (sometimes mixed * and -)
        # (Optional: might be too opinionated, but GFM prefers - or *)
    ]

    PATTERNS = []
    for pattern, replacement in _RAW_PATTERNS:
        flags = re.MULTILINE | re.DOTALL if '<!--' in pattern else re.MULTILINE
        PATTERNS.append((re.compile(pattern, flags=flags), replacement))

    def __init__(self):
        self.patterns = self.PATTERNS

    def sanitize(self, markdown: str) -> str:
        """
        Applies a series of transformations to clean the Markdown.
        """
        cleaned = markdown
        
        # Apply regex patterns using precompiled pattern.sub
        for pattern, replacement in self.patterns:
            cleaned = pattern.sub(replacement, cleaned)

        # 7. Specific Table Fixes
        cleaned = self._fix_tables(cleaned)

        return cleaned.strip()

    def _fix_tables(self, markdown: str) -> str:
        """
        Attempts to fix common issues in Markdown tables, 
        like missing alignment separators or inconsistent columns.
        """
        lines = markdown.split('\n')
        fixed_lines = []
        
        table_row_count = 0
        for line in lines:
            stripped = line.strip()
            # Very basic check for a table row: starts and ends with |
            is_row = stripped.startswith('|') and stripped.endswith('|')
            
            if is_row:
                table_row_count += 1
                if table_row_count == 2:
                    # Check if current line is already a separator line
                    # A separator line should only contain '|', '-', ':', ' ', '\t'
                    # If there are other characters, it's a data row and the separator is missing
                    is_separator = not bool(re.sub(r'[\s|\-:]', '', stripped))

                    if not is_separator:
                        # Current row is NOT a separator, but it's the second row.
                        # We need to insert a separator before this line based on the first row's columns.
                        prev_line = fixed_lines[-1]
                        # Preserve indentation of the first row
                        indent_str = prev_line[:len(prev_line) - len(prev_line.lstrip())]

                        num_cols = prev_line.strip().count('|') - 1
                        if num_cols > 0:
                            separator = indent_str + '|' + '|'.join(['---'] * num_cols) + '|'
                            fixed_lines.append(separator)

                        # We inserted a separator, so the current line is now the third row (data row)
                        table_row_count += 1
            else:
                table_row_count = 0
            
            fixed_lines.append(line)
            
        return '\n'.join(fixed_lines)

    @staticmethod
    def strip_non_ascii(text: str) -> str:
        """
        Removes non-printable/junk characters.
        """
        return text.encode('ascii', 'ignore').decode('ascii')
