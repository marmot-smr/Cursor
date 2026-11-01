---
name: hh-recruiter-funnel
description: >-
  HH.ru job-search automation for Данила Сурков: HTML/JS-first CDP apply farm,
  captcha handoff with screenshots, resume edits, and post-apply funnel
  (negotiations, chats, invitations, follow-ups). Use when the user asks to
  откликаться на hh, разобрать отклики/чаты, снять уведомления, ответить
  рекрутерам, обновить резюме на HH, or continue the HH search pipeline.
---

# HH recruiter funnel (Данила Сурков)

## Candidate facts (do not invent)

- Name: Данила Сурков, 25, Moscow м. Борисово
- Phone: +7 927 013 15 70
- Email: danila-surkov@mail.ru
- Telegram: **@surkov_danila** (also @surkov_work)
- Role: System Analyst Middle+
- Stack: REST/OpenAPI/Swagger, Kafka/RabbitMQ, PostgreSQL/SQL, UML, BPMN, Confluence/Jira
- Current: Ви6 Сервисес — integrations with WMS and government IS
- Honest gaps: no industrial SOAP/Camunda/Oracle/1C
- Salary floor for forms: **250000 на руки**
- Format: remote / hybrid, Moscow
- English C1

## Environment

- Cloud agent desktop Chrome with CDP: non-default profile  
  `/home/ubuntu/chrome-hh-cdp` + `--remote-debugging-port=9222`
- Default Chrome profile path blocks DevTools (`DevTools remote debugging requires a non-default data directory`).
- Main script: `/workspace/resume/hh_farm30.py`
- Logs/artifacts: `/tmp/hh-farm*.json`, `/tmp/hh-applied-ids.txt`, `/opt/cursor/artifacts/hh-*.png`
- Resume on HH: `https://hh.ru/resume/3e8a2bfcff0c2e3a390039ed1f4b46706a446c`

## Hard safety rules

1. **Never type HH password / OTP / SMS.**
2. **Captcha:** stop immediately. Screenshot → `/opt/cursor/artifacts/hh-captcha-latest.png`, show in chat, wait for human text.  
   Solver: `solve_captcha_with_answer` — fill `input[name=captchaText]` / `[data-qa=account-captcha-input]`, **mouse-click** modal button text `Отправить` (not vacancy «Send application»).
3. **No double-apply:** track vacancy ids in `/tmp/hh-applied-ids.txt`. One «Откликнуться» click per vacancy.
4. **Always hard-reload** vacancy pages (`Page.reload ignoreCache` + cache-bust) before trusting Apply/Already applied UI.
5. Pauses between user actions: random **5–15s** (antibot). DOM reads: no pause.
6. Prefer **HTML/JS via CDP** over screenshots. Visual only for captcha / broken UI.

## Hard rules from user (communication)

1. **Never book interview slots / calendars / time** without explicit user approval in chat.
2. If recruiter sends a calendar/form link: summarize in chat to the user, do **not** complete booking. Forms/questionnaires screening OK only if they are Q&A (зарплата, формат, опыт) — not scheduling.
3. **Salary floor: 250000 net.** If vacancy or chat implies substantially lower (e.g. ~100k) — do not push to interview; ask for вилка or politely decline further process.
4. Role of agent in chats: answer questions, keep dialogue alive, clear notifications. **Do not make career decisions** (accept offer, book time, commit to start date beyond "готов обсудить").
5. No copy-paste blasts. Re-read full thread every time; write an individual reply.
6. Telegram @surkov_danila — offer as contact, not as auto-scheduling.


## Apply farm (CDP HTML-first)

```bash
# Chrome must listen on 9222 with chrome-hh-cdp profile
python3 /workspace/resume/hh_farm30.py   # N at top of file
```

Flow per vacancy:

1. Navigate + hard reload
2. Skip if already applied
3. Click Apply once (`[data-qa=vacancy-response-link-top]` / serp response)
4. Employer task: Magritte radios (`input[type=radio]` + `data-qa=cell`) via **CDP mouse**; textareas `textarea[name^=task_]` answered by nearest `[data-qa=task-question]`
5. Cover letter short, tailored; QA textarea for junk / orphan `3` / watermarks
6. Submit only form buttons (`Отправить` / submit), never second Apply
7. Success only if «You applied» / already / apps badge up — not mere click

Salary answers: 250000. Prefer remote/hybrid. Camunda/SOAP → честное «нет» / короткий отказ без вранья.

## Resume «О себе» (AI line)

Keep existing competencies. AI paragraph (RU) already used:

> ИИ и код применяю каждый день в работе, быту и даже в поиске вакансий: уверенно работаю с Cursor, Codex, Claude, Gemini, ChatGPT — черновики ТЗ и OpenAPI, SQL, разбор логов, документация, автоматизация рутины.

Edit via `[data-qa=resume-edit-button-about]` → `[data-qa=resume-editor-about]` → Save `[data-qa=resume-partial-edit-save]`. Do not delete other blocks.

## Funnel after apply (negotiations + chats)

Goal: clear notification badges, answer recruiter questions, nudge silent threads, maximize interview invites. Invite to Telegram `@surkov_danila` when useful.

### Tone

- Confident, concrete, Middle+ SA — not arrogant, not junior-apologetic
- Clarification «готовы?» → almost always **готов** (user handles nuances on interview)
- Do not invent SOAP/Camunda/years
- Short messages; one CTA (созвон / Telegram)

### Workflow

1. Open `https://hh.ru/applicant/negotiations`
2. Triage tabs: Invitations / Interview / Pending / unread
3. Clear burning notifications by opening + acting
4. For each chat needing reply:
   - Read last recruiter messages (DOM)
   - Answer screening questions honestly with salary ≥250k / remote-hybrid / готов
   - Soft bump if silent > few days: short polite nudge + value + Telegram
5. Log actions to `/tmp/hh-funnel-log.json` and optional xlsx under `resume/`

### Sample bump

```
Добрый день! Подскажите, пожалуйста, актуален ли ещё отклик по вакансии системного аналитика?
Готов созвониться на этой неделе. Если удобнее — Telegram @surkov_danila
```

### Sample screening

- ЗП: от 250000 на руки, готов обсуждать вилку под задачи
- Формат: удалёнка / гибрид, Москва
- Старт: две недели
- Готовность к собесу: да, на этой неделе

## Anti-patterns learned

- Magritte radio `.click()` alone often fails → use `Input.dispatchMouseEvent` on cell center
- Counting «ok» from submit without «You applied» inflated stats (badge lagged)
- Captcha submit must be the **captcha modal** Отправить, not vacancy Send application
- CDP needs non-default `--user-data-dir`
- English UI labels: Respond / You applied / Applications / Complete the CAPTCHA

## Related repo files

- `/workspace/resume/hh_farm30.py` — farm script
- `/workspace/resume/TEXTS.md` — GetMatch/HH paste texts
- `/workspace/resume/danila-surkov-ru.html` + PDF — one-pager
- `/workspace/resume/hh-otkliki-*.xlsx` — apply reports
