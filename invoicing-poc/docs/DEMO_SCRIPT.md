# Demo script (about 5 minutes)

**Setup:** seed data loaded, logged in, ngrok running with the Paystack test webhook URL set, a second browser tab ready for the Paystack checkout.

| Time | Do | Say |
|---|---|---|
| 0:00 | Show the dashboard | "Small-business owners in Nigeria track this in notebooks and WhatsApp. This is invoicing, payments, expenses and an AI accountant in one place. That's real data from a real database." Point to the red overdue banner and the summary. |
| 0:40 | **Create an invoice:** existing customer *Dara Fashion*, one line item (e.g. Consulting, 1 x 25,000), due date next week -> Create | "Total is computed on the server, never trusted from the browser. And I get a real Paystack payment link." |
| 1:30 | Click **Open sandbox payment link**, pay with `4084 0840 8408 4081`, any future expiry, CVV `408`, OTP `123456` | "This is the customer paying." |
| 2:15 | Back on the dashboard, **Refresh** (or wait a few seconds) | "No button pressed - Paystack called our signed webhook and the invoice flipped to **paid**. Duplicate deliveries can't double-count." Point at the badge and "Money in" going up. (If webhook isn't reachable: click **Check payment**.) |
| 2:45 | **Remind customer** on an overdue invoice (e.g. Emeka) -> confirm | "One click emails and texts the customer with the amount owed and a pay link. Manual, confirmed, rate-limited, and logged." |
| 3:15 | **Ask:** click "Which customers are slow payers?" then "Am I in the red or green this week?" | "The AI never guesses - every number comes from the database." |
| 3:50 | **Trick question:** type "Predict next month's revenue" | "It says it doesn't have that data instead of inventing a number. That's the design." |
| 4:15 | **Generate insights** (This week vs last) | Read one aloud, e.g. Ada's payments slowing. "That's not on the dashboard - it compared periods and customers." |
| 4:50 | Close | Use the "what's real" paragraph from README_day10.md. |

**If something breaks live:** payment not flipping -> "Check payment"; AI slow -> say "it's calling the Llama model live"; nothing loads -> `GET /health` and check the backend terminal.
