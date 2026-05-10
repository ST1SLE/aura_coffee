# Menu Catalog Source Notes

Generated from the owner-provided drink spreadsheet on 2026-05-07.

## Transformations

- Spreadsheet prices in rubles were converted to integer kopecks.
- Drink volumes were mapped to current app size labels: `S=200 ml`, `M=300 ml`, `L=400 ml`. Tea-pot items use `S=0.5 l`, `M=1 l`.
- Alternative milk rows were treated as modifiers, not separate menu items.
- Media filenames were mapped to `/media/menu/{item_code}/hero.mp4`; posters are generated separately from the videos.

## Known Caveats Before Owner Approval

- The current database and frontend expose only generic `S/M/L` size labels, not item-specific volume labels. Descriptions include the volume mapping as a temporary usability bridge.
- The app has one price per modifier. The spreadsheet has cacao/matcha alternative-milk deltas that vary by drink and sometimes by size, so the catalog uses conservative global milk modifiers: lactose-free +30 RUB, coconut/almond/banana +50 RUB. Owner/product approval is required before public launch.
- English names are operational translations for the bilingual app; they still need owner approval.
