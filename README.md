# Резюме Данилы Суркова

Одностраничное резюме системного аналитика Middle+ под отклики рекрутеров (GetMatch, HH, LinkedIn).

Факты, даты, компании и результаты взяты из исходной выгрузки GetMatch. Переписаны заголовок, порядок блоков, формулировки и плотность — без выдуманного опыта.

## Файлы

| Файл | Зачем |
|------|--------|
| `resume/Danila-Surkov-System-Analyst-RU.pdf` | Основной файл на отклик в РФ |
| `resume/Danila-Surkov-System-Analyst-EN.pdf` | Для англоязычных команд и GetMatch EN |
| `resume/danila-surkov-ru.html` / `danila-surkov-en.html` | Исходники вёрстки |
| `resume/TEXTS.md` | Заголовок, «обо мне», сопроводительное, сообщение рекрутеру |
| `scripts/render_resume.sh` | Пересборка PDF |

## Сборка PDF

```bash
bash scripts/render_resume.sh
```

Нужен Google Chrome в `PATH` или `/usr/local/bin/google-chrome`.
