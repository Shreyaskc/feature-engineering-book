# Chapter 3 exercises

Use the unchanged base fixture unless an extension is specified. All times are
integer synthetic minutes. Run `python exercise_answers.py` for computed answers
and explanations. Its hardcoded expectations assert each result, and every
correct numeric answer must agree between the reference and SQLite evaluators.

1. Compute D1 at 600 over [540,600), D2 at 610 over [550,610), and the fixed
   [540,600) window known at 610. List each contribution and explain why the
   last two queries differ.
2. Select the latest version of every event before testing availability.
   Calculate the wrong D1 result and identify the lost source version.
3. Jointly add K (event 540, available 541, amount 5), L (600,600,7), and
   M (599,600,3), all revision 1 for C1. Calculate D1. Change only M's
   availability to 601, with its delivery observation at 601; calculate again.
4. Hold [540,600) fixed and query cutoffs 604, 605, 606, and 607. Explain the
   decrease and subsequent increase. What remains true at the original cutoff 600?
5. Add C revision 3, event 585, available 605, amount 22. Calculate the fixed
   window at 604 and 605. Which rule resolves the equal-availability tie?
6. Use the deletion fixture at 620 and the restoration fixture at 619 and 620,
   always over [540,600). What happens if SQL removes deletes before ranking?
   Demonstrate that restoration requires explicit ledger opt-in.
7. Query C9 with known history, then unknown history. Query C1 with supplied
   rows but unknown relevant history. Explain why a sum cannot prove coverage.
8. Add a new delivery of A revision 1 observed at 609 and reverse all deliveries.
   Count deliveries and canonical versions and recalculate D1. What false result
   follows from replacing A's first availability with retry time 609? Explain
   why the authentic ledger rejects such a conflicting version.
