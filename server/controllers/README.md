# Controllers

This directory houses the business logic for the API.

I separated the logic from the route definitions to adhere to the single-responsibility principle. Furthermore, following the strict "1 file = 1 feature" rule, each controller function has its own dedicated file.

- To find the account creation logic (including the 10-digit hashed account number generator) visit [createAccount.ts](file:///c:/Hackathons/Wema%20MCP-API/server/controllers/createAccount.ts).
- To find the account update logic visit [updateAccount.ts](file:///c:/Hackathons/Wema%20MCP-API/server/controllers/updateAccount.ts).
- To find the transfer logic visit [createTransfer.ts](file:///c:/Hackathons/Wema%20MCP-API/server/controllers/createTransfer.ts).
- To find the transaction statement history logic visit [getStatement.ts](file:///c:/Hackathons/Wema%20MCP-API/server/controllers/getStatement.ts).
