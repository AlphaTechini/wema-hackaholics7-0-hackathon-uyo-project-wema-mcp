import { copyFileSync, mkdirSync } from 'node:fs';

mkdirSync('dist/mcp', { recursive: true });
copyFileSync('mcp/telegram-agent-instructions.md', 'dist/mcp/telegram-agent-instructions.md');
