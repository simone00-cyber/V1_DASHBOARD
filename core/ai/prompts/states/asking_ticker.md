The current objective is to identify the financial instrument.

If the user provides a ticker, propose a SET operation for:

/instrument/ticker

Normalize the ticker to uppercase.

After receiving the ticker, transition to asking_goal.

Do not define entry or exit rules yet unless the user has already provided
a complete and unambiguous strategy description.