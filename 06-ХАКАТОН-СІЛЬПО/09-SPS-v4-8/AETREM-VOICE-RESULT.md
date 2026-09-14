# Аетрем → Ейден: СПС v4.8 — повний reset озвучення

**Дата:** 14.09.2026  
**Джерело:** `AETREM-VOICE-RESET-v4-8.md` — єдиний актуальний сценарій.  
**Статус:** RENDERING / v4.8-protection-final / CREDIT FALLBACK  

> **ОСТАННЄ ОНОВЛЕННЯ:** у `AETREM-VOICE-RESET-v4-8.md` змінено **лише `outro`**. Інші 13 озвучених блоків не перезаписувати без потреби. Старий outro `e7a7f7bec779a478ea79425f215f7aa1` завершив рендер, але є **SUPERSEDED — НЕ ВИКОРИСТОВУВАТИ**.

## ВАЖЛИВО: збій HeyGen через кредити

Новий Avatar V outro `e6f6164c78740a23d7a7cfe82ceb2f8c` завершився помилкою:

`AVATAR_IV_VIDEO_GENERATION_OUT_OF_CREDIT — Insufficient credits. Upgrade to continue.`

Це не помилка тексту, голосу або аватара. Та сама причина зупинила три елементи великого batch v4.8:
- `community` → `5db7ac7edf5956555933ccb32ab5e247` — FAILED / OUT_OF_CREDIT;
- `B-demand` → `68b15ce96cb8c644fd3332d669620fdf` — FAILED / OUT_OF_CREDIT;
- `C-pilot` → `fdced2d8195cbe5a60f5641d29a56009` — FAILED / OUT_OF_CREDIT.

Параметри основної партії: Avatar V, look `a167b8806efda2475f422bb43eac0070`, voice `c68bbe981f4b4d5fb87d52660f035090`, `uk-UA`, speed `0.95`, pitch `0`, volume `1`, фон `#F5F3F0`, 16:9. Standalone Starfish TTS **не використовувати** як фінальний голос.

## НОВИЙ фінальний outro — fallback уже запущений

Avatar V-версія впала через quota, тому без зміни тексту запущено той самий look + voice через **Avatar III** як аварійний fallback. Голосові параметри лишаються ті самі; engine змінено лише для рендера відео.

**id:** `outro`  
**версія:** `v4.8-protection-final`  
**Avatar III fallback video_id:** `74d94d701bf8e0670a74d51e60236fb9`  
**статус:** processing  
**формат:** 1080p MP4 з lip-sync  
**HeyGen:** https://app.heygen.com/videos/74d94d701bf8e0670a74d51e60236fb9

Актуальний текст:

> ес-пе-ес поєднує особисті й колективні інтереси покупців. Пані Одарка персоналізує закупівлі та аналізує спільний попит. ем-сі-пі Сільпо з'єднує платформу з магазином. Модель передбачає контроль передачі даних і меж дій штучного інтелекту. Адвокатка представляє покупців і допомагає захищати їхні права у тривалих відносинах із Сільпо. Запрошуємо до пілоту: спільна сила, особистий вибір.

### Старі outro — НЕ використовувати

- `e7a7f7bec779a478ea79425f215f7aa1` — completed, але **SUPERSEDED** через фінальну змістову правку;
- `e6f6164c78740a23d7a7cfe82ceb2f8c` — failed / out of credit.

## Пріоритет 1 — інші два блоки v4.8 готові

Batch: `fef0e692e51e47c290df9ae0fa788097`

- `mcp` → video_id `0f2f1e1391216f30179fa2cfc9cf7326` — completed;
- `A-personal` → video_id `203f479ce0938bdeace0d52fbc9832ea` — completed.

## Решта v4.8

Batch: `7b538c6da3344209a0d11fedccc50e8a`

Готові:
- `opening` → `36cf9c08735a219d232edc6708efcdf4` — completed;
- `scale` → `104920ba2b9ced4c8907ff7ce13f9ed6` — completed;
- `value` → `8411db24054eaff8552d66b0d6456247` — completed;
- `olena` → `fae6c761501ed31bc8488dba41a9ed89` — completed;
- `odarka` → `5d2b07df7f6a976704cf234d41691db5` — completed;
- `mandate` → `401df35c45262b2ab44333018060719e` — completed;
- `contract` → `3b3d5e0b41cf0827b94810bf3ee7f64d` — completed;
- `return` → `f9a9cba417b7abc73a8e995f3bcf3530` — completed.

Не завершилися через кредити:
- `community` → `5db7ac7edf5956555933ccb32ab5e247` — FAILED;
- `B-demand` → `68b15ce96cb8c644fd3332d669620fdf` — FAILED;
- `C-pilot` → `fdced2d8195cbe5a60f5641d29a56009` — FAILED.

### community — fallback

Для `community` запущено Avatar III fallback з **точно тим самим v4.8-текстом**:
- video_id `75de94d70344f96ed53858d778906fd7` — processing;
- HeyGen: https://app.heygen.com/videos/75de94d70344f96ed53858d778906fd7

### B-demand і C-pilot — безпечний резерв

Тексти `B-demand` і `C-pilot` у v4.8 **дослівно збігаються** з уже готовими timing-safe Avatar V-рендерами v4.7, тому у разі браку кредитів їх можна використати без змістової невідповідності:

- `B-demand` → `8795755ba47de11f3cc5ce467d74fdb9` — 30.960 с — completed;
- `C-pilot` → `ef9f2c4a214a3ca0aa65ea302be0e921` — 10.752 с — completed.

Це не повернення до старого сценарію: саме ці два тексти залишилися незмінними у v4.8.

`lion` не озвучується; вступ 00:00–00:27.56 лишається незмінним.

Після завершення fallback-рендерів оновити фактичну тривалість і джерело завантаження. Голос не прискорювати й не обрізати.

— Aetrem 🦊