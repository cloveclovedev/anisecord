# anisecord Strategic Design: Discord Hub Strategy

## Positioning

anisecord is "a suite of AI assistants living in your Discord server." It naturally generates outputs, analyzes life logs, supports planning, and accumulates knowledge from everyday memos and conversations.

### Differentiation from Competitors

- **Claude Code / ChatGPT**: "Go talk to AI" experience. Primarily for engineers/technical users
- **Notion / Obsidian**: "Organize it yourself" experience. Requires structured input
- **anisecord**: "AI lives in your daily space" experience. Minimal input friction

### Discord Hub Advantages

| Aspect | Discord Hub | AI App + Plugin | Custom Web App |
|--------|------------|-----------------|----------------|
| Onboarding barrier | Very low (server invite only) | Medium (app + plugin setup) | High (new registration) |
| Mobile image input | Natively seamless | Possible but more steps | Must build from scratch |
| Memo / AI toggle | Channel separation | Impossible (all sent to AI) | Must build from scratch |
| Community effect | Built-in | None | Must build from scratch |
| API cost control | User-controlled | Difficult | Must build from scratch |
| Target audience | Broad (existing Discord users) | Skews technical | All, but hard to acquire |
| Development cost | Low (leverage existing assets) | Medium (learn Plugin APIs) | Very high |

**Core value**: "Accumulate without thinking, let AI turn it into value when needed."

## Four Feature Pillars

### Pillar 1: Output Generation
Generate SNS posts, blog drafts, etc. from accumulated conversations and memos.
- Existing: SNS-X
- Future: Blog drafts, weekly summaries, meeting notes

### Pillar 2: Life Log x AI
Record daily life via images and text. AI analyzes and advises.
- Existing: Nutrition
- Future: Exercise tracking, sleep, expense management

### Pillar 3: Planning & Task Management (High Priority)
Integrate with external tools (TickTick, GitHub Issues, etc.) to auto-generate and post plans.
- Today's plan / weekly plan auto-posted to diary channels
- Core: aggregating information from external tools

### Pillar 4: Knowledge Accumulation
AI organizes memos, links, and conversations for search and summarization.

### Relationship Between Pillars

```
External Tools ──→ [Pillar 3: Planning]  ──→ Diary Channel
                        ↑
[Pillar 4: Knowledge] ←→ Discord Accumulation ←→ [Pillar 2: Life Log]
                        ↓
                   [Pillar 1: Output] ──→ SNS / Blog etc.
```

Natural flow: Input (planning) → Accumulation (knowledge, life log) → Output (generation).

## Server / Channel Design

### A. Personal Server (1 server per user)

Each user creates their own server and invites the anisecord Bot. The Bot recognizes channel roles based on naming conventions.

```
[User's Personal Server]
├── #daily-plan       ← Pillar 3: today's plan auto-post
├── #weekly-plan      ← Pillar 3: weekly plan auto-post
├── #memo             ← Pillar 4: free memos (no AI intervention)
├── #knowledge        ← Pillar 4: AI search & summarization target
├── #meal             ← Pillar 2: meal records
├── #sns-draft        ← Pillar 1: SNS draft generation
└── #bot-config       ← Settings
```

### B. Shared Server (operated by anisecord)

Community for sharing content users are comfortable making public.

```
[anisecord Shared Server]
├── #meal-share       ← Share meal records (motivation)
├── #workout-share    ← Share workout records
├── #sns-draft-share  ← Draft feedback
└── #general          ← Community chat
```

## Subscription

- **Unit**: Discord User ID
- Tied to user, so same permissions across all servers
- On shared servers, Bot checks subscription status by user ID at command execution
- Free tier to lower onboarding barrier (e.g., N uses per month free)

## Technical Strategy

- **DB**: Neon (PostgreSQL) - Data persistence only. $0/month
- **User management**: Mock for now. Swap Repository when ready for DB
- **Auth**: Discord's native user ID (no additional auth infrastructure needed)
- **Subscription**: Phase 2. feature_enabled decorator is sufficient until then
- **Design principle**: Services swappable via Repository layer (existing DDD pattern)

### Architecture

```
bot/
├── core/
│   ├── bot.py
│   ├── user/                   # Mock for now → DB later
│   └── subscription/           # Added in Phase 2
├── features/
│   ├── sns_x/                  # Existing
│   ├── nutrition/              # Existing
│   ├── daily_plan/             # Added in Phase 1
│   └── knowledge/              # Added in Phase 3
└── services/
    ├── discord/                # Existing
    ├── llm/                    # Existing
    ├── database/               # Added in Phase 1 (Neon)
    ├── ticktick/               # Added in Phase 1
    └── github/                 # Added in Phase 1
```

## Implementation Priority

### Phase 1: Planning & Task Management (Pillar 3)
1. Neon connection + DB infrastructure (migrations, etc.)
2. TickTick / GitHub Issues integration services
3. `/daily-plan` command + diary channel auto-posting
4. `/weekly-plan` command

### Phase 2: Subscription + User Persistence
5. UserRepository DB implementation
6. Stripe + subscription decorator

### Phase 3: Knowledge Accumulation (Pillar 4)
7. Memo channel monitoring + DB storage
8. AI search & summarization commands

### Phase 4: Shared Server + Community
9. Shared server design & launch
10. Life log sharing features
