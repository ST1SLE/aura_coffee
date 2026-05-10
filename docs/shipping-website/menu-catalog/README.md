# Menu Catalog Packet

This directory is the Stage 3 handoff for final Aura Coffee menu and media.
It is intentionally CSV-based so the owner can fill it from a spreadsheet and
we can validate it before any database import.

## Files

| File | Purpose |
|------|---------|
| `categories.csv` | Public menu sections. |
| `items.csv` | Sellable menu items and media references. |
| `sizes.csv` | Optional size prices for items. |
| `modifiers.csv` | Optional add-ons such as milk or syrup. |
| `item_modifiers.csv` | Allowed item-to-modifier links. |
| `media_manifest.csv` | Source video filename mapped to each public media path. |
| `SOURCE_NOTES.md` | Transformation notes and caveats from the owner spreadsheet. |

## Rules

- Use stable lowercase codes, for example `cappuccino` or `almond-croissant`.
- Do not use display names as identifiers; names can change, codes should not.
- Prices are integer kopecks, not rubles. `52000` means `520.00 RUB`.
- Empty `inventory_quantity` means unlimited or not tracked. `0` means out of
  finite stock.
- Keep media as local public paths only:
  `/media/menu/{item_code}/hero.mp4` and
  `/media/menu/{item_code}/poster.webp`.
- If `media_type=video`, `media_url` and `media_poster_url` are both required.
- Do not put secrets, signed URLs, provider keys, customer data, or owner
  private information in these files.

## Validate

```bash
scripts/production/validate-menu-catalog.py docs/shipping-website/menu-catalog
```

To also check that referenced files exist under the local menu media root:

```bash
scripts/production/validate-menu-catalog.py \
  docs/shipping-website/menu-catalog \
  --media-root web/customer/public/media/menu \
  --require-media-files
```

Passing validation means the spreadsheet shape is safe to review or import. It
does not mean prices, names, media quality, or legal text are owner-approved.

## Import

After validation, load the catalog into a guarded database environment:

```bash
ALLOW_MENU_CATALOG_IMPORT=1 python -m database.seeds.menu_catalog \
  --catalog-dir docs/shipping-website/menu-catalog \
  --replace-existing
```

`--replace-existing` archives/hides existing menu rows before loading this
packet. It does not delete or mutate orders, order items, customers, staff,
payments, providers, or secrets.
