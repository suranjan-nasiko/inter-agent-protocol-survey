# Build configuration, not a style change: the JAIR style files are untouched.
#
# Why this file exists. On a cold build (no main.aux yet), latexmk writes a
# stub aux containing \gdef\@abspage@last{1} to save a pass on short
# documents. That makes acmart's TotPages resolve to 1 during pass 1, which
# shrinks the page-1 layout enough that the authors'-contact-information
# footnote is typeset inside \maketitle's group, before jair.cls neutralizes
# \@ACM@checkaffil. The affiliation check then runs a second time on consumed
# state and raises "No country present for an affiliation", which is a
# ClassError, so pass 1 dies and latexmk stops.
#
# It is a false alarm: all seven author blocks carry \country, and the same
# source compiles clean under bare pdflatex, or under latexmk once a real aux
# exists. The trigger is length-dependent (seven authors plus a long
# structured abstract), so it is not something the source can grow out of.
#
# Dropping the \@abspage@last line from the stub removes the trigger and costs
# one extra pass on a document that needs several anyway. Verified against
# acmart 2.12 (AuthorKit) and 2.16 (TeX Live 2026).
#
# This lives here rather than in the Makefile so it also applies on Overleaf
# and anywhere else latexmk drives the build.
{
    no warnings 'redefine';
    my $orig = \&set_trivial_aux_fdb;
    *set_trivial_aux_fdb = sub {
        $orig->();
        open( my $aux, '> :raw', $aux_main ) or die "Cannot write '$aux_main'\n";
        print $aux "\\relax \n";
        close($aux);
        my $t = get_mtime($aux_main) - $filetime_causality_threshold - 3;
        utime $t, $t, $aux_main;
    };
}

# JAIR uses biblatex with the biber backend, so biber must run, not bibtex.
$bibtex_use = 2;
