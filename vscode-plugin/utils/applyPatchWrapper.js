const diff = require('diff');

// Create a wrapper function
function applyPatchWithWhitespaceIgnore(source, uniDiff, options = {}) {
    // Modify the compareLine function in options to ignore whitespace
    const originalCompareLine = options.compareLine || ((lineNumber, line, operation, patchContent) => line === patchContent);
    
    options.compareLine = (lineNumber, line, operation, patchContent) => {
        // Normalize whitespace for both lines before comparison
        const normalizedLine = line.replace(/\s+/g, ' ').trim();
        const normalizedPatchContent = patchContent.replace(/\s+/g, ' ').trim();
        return originalCompareLine(lineNumber, normalizedLine, operation, normalizedPatchContent);
    };

    // Call the original applyPatch function with modified options
    return diff.applyPatch(source, uniDiff, options);
}

module.exports = { applyPatchWithWhitespaceIgnore };
