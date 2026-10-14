# AI Prompt Log

## Section 1

1. This file records the prompts used to do work in this directory.

2. I will be creating an agentic team that runs a shop. Before we start working, I want to set some rules of this shop - The field `desk.date_today` is “today” for the shop. Use this date to determine what is overdue.

- Vendor lead times come from the `vendors` table
- A vendor will not ship new product while they still have an open unpaid invoice
- Human approval is required for any payments. Points will be deducted if this is not done. If payment is made, make sure to update the relevant table.
- If there is not enough cash, the pay tool must refuse — no negative balances
- Cash only goes out in this homework — we did not model revenue, so no money comes in
- Before a full run to resolve the tickets, make sure to reset the database to the original values
- Do **not** email customers or call real vendors. Drafts stay on the board.

## Section 2

3. Create section 2

4. Open `data/campus_customs.db` and look through every table and its fields. Copy the original file to `data/campus_customs_new.db`. Later problems update that working copy.

Study the three open tickets so you see how they link to other tables. Start `output/harness.md`. For each table, list the fields and one short line on why that table matters for the agents.

You will keep growing this harness file in later problems.

## Section 3

5. Create section 3

6. Write an **MCP server** in `mcp_server/` using **FastMCP**. It will talk to `data/campus_customs_new.db`. You do **not** need to connect or run it in this problem.

**Every agent in this homework uses the tools in this MCP server.** You will add more tools to it later; for now write **three** tools you know you will need for the tickets in the database. Keep the names clear. Never invent any data, only use information in the database. In `output/harness.md`, list each of your three MCP tools. For every tool include: which table it reads, **which ticket** it helps unlock (101, 102, or 103), and **one sentence** on why that tool is the right one for that ticket. Vague lines like “reads inventory” score low — tie the tool to the ticket.

Also add a short `mcp_server/README.md` file that explains what the MCP server is for, which database file it uses, and the three tools it has.

## Section 4

7. Create section 4

8. In your vibe coder (Claude Code, Codex, or Cursor), add your MCP server to **this project** so the vibe coder can call the tools. Save the connection JSON text in `.mcp.json` at the project root (or however your vibe coder saves local MCP server lists). With your vibe coder connected, test **each** of your three MCP tools. Save the evidence in `output/mcp_smoke.json`. For every tool include:

- the prompt you asked the vibe coder
- the tool name
- the tool output (must match values in `data/campus_customs_new.db`)

## Section 5

9. Create section 5

10. Build the agentic team for Campus Customs using **PydanticAI**: **Boss**, **Inventory**, **Accounting**, **Facilities**, and **Customer Service**. Include prompts, models, and agent loops so they can delegate work to each other with full connectivity.

Put the agent prompts in `backend/prompts/` — **one file per agent**. Put data types in `backend/models.py`, and the agent files under `backend/` (your layout can vary as long as the five roles are clear). Use your `PORTKEY_API_KEY` and **only** `gpt-6-luna` for every agent.

Write each prompt in your own words with the shop rules that agent needs. More detailed prompts that cover all aspects of an agent’s work and scope score higher than a short generic prompt. Add any tools the agents need to your MCP server so they can work on the open tickets. Shop facts come from the MCP server over `data/campus_customs_new.db` — do not invent a second shop-tools layer that bypasses MCP.

Wire the agents so they append to `output/audit_trail.json` as they run: for each agent-loop step, record enough to audit later. Append to this file — do not wipe it each run.

In `output/harness.md`, list each agent and each MCP tool (including ones you add in this problem) along with which table the tool uses. Also add a short **safety** section: the guardrails a real business would want when agents touch real customers and real money, plus limits that keep token use in check.

Update `mcp_server/README.md` so the tool list matches what you have now.

## Section 6

11. create section 6

12. Before you wire the backend, write down what you **expect** the team to do on each open ticket. Build `output/desk_tickets.html`— a page you can double-click with **one tab per ticket** (101, 102, and 103). Also add empty **Cash** and **Reflection** tabs for later problems (leave them blank or with a short “coming later” note for now).

On each ticket tab, fill an **Expected** section only (leave room for an **Actual** section you will fill after you run the agents). For each ticket’s Expected section, write in your own words:

- Who the **Boss** should call **first**, and why
- **All** the agent delegations you expect — not “Boss calls everyone”
- Which **MCP tools** you expect that run to use

Plans that send every specialist on every ticket score low. You will compare this plan to what actually happens when your agents resolve the three tickets.

## Section 7

13. create section 7

14. Your React frontend dashboard (the next problem) needs a backend it can call. In `backend/main.py`, use **FastAPI** and add **routes** that do the following:

- Return the three tickets and whether each is open or resolved
- Take a ticket id and run your agent team on that ticket
- Return recent agent events — what each agent said and which tools they used — so the board can refresh
- Approve a payment or purchase after a human clicks approve (agents only prepare the pay; this route is what actually changes cash)
- Return the current checking balance from `cash_accounts`
- Reset the database to the original values when you want to try a fresh run

15. From the `backend/` folder, start the server with:

```plaintext
uvicorn main:app --reload --port 8000
```

This turns on your backend at `http://localhost:8000` so the frontend dashboard can call those routes.

In `output/harness.md`, list each route in one line (what URL / what it does).

## Section 8

16. create section 8

17. Build the frontend dashboard in `frontend/` with **React + Vite + TypeScript**. The page should call the routes you built in Problem 7. At minimum the board should:

- List all **three** tickets
- Let you **pick one ticket** and start the agent team on it
- Show each agent and what they are saying / doing while the ticket runs
- Mark a ticket **resolved** when the run finishes
- Show a short **summary of what each agent did** on that ticket
- Let a human **approve** a pay or purchase when asked
- Show the checking balance (it should drop after an approved pay)

Make the dashboard look good. Be creative with the layout and feel — this is a real desk people would want to sit at, so put thought into how it looks.

18. Tell the front end to talk to your backend at `http://localhost:8000`. On the backend, allow the Vite page origin (usually `http://localhost:5173`) so the browser is allowed to call those routes. Start the board with:

```text
npm run dev
```

This opens the React desk in your browser so you can pick tickets and watch agents.

Write `output/design.md` with what you chose for the dashboard look (layout, how agents read differently, how resolved tickets and cash show up) and why — including the creative choices that make it feel special and something humans would actually enjoy using.

## Section 9

19. Create section 9

20. Before testing the agents on a full run over the three tickets, reset the working database `data/campus_customs_new.db` again so you start clean. Note the starting checking balance. Then run all three tickets on the board (101, 102, 103) until each is resolved.

Open `output/desk_tickets.html` from Problem 6. On each ticket tab, fill the **Actual** section from this run: which agents worked, what they delegated, and which tools they used. Keep your Expected section so you can compare the two.

21. On the **Cash** tab of the same `output/desk_tickets.html`, itemize the money:

- Starting checking balance (after the reset)
- For **each** ticket: how cash changed when that ticket resolved, and why (which pay / purchase, dollar amount)
- Ending checking balance — it must match `cash_accounts` in the working database

Wrong cash math loses points even if the board shows every ticket resolved. Also save:

- `output/resolved_tickets.json` — for each ticket: id, final status, short outcome, what each agent contributed, and any human approvals
- `output/resolved_board.html` — a page you can double-click with a screenshot of your React board for each resolved ticket (101, 102, and 103)

Append real runs to `output/audit_trail.json`. Finish `output/harness.md` so it covers tables, MCP tools, the five agents, API routes, the dashboard, and safety rules.

## Section 10

22. Create section 10

23. Open `output/desk_tickets.html` and fill the **Reflection** tab. Answer in your own vibe, and be detailed and thorough:

- How would you evaluate the performance of the agents on each ticket and why?
- For each ticket, how did Actual compare to the Expected plan you wrote earlier?
- What would have been simpler as one agent with tools — and **why**?
- Describe three **new** problems Campus Customs might face that this agent team could solve with the tools you built
- Describe three **new** problems Campus Customs might face that this agent team could **not** solve with the tools you built, and explain the tools and agents you would need to solve them

24. Tie every answer to *this* app and the three tickets you ran — use the ticket tabs and Cash tab on the same page as your evidence. Generic AI essays without Campus Customs details will score low.

## Section 11

25. Create section 11

26. How to access the shop

27. Clicking on backend API link it shows Not Found

28. Run the whole thing

29. Make this the project folder layout:

```text
hw5/
├── AI_prompts.md
├── requirements.txt
├── .env.example
├── .gitignore
├── .mcp.json
├── README.md
├── data/
├── mcp_server/
├── frontend/
├── backend/
└── output/
```

The README should explain copying the original database to the working copy for a clean run, starting the MCP server, starting the FastAPI backend, starting the React board, and resetting the database before a full ticket run.

31. Push my code to a public Github repository so graders can clone it. Also put it in output/github_url.txt. Do not push real .env to the Github repo. Do include both database files under data/ (the original and your working copy) so graders can run the app easily


