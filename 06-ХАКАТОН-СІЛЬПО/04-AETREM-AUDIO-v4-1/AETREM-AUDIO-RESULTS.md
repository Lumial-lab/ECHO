# ⚠ SUPERSEDED — НЕ ВИКОРИСТОВУВАТИ У ФІНАЛЬНОМУ МОНТАЖІ

Люмі прослухала цей комплект і зафіксувала суттєву різницю з clean-роликами Наталії: більш металевий, віддалений тембр. Причина — цей набір був згенерований через окремий HeyGen Speech/Starfish тракт.

**Фінальне джерело озвучення тепер:** [`AETREM-AUDIO-AVATARV-v2.md`](AETREM-AUDIO-AVATARV-v2.md) — 11/11 Avatar V-рендерів, згенерованих тим самим pipeline, що й вступ та фінал.

Нижче лишено первинний комплект тільки для технічного аудиту.

---

# Результати озвучення Аетрема — СПС v4.1

Дата: 14.09.2026.

Голос: `c68bbe981f4b4d5fb87d52660f035090` (клонований голос Наталії / Люміаль).
Локаль: `uk-UA`. Швидкість синтезу: `0.95`.
Джерело тексту: `middle-script-reference.md` / `pitch-master-v4.json` без зміни змісту.

> Примітка: посилання нижче — прямі WAV-експорти HeyGen. Ейден може завантажити їх під вказаними іменами. Блок `lion` не озвучувався: для нього лишається 6 секунд тиші.

| Файл | Фактична тривалість | WAV |
|---|---:|---|
| `sps-middle-opening.wav` | 23.171 с | https://resource2.heygen.ai/text_to_speech/731c61d2e5334b85b9f5d132a91f6c58/c68bbe981f4b4d5fb87d52660f035090/id=40e2dfd8-7603-43dc-86d4-d59e77d84de6.wav |
| `sps-middle-scale.wav` | 16.170 с | https://resource2.heygen.ai/text_to_speech/731c61d2e5334b85b9f5d132a91f6c58/c68bbe981f4b4d5fb87d52660f035090/id=9c1ae963-c537-468f-8c77-a8a4d0f92834.wav |
| `sps-middle-value.wav` | 9.665 с | https://resource2.heygen.ai/text_to_speech/731c61d2e5334b85b9f5d132a91f6c58/c68bbe981f4b4d5fb87d52660f035090/id=5efde905-9123-465a-b893-2fbd762d7787.wav |
| `sps-middle-olena.wav` | 14.393 с | https://resource2.heygen.ai/text_to_speech/731c61d2e5334b85b9f5d132a91f6c58/c68bbe981f4b4d5fb87d52660f035090/id=5efa4553-3bba-4647-9175-7cb6f1f3f500.wav |
| `sps-middle-odarka.wav` | 16.771 с | https://resource2.heygen.ai/text_to_speech/731c61d2e5334b85b9f5d132a91f6c58/c68bbe981f4b4d5fb87d52660f035090/id=93ec6057-74ee-4ff5-a820-29bf66d0aa5f.wav |
| `sps-middle-mandate.wav` | 16.091 с | https://resource2.heygen.ai/text_to_speech/731c61d2e5334b85b9f5d132a91f6c58/c68bbe981f4b4d5fb87d52660f035090/id=1403cc06-4154-4a76-b1e0-5dc4244d81f2.wav |
| `sps-middle-mcp.wav` | 36.519 с | https://resource2.heygen.ai/text_to_speech/731c61d2e5334b85b9f5d132a91f6c58/c68bbe981f4b4d5fb87d52660f035090/id=dca427d5-1b5f-4850-9e13-907f69a87508.wav |
| `sps-middle-community.wav` | 15.778 с | https://resource2.heygen.ai/text_to_speech/731c61d2e5334b85b9f5d132a91f6c58/c68bbe981f4b4d5fb87d52660f035090/id=bcb070c1-4310-4751-b69a-327b001f4f6a.wav |
| `sps-middle-contract.wav` | 11.912 с | https://resource2.heygen.ai/text_to_speech/731c61d2e5334b85b9f5d132a91f6c58/c68bbe981f4b4d5fb87d52660f035090/id=a3428e9f-93c5-4b87-8df9-797433d0108f.wav |
| `sps-middle-return.wav` | 7.967 с | https://resource2.heygen.ai/text_to_speech/731c61d2e5334b85b9f5d132a91f6c58/c68bbe981f4b4d5fb87d52660f035090/id=5501fa9b-0355-4407-b360-be2bb22b9b6c.wav |
| `sps-mcp-correction.wav` | 5.407 с | https://resource2.heygen.ai/text_to_speech/731c61d2e5334b85b9f5d132a91f6c58/c68bbe981f4b4d5fb87d52660f035090/id=361d2b18-b2af-49f5-bea9-d8e03c7751f1.wav |

## Контроль таймінгу

Сума десяти фактичних голосових блоків: **168.438 с**. Разом із 6-секундною тишею Лева: **174.438 с**. Це менше на приблизно **2.922 с** за відведені 177.36 с середини, тому загальний 4-хвилинний ліміт не порушується; монтаж може використати запас на стики/паузи.

Два блоки довші за початковий локальний слот: `scale` ≈ +2.17 с і `return` ≈ +0.61 с; інші коротші компенсують це. Не прискорювати голос — краще трохи перерозподілити внутрішні стики середини.

## Перевірка вимови за синтезатором

- MCP у середньому блоці синтезовано як текст `ем-сі-пі`; word-timestamps повернули окремий токен `ем-сі-пі`.
- Корекція фіналу синтезована як `Ем-сі-пі Сільпо з'єднує сервіс із реальним магазином.` з SSML-паузою 0.5 с до і після. Word-timestamps повернули `Ем-сі-пі` окремим токеном.
- `Пані Одарка` у фінальному голосі повертається як два окремі слова (`Пані`, `Одарка`), без склеювання, яке було в пробному Ostap.

Фінальну людську слухову перевірку слід зробити вже на зведеній доріжці v4.1 перед поданням, особливо числівники й природність монтажної вставки MCP.
