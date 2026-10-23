#!/usr/bin/env python3
"""HH.ru HTML/JS-first apply farm via Chrome CDP. Target N successful applies.

ПРАВИЛА (жёстко):
1. Капча / «докажите что вы человек» / SmartCaptcha → НЕМЕДЛЕННЫЙ СТОП всего фарма.
   Никаких кликов по капче. Пишем /tmp/hh-CAPTCHA-STOP и ждём человека.
2. Перед работой со страницей вакансии — всегда hard reload (не из кэша).
   Иначе UI врёт («Откликнуться» при уже откликнутой).
3. Один клик «Откликнуться» на вакансию. Повторно на ту же vacancyId — никогда.
4. Перед кликом проверить already/You applied / «уже откликались» — если да, SKIP.
5. Не трогать капчу «в фоне», не угадывать картинки.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook
from websocket import create_connection

# Batch size: HH_FARM_N=3 python3 resume/hh_farm30.py   or   python3 resume/hh_farm30.py 3
N = int(os.environ.get("HH_FARM_N") or (sys.argv[1] if len(sys.argv) > 1 else "5"))
CDP_HTTP = "http://127.0.0.1:9222"
OUT_XLSX = Path("/workspace/resume/hh-otkliki-30.xlsx")
OUT_JSON = Path("/tmp/hh-farm30.json")
LOG = Path("/tmp/hh-farm30.log")
CAPTCHA_STOP = Path("/tmp/hh-CAPTCHA-STOP")
APPLIED_IDS = Path("/tmp/hh-applied-ids.txt")


class CaptchaStop(Exception):
    """Hard stop — human must solve captcha. Do not click anything."""

SEARCH_URLS = [
    # Москва + удалёнка, системный аналитик, 1-3 и 3-6
    "https://hh.ru/search/vacancy?text=%D0%A1%D0%B8%D1%81%D1%82%D0%B5%D0%BC%D0%BD%D1%8B%D0%B9+%D0%B0%D0%BD%D0%B0%D0%BB%D0%B8%D1%82%D0%B8%D0%BA&area=1&schedule=remote&experience=between1And3&experience=between3And6&search_field=name&items_on_page=50",
    "https://hh.ru/search/vacancy?text=%D0%A1%D0%B8%D1%81%D1%82%D0%B5%D0%BC%D0%BD%D1%8B%D0%B9+%D0%B0%D0%BD%D0%B0%D0%BB%D0%B8%D1%82%D0%B8%D0%BA&area=1&experience=between1And3&experience=between3And6&search_field=name&items_on_page=50",
    "https://hh.ru/search/vacancy?text=System+Analyst&area=1&schedule=remote&experience=between1And3&experience=between3And6&search_field=name&items_on_page=50",
    "https://hh.ru/search/vacancy?text=%D1%81%D0%B8%D1%81%D1%82%D0%B5%D0%BC%D0%BD%D1%8B%D0%B9+%D0%B0%D0%BD%D0%B0%D0%BB%D0%B8%D1%82%D0%B8%D0%BA&schedule=remote&experience=between1And3&experience=between3And6&search_field=name&items_on_page=50",
]

SKIP_TITLE_RE = re.compile(
    r"стаж[её]р|intern|курьер|1[cс]|тестировщик|qa\b|рекрутер|продаж|sales|hr[- ]|маркетолог",
    re.I,
)


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


class Browser:
    def __init__(self) -> None:
        self.ws = None
        self.mid = 0
        self.connect()

    def connect(self) -> None:
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        tabs = json.load(urllib.request.urlopen(f"{CDP_HTTP}/json/list"))
        page = next(
            (t for t in tabs if t.get("type") == "page" and "hh.ru" in (t.get("url") or "")),
            None,
        )
        if not page:
            page = next(t for t in tabs if t.get("type") == "page")
        self.ws = create_connection(page["webSocketDebuggerUrl"], suppress_origin=True)
        self.mid = 0
        self.call("Runtime.enable")
        self.call("Page.enable")
        self.call("DOM.enable")
        log(f"cdp connected {page.get('url','')[:90]}")

    def call(self, method: str, params: dict | None = None, timeout: float = 20):
        self.mid += 1
        msg = {"id": self.mid, "method": method}
        if params:
            msg["params"] = params
        self.ws.send(json.dumps(msg))
        end = time.time() + timeout
        while time.time() < end:
            raw = self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == self.mid:
                if "error" in data:
                    raise RuntimeError(f"{method}: {data['error']}")
                return data.get("result", {})
        raise TimeoutError(method)

    def js(self, expression: str, timeout: float = 20):
        r = self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
                "userFriendly": True,
            },
            timeout=timeout,
        )
        if "exceptionDetails" in r:
            det = r["exceptionDetails"]
            raise RuntimeError(det.get("text") or det)
        return r.get("result", {}).get("value")

    def wait_ready(self, wait: float = 2.5) -> None:
        time.sleep(wait)
        for _ in range(20):
            try:
                st = self.js("document.readyState")
                if st == "complete":
                    break
            except Exception:
                self.connect()
            time.sleep(0.3)

    def navigate(self, url: str, wait: float = 2.5, *, hard: bool = True) -> None:
        """Open URL. hard=True → cache-bust query so HH не отдаёт stale 'уже откликались'."""
        if hard:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}_r={int(time.time() * 1000)}"
        self.call("Page.navigate", {"url": url})
        self.wait_ready(wait)
        self.raise_if_captcha("after navigate")

    def reload(self, wait: float = 2.0) -> None:
        """Hard reload текущей страницы (bypass cache)."""
        try:
            self.call("Page.reload", {"ignoreCache": True})
        except Exception:
            # fallback
            self.js("location.reload()")
        self.wait_ready(wait)
        self.raise_if_captcha("after reload")

    def dump_captcha_screenshot(self, tag: str = "captcha") -> str:
        """Save PNG for the chat; human replies with text into /tmp/hh-captcha-answer.txt."""
        import base64
        from pathlib import Path as _P
        try:
            r = self.call("Page.captureScreenshot", {"format": "png"})
            path = _P(f"/opt/cursor/artifacts/hh-{tag}-{int(time.time())}.png")
            path.write_bytes(base64.b64decode(r["data"]))
            latest = _P("/opt/cursor/artifacts/hh-captcha-latest.png")
            latest.write_bytes(path.read_bytes())
            log(f"CAPTCHA screenshot: {path}")
            return str(path)
        except Exception as e:
            log(f"CAPTCHA screenshot fail: {e}")
            return ""

    def raise_if_captcha(self, where: str = "") -> None:
        try:
            hit = self.js(
                r"""(() => {
                  const t = (document.body && document.body.innerText) || '';
                  const href = location.href || '';
                  const html = (document.documentElement && document.documentElement.innerHTML) || '';
                  return /SmartCaptcha|captcha\.yandex|checkbox-captcha|я не робот|докажите, что вы человек|Are you a human|hcaptcha|recaptcha/i.test(t+href+html)
                    || !!document.querySelector('[class*="Captcha"], [class*="captcha"], iframe[src*="captcha"], [data-testid*="captcha"]');
                })()"""
            )
        except Exception:
            hit = False
        if hit:
            url = ""
            try:
                url = self.js("location.href") or ""
            except Exception:
                pass
            shot = self.dump_captcha_screenshot("captcha")
            CAPTCHA_STOP.write_text(
                f"{datetime.now(timezone.utc).isoformat()} CAPTCHA at {where} url={url}\nshot={shot}\n"
                f"Ответ напиши в чат ИЛИ в файл /tmp/hh-captcha-answer.txt\n",
                encoding="utf-8",
            )
            log(f"STOP CAPTCHA {where} — скрин {shot}; жду ответ в чат или /tmp/hh-captcha-answer.txt")
            raise CaptchaStop(where)

    def pause(self) -> None:
        delay = random.uniform(5, 15)
        log(f"pause {delay:.1f}s")
        time.sleep(delay)

    def mouse_click_xy(self, x: float, y: float) -> None:
        for typ in ("mousePressed", "mouseReleased"):
            self.call(
                "Input.dispatchMouseEvent",
                {
                    "type": typ,
                    "x": float(x),
                    "y": float(y),
                    "button": "left",
                    "clickCount": 1,
                },
            )
        time.sleep(0.15)

    def click_selector_mouse(self, selector_js: str) -> bool:
        """Click element center via CDP mouse (works for Magritte radios)."""
        pos = self.js(
            f"""(() => {{
          const el = ({selector_js});
          if (!el) return null;
          el.scrollIntoView({{block:'center'}});
          const r = el.getBoundingClientRect();
          if (r.width < 1 || r.height < 1) return null;
          return {{x: r.x + r.width/2, y: r.y + r.height/2}};
        }})()"""
        )
        if not pos:
            return False
        self.mouse_click_xy(pos["x"], pos["y"])
        return True


def letter_for(title: str, company: str, desc: str) -> str:
    stack_bits = []
    low = (desc + " " + title).lower()
    for k, label in [
        ("openapi", "OpenAPI"),
        ("swagger", "Swagger"),
        ("kafka", "Kafka"),
        ("rabbit", "RabbitMQ"),
        ("postgresql", "PostgreSQL"),
        ("sql", "SQL"),
        ("rest", "REST"),
        ("bpmn", "BPMN"),
        ("uml", "UML"),
        ("микросерв", "микросервисы"),
        ("интеграц", "интеграции"),
        ("wms", "WMS"),
        ("лояльн", "лояльность"),
    ]:
        if k in low and label not in stack_bits:
            stack_bits.append(label)
        if len(stack_bits) >= 3:
            break
    stack = ", ".join(stack_bits) if stack_bits else "REST, SQL, ТЗ, интеграции"
    role = title.split("(")[0].strip() or "системного аналитика"
    company = company or "вашей команде"
    text = (
        f"Здравствуйте!\n\n"
        f"Откликаюсь на роль {role} в {company}. "
        f"Сейчас System Analyst Middle+ в Ви6 Сервисес: интеграции с WMS и государственными ИС, "
        f"БТ/ФТ/ТЗ, постановки с критериями приёмки.\n\n"
        f"Близко к вакансии по стеку: {stack}. "
        f"Описываю REST в OpenAPI, сценарии Kafka/RabbitMQ, SQL к PostgreSQL, UML и BPMN. "
        f"Кейс: трудозатраты процесса снизились в два раза по торговой сети.\n\n"
        f"Английский C1. Москва, гибрид или удалённо. Готов обсудить задачи на этой неделе.\n\n"
        f"Telegram: surkov_danila"
    )
    # QA: no orphan junk
    text = text.replace("×", "x").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


HELPER_JS = r"""
window.__hh = {
  byText(t, root=document) {
    const re = typeof t === 'string' ? null : t;
    const s = typeof t === 'string' ? t : null;
    return [...root.querySelectorAll('a,button,[role=button],span,div,label')].find(el => {
      const tx = (el.innerText || el.textContent || '').replace(/\s+/g,' ').trim();
      if (!tx) return false;
      if (s) return tx.includes(s) || tx === s;
      return re.test(tx);
    }) || null;
  },
  click(el) {
    if (!el) return false;
    el.scrollIntoView({block:'center'});
    el.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true, view:window}));
    if (typeof el.click === 'function') el.click();
    return true;
  },
  pageFlags() {
    const body = (document.body && document.body.innerText) || '';
    const href = location.href;
    const hasTask = !!document.querySelector('[data-qa="task-question"], [data-qa="task-body"]')
      || /Answer the questions|Опросник для вакансии|must answer a few questions/i.test(body);
    const uncheckedRadios = [...document.querySelectorAll('input[type=radio]')].filter(r => {
      if (!(r.offsetParent || r.getClientRects().length)) return false;
      const name = r.name;
      if (!name) return !r.checked;
      return !document.querySelector(`input[type=radio][name="${CSS.escape(name)}"]:checked`);
    });
    // unique unchecked groups
    const groups = new Set(uncheckedRadios.map(r => r.name || r.value));
    return {
      href,
      captcha: /captcha|я не робот|докажите, что вы человек|SmartCaptcha/i.test(body+href),
      login: /account\/login|Вход в личный кабинет/i.test(href) || !!document.querySelector('[data-qa="account-login-form"]'),
      hasTask,
      unansweredRadioGroups: groups.size,
      already: /вы откликнулись|уже откликались|отклик отправлен|you applied|already applied|responded/i.test(body)
        || !!document.querySelector('[data-qa="vacancy-response-link-view-topic"]'),
      success: /отклик отправлен|вы откликнулись|отклик на вакансию отправлен|response has been sent|you applied|you responded/i.test(body)
        || !!document.querySelector('[data-qa="vacancy-response-success"]'),
      apps: (() => {
        const badge = document.querySelector('[data-qa="vacancyResponses-badge"]');
        const m1 = badge && (badge.innerText || '').match(/(\d+)/);
        if (m1) return parseInt(m1[1], 10);
        const nav = document.querySelector('[data-qa="vacancyResponses-button-text"], [data-qa="mainmenu_vacancyResponses"]');
        const m2 = nav && (nav.innerText || '').match(/(\d+)/);
        if (m2) return parseInt(m2[1], 10);
        const m3 = body.match(/Applications\s+(\d+)/i) || body.match(/Отклики[^\d]*(\d+)/i);
        return m3 ? parseInt(m3[1], 10) : null;
      })(),
    };
  },
  meta() {
    const title = (document.querySelector('[data-qa="vacancy-title"], h1')?.innerText || '').trim();
    const company = (document.querySelector('[data-qa="vacancy-company-name"], [data-qa="bloko-header-2"] a, .vacancy-company-name')?.innerText || '').trim();
    let salary = '';
    const salEl = document.querySelector('[data-qa="vacancy-salary"], [data-qa="vacancy-salary-compensation"]');
    if (salEl) salary = salEl.innerText.trim();
    if (!salary) {
      const m = (document.body.innerText||'').match(/от\s+[\d\s\u00a0]+(?:до\s+[\d\s\u00a0]+)?\s*(?:₽|руб)/i);
      if (m) salary = m[0];
    }
    const desc = (document.querySelector('[data-qa="vacancy-description"], .vacancy-description, [data-qa="vacancy-branded-description"]')?.innerText || '').slice(0, 2500);
    const schedule = ((document.body.innerText||'').match(/удал[её]нн\w+|гибрид\w+|офис/i)||[''])[0];
    return {title, company, salary, desc, schedule, href: location.href.split('?')[0]};
  },
  findApply() {
    const qa = document.querySelector('[data-qa="vacancy-response-link-top"], [data-qa="vacancy-response-link-bottom"], [data-qa="vacancy-serp__vacancy_response"], a[href*="vacancy_response"]');
    if (qa) return qa;
    return this.byText(/^(Откликнуться|Apply)$/i) || this.byText('Откликнуться');
  },
  listVacancies() {
    const cards = [...document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]')];
    return cards.map(c => {
      const a = c.querySelector('a[data-qa="serp-item__title"], a[href*="/vacancy/"]');
      const href = (a && a.href) ? a.href.split('?')[0] : '';
      const id = (href.match(/vacancy\/(\d+)/)||[])[1] || c.querySelector('[id]')?.id || '';
      const title = (a?.innerText || a?.getAttribute('title') || c.querySelector('[data-qa="serp-item__title-text"]')?.textContent || '').trim();
      const company = (c.querySelector('[data-qa="vacancy-serp__vacancy-employer-text"], [data-qa="vacancy-serp__vacancy-employer"]')?.innerText || '').trim();
      const resp = c.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
      const respText = (resp?.innerText || resp?.textContent || resp?.getAttribute('aria-label') || '').trim();
      const already = /откликнул|responded|already/i.test(respText);
      const salary = (c.querySelector('[data-qa="vacancy-serp__vacancy-compensation"], [data-qa*="compensation"]')?.innerText || '').trim();
      return {id, href, title, company, already, respText, salary};
    }).filter(x => x.href || x.id);
  }
};
'done'
"""


def answer_task_radios(cdp: Browser) -> list[str]:
    """Answer Magritte radio groups: pick Да/Нет by question text; CDP mouse click."""
    plan = cdp.js(
        r"""(() => {
      const groups = {};
      for (const inp of document.querySelectorAll('input[type=radio]')) {
        if (!(inp.offsetParent || inp.getClientRects().length)) continue;
        const name = inp.name || ('anon_'+Math.random());
        const cell = inp.closest('[data-qa="cell"]') || inp.closest('label') || inp.parentElement;
        const optText = ((cell && cell.innerText) || inp.value || '').replace(/\s+/g,' ').trim();
        const body = inp.closest('[data-qa="task-body"]') || inp.closest('form') || document.body;
        const qel = body.querySelector('[data-qa="task-question"]');
        const q = ((qel && qel.innerText) || (body.innerText||'')).replace(/\s+/g,' ').trim().slice(0,200);
        if (!groups[name]) groups[name] = {q, options: []};
        const r = (cell||inp).getBoundingClientRect();
        groups[name].options.push({
          value: inp.value, text: optText, checked: !!inp.checked,
          x: r.x + r.width/2, y: r.y + r.height/2
        });
      }
      return Object.entries(groups).map(([name,g]) => ({name, q:g.q, options:g.options, answered: g.options.some(o=>o.checked)}));
    })()"""
    ) or []
    done = []
    for g in plan:
        if g.get("answered"):
            done.append(f"radio_already:{g['name']}")
            continue
        q = (g.get("q") or "").lower()
        opts = g.get("options") or []
        # prefer Нет for skills we don't have
        want_no = bool(re.search(r"camunda|soap|oracle|\b1[cс]\b|продаж|релокац(?!.*моск)", q))
        # prefer Да for fit / REST / готовность
        want_yes = bool(re.search(r"подходят|условия|rest|готов|удал|гибрид|моск", q)) and not want_no
        target = None
        for o in opts:
            t = (o.get("text") or "").strip().lower()
            if want_no and t in ("нет", "no"):
                target = o
                break
            if want_yes and t in ("да", "yes"):
                target = o
                break
        if not target:
            # default: first Да, else first option
            target = next((o for o in opts if (o.get("text") or "").strip().lower() in ("да", "yes")), None) or (opts[0] if opts else None)
        if not target:
            continue
        cdp.mouse_click_xy(target["x"], target["y"])
        time.sleep(0.25)
        # verify; fallback JS click on input
        ok = cdp.js(
            f"""(() => {{
          const inp = document.querySelector('input[type=radio][name={json.dumps(g["name"])}][value={json.dumps(target.get("value",""))}]');
          if (inp && inp.checked) return true;
          if (inp) {{ inp.click(); return !!inp.checked; }}
          return false;
        }})()"""
        )
        done.append(f"radio:{g['name']}={(target.get('text') or '')[:20]}:{ok}")
    return done


def answer_task_textareas(cdp: Browser) -> list[str]:
    """Fill employer task_* textareas by nearest preceding question text."""
    return (
        cdp.js(
            r"""(() => {
      const setVal = (el, val) => {
        const proto = el.tagName === 'TEXTAREA'
          ? Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')
          : Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
        if (proto && proto.set) proto.set.call(el, val); else el.value = val;
        el.dispatchEvent(new Event('input', {bubbles:true}));
        el.dispatchEvent(new Event('change', {bubbles:true}));
      };
      const nearestQ = (el) => {
        const body = el.closest('[data-qa="task-body"]');
        if (body) {
          const q = body.querySelector('[data-qa="task-question"]');
          if (q) return (q.innerText || '').trim();
        }
        // walk previous siblings / parents for nearest task-question
        let cur = el;
        for (let i = 0; i < 12 && cur; i++) {
          let sib = cur.previousElementSibling;
          while (sib) {
            const q = sib.matches?.('[data-qa="task-question"]') ? sib : sib.querySelector?.('[data-qa="task-question"]');
            if (q) return (q.innerText || '').trim();
            sib = sib.previousElementSibling;
          }
          cur = cur.parentElement;
        }
        return '';
      };
      const out = [];
      const fields = [...document.querySelectorAll('textarea[name^="task_"], input[type="text"][name^="task_"]')].filter(el => {
        return !!(el.offsetParent || el.getClientRects().length);
      });
      for (const el of fields) {
        const q = nearestQ(el).toLowerCase();
        let val = null;
        if (/город|прожива/.test(q)) val = 'Москва';
        else if (/зарплат|сумм|вилк|ожидан|на руки|compensation|salary/.test(q)) val = '250000 на руки (минимум), готов обсуждать вилку под задачи';
        else if (/офис|гибрид|удал|формат работы/.test(q)) val = 'Готов к удалёнке и гибриду. Москва.';
        else if (/трудов|тк|книжк/.test(q)) val = 'Да, опыт отражён; готов предоставить электронную ТК.';
        else if (/rest|openapi|swagger/.test(q)) val = 'Да. Описываю REST в OpenAPI/Swagger: методы, модели, ошибки, примеры; согласование контрактов.';
        else if (/брокер|kafka|rabbit|очеред/.test(q)) val = 'Kafka и RabbitMQ: события, статусы, повтор, разбор расхождений.';
        else if (/camunda|bpm/.test(q)) val = 'Промышленного опыта с Camunda нет. BPMN 2.0 для моделирования процессов использую. Готов изучить движок под задачу.';
        else if (/мобильн|экранн/.test(q)) val = 'Отдельного проектирования экранных форм мобильных приложений как основной роли не было; требования и постановки для UI делал.';
        else if (/финтех|банк|плат[её]ж/.test(q)) val = 'Да: Бест2пей (платёжный контур), интеграции; сейчас Ви6 Сервисес — интеграции с внешними и госИС.';
        else if (/интеграц.*теори|теории/.test(q)) val = 'В теории знаю SOAP/gRPC глубже, чем применял в проде; в работе основной контур — REST и очереди.';
        else if (/подходят|условия/.test(q)) val = 'Да, готов обсудить. Формат удалёнка/гибрид. Ориентир ЗП от 250000 на руки.';
        else val = 'Готов обсудить детали на собеседовании. Стек: REST/OpenAPI, Kafka/RabbitMQ, SQL/PostgreSQL, ТЗ, UML, BPMN.';
        setVal(el, val);
        out.push((q || el.name || 'ta').slice(0,50) + '->' + val.slice(0,40));
      }
      return out;
    })()"""
        )
        or []
    )


def fill_cover_and_questions(cdp: Browser, letter: str) -> dict:
    """Fill cover letter + employer task (radios/text) + submit."""
    actions: list[str] = []
    flags = cdp.js("window.__hh.pageFlags()") or {}
    actions.append(f"flags_task={flags.get('hasTask')},radios={flags.get('unansweredRadioGroups')}")

    # RADIO GROUPS first (user blocker)
    if flags.get("hasTask") or flags.get("unansweredRadioGroups"):
        radio_res = answer_task_radios(cdp)
        actions.append("radios=" + ",".join(radio_res) if radio_res else "radios=none")
        ta_res = answer_task_textareas(cdp)
        actions.append("task_ta=" + str(len(ta_res)))
        time.sleep(0.4)

    # cover letter
    cdp.js(
        """(() => {
      const t = window.__hh.byText('Сопроводительное') || window.__hh.byText('Добавить сопроводительное')
        || document.querySelector('[data-qa="textarea-letter"], [data-qa*="cover"], [data-qa*="letter"]');
      if (t && t.tagName !== 'TEXTAREA') window.__hh.click(t);
      return true;
    })()"""
    )
    time.sleep(0.3)
    letter_js = json.dumps(letter)
    set_res = cdp.js(
        f"""(() => {{
      const letter = {letter_js};
      let ta = document.querySelector('textarea[data-qa="vacancy-response-popup-form-letter-input"], textarea[data-qa="textarea-letter"], textarea[name="letter"], textarea[data-qa*="letter"]');
      if (!ta) {{
        const all = [...document.querySelectorAll('textarea')].filter(t => {{
          if ((t.name||'').startsWith('task_')) return false;
          return t.offsetParent || t.getClientRects().length;
        }});
        ta = all.sort((a,b) => (b.clientHeight||0)-(a.clientHeight||0))[0];
      }}
      if (!ta) return {{ok:false, reason:'no_textarea'}};
      const proto = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');
      if (proto && proto.set) proto.set.call(ta, letter); else ta.value = letter;
      ta.dispatchEvent(new Event('input', {{bubbles:true}}));
      ta.dispatchEvent(new Event('change', {{bubbles:true}}));
      const v = ta.value || '';
      const junk = /(ChatGPT|Cursor|сгенерир|watermark|×)/i.test(v) || /^\\s*3\\s*$/m.test(v);
      return {{ok:true, len:v.length, junk, head:v.slice(0,50)}};
    }})()"""
    )
    actions.append(f"letter={set_res}")

    # re-check radios still unanswered — click again with mouse
    flags = cdp.js("window.__hh.pageFlags()") or {}
    if flags.get("unansweredRadioGroups"):
        actions.append("retry_radios")
        actions.append("radios2=" + ",".join(answer_task_radios(cdp)))

    # submit only if no unanswered radios
    flags = cdp.js("window.__hh.pageFlags()") or {}
    if flags.get("unansweredRadioGroups"):
        actions.append(f"BLOCK_radios={flags.get('unansweredRadioGroups')}")
        return {"actions": actions, "submitted": None, "blocked": True}

    submitted = cdp.js(
        r"""(() => {
      const order = [
        '[data-qa="vacancy-response-submit-popup"]',
        '[data-qa="vacancy-response-submit"]',
        '[data-qa*="response-submit"]',
        'button[type="submit"]'
      ];
      for (const s of order) {
        const el = document.querySelector(s);
        if (el) { window.__hh.click(el); return 'css:'+s; }
      }
      // НЕ кликать снова «Откликнуться»/Respond — только отправка формы
      const b = window.__hh.byText(/^(Отправить|Продолжить|Готово|Далее|Submit|Send)$/i);
      if (b) { window.__hh.click(b); return 'text:'+(b.innerText||'').slice(0,40); }
      return null;
    })()"""
    )
    actions.append(f"submit={submitted}")
    return {"actions": actions, "submitted": submitted, "blocked": False}



def solve_captcha_with_answer(cdp: "Browser", answer: str) -> dict:
    """Fill HH captcha modal and mouse-click its Отправить."""
    answer = (answer or "").strip()
    if not answer:
        return {"ok": False, "reason": "empty"}
    ans_js = json.dumps(answer)
    filled = cdp.js(
        f"""(() => {{
      const answer = {ans_js};
      const el = document.querySelector('[data-qa="account-captcha-input"], input[name="captchaText"]');
      if (!el) return {{ok:false, reason:'no_input'}};
      el.focus();
      const proto = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
      if (proto && proto.set) proto.set.call(el, answer); else el.value = answer;
      el.dispatchEvent(new Event('input', {{bubbles:true}}));
      el.dispatchEvent(new Event('change', {{bubbles:true}}));
      const buttons = [...document.querySelectorAll('button,[role=button]')];
      const b = buttons.find(el => {{
        const t = (el.innerText || '').replace(/\s+/g, ' ').trim();
        const r = el.getBoundingClientRect();
        return t === 'Отправить' && r.width > 50 && r.height > 20 && r.y > 200;
      }});
      if (!b) return {{ok:false, reason:'no_submit', value: el.value}};
      const r = b.getBoundingClientRect();
      return {{ok:true, value: el.value, x: r.x + r.width/2, y: r.y + r.height/2}};
    }})()"""
    ) or {"ok": False}
    if not filled.get("ok"):
        return filled
    cdp.mouse_click_xy(filled["x"], filled["y"])
    time.sleep(1.5)
    return {"ok": True, "value": filled.get("value"), "clicked": True}


def vacancy_id(url: str) -> str:
    m = re.search(r"/vacancy/(\d+)", url or "")
    return m.group(1) if m else ""


def load_applied_ids() -> set[str]:
    ids: set[str] = set()
    if APPLIED_IDS.exists():
        ids |= {x.strip() for x in APPLIED_IDS.read_text(encoding="utf-8").splitlines() if x.strip()}
    for path in (Path("/tmp/hh-farm30.json"), Path("/tmp/hh-farm30-before-radiofix.json")):
        if not path.exists():
            continue
        try:
            for r in json.loads(path.read_text(encoding="utf-8")):
                if r.get("status") in ("ok", "skip") or "уже" in (r.get("note") or ""):
                    vid = vacancy_id(r.get("url") or "")
                    if vid:
                        ids.add(vid)
        except Exception:
            pass
    return ids


def mark_applied(vid: str) -> None:
    if not vid:
        return
    with APPLIED_IDS.open("a", encoding="utf-8") as f:
        f.write(vid + "\n")


def is_already_on_page(cdp: Browser) -> bool:
    return bool(
        cdp.js(
            r"""(() => {
      const t = (document.body.innerText || '');
      if (/you applied|already applied|уже отклик|вы откликнулись|откликнулись на эту/i.test(t)) return true;
      if (document.querySelector('[data-qa="vacancy-response-link-view-topic"]')) return true;
      const apply = window.__hh.findApply();
      if (!apply) {
        // нет Respond, но есть Chat / откликнулись — считаем applied
        if (/chat|написать|откликн/i.test(t) && /you applied|откликнул/i.test(t)) return true;
      }
      const tx = ((apply && (apply.innerText || apply.textContent)) || '').toLowerCase();
      if (/откликнул|already|applied|responded/.test(tx)) return true;
      // кнопка disabled / aria
      if (apply && (apply.getAttribute('aria-disabled') === 'true' || apply.className.includes('disabled'))) return true;
      return false;
    })()"""
        )
    )


def apply_one(cdp: Browser, url: str, applied_ids: set[str]) -> dict:
    row = {
        "url": url.split("?")[0],
        "title": "",
        "company": "",
        "salary": "",
        "schedule": "",
        "status": "",
        "actions": "",
        "letter": "",
        "note": "",
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    vid = vacancy_id(url)
    if vid and vid in applied_ids:
        row["status"] = "skip"
        row["note"] = "уже в applied-ids"
        return row

    clean = url.split("?")[0]
    cdp.navigate(clean, wait=2.2, hard=True)
    # всегда hard reload — HH часто отдаёт stale кнопку «Откликнуться»
    cdp.reload(wait=1.8)
    cdp.js(HELPER_JS)
    cdp.raise_if_captcha("vacancy open")

    flags = cdp.js("window.__hh.pageFlags()") or {}
    if flags.get("login"):
        row["status"] = "login"
        row["note"] = "нужен логин"
        return row

    meta = cdp.js("window.__hh.meta()") or {}
    row.update(
        {
            "title": meta.get("title") or "",
            "company": meta.get("company") or "",
            "salary": meta.get("salary") or "",
            "schedule": meta.get("schedule") or "",
            "url": (meta.get("href") or clean).split("?")[0],
        }
    )
    if SKIP_TITLE_RE.search(row["title"] or ""):
        row["status"] = "skip"
        row["note"] = "нецелевая роль"
        return row

    if is_already_on_page(cdp):
        row["status"] = "skip"
        row["note"] = "уже откликался (после reload)"
        if vid:
            applied_ids.add(vid)
            mark_applied(vid)
        return row

    letter = letter_for(row["title"], row["company"], meta.get("desc") or "")
    row["letter"] = letter

    # один клик — без повторного findApply.click
    clicked = cdp.js(
        """(() => {
      const el = window.__hh.findApply();
      if (!el) return null;
      const tx = ((el.innerText || el.textContent) || '').toLowerCase();
      if (/откликнул|already|applied|responded/.test(tx)) return 'ALREADY';
      if (el.dataset && el.dataset.hhClicked === '1') return 'DUP';
      el.dataset.hhClicked = '1';
      window.__hh.click(el);
      return (el.getAttribute('data-qa') || el.tagName || 'btn');
    })()"""
    )
    if clicked == "ALREADY" or clicked == "DUP":
        row["status"] = "skip"
        row["note"] = "уже откликался (кнопка)"
        if vid:
            applied_ids.add(vid)
            mark_applied(vid)
        return row
    if not clicked:
        row["status"] = "need-visual"
        row["note"] = "нет кнопки отклика"
        return row
    row["actions"] = f"click:{clicked}"
    cdp.raise_if_captcha("after apply click")
    cdp.pause()

    cdp.js(HELPER_JS)
    cdp.raise_if_captcha("before form fill")
    # если после клика сразу «уже откликались» — не долбим форму
    if is_already_on_page(cdp) and not (cdp.js("window.__hh.pageFlags()") or {}).get("hasTask"):
        row["status"] = "ok"
        row["note"] = "отклик (уже подтверждён после клика)"
        if vid:
            applied_ids.add(vid)
            mark_applied(vid)
        return row

    apps_before = (cdp.js("window.__hh.pageFlags()") or {}).get("apps")
    fill = fill_cover_and_questions(cdp, letter)
    row["actions"] += ";" + ";".join(fill["actions"])
    cdp.raise_if_captcha("after form fill/submit")
    if fill.get("blocked"):
        row["status"] = "fail"
        row["note"] = "не отвечены radio-вопросы"
        return row
    time.sleep(1.8)
    cdp.js(HELPER_JS)
    flags2 = cdp.js("window.__hh.pageFlags()") or {}
    cdp.raise_if_captcha("after submit wait")

    if flags2.get("hasTask") and not flags2.get("success") and not flags2.get("already"):
        row["actions"] += ";pass2_task"
        fill2 = fill_cover_and_questions(cdp, letter)
        row["actions"] += ";" + ";".join(fill2["actions"])
        cdp.raise_if_captcha("after pass2")
        time.sleep(1.5)
        flags2 = cdp.js("window.__hh.pageFlags()") or {}

    apps_after = flags2.get("apps")
    apps_up = (
        apps_before is not None
        and apps_after is not None
        and apps_after > apps_before
    )

    if flags2.get("success") or flags2.get("already") or apps_up or is_already_on_page(cdp):
        row["status"] = "ok"
        bits = ["отклик"]
        if "letter=" in row["actions"]:
            bits.append("письмо")
        if "radios=" in row["actions"] or "task_ta=" in row["actions"]:
            bits.append("опрос")
        if apps_up:
            bits.append(f"apps{apps_before}->{apps_after}")
        row["note"] = "+".join(bits)
        if vid:
            applied_ids.add(vid)
            mark_applied(vid)
    elif flags2.get("unansweredRadioGroups"):
        row["status"] = "fail"
        row["note"] = f"остались radio групп: {flags2.get('unansweredRadioGroups')}"
    elif flags2.get("hasTask"):
        row["status"] = "fail"
        row["note"] = "застрял на опроснике"
    else:
        row["status"] = "fail"
        row["note"] = "нет подтверждения отклика"
    return row


def collect_links(cdp: Browser, seen: set[str], applied_ids: set[str]) -> list[str]:
    links: list[str] = []
    for su in SEARCH_URLS:
        if len(links) > 120:
            break
        cdp.navigate(su, wait=3, hard=True)
        cdp.reload(wait=1.5)
        cdp.js(HELPER_JS)
        cdp.raise_if_captcha("search")
        flags = cdp.js("window.__hh.pageFlags()") or {}
        if flags.get("login"):
            log("STOP login wall on search")
            return links
        batch = cdp.js("window.__hh.listVacancies()") or []
        log(f"search got {len(batch)} cards from {su[:60]}")
        for v in batch:
            href = (v.get("href") or (f"https://hh.ru/vacancy/{v['id']}" if v.get("id") else "")).split("?")[0]
            vid = vacancy_id(href) or str(v.get("id") or "")
            if not href or href in seen:
                continue
            if vid and vid in applied_ids:
                continue
            if v.get("already"):
                if vid:
                    applied_ids.add(vid)
                    mark_applied(vid)
                continue
            title = v.get("title") or ""
            if title and SKIP_TITLE_RE.search(title):
                continue
            links.append(href)
            seen.add(href)
        cdp.pause()
    return links


def write_xlsx(rows: list[dict]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "otkliki"
    headers = [
        "status",
        "company",
        "title",
        "salary",
        "schedule",
        "url",
        "actions_note",
        "what_done",
        "letter",
        "ts_utc",
    ]
    ws.append(headers)
    for r in rows:
        what = r.get("note") or r.get("status")
        if r.get("status") == "ok":
            if "тест" in (r.get("note") or "") or "answers=" in (r.get("actions") or ""):
                what = "отклик + сопровод + вопросы/тест"
            elif "letter" in (r.get("actions") or ""):
                what = "отклик + сопроводительное"
            else:
                what = "простой отклик (клик)"
        ws.append(
            [
                r.get("status"),
                r.get("company"),
                r.get("title"),
                r.get("salary"),
                r.get("schedule"),
                r.get("url"),
                r.get("note"),
                what,
                r.get("letter"),
                r.get("ts"),
            ]
        )
    wb.save(OUT_XLSX)
    log(f"xlsx {OUT_XLSX}")


def main() -> None:
    if CAPTCHA_STOP.exists():
        log(f"STOP: найден {CAPTCHA_STOP} — сначала сними капчу руками и удали файл")
        return
    LOG.write_text("", encoding="utf-8")
    cdp = Browser()
    cdp.js(HELPER_JS)
    cdp.raise_if_captcha("start")
    flags = cdp.js("window.__hh.pageFlags()") or {}
    if flags.get("login"):
        log("STOP: не залогинен")
        return
    log(f"start farm N={N} (reload+no-double-click+captcha-hard-stop)")

    applied_ids = load_applied_ids()
    log(f"known applied ids: {len(applied_ids)}")
    seen: set[str] = set()
    for vid in applied_ids:
        seen.add(f"https://hh.ru/vacancy/{vid}")

    try:
        links = collect_links(cdp, seen, applied_ids)
    except CaptchaStop:
        write_xlsx([])
        log("STOPPED on captcha during search")
        return

    log(f"queue {len(links)} urls")
    rows: list[dict] = []
    ok = 0
    miss_btn = 0
    i = 0
    while ok < N and i < len(links):
        url = links[i]
        i += 1
        log(f"try {i}/{len(links)} ok={ok}/{N} {url}")
        try:
            row = apply_one(cdp, url, applied_ids)
        except CaptchaStop:
            row = {
                "url": url.split("?")[0],
                "title": "",
                "company": "",
                "salary": "",
                "schedule": "",
                "status": "captcha",
                "actions": "",
                "letter": "",
                "note": "STOP — капча, жду человека",
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            rows.append(row)
            OUT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            write_xlsx(rows)
            log("STOPPED on captcha — no more clicks")
            return
        except Exception as e:
            log(f"ERR {e}")
            traceback.print_exc()
            try:
                cdp.connect()
                cdp.js(HELPER_JS)
            except Exception:
                pass
            row = {
                "url": url,
                "title": "",
                "company": "",
                "salary": "",
                "schedule": "",
                "status": "fail",
                "actions": "",
                "letter": "",
                "note": str(e)[:200],
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        rows.append(row)
        OUT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"-> {row['status']} | {row.get('company','')[:40]} | {row.get('note','')}")
        if row["status"] == "ok":
            ok += 1
            miss_btn = 0
            cdp.pause()
        elif row["status"] == "need-visual":
            miss_btn += 1
            if miss_btn >= 3:
                log("STOP: 3x нет кнопки отклика")
                break
        elif row["status"] == "login":
            log("STOP: login")
            break
        else:
            time.sleep(random.uniform(3, 7))

        if ok < N and i >= len(links) - 2:
            try:
                more = collect_links(cdp, seen, applied_ids)
            except CaptchaStop:
                write_xlsx(rows)
                log("STOPPED on captcha during replenish")
                return
            for u in more:
                if u not in links:
                    links.append(u)
            log(f"replenished queue={len(links)}")

    write_xlsx(rows)
    log(f"DONE ok={ok}/{N} total_rows={len(rows)} xlsx={OUT_XLSX}")


if __name__ == "__main__":
    main()
