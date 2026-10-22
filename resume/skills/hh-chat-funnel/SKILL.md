---
name: hh-chat-funnel
description: >-
  HH.ru chats and negotiations funnel for Данила Сурков: clear unread badges,
  read full threads, answer recruiter questions individually, follow up without
  copy-paste. Use when the user asks to разобрать чаты/отклики/уведомления,
  ответить рекрутерам, снять непрочитанные, or maintain post-apply communication.
  Not for mass applying — use hh-apply-farm.
---

# HH chat funnel (чаты и коммуникация)

## Goal

Keep the funnel alive after applies: clear burning notifications, answer screening questions, nudge silent threads when asked, maximize real interview invites — **without deciding for the candidate**.

## Candidate (do not invent)

- Данила Сурков · System Analyst Middle+
- Telegram **@surkov_danila** · phone/email as in resume
- **Salary floor: 250000 на руки** · remote/hybrid · Moscow · EN C1
- Stack: REST/OpenAPI, Kafka/RabbitMQ, SQL/PostgreSQL, UML, BPMN, integrations (WMS/gov IS), Best2Pay fintech background
- Honest gaps: no industrial SOAP/Camunda/Oracle/1C; no Bitrix24/amoCRM/CFT ABS unless true

## Environment

- Same Chrome CDP session as applies: `127.0.0.1:9222`, profile `/home/ubuntu/chrome-hh-cdp`
- Chats UI: `https://hh.ru/chat` (filter «Unread only»)
- Negotiations: `https://hh.ru/applicant/negotiations`
- Send control: `textarea[data-qa=text-input]` + `[data-qa=chatik-do-send-message]`
- Open chat: `[data-qa=chatik-open-chat-{id}]`
- Message bodies: `[data-qa^=chatik-chat-message-][data-qa$=-text]`
- Log: `/tmp/hh-funnel-individual.json`

## Hard rules (user-enforced)

1. **Re-read the full thread every time** before writing. No copy-paste blasts across dialogs.
2. **Never book calendars / slots / time** (Google Appointment, Calendly, etc.).  
   Summarize the link to the user and wait. Do not click «Confirm/Book».
3. **Do not make career decisions**: no accepting offers, no committing to start dates beyond «готов обсудить», no auto-scheduling.
4. If вилка clearly **≪ 250k** (e.g. ~100k) — do not push interview; ask for compensation or politely decline further process.
5. Screening Q&A («готовы?», анкета без записи времени, опыт, формат) — answer; «создать анкету / пройти опрос» → **да, готов**, then open links that are forms/surveys, not schedulers.
6. Never type passwords / OTP. Captcha → screenshot to chat, wait.
7. When classifying Rejection vs Interview, look at **active chat status**, not sidebar text of other chats (sidebar pollutes `document.body`).

## Tone

- Confident Middle+, concrete, short
- Not arrogant, not junior-apologetic
- «Готовы?» → usually **да, готов** (nuances on interview)
- Offer Telegram `@surkov_danila` when useful
- Individual: mention vacancy title / recruiter name / their exact question

## Workflow

1. Open `https://hh.ru/chat`, enable **Unread only**.
2. List chats: id, company, title, last line, badges.
3. For each chat, in order (Interview / questions first, then rejections to clear badge):
   1. Open chat by `data-qa`.
   2. Extract **full** message list + links from the **open thread only**.
   3. Decide action:
      - **Rejection, no question** → open only (clear unread), no message.
      - **Question / screening** → individual answer from thread content.
      - **Interview invite + calendar link** → thank, **do not book**, ask вилка/format if needed, tell user about the link.
      - **Low salary vs 250k** → clarify compensation; don’t schedule.
   4. Send via composer; pause 5–12s; log to `/tmp/hh-funnel-individual.json`.
4. Re-check Unread only until empty (or report leftovers).
5. Optionally glance Interview tab on negotiations — still no auto-booking.

## Answer patterns (adapt, don’t paste verbatim)

- Hybrid/remote: готов к гибриду и удалёнке, Москва.
- Salary: от 250000 на руки, готов обсуждать вилку после задач.
- Unknown CRM/CFT/etc.: honestly no industrial experience + adjacent strengths + готов погрузиться.
- Calendar invite: слот сам не бронирую; пришлите/согласуем окна; вилка?
- Pure «отклик направлен в команду»: short thanks + wait + optional вилка/format ask.

## Anti-patterns learned

- Mass identical «Да, готов. Могу созвониться…» → forbidden.
- Booking Google Calendar because recruiter sent a link → forbidden.
- Treating whole `body.innerText` as chat status → false Rejection classification.
- Pushing CRM interview at ~100k against 250k floor → forbidden.

## Related

- Apply skill: `hh-apply-farm`
- Combined notes (legacy): may exist as `hh-recruiter-funnel`
- Resume AI wording lives in apply/resume edit flow, not in chat spam
