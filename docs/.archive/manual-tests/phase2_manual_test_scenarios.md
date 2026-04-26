---                                                                              
Pre-flight                                                                                      
                                                                                
./scripts/up.sh

Banner must show Migrations: applied ✓. If it shows FAILED, stop — run docker compose logs      
db-migrate.

> Dev note — OTP codes: The dev stack sets SMS_BACKEND=log.
> OTP codes are printed to `docker compose logs sms-worker` as:
>   [SMS:log] to=<phone> msg=Код подтверждения: NNNNNN. Aura Coffee
> If another worktree stack is running, host port NGINX_PORT=8240 may belong to a
> sibling compose project. Fix: bump ports in .env (see .env.example:22-28),
> or prefix docker compose calls with -p <project-name>.
                                                                                                
---                                                                              
Part A — Get admin JWT
                    
1. Open http://localhost:8240/admin (no slash) → browser lands on http://localhost:8240/admin/
dashboard.                                                                                      
2. Log in with admin / admin123.
3. You are now logged in. Keep this tab open.                                                   
                                                                                                
For API testing get a token:                                                                    
curl -s -X POST http://localhost:8240/api/v1/staff/auth/login \                                 
-H 'Content-Type: application/json' \                                                         
-d '{"login":"admin","password":"admin123"}' | jq -r .access_token             
Save as $ADMIN_TOKEN.                                               
                                                                                                
---                                                                                             
Part B — Get customer JWT (OTP workaround)                                                      
                                                                                                
1. Open http://localhost:8240/ → navigate to login page.                         
2. Enter phone +79991234567, submit.                                                            
3. Pull the OTP from `docker compose logs sms-worker` (look for the `[SMS:log]` line):
docker compose logs --tail 20 sms-worker | grep '[SMS:log]'
# OTP is in the msg=Код подтверждения: NNNNNN substring
4. Enter the code on the verify page.                                                           
5. You are logged in as customer. Keep this tab open.                                           
                                                                                                
For API testing get a token:                                                                    
curl -s -X POST http://localhost:8240/api/v1/auth/send-code \                  
-H 'Content-Type: application/json' \                                                         
-d '{"phone":"+79991234567"}'
# Expected: HTTP 200, {"message":"OTP sent","phone_hash":"<64-hex>"}
# get code from: docker compose logs --tail 20 sms-worker | grep '[SMS:log]'
curl -s -X POST http://localhost:8240/api/v1/auth/verify-code \
-H 'Content-Type: application/json' \                                                         
-d '{"phone":"+79991234567","code":"<code>"}' | jq -r .access_token            
Save as $CUST_TOKEN.
                                                                                                
---
Block 1 — Admin: Menu CRUD                                                                      
                                                                                
1.1 Categories
                                                                                                
Create category 1

- Admin SPA → Menu → Categories → Create                                                        
- name_ru=Кофе, name_en=Coffee, sort_order=1, is_visible=true                                   
- Expect: row appears in categories list                     
                                                                                                
Create category 2                                                                               
- name_ru=Десерты, name_en=Desserts, sort_order=2                                               
- Expect: second row appears, sorted below Кофе                                                 
                                                                                
Or via API:                                                                                     
curl -s -X POST http://localhost:8240/api/v1/admin/menu/categories \             
-H "Authorization: Bearer $ADMIN_TOKEN" \                         
-H 'Content-Type: application/json' \                                                         
-d '{"type":"drink","name_ru":"Кофе","name_en":"Coffee","sort_order":1,"is_visible":true}'
# Expect: HTTP 201                                                                              
                                                                                
curl -s -X POST http://localhost:8240/api/v1/admin/menu/categories \                            
-H "Authorization: Bearer $ADMIN_TOKEN" \                                      
-H 'Content-Type: application/json' \                                                         
-d '{"type":"food","name_ru":"Десерты","name_en":"Desserts","sort_order":2,"is_visible":true}'
# Expect: HTTP 201                                                                              
                                                                                                
Edit category
- Click edit on Кофе → change name_en=Hot Coffee → save                                         
- Expect: list updates in place, no full reload                                                 
                                                                                                
Reorder                                                                                         
- Change Десерты sort_order to 0 → save                                                         
- Expect: Десерты appears above Кофе in the list
                                                                                                
Delete empty category                                                                           
- Create a throwaway category → delete it
- Expect: disappears from list                                                                  
                                                                                
---                                                                                             
1.2 Menu items — no sizes, no modifiers                                          
                                                                                                
Create item
- Menu → Items → Create in category Кофе                                                        
- name_ru=Эспрессо, name_en=Espresso, base_price=150, available=true             
- Expect: HTTP 201, row appears in items table, bound to Кофе       
                                                                                                
curl -s -X POST http://localhost:8240/api/v1/admin/menu/items \                                 
-H "Authorization: Bearer $ADMIN_TOKEN" \                                                     
-H 'Content-Type: application/json' \                                                         
-d '{"category_id":<кофе_id>,"name_ru":"Эспрессо","name_en":"Espresso","base_price":150,"avail
able":true,"sort_order":1}'

# Expect: HTTP 201, note the returned id
Save returned id as $ESPRESSO_ID.                                                               
                                                                                                
Edit bilingual description
- Edit Эспрессо → fill in description_ru and description_en → save                              
- Refresh the page                                                                              
- Expect: descriptions persist
                                                                                                
Delete item                                                                                     
- Delete Эспрессо
- Expect: row gone                                                                              
                                                                                
Recreate Эспрессо (needed for Block 3)
- Same as create above, save $ESPRESSO_ID again                                                 
                                                                                                
---                                                                                             
1.3 Menu items — with sizes                                                                     
                                                                                
Create Капучино
curl -s -X POST http://localhost:8240/api/v1/admin/menu/items \                                 
-H "Authorization: Bearer $ADMIN_TOKEN" \                    
-H 'Content-Type: application/json' \                                                         
-d '{"category_id":<кофе_id>,"name_ru":"Капучино","name_en":"Cappuccino","base_price":0,"avail
able":true,"sort_order":2}'                                                                     
# Expect: HTTP 201                                                                              
Save id as $CAPPUCCINO_ID.                                                                      
                                                                                                
Add 3 sizes                                                                      
for payload in \                                                                                
'{"menu_item_id":'$CAPPUCCINO_ID',"label":"S","price":200}' \
'{"menu_item_id":'$CAPPUCCINO_ID',"label":"M","price":250}' \                                      
'{"menu_item_id":'$CAPPUCCINO_ID',"label":"L","price":300}'; do                                    
curl -s -X POST http://localhost:8240/api/v1/admin/menu/sizes \                               
    -H "Authorization: Bearer $ADMIN_TOKEN" \                                                   
    -H 'Content-Type: application/json' \                                                       
    -d "$payload"                                                                
done                                                                                            
# Expect: 3× HTTP 201


Edit M → 260                                                                                    
- In admin UI: find size M on Капучино, edit price to 260, save
- Expect: price updates, S and L unchanged                                                      
                                                                                
Delete S                                                                                        
- Delete size S                                                                  
- Expect: only M(260) and L(300) remain, no errors                                              
                                                                                
---                                                                                             
1.4 Modifiers                                                                    
                                                                                                
Create modifiers
curl -s -X POST http://localhost:8240/api/v1/admin/menu/modifiers \                             
-H "Authorization: Bearer $ADMIN_TOKEN" \                                      
-H 'Content-Type: application/json' \    
-d '{"name_ru":"Сироп ваниль","name_en":"Vanilla 
syrup","price":50,"available":true,"sort_order":1}'                                             
# Expect: HTTP 201                                                                              
# Save id as $VANILLA_ID                                                                        
                                                                                                
curl -s -X POST http://localhost:8240/api/v1/admin/menu/modifiers \                             
-H "Authorization: Bearer $ADMIN_TOKEN" \                        
-H 'Content-Type: application/json' \                                                         
-d '{"name_ru":"Молоко овсяное","name_en":"Oat                                 
milk","price":70,"available":true,"sort_order":2}'                                              
# Expect: HTTP 201                                
# Save id as $OAT_ID                                                                            
                                                                                                
Attach modifiers to Капучино
- In admin UI: edit Капучино → modifiers section → attach Vanilla syrup and Oat milk → save     
- Expect: both modifiers listed under Капучино                                                  

Edit modifier price                                                                             
- Edit Vanilla syrup → price=55 → save                                           
- Expect: price updates to 55, Oat milk unchanged                                               
                                                                                
Delete modifier                                                                                 
- Delete Oat milk                                                                
- Expect: disappears from modifiers list, detaches from Капучино silently (or with confirmation
— note the behavior)
                                                                                                
---
1.5 Stop-list                                                                                   
                                                                                
Stop an item
- Edit Капучино → set available=false → save                                                    
- Expect: Капучино row shows as stopped/unavailable in admin items table
                                                                                                
Stop a modifier                                                                                 
- Edit Vanilla syrup → set available=false → save

- Expect: modifier row shows stopped                                                            
                                                                                                
---                                                                              
Block 2 — Customer: Public menu
                                
Use the logged-in customer tab from Part B.
                                                                                                
2.1 Menu page renders                                                                           
- Navigate to /menu                                                                             
- Expect: categories (Кофе, Десерты) visible; items grouped under their category; sorted by     
sort_order                                                                       
                                                                                                
2.2 Language switch
- Switch language RU → EN (in profile or header switcher)                                       
- Expect: category and item names switch to English values (Coffee, Espresso, etc.)             
- Switch back to RU                                                                
- Expect: names revert                                                                          
                                                                                
2.3 Stopped item                                                                                
- Капучино was stopped in 1.5                                                    
- Expect: Капучино is either hidden or visibly marked unavailable on the menu page              
                                                                                
2.4 Stopped modifier                                                                            
- Open any item that had Vanilla syrup                                                          
- Expect: Vanilla syrup is either absent or greyed out / unselectable
                                                                                                
2.5 Size selection                                                                              
- Open Капучино's detail view (assuming you re-enable it for this check, or use another item
with sizes)                                                                                     
- Expect: size selector shows M(260) and L(300); price in UI updates as you click each size
                                                                                                
2.6 Modifier price sum                                                                          
- Select size M (260) → add Vanilla syrup (55)                                                  
- Expect: displayed total = 315                                                                 
                                                                                                
2.7 No-size item                                                                                
- Open Эспрессо detail                                                                          
- Expect: no size selector; price shows 150 flat
                                                                                                
2.8 Error state and recovery                                                                    
docker compose stop core-api
- Reload /menu in browser                                                                       
- Expect: friendly error message + retry button (not a blank page, not 500 raw)                 

docker compose start core-api                                                                   
- Click retry                                                                    
- Expect: menu loads normally

                                                                                
---
Block 3 — Customer: Cart
                                                                                                
Re-enable Капучино (available=true) before these steps.
                                                                                                
3.1 Add single item                                                                             
- From /menu, tap Эспрессо → Add to cart (qty 1)
- Expect: cart badge shows 1; /cart shows one line: Эспрессо × 1 = 150                          
                                                                                
3.2 Add item with size + modifier                                                               
- Add Капучино, select size M(260), add Vanilla syrup(55)                                       
- Expect: line price = 315; verify in DevTools → Network → POST /api/v1/cart/items response body
has total_price: 315 (backend-computed, not frontend-only)                                     
                                                                                                
3.3 Duplicate → quantity increment
- Add the exact same Капучино (size M + Vanilla syrup) again                                    
- Expect: existing line qty becomes 2, NOT a new line; total for that line = 630                

3.4 Different modifiers → new line                                                              
- Add Капучино size M with NO modifiers                                          
- Expect: new separate cart line appears (different variant)                                    
                                                                                
3.5 Quantity controls                                                                           
- Tap + on Эспрессо line                                                         
- Expect: PATCH /api/v1/cart/items/{line_id} fires in DevTools; qty becomes 2; total updates    
- Tap − on Эспрессо line                                                                    
- Expect: qty back to 1; totals update                                                          
                                                                                
3.6 Decrement to remove                                                                         
- When qty is 1, tap −                                                            
- Expect: line is removed from cart (triggers DELETE, not PATCH with qty=0)                                       
                                                                                
3.7 Delete line                                                                                 
- Tap trash icon on a remaining line                                                            
- Expect: DELETE /api/v1/cart/items/{line_id} fires; line disappears
                                                                                                
3.8 Clear cart                                                                                  
- Tap "Clear cart"
- Expect: DELETE /api/v1/cart fires; cart is empty                                              
- Tap again                                                                      
- Expect: no error (idempotent)                                                                 
                                
Re-add Эспрессо × 1 for the next checks.                                                        
                                                                                                
3.9 Cart persistence                                                                            
- Hard-refresh the page (Ctrl+Shift+R)                                                          
- Expect: cart still shows Эспрессо (persisted in Redis by user_id)

                                                                    
3.10 Stop-list enforcement                                                                      
- In admin: set Эспрессо available=false                                                        
- Back in customer tab (do NOT refresh — use the cached menu page): try to add Эспрессо         
- Expect: POST /api/v1/cart/items returns 409; UI shows a meaningful error, no silent failure   
                                                                                                
Re-enable Эспрессо in admin.                                                                    
                                                                                                
3.11 Cart survives logout/login                                                                 
- Add Эспрессо if cart is empty → log out → log back in as same customer         
- Expect: cart still contains the item                                                          
                                                                                
3.12 Nonexistent item via DevTools                                                              
- Open DevTools → Network → find any POST /api/v1/cart/items request → copy as fetch → modify   
menu_item_id to a UUID that doesn't exist → run in console                                      
- Expect: 404 response; UI handles it gracefully (no uncaught crash)                            
                                                                                                
---                                                                                             
Block 4 — Cross-cutting
                                                                                                
4.1 Accept-Language header                                                       
curl -s http://localhost:8240/api/v1/menu \                                                     
-H 'Accept-Language: en' | jq '.[0].name'
# Expect: English name string                                                                   
                                                                                                
curl -s http://localhost:8240/api/v1/menu \
-H 'Accept-Language: ru' | jq '.[0].name'                                                     
# Expect: Russian name string                                                    
                                                                                                
curl -s 'http://localhost:8240/api/v1/menu?available=true' \                     
-H 'Accept-Language: en' | jq '[.[].items[].available] | all'                                 
# Expect: true (only available items)                          
                                                                                                
4.2 Admin routes require JWT                                                     
curl -s -o /dev/null -w '%{http_code}\n' \                                                      
http://localhost:8240/api/v1/admin/menu/items                                  
# Expect: 401                                                                                   
                                                                                                
4.3 Cart routes require JWT
curl -s -o /dev/null -w '%{http_code}\n' \                                                      
http://localhost:8240/api/v1/cart                                              
# Expect: 401
