---
name: hh-apply-farm
description: >-
  HH.ru vacancy apply farm for Данила Сурков via Chrome CDP (HTML/JS-first).
  Use when the user asks to откликаться на hh, нафармить отклики, apply to
  System Analyst vacancies, handle HH captcha handoff, or run scheduled apply
  batches (3–5 vacancies). Not for chat replies — use hh-chat-funnel.
---

# HH apply farm (отклики)

## Candidate (do not invent)

- Данила Сурков, 25, Москва (м. Борисово)
- +7 927 013 15 70 · danila-surkov@mail.ru · Telegram **@surkov_danila**
- System Analyst Middle+ · Ви6 Сервисес (WMS / госИС / REST / Kafka)
- Stack: REST/OpenAPI/Swagger, Kafka/RabbitMQ, PostgreSQL/SQL, UML, BPMN, Jira/Confluence
- Honest gaps: no industrial SOAP / Camunda / Oracle / 1C
- **Salary floor: 250000 на руки** · remote/hybrid · EN C1
- AI line in resume «О себе»: Cursor, Codex, Claude, Gemini, ChatGPT daily (work, life, job search)

## Environment

- Chrome CDP on `127.0.0.1:9222` with **non-default** profile:  
  `/home/ubuntu/chrome-hh-cdp` (default `~/.config/google-chrome` blocks DevTools)
- Script: `/workspace/resume/hh_farm30.py` (`N` at top = batch size)
- State: `/tmp/hh-applied-ids.txt`, `/tmp/hh-farm*.json`, `/tmp/hh-CAPTCHA-STOP`
- Screenshots: `/opt/cursor/artifacts/hh-*.png`
- Resume: `https://hh.ru/resume/3e8a2bfcff0c2e3a390039ed1f4b46706a446c`

## Hard rules

1. Never type HH password / OTP / SMS.
2. **Captcha → STOP.** Screenshot `/opt/cursor/artifacts/hh-captcha-latest.png`, show in chat, wait for human text.  
   Fill `[data-qa=account-captcha-input]` / `input[name=captchaText]`, **mouse-click** modal **Отправить** (not vacancy «Send application»).
3. One Apply click per `vacancyId`; track `/tmp/hh-applied-ids.txt`.
4. Always **hard reload** vacancy page before trusting Apply / Already applied UI.
5. Pauses between user actions: random **5–15s**.
6. Prefer CDP DOM/JS over screenshots (except captcha / broken UI).
7. Skip or don’t push roles with вилка clearly below **250k net**.
8. HTML-first: `data-qa`, then text; Magritte radios → CDP mouse on `[data-qa=cell]`.

## Flow per vacancy

1. Search: System Analyst, Moscow / remote, 1–3 or 3–6y.
2. Open vacancy → hard reload → skip if already applied.
3. Click Apply once (`vacancy-response-link-top` / serp response).
4. Employer task: radios by question (Да/Нет honestly); `textarea[name^=task_]` by nearest `[data-qa=task-question]`.
5. Short individual cover letter; QA for junk / orphan `3` / watermarks.
6. Submit only form send buttons — never second Apply.
7. Success only if «You applied» / already / real confirmation — not mere click.

## Captcha helper

Use `solve_captcha_with_answer(cdp, text)` in `hh_farm30.py` (mouse on Отправить).

## Related

- Texts: `/workspace/resume/TEXTS.md`
- One-pager: `/workspace/resume/danila-surkov-ru.html` + PDF
- Reports: `/workspace/resume/hh-otkliki-*.xlsx`
- Chats skill: `hh-chat-funnel`
