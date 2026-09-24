import { verifyCampaignJournal } from "./index.ts";
if (process.argv.length !== 3) throw new Error("Usage: bun orchestrator/check-journal.ts EVENTS_DIRECTORY");
const state = verifyCampaignJournal(process.argv[2]!);
console.log(JSON.stringify({ events: state.eventCount, headSha256: state.headSha256 }));
