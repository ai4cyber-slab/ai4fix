import re
import sys

class JavaParser:
    def __init__(self, path, line_number_min=None, line_number_max=None):
        self.path = path
        self.line_number_min = line_number_min
        self.line_number_max = line_number_max
        
    def remove_extra_braces(self):
        """
        Remove exactly those braces that are truly unmatched or incorrectly close
        the top-level class/interface/enum too early. Only remove braces in the
        specified line range [self.line_number_min, self.line_number_max].
        """
        with open(self.path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # We'll reconstruct lines with braces removed where necessary.
        # Keep track of which character indexes (line, col) are removed.
        braces_to_remove = set()
        
        # State flags
        in_block_comment = False
        in_line_comment = False
        in_string = False
        string_delim = None
        
        def is_effectively_empty_or_comment(ln):
            stripped = ln.strip()
            return (not stripped) or stripped.startswith('//')
        
        # We will locate where the top-level '{' is (from "class", "interface", or "enum").
        classlike_pattern = re.compile(r'\b(class|interface|enum)\s+[\w$]+')
        found_top_level = False
        top_level_candidate_line = -1
        top_level_brace_col = -1
        
        # First pass: find the top-level "class", "interface", or "enum" and its next '{'
        for i, line in enumerate(lines):
            j = 0
            while j < len(line):
                c = line[j]
                # handle existing block comment
                if in_block_comment:
                    if c == '*' and (j+1 < len(line) and line[j+1] == '/'):
                        in_block_comment = False
                        j += 2
                        continue
                    j += 1
                    continue
                
                # handle line comment
                if in_line_comment:
                    # line comment ends at newline
                    break
                
                # check start of comment
                if c == '/':
                    if j+1 < len(line) and line[j+1] == '/':
                        in_line_comment = True
                        break
                    elif j+1 < len(line) and line[j+1] == '*':
                        in_block_comment = True
                        j += 2
                        continue
                
                # check for string toggling
                if not in_string:
                    if c in ('"', "'"):
                        in_string = True
                        string_delim = c
                else:
                    # if we see the same delimiter and it's not escaped, end string
                    if c == string_delim:
                        if not (j > 0 and line[j-1] == '\\'):
                            in_string = False
                
                j += 1
            
            in_line_comment = False  # reset at end of line
            
            if not found_top_level and not in_block_comment and not in_string:
                # Check if line has something like "class", "interface" or "enum"
                if classlike_pattern.search(line):
                    # The next '{' on this line is presumably the top-level open brace
                    brace_index = line.find('{')
                    if brace_index != -1:
                        found_top_level = True
                        top_level_candidate_line = i
                        top_level_brace_col = brace_index
        
        top_level_open = (top_level_candidate_line, top_level_brace_col) if found_top_level else None
        
        # Reset comment/string state for the main pass
        in_block_comment = False
        in_line_comment = False
        in_string = False
        string_delim = None
        
        # We'll keep track of matching braces in a stack
        stack = []
        line_char_list = [list(ln) for ln in lines]
        
        for i, line in enumerate(lines):
            j = 0
            while j < len(line):
                c = line[j]
                
                # handle existing block comment
                if in_block_comment:
                    if c == '*' and j+1 < len(line) and line[j+1] == '/':
                        in_block_comment = False
                        j += 2
                        continue
                    j += 1
                    continue
                
                # handle line comment
                if in_line_comment:
                    break
                
                # check for comment starts
                if c == '/':
                    if j+1 < len(line) and line[j+1] == '/':
                        in_line_comment = True
                        break
                    elif j+1 < len(line) and line[j+1] == '*':
                        in_block_comment = True
                        j += 2
                        continue
                
                # check for string toggling
                if not in_string:
                    if c in ('"', "'"):
                        in_string = True
                        string_delim = c
                else:
                    if c == string_delim:
                        if not (j > 0 and line[j-1] == '\\'):
                            in_string = False
                
                if not in_block_comment and not in_line_comment and not in_string:
                    if c == '{':
                        if (i, j) == top_level_open:
                            stack.append((i, j, True))  # top-level
                        else:
                            stack.append((i, j, False))
                    elif c == '}':
                        if stack:
                            top_i, top_j, is_top = stack[-1]
                            if is_top:
                                # Check if there's more code (non-empty) after this brace
                                any_nonempty_after = False
                                for rem_line in lines[i+1:]:
                                    if not is_effectively_empty_or_comment(rem_line):
                                        any_nonempty_after = True
                                        break
                                if any_nonempty_after:
                                    # Closing the class too early => mark as extra
                                    braces_to_remove.add((i, j))
                                    # Do NOT pop => keep class open
                                else:
                                    # Final brace for the class
                                    stack.pop()
                            else:
                                stack.pop()
                        else:
                            # No matching open => extra
                            braces_to_remove.add((i, j))
                
                j += 1
            
            in_line_comment = False
        
        # Unmatched opens in the stack => extra
        while stack:
            line_idx, col_idx, is_top = stack.pop()
            braces_to_remove.add((line_idx, col_idx))
        
        # Filter braces by the provided line range, if given.
        if self.line_number_min is not None and self.line_number_max is not None:
            filtered_braces = set()
            for (r, c) in braces_to_remove:
                if self.line_number_min <= (r + 1) <= self.line_number_max:
                    filtered_braces.add((r, c))
            braces_to_remove = filtered_braces
        
        for (r, c) in braces_to_remove:
            line_char_list[r][c] = ''
        
        corrected_lines = [''.join(chars) for chars in line_char_list]
        
        with open(self.path, 'w', encoding='utf-8') as f:
            f.write(''.join(corrected_lines))
        if len(braces_to_remove)>0:
            print(f"Removed {len(braces_to_remove)} unmatched/extra brace(s).")
