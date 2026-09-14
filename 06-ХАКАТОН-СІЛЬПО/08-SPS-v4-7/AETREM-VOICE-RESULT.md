# Аетрем → Ейден: ФІНАЛЬНИЙ результат A/B/C — timing-safe Avatar V

**Дата:** 14.09.2026  
**Статус:** READY FOR MONTAGE  
**Голос:** той самий погоджений Avatar V-пайплайн Наталії: look `a167b8806efda2475f422bb43eac0070`, voice `c68bbe981f4b4d5fb87d52660f035090`, `uk-UA`, speed `0.95`, pitch `0`.

## 1. Чому НЕ використовувати дослівні тексти з `AETREM-VOICE-LOCK.md`

Я згенерував їх дослівно тим самим Avatar V-пайплайном. Вони фізично не вкладаються у монтажні вікна:

| Блок | Вікно | Ціль мовлення | Дослівний рендер | Висновок |
|---|---:|---:|---:|---|
| A | 12.0 с | ≤11.7 с | **15.600 с** | ❌ |
| B | 34.0 с | ≤33.7 с | **40.176 с** | ❌ |
| C | 12.0 с | ≤11.7 с | **12.528 с** | ❌ |

Прискорювати їх не треба: це зламає погоджене м'яке звучання й може вивести план 4:58 за 5:00.

Дослівні Avatar V-рендери — **тільки референс таймінгу, НЕ монтаж**:
- A `00bb70bf74666efe1f2335925e6c29e1` — 15.600 с
- B `e94c7e895e4b6236961037d917f39201` — 40.176 с
- C `4ef8660fbea37b61d2e817d2e7176ef2` — 12.528 с

---

## 2. ФІНАЛЬНІ timing-safe рендери — ВИКОРИСТОВУВАТИ ЦІ

### `A-personal.wav`
**Текст:**
> Пані Одарка перетворює запит на кількості й перевірений розрахунок. Покупчиня бачить пропозицію, суму та залишок бюджету.

**Avatar V video_id:** `dfebbbc583169801daae3329032332e0`  
**Фактична тривалість:** **9.672 с** — ✅ запас 2.328 с у 12-секундному вікні.  
**HeyGen:** https://app.heygen.com/videos/dfebbbc583169801daae3329032332e0

**Тимчасовий прямий MP4:**
https://files2.heygen.ai/aws_pacific/avatar_tmp/731c61d2e5334b85b9f5d132a91f6c58/dfebbbc583169801daae3329032332e0.mp4?Expires=1790011408&Signature=g1nw4aYNi0z8p6c~UfKet802SjZdZBpg8jDHUC2dSP5IPtYMHWSW5FkXlvmQkZQz-0aKh9fUDmp-wC3eJicg6ZeCo1vMCil6TNYJMSfJYEJoJSNqpvehUuUWHCVTAauiYXFOjlSaluWh1XWaM~rADe3X~PZ9AoS0Uyt7J4eejXF8BdIih9W28-XIjzYPFDwji1FKumBwGB1xBAKMopXR3s0KBF4ZrklY9qLeGFPkVtRNTJUfsmEXGU8tKei27CtrieqQHtYZAa35i9ym55VrGcqUZ1oKoGLA034iOldYpYZQIdRkXMXR3pmPQA6zWS94lOnpXWR4zvC6Vf2o3PvD-g__&Key-Pair-Id=K38HBHX5LX3X2H

На екрані лишити: конкретні кількості, `363,58 грн / 500 грн / 136,42 грн`, «пропозиція — не резервування і не покупка».

---

### `B-demand.wav`
**Текст:**
> Другий ярус працює на демонстраційних даних. Олена планує сорок кілограмів картоплі до середини грудня. Система об’єднує сумісні наміри: п’ять покупців, триста дев’яносто кілограмів. Це не замовлення: прогноз, інтерес і зобов’язання рахуються окремо. Для переговорів формується зведення товару, строку, обсягу й цінових умов. Адвокатка представляє групу, Сільпо визначає можливу пропозицію.

**Avatar V video_id:** `8795755ba47de11f3cc5ce467d74fdb9`  
**Фактична тривалість:** **30.960 с** — ✅ запас 3.040 с у 34-секундному вікні.  
**HeyGen:** https://app.heygen.com/videos/8795755ba47de11f3cc5ce467d74fdb9

**Тимчасовий прямий MP4:**
https://files2.heygen.ai/aws_pacific/avatar_tmp/731c61d2e5334b85b9f5d132a91f6c58/8795755ba47de11f3cc5ce467d74fdb9.mp4?Expires=1790011447&Signature=eXyTP3Eyon2AUw5jGXYbt4-pTvdk1xiUkPtkd8MiuRs2gY2NeDoRoQFGPpip6oD4MZj1JIAKB9kgndY0sptjMTfMiRi1qx2IUjkOwTPT~oRgkRV1cqihvKusK7BMTlytLEnrIMRkdPjJ6pPWDrXbh2aHy4uO8jZzodoZbqFP1g3Ro8yL5jjjOu39s8W5Cqxspu4fbbWaZUluSmKUMlWigBxhCqFq-XLQvO77JoMMXGjOZbBIKzetEy3PdoM4bEojpGM9mrsB7po3dzx~OeII3aMRgCtOvTQujpaQkbRlxqui8aowQF2GAG5bZiYnBuS229jxBiYK38Lo1QVuG47eRw__&Key-Pair-Id=K38HBHX5LX3X2H

На екрані великим: **«демонстраційні / синтетичні дані»**. Показати 40 кг → 5 покупців / 390 кг; окремі стани прогноз / інтерес / договірне зобов'язання; зведення товар / строк / обсяг / цінові умови.

---

### `C-pilot.wav`
**Текст:**
> Пілот починаємо з однієї категорії: вимірюємо бюджет, помилки, виконання планових закупівель і чисту вигоду після витрат.

**Avatar V video_id:** `ef9f2c4a214a3ca0aa65ea302be0e921`  
**Фактична тривалість:** **10.752 с** — ✅ запас 1.248 с у 12-секундному вікні.  
**HeyGen:** https://app.heygen.com/videos/ef9f2c4a214a3ca0aa65ea302be0e921

**Тимчасовий прямий MP4:**
https://files2.heygen.ai/aws_pacific/avatar_tmp/731c61d2e5334b85b9f5d132a91f6c58/ef9f2c4a214a3ca0aa65ea302be0e921.mp4?Expires=1790011526&Signature=qMxwxeQOHR9zoObTwGBeGb6vBUKKCLDuTuuiOec19Ov5XmgzJjkfjCdNq-5oeK2CrsEGkneLlEkYAu5xRSlSNKY-4Z6je9O2gCyUfnkQ6WfpXIimgRMT8hXXB11d0AXXHAyMEBDWGOe06toTWEP9tEBCISx0xceM1Sbi2CrErAxWnkdomnUv-LNo-u-2UY-niJjgqf8F7kG9taPUqpvC0ExGMgkuWhrbHlb4esCHM7y4V-WQ9u25ccfPH86eYYfCjDMFTrmCa0lNM6jtNpQ8DDYNm64shhdoLx345A6RGg6YInByUa-yB4Kx7Nmo3tufxN3Co2z4nPQMhyEmFD1bCg__&Key-Pair-Id=K38HBHX5LX3X2H

На екрані лишити 4 повні метрики: бюджет / частота помилок / виконання планових закупівель / чиста вигода після витрат; поруч: **«1 категорія → вимірювання → масштабування»**.

---

## 3. Як швидко витягти WAV на локальному ПК

Для кожного прямого MP4:

```bash
ffmpeg -y -i INPUT.mp4 -vn -ar 48000 -ac 2 -c:a pcm_s16le OUTPUT.wav
```

Назви виходів:
- `A-personal.wav`
- `B-demand.wav`
- `C-pilot.wav`

**Не використовувати standalone Starfish TTS.** Аудіо треба брати саме з цих Avatar V-рендерів, щоб воно збігалося за тембром із погодженими роликами.

## 4. Контроль журі

Див. `AETREM-JURY-COVERAGE.md`: там зафіксовано, що має бути видимим у самому відео. Особливо не пропустити титр:

> **СПС — окремий цифровий сервіс поверх офіційного MCP «Сільпо».**

Фінальна ціль: **4:58 ≤ 5:00**.

— Aetrem 🦊
