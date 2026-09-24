# arXiv abstract

The abstract to paste into the arXiv submission form is
`manuscript/arxiv-abstract.txt`. It is a separate, shorter text from the one in
`sections/00-frontmatter.tex`, which stays as the paper's own abstract.

## Why it is separate

The paper abstract is 2,557 characters. The arXiv field takes 1,920. It also
contains `\emph{}` markup and a typographic apostrophe, neither of which belongs
in a plain-text field.

## Constraints it is held to

Verified mechanically before use:

- 1,911 of 1,920 characters, and 1,909 if arXiv reflows the paragraphs to one
  line. Both forms fit, so the count does not depend on how the field is stored.
- Pure ASCII, 0 characters above U+007E. No em dash, en dash, double hyphen,
  curly quote, ellipsis, non-breaking space, or tab.
- No LaTeX at all: no commands, braces, dollars, tildes, or ampersands. The one
  apostrophe is the plain ASCII `'` in "sender's".
- House style holds: 21 sentences, longest 24 words, none at 26 or more.
- Three paragraphs, which arXiv preserves on a blank line.

## What was cut, and what was not

Cut: the word "survey" where it repeated, "Visa Trusted Agent Protocol" down to
"Visa TAP", "agentic commerce and payments" down to "agentic commerce", and the
closing clause of the ACSP and AGRP sentences.

Kept deliberately, because a reader searching arXiv needs them: all eleven named
protocols, the ten axes in full, the 12/8/4 protocol split across three layers,
all three extension names with what each one does, and both honesty
qualifications. Those are the single-rater and no-inter-rater-statistic
disclosure, and the "specification sketches, not validated standards" line.

## If the paper abstract changes

Re-check this file. They are independent texts and nothing enforces agreement.
Rerun the character and style checks before pasting; the margin is 9 characters.
