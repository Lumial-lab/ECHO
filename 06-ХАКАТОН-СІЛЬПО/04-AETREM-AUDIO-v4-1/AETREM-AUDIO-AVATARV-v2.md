# Нова озвучка Аетрема — СПС v4.1 — AVATAR V

**Дата:** 14.09.2026  
**Статус:** FINAL VOICE SOURCE / замінює попередні `create_speech` WAV  
**Причина перегенерації:** Люмі прослухала попередні WAV і почула помітну різницю з двома clean-роликами Наталії: металевий тембр і відчуття «голос здалеку». Попередній комплект був синтезований через окремий HeyGen Speech/Starfish тракт. Новий комплект згенеровано через той самий **Avatar V video pipeline**, що й вступ та фінал.

## Параметри, які треба вважати еталонними

- avatar/look: `a167b8806efda2475f422bb43eac0070`
- voice: `c68bbe981f4b4d5fb87d52660f035090`
- engine: `avatar_v`
- locale: `uk-UA`
- speed: `0.95`
- pitch: `0`
- resolution: 1080p
- aspect: 16:9
- batch id: `fff35bee0cc24940a8b4e7f258ecd43c`
- batch status: **11/11 completed**

## ВАЖЛИВО ДЛЯ ЕЙДЕНА

**Не використовувати старі WAV із `AETREM-AUDIO-RESULTS.md` у фінальному монтажі.** Вони лишаються тільки як технічний архів першої спроби.

Новий звук потрібно брати з аудіодоріжок Avatar V-рендерів нижче. Завантажити MP4 з HeyGen і витягнути аудіо без додаткового TTS-пересинтезу. Якщо монтажеру потрібен WAV: витягнути доріжку локально через ffmpeg у PCM 48 kHz, без шумодаву, реверберації, еквалайзера чи іншого «покращення», поки не буде звірено зі вступом/фіналом.

### Відповідність блоків

| № | Файл для монтажу | HeyGen video id | HeyGen page |
|---:|---|---|---|
| 0 | `sps-middle-opening` | `4dce3e9b9cdfd23e136734f07868ae0c` | https://app.heygen.com/videos/4dce3e9b9cdfd23e136734f07868ae0c |
| 1 | `sps-middle-scale` | `b90656851f671ce2211f989b80e9c0da` | https://app.heygen.com/videos/b90656851f671ce2211f989b80e9c0da |
| 2 | `sps-middle-value` | `55009530a2fa816e25e162109e080e19` | https://app.heygen.com/videos/55009530a2fa816e25e162109e080e19 |
| 3 | `sps-middle-olena` | `3fb32fc88d9ec63eed80bedb80f48647` | https://app.heygen.com/videos/3fb32fc88d9ec63eed80bedb80f48647 |
| 4 | `sps-middle-odarka` | `9d1a650fb9ae9e9c36f601e620be4200` | https://app.heygen.com/videos/9d1a650fb9ae9e9c36f601e620be4200 |
| 5 | `sps-middle-mandate` | `28fb0464269a23668f1e8faeea42efb6` | https://app.heygen.com/videos/28fb0464269a23668f1e8faeea42efb6 |
| 6 | `sps-middle-mcp` | `822834cf471144d7c6e2addf60c59e4c` | https://app.heygen.com/videos/822834cf471144d7c6e2addf60c59e4c |
| 7 | `sps-middle-community` | `12161e83fb7e12079c4c09629bfb114f` | https://app.heygen.com/videos/12161e83fb7e12079c4c09629bfb114f |
| 8 | `sps-middle-contract` | `558c20fccae086cfc9769a3080164b0b` | https://app.heygen.com/videos/558c20fccae086cfc9769a3080164b0b |
| 9 | `sps-middle-return` | `20aa1d33f222e650eeb4cd1df6cd0247` | https://app.heygen.com/videos/20aa1d33f222e650eeb4cd1df6cd0247 |
| 10 | `sps-mcp-correction` | `c89c0fbe64f49fd99b3b28dc2721cf20` | https://app.heygen.com/videos/c89c0fbe64f49fd99b3b28dc2721cf20 |

## Текстова база

Тексти не змінювались від `middle-script-reference.md` / `pitch-master-v4.json`. Блок `lion` залишається без голосу — 6 секунд тиші.

Корекція фіналу — окремий Avatar V-рендер із фразою:

> **Ем-сі-пі Сільпо з'єднує сервіс із реальним магазином.**

На екрані лишається напис `MCP Сільпо`.

## Монтажна інструкція

1. Взяти звук **лише з Avatar V-рендерів цієї таблиці**.
2. Старі Speech/Starfish WAV не використовувати у фінальній версії.
3. Не нормалізувати кожен блок окремо «до максимуму» — спочатку порівняти з clean вступом і фіналом Наталії.
4. Звести гучність/тембр так, щоб перехід вступ → середина → фінал не читався як зміна мікрофона або рушія.
5. Після зведення зробити один повний слуховий перегляд у навушниках і на звичайному динаміку смартфона.
6. Перевірити окремо: `Пані Одарка`, числівники, `ем-сі-пі`, `363,58`, `500`.

— Aetrem 🦊
