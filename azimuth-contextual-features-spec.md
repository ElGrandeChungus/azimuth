# BUILD SPEC: Azimuth — Contextual Chat Features

> **Scope**: Small feature set for the Azimuth shell (not Lore Map specific)
> **Depends on**: Azimuth Phase 0 running
> **Estimated effort**: 1 session (2-3 hours)

---

## OVERVIEW

A set of interrelated features that improve how the user references,
quotes, and provides context in conversations. All share the same
underlying principle: make it explicit to the AI which parts of the
conversation the user is responding to or referencing.

These are generic chat features that improve every conversation,
not just worldbuilding.

---

## Feature 1: Quote Reply

### What it does

User selects text in an assistant message, clicks "Quote," and the
quoted text is inserted at the cursor position in the message input
with contextual framing.

### User flow

1. User reads an assistant message with multiple questions or points
2. User highlights a specific passage (e.g., "Name — what are they called?")
3. A small floating "Quote" button appears near the selection
   (like Medium's highlight popover)
4. User clicks "Quote"
5. The quoted text is inserted into the message input at the current
   cursor position, formatted as:

```
> Name — what are they called?

```

6. Cursor is placed on the blank line after the quote, ready to type
7. User can repeat — highlight another passage, quote it, type a
   response under it
8. Final message might look like:

```
> Name — what are they called?
Kael Vasuda

> Category — would you say they're a civilian, criminal, or something else?
Criminal, but he presents as a civilian dock worker

I'll fill in the rest later, still thinking about his backstory.
```

### Technical details

**Frontend:**
- Text selection listener on assistant message bubbles
- Floating popover positioned near the selection (above or below)
- On click: get selected text, insert into message input at cursor
- Use markdown blockquote syntax (`> quoted text`)
- Add a blank line after the quote block for the user to type
- If input already has content, insert at cursor with appropriate
  line breaks before and after
- Popover dismisses on click-outside or Escape

**Backend:**
- No backend changes needed for basic functionality
- The `> quoted text` markdown syntax is already readable by LLMs
- For enhanced extraction, the orchestrator can optionally detect
  blockquote patterns and annotate them as explicit quote-response
  pairs before passing to the producer model

**Message format sent to AI:**
The raw message text includes the markdown blockquotes naturally.
Add a small instruction to the system prompt:

```
When the user's message contains markdown blockquotes (lines starting
with ">"), these are direct quotes from your previous message. The
text following each blockquote is the user's response to that specific
quoted passage. Use this to map responses to your questions precisely.
```

### Edge cases
- Multiple quotes from the same message: each gets its own blockquote
- Quote from an older message (not the most recent): still works, the
  AI can see the context
- Empty quote (user quotes but doesn't respond below it): treat as
  "I want to address this but haven't answered yet"
- Very long selections: truncate display in input to first ~100 chars
  with "..." but keep full text

---

## Feature 2: Quick Copy Blocks

### What it does

Code blocks, entry names, slugs, and other structured output from
the assistant get a one-click copy button. Standard chat feature that
every AI interface has — Azimuth should have it too.

### User flow

1. Assistant message contains a code block, a lore entry slug, a
   formatted name, or any backtick-wrapped content
2. A small copy icon appears in the top-right corner of the block
   (or on hover for inline code)
3. User clicks the icon
4. Content is copied to clipboard
5. Icon briefly changes to a checkmark to confirm

### Technical details

**Frontend only — no backend changes.**

- Detect fenced code blocks (```) in rendered markdown: add a copy
  button overlay to the rendered block
- Detect inline code (`backtick wrapped`) in rendered markdown:
  add copy-on-click behavior (click the inline code to copy it)
- Use `navigator.clipboard.writeText()` for clipboard access
- Brief visual feedback: icon swap to checkmark for 1.5 seconds

---

## Feature 3: Pin to Context

### What it does

User can "pin" a specific assistant message (or a highlighted portion)
so that it stays in the AI's context even as the conversation gets long.
Solves the problem of important information getting pushed out of the
context window in long worldbuilding sessions.

### User flow

1. User is deep in a conversation and the AI made an important
   statement 20 messages ago (e.g., established a key canon fact)
2. User clicks a pin icon on that message (or highlights text and
   clicks "Pin" from the same popover as Quote)
3. A small indicator appears on the message showing it's pinned
4. Pinned content is included at the top of the context sent to the
   AI on every subsequent message in this conversation
5. User can view and manage pins from a small panel (list of pinned
   items with unpin buttons)

### Technical details

**Frontend:**
- Pin icon on each assistant message (visible on hover)
- If Quote popover is open, add "Pin" as a second option alongside
  "Quote" — this pins just the selected text rather than the full
  message
- Pinned messages panel accessible from conversation header
  (small icon showing pin count)
- Pinned items show a truncated preview with unpin button

**Backend:**
- New database table (or add to existing messages table):

```sql
CREATE TABLE IF NOT EXISTS pinned_context (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    message_id TEXT,              -- source message (nullable if custom)
    content TEXT NOT NULL,         -- the pinned text
    pinned_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
```

- When building the messages array for the AI call, inject pinned
  content as a system message after the main system prompt:

```
[Pinned context for this conversation:]
- "The Margwan scholars control the northern trade corridor" (pinned from message 12)
- "Kael Vasuda is a criminal operating under civilian cover on Seicoe Station" (pinned from message 28)
[End pinned context]
```

- Pinned content counts against the context window, so limit to
  ~10 pins or ~2000 tokens of pinned content per conversation
- API endpoints:
  ```
  POST   /api/conversations/:id/pins    Add a pin
  GET    /api/conversations/:id/pins    List pins
  DELETE /api/conversations/:id/pins/:pin_id   Remove a pin
  ```

### Why this belongs with Quote

Quote and Pin come from the same interaction: selecting text in an
assistant message. The popover that appears on text selection should
offer both "Quote" (insert into my reply) and "Pin" (keep in context).
They share the selection UI. Building them together is natural.

---

## Feature 4: Paste with Source Label

### What it does

When the user pastes external content (from a wiki, a rulebook PDF,
another chat, etc.), Azimuth detects the paste event and offers to
label it with a source tag. This tells the AI "this is reference
material, not my own words."

### User flow

1. User copies text from a Lancer rulebook PDF or wiki page
2. User pastes into the Azimuth message input
3. A small toast/bar appears above the input: "Label this paste?
   [Add source] [Skip]"
4. If user clicks "Add source": a small input appears to type a
   label (e.g., "Lancer Core Rulebook p.142")
5. The pasted text gets wrapped:

```
[Reference from: Lancer Core Rulebook p.142]
> Pasted content here...
[End reference]
```

6. If user clicks "Skip": paste goes in as normal text
7. Toast auto-dismisses after 5 seconds if no action taken (paste
   stays as normal text)

### Technical details

**Frontend:**
- Listen for `paste` events on the message input
- Detect if pasted content is >50 characters (skip labeling prompt
  for short pastes like a single word)
- Show a non-blocking toast/bar that doesn't interrupt typing
- If labeled: wrap content in reference markers
- Store a per-conversation preference: if user always skips, stop
  asking (with a "don't ask again" option)

**Backend:**
- No backend changes strictly needed — the `[Reference from: ...]`
  markers are readable by the AI naturally
- Add to system prompt:

```
When the user's message contains blocks wrapped in [Reference from: ...]
markers, this is external content they've pasted for context. Treat it
as reference material — acknowledge the source, use the information,
but do not assume the user wrote it or that it is canon unless they
confirm it.
```

### Why this belongs here

This is the mirror of Quote Reply. Quote Reply lets you reference the
AI's output with context. Paste with Source lets you inject external
content with context. Both solve the same problem: telling the AI
where information came from so it can use it appropriately.

---

## BUILD ORDER

### Task 1: Selection Popover Infrastructure
Build the text selection detection and floating popover component
that appears when text is selected in assistant messages. This is
shared infrastructure for Quote and Pin.

- Selection listener on message bubbles
- Popover positioning logic (above selection, stay in viewport)
- Two buttons: "Quote" and "Pin"
- Dismiss on click-outside, Escape, or new selection
- Mobile: long-press to select, popover appears on release

**Verify:** Selecting text in an assistant message shows the popover
with both buttons. Buttons don't do anything yet.

### Task 2: Quote Reply
Wire up the Quote button:

- Insert blockquoted text into message input at cursor position
- Handle multiple quotes (accumulate in input)
- Add line break after quote for typing
- Add system prompt instruction for blockquote interpretation

**Verify:** Can select text, click Quote, see it in input as
blockquote, type response below it, send message. AI correctly
interprets quoted text as referencing specific prior content.

### Task 3: Quick Copy Blocks
Add copy buttons to code blocks and click-to-copy on inline code:

- Copy button overlay on fenced code blocks
- Click-to-copy on inline code spans
- Clipboard write + visual confirmation

**Verify:** Code blocks show copy button. Clicking copies content.
Inline code copies on click. Checkmark confirmation appears.

### Task 4: Pin to Context
Wire up the Pin button and build the pinned context system:

- Backend: pinned_context table, CRUD endpoints
- Frontend: Pin button in popover, pin indicator on messages,
  pinned items panel in conversation header
- Backend: inject pinned content into AI message array
- Limit: 10 pins or ~2000 tokens per conversation

**Verify:** Can pin text from a message. Pinned content appears in
panel. AI references pinned content in later messages even if the
original message is far back in history. Can unpin.

### Task 5: Paste with Source Label
Implement paste detection and source labeling:

- Paste event listener on message input
- Toast component for label prompt
- Source wrapping with reference markers
- System prompt instruction for reference handling
- "Don't ask again" preference

**Verify:** Pasting long text triggers label prompt. Adding a label
wraps content in reference markers. AI acknowledges source in
response. Skipping leaves paste as normal text.

---

## AGENT INSTRUCTIONS

1. Follow BUILD ORDER. Task 1 is shared infrastructure for Tasks 2 and 4.
2. The selection popover is the core UI component — get this right
   and Tasks 2 and 4 are mostly wiring.
3. All features must work on mobile. Long-press replaces hover.
   Popovers must not overflow the viewport.
4. Do not modify the orchestrator or producer pipeline. These are
   chat-level features, not Lore Map features. The AI interprets
   the quote/pin/reference markers through natural language
   understanding, not custom parsing.
5. Keep the popover minimal — two small buttons, no chrome. It
   should feel lightweight, not like opening a menu.
6. Pin to Context is the only feature requiring backend changes.
   The other three are frontend-only.
7. Commit after each task.

---

## ACCEPTANCE TESTS

- [ ] Text selection in assistant messages shows popover with Quote and Pin
- [ ] Quote inserts blockquoted text at cursor in message input
- [ ] Multiple quotes accumulate correctly in the input
- [ ] AI interprets blockquotes as references to its prior content
- [ ] Code blocks have copy button, inline code is click-to-copy
- [ ] Clipboard copy works with visual confirmation
- [ ] Pinning text stores it and shows pin indicator
- [ ] Pinned content panel shows all pins with unpin option
- [ ] AI uses pinned content even 20+ messages later
- [ ] Pin limit (10 or ~2000 tokens) is enforced
- [ ] Pasting long text triggers source label prompt
- [ ] Labeled pastes are wrapped in reference markers
- [ ] AI acknowledges external sources appropriately
- [ ] All features work on mobile viewport
- [ ] No regressions in existing chat functionality
